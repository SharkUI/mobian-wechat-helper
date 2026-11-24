#!/usr/bin/python3
"""Scroll owned WeChat windows by touch, forwarding taps and horizontal drags."""
import argparse
import ctypes as c
import fcntl
import json
import math
import os
import pathlib
import select
import signal
import socket
import sys
import time

P,U,I=c.c_void_p,c.c_ulong,c.c_int

class Mask(c.Structure):
    _fields_=[('deviceid',I),('mask_len',I),('mask',c.POINTER(c.c_ubyte))]

class Motion(c.Structure):
    _fields_=[('type',I),('serial',U),('send_event',I),('display',P),('extension',I),('evtype',I),
        ('time',U),('deviceid',I),('sourceid',I),('detail',I),('root',U),('event',U),('child',U),
        ('root_x',c.c_double),('root_y',c.c_double),('event_x',c.c_double),('event_y',c.c_double),('flags',I)]

class Cookie(c.Structure):
    _fields_=[('type',I),('serial',U),('send_event',I),('display',P),('extension',I),('evtype',I),('cookie',c.c_uint),('data',P)]

class Event(c.Union):
    _fields_=[('type',I),('cookie',Cookie),('pad',c.c_long*24)]

class Error(c.Structure):
    _fields_=[('type',I),('display',P),('resourceid',U),('serial',U),('error_code',c.c_ubyte),('request_code',c.c_ubyte),('minor_code',c.c_ubyte)]


class Mods(c.Structure):
    _fields_=[('modifiers',I),('status',I)]

# Touch uses the same XIDeviceEvent prefix as Motion, through flags.
Touch=Motion

