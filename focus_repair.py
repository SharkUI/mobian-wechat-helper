"""Restore only a recently tapped WeChat window; never inject keys or text."""
import ctypes as c
import json
import math
import os
import pathlib
import shutil
import subprocess
import time
from x11_windows import Attr,MAIN,U,I,P

def parse_tap(raw,now,mapped):
    try:value=json.loads(raw)
    except (ValueError,UnicodeError):return None
    if not isinstance(value,dict) or set(value)!={'window','tapAt'}:return None
    window=value['window'];stamp=value['tapAt']
    if type(window) is not int or window not in mapped:return None
    if type(stamp) not in (int,float):return None
    try:stamp=float(stamp)
    except (OverflowError,ValueError):return None
    if not math.isfinite(stamp):return None
    if not -.02<=now-stamp<=.8:return None
    return window,float(stamp)

class FocusRepair:
    def __init__(self,reader):
        self.reader=reader;self.available=False;self.last={};self.last_result=None;self.repaired=0
        self.pactl=shutil.which('pactl')
        try:
            from gi.repository import Gio,GLib
            self.Gio=Gio;self.GLib=GLib;self.bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
            self.available=bool(self.pactl)
        except Exception:return
        x=reader.x
        x.XGetInputFocus.argtypes=[P,c.POINTER(U),c.POINTER(I)]
        x.XQueryPointer.argtypes=[P,U,c.POINTER(U),c.POINTER(U),c.POINTER(I),c.POINTER(I),c.POINTER(I),c.POINTER(I),c.POINTER(c.c_uint)]
        x.XKeysymToKeycode.argtypes=[P,U];x.XKeysymToKeycode.restype=c.c_ubyte
        x.XQueryKeymap.argtypes=[P,c.POINTER(c.c_ubyte)]
        x.XUnmapWindow.argtypes=[P,U];x.XMapRaised.argtypes=[P,U]

    def call(self,dest,path,interface,method,args=None):
        return self.bus.call_sync(dest,path,interface,method,args,None,self.Gio.DBusCallFlags.NONE,200,None).unpack()[0]

    def focus(self):
        focus=U();revert=I();self.reader.x.XGetInputFocus(self.reader.d,c.byref(focus),c.byref(revert))
        return focus.value

    def controls_held(self):
        # No keyboard listener or character decoding: inspect only known Space.
        x=self.reader.x;d=self.reader.d;root=U();child=U();rx=I();ry=I();wx=I();wy=I();mask=c.c_uint()
        x.XQueryPointer(d,x.XDefaultRootWindow(d),c.byref(root),c.byref(child),c.byref(rx),c.byref(ry),c.byref(wx),c.byref(wy),c.byref(mask))
        if mask.value&0x1f00:return True
        code=x.XKeysymToKeycode(d,0x20)
        if code:
            states=(c.c_ubyte*32)();x.XQueryKeymap(d,states)
            if states[code//8]&(1<<(code%8)):return True
        return False

    def microphone_busy(self):
        result=subprocess.run([self.pactl,'--format=json','list','source-outputs'],capture_output=True,text=True,timeout=.3)
        if result.returncode:return True
        rows=json.loads(result.stdout)
        for row in rows:
            props=row.get('properties',{});binary=str(props.get('application.process.binary','')).lower()
            if 'wechat' in binary:return True
            try:
                proc=pathlib.Path('/proc')/str(int(props.get('application.process.id','0')))
                if proc.stat().st_uid==os.getuid() and (proc/'exe').resolve(strict=True).is_relative_to(MAIN.parent):return True
            except (ValueError,FileNotFoundError,PermissionError):pass
        return False

    def attempt(self,window,pid,stamp):
        reason=self._attempt(window,pid,stamp)
        self.last_result=dict(window=window,result=reason)
        return reason

    def _attempt(self,window,pid,stamp):
        if not self.available:return 'unavailable'
        now=time.monotonic()
        if not 0<=now-stamp<=.8:return 'stale'
        if now-self.last.get(window,0)<1.5:return 'cooldown'
        proc=pathlib.Path('/proc')/str(pid)
        try:
            if proc.stat().st_uid!=os.getuid() or (proc/'exe').resolve(strict=True)!=MAIN:return 'not-main'
        except (FileNotFoundError,PermissionError):return 'gone'
        r=self.reader;x=r.x;d=r.d
        if r.property32(window,b'_NET_WM_PID')!=[pid] or r.property32(window,b'WM_TRANSIENT_FOR'):return 'not-main'
        a=Attr()
        if not x.XGetWindowAttributes(d,window,c.byref(a)) or a.map_state!=2 or a.override_redirect or min(a.width,a.height)<200:return 'not-main'
        normal=x.XInternAtom(d,b'_NET_WM_WINDOW_TYPE_NORMAL',1)
        if not normal or normal not in r.property32(window,b'_NET_WM_WINDOW_TYPE'):return 'not-normal'
        full=x.XInternAtom(d,b'_NET_WM_STATE_FULLSCREEN',1)
        if full and full in r.property32(window,b'_NET_WM_STATE'):return 'fullscreen'
        if self.focus()!=0:return 'focus-present'
        try:
            if self.call('org.gnome.ScreenSaver','/org/gnome/ScreenSaver','org.gnome.ScreenSaver','GetActive'):return 'locked'
            args=self.GLib.Variant('(ss)',('sm.puri.OSK0','Visible'))
            if not self.call('sm.puri.OSK0','/sm/puri/OSK0','org.freedesktop.DBus.Properties','Get',args):return 'keyboard-hidden'
            args=self.GLib.Variant('(ss)',('org.gnome.Shell','OverviewActive'))
            if self.call('org.gnome.Shell','/org/gnome/Shell','org.freedesktop.DBus.Properties','Get',args):return 'overview'
            if self.controls_held():return 'controls-held'
            if self.microphone_busy():return 'microphone-busy'
        except Exception:return 'state-unknown'
        if time.monotonic()-stamp>.8 or self.focus()!=0 or r.mapped().get(window)!=pid:return 'changed'
        self.last[window]=time.monotonic()
        x.XUnmapWindow(d,window);x.XSync(d,0);time.sleep(.06)
        x.XMapRaised(d,window);x.XSync(d,0)
        deadline=time.monotonic()+.3
        while time.monotonic()<deadline:
            if self.focus()==window:self.repaired+=1;return 'repaired'
            time.sleep(.02)
        return 'focus-not-restored'