def main():
 from x11_windows import Windows
 p=argparse.ArgumentParser();p.add_argument('--window',type=int,required=True);p.add_argument('--seconds',type=int,default=3600);p.add_argument('--parent-pid',type=int);p.add_argument('--anchor');p.add_argument('--focus-socket');a=p.parse_args()
 assert os.getuid()!=0
 os.umask(0o077);running=True;stats=dict(touchBegins=0,touchUpdates=0,scrolls=0,forwarded=0,wheelDown=0,wheelUp=0,focusRequests=0,errors=0);active={}
 def stop(*_):
  nonlocal running
  running=False
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 if a.parent_pid:
  libc=c.CDLL(None);libc.prctl.argtypes=[I,U,U,U,U];assert libc.prctl(1,signal.SIGTERM,0,0,0)==0
  if os.getppid()!=a.parent_pid:return
 reader=Windows();x=reader.x;d=reader.d;xi=c.CDLL('libXi.so.6');xt=c.CDLL('libXtst.so.6');expected=reader.mapped().get(a.window);assert expected
 pager=(pathlib.Path('/proc')/str(expected)/'exe').resolve().name=='WeChatAppEx'
 x.XSync.argtypes=[P,I];x.XSelectInput.argtypes=[P,U,c.c_long];x.XPending.argtypes=[P];x.XNextEvent.argtypes=[P,c.POINTER(Event)]
 x.XGetEventData.argtypes=[P,c.POINTER(Cookie)];x.XFreeEventData.argtypes=[P,c.POINTER(Cookie)];x.XConnectionNumber.argtypes=[P];x.XConnectionNumber.restype=I
 x.XQueryExtension.argtypes=[P,c.c_char_p,c.POINTER(I),c.POINTER(I),c.POINTER(I)]
 xi.XIQueryVersion.argtypes=[P,c.POINTER(I),c.POINTER(I)];xi.XIGrabTouchBegin.argtypes=[P,I,U,I,c.POINTER(Mask),I,c.POINTER(Mods)]
 xi.XIUngrabTouchBegin.argtypes=[P,I,U,I,c.POINTER(Mods)];xi.XIAllowTouchEvents.argtypes=[P,I,c.c_uint,U,I]
 xt.XTestFakeMotionEvent.argtypes=[P,I,I,I,U];xt.XTestFakeButtonEvent.argtypes=[P,c.c_uint,I,U]
 cbtype=c.CFUNCTYPE(I,P,c.POINTER(Error))
 @cbtype
 def on_error(_,error):
  nonlocal running
  if error.contents.error_code!=3:stats['errors']+=1
  running=False;return 0
 x.XSetErrorHandler.argtypes=[cbtype];x.XSetErrorHandler(on_error)
 lock=os.open(f'/run/user/{os.getuid()}/wechat-touch-{a.window}.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600);fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 bits=(c.c_ubyte*4)()
 for bit in (18,19,20,21):bits[bit//8]|=1<<(bit%8)
 mask=Mask(2,4,bits);mods=Mods(c.c_int(1<<31).value,0);grabbed=False;start=time.monotonic()
 out=pathlib.Path.home()/'.local/state/wechat-mobile/windows'/f'{a.window}.json'
 out.parent.mkdir(parents=True,mode=0o700,exist_ok=True);out.parent.chmod(0o700)
 def save():
  tmp=out.with_suffix('.next');tmp.write_text(json.dumps({'version':5,'running':running,'stats':stats,'keyboardEventsObserved':False,'coordinatesStored':False,'inputGrabbed':'this WeChat window only','pixelStep':30,'mode':'single-step-web' if pager else 'continuous-main'},indent=2)+'\n');tmp.replace(out)
 def request_focus(stamp):
  if pager or not a.focus_socket:return
  try:
   with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as sock:
    sock.setblocking(False);sock.sendto(json.dumps({'window':a.window,'tapAt':stamp}).encode(),a.focus_socket);stats['focusRequests']+=1
  except OSError:pass
 def decide(key,accept):
  g=active.get(key)
  if not g or g['state']!='pending':return
  xi.XIAllowTouchEvents(d,key[0],key[1],a.window,6 if accept else 7);g['state']='scroll' if accept else 'forwarded'
  stats['scrolls' if accept else 'forwarded']+=1;x.XSync(d,0)
 def wheel(g,dy):
  if reader.mapped().get(a.window)!=expected:return
  if pager and g.get('emitted'):return
  g['acc']+=dy
  unit=10 if pager else 30
  steps=min(1 if pager else 8,int(abs(g['acc'])/unit))
  if not steps:return
  button=5 if g['acc']<0 else 4;g['acc']-=(-1 if g['acc']<0 else 1)*steps*unit;g['emitted']=True
  xt.XTestFakeMotionEvent(d,-1,round(g['rootx']),round(g['rooty']),0)
  for _ in range(steps):xt.XTestFakeButtonEvent(d,button,1,0);xt.XTestFakeButtonEvent(d,button,0,0)
  x.XSync(d,0);stats['wheelDown' if button==5 else 'wheelUp']+=steps
 try:
  major=I(2);minor=I(2);assert xi.XIQueryVersion(d,c.byref(major),c.byref(minor))==0
  opcode=I();base=I();error=I();assert x.XQueryExtension(d,b'XInputExtension',c.byref(opcode),c.byref(base),c.byref(error))
  assert xi.XIGrabTouchBegin(d,2,a.window,0,c.byref(mask),1,c.byref(mods))==0 and mods.status==0;grabbed=True
  x.XSelectInput(d,a.window,1<<17);x.XSync(d,0);assert running;save();print('READY per-window touch scrolling; keyboard untouched',flush=True)
  fd=x.XConnectionNumber(d);last_save=0
  while running and (a.seconds==0 or time.monotonic()-start<a.seconds):
   while running and x.XPending(d):
    event=Event();x.XNextEvent(d,c.byref(event))
    if event.type in (17,18):running=False;break
    if event.type!=35 or event.cookie.extension!=opcode.value:continue
    if not x.XGetEventData(d,c.byref(event.cookie)):continue
    try:
     if event.cookie.evtype not in (18,19,20):continue
     t=c.cast(event.cookie.data,c.POINTER(Touch)).contents;key=(t.deviceid,t.detail);now=time.monotonic()
     if t.evtype==18:
      stats['touchBegins']+=1;active[key]=dict(x=t.event_x,y=t.event_y,lasty=t.event_y,rootx=t.root_x,rooty=t.root_y,acc=0.,start=now,state='pending')
      if len(active)>1:
       for k in list(active):decide(k,False)
     elif key in active:
      g=active[key];dx=t.event_x-g['x'];dy=t.event_y-g['y'];delta=t.event_y-g['lasty'];g['lasty']=t.event_y
      if t.evtype==19:
       stats['touchUpdates']+=1
       if g['state']=='pending':
        if abs(dy)>=10 and math.hypot(dx,dy)>=14 and abs(dy)>=.65*abs(dx):decide(key,True);delta=dy
        elif abs(dx)>=22 and abs(dy)<.65*abs(dx):decide(key,False)
       if g['state']=='scroll' and len(active)==1:wheel(g,delta)
      if t.evtype==20:
       tap=g['state']=='pending' and now-g['start']<.35
       if g['state']=='pending':decide(key,False)
       active.pop(key,None)
       if tap:request_focus(now)
    finally:x.XFreeEventData(d,c.byref(event.cookie))
   now=time.monotonic()
   for key,g in list(active.items()):
    if g['state']=='pending' and now-g['start']>.45:decide(key,False)
   if now-last_save>1:save();last_save=now
   if running:select.select([fd],[],[],.016)
 finally:
  for key in list(active):decide(key,False)
  if grabbed:xi.XIUngrabTouchBegin(d,2,a.window,1,c.byref(mods))
  x.XSync(d,0);running=False;save();reader.close();os.close(lock)
if __name__=='__main__':main()
