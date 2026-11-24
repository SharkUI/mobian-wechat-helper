#!/usr/bin/python3
"""Add wheel steps for vertical touch-emulated pointer drags on one window."""
import argparse
import ctypes as c
import fcntl
import json
import math
import os
import pathlib
import select
import signal
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

def classify_reason(points):
    """Recognize short, mirrored thumb arcs while rejecting taps and horizontal drags."""
    if len(points)<3:return None,'tooFewPoints'
    dx=points[-1][0]-points[0][0];dy=points[-1][1]-points[0][1]
    duration=points[-1][2]-points[0][2]
    if not .04<=duration<=2:return None,'timing'
    chord=math.hypot(dx,dy)
    if abs(dy)<18 or chord<26:return None,'shortDistance'
    # The same cone accepts left/right thumb arcs, including a 45-degree flick.
    if abs(dy)<.65*abs(dx):return None,'tooHorizontal'
    clean=[points[0]]
    for point in points[1:-1]:
        if math.hypot(point[0]-clean[-1][0],point[1]-clean[-1][1])>=2:
            clean.append(point)
    if points[-1][:2]!=clean[-1][:2]:clean.append(points[-1])
    steps=[(b[0]-a[0],b[1]-a[1]) for a,b in zip(clean,clean[1:])]
    if any(abs(x)>140 or abs(y)>140 for x,y in steps):return None,'jump'
    path=sum(math.hypot(x,y) for x,y in steps)
    if chord<.55*path:return None,'wandering'
    if abs(dy)<.65*sum(abs(y) for _,y in steps):return None,'reversal'
    return (5 if dy<0 else 4),'accepted'

def classify(points):
    return classify_reason(points)[0]

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',type=lambda s:int(s,0),required=True);p.add_argument('--seconds',type=int,default=1800)
    p.add_argument('--anchor',choices=['start','center'],default='start')
    p.add_argument('--parent-pid',type=int)
    args=p.parse_args();assert 0<=args.seconds<=86400
    assert os.getuid()!=0, "Run as the phone desktop user"
    x=c.CDLL('libX11.so.6');xi=c.CDLL('libXi.so.6');xt=c.CDLL('libXtst.so.6')
    x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=P;x.XCloseDisplay.argtypes=[P]
    x.XDefaultRootWindow.argtypes=[P];x.XDefaultRootWindow.restype=U
    x.XInternAtom.argtypes=[P,c.c_char_p,I];x.XInternAtom.restype=U
    x.XGetWindowProperty.argtypes=[P,U,U,c.c_long,c.c_long,I,U,c.POINTER(U),c.POINTER(I),c.POINTER(U),c.POINTER(U),c.POINTER(P)]
    x.XFree.argtypes=[P];x.XSync.argtypes=[P,I];x.XSelectInput.argtypes=[P,U,c.c_long]
    x.XQueryExtension.argtypes=[P,c.c_char_p,c.POINTER(I),c.POINTER(I),c.POINTER(I)]
    x.XQueryPointer.argtypes=[P,U,c.POINTER(U),c.POINTER(U),c.POINTER(I),c.POINTER(I),c.POINTER(I),c.POINTER(I),c.POINTER(c.c_uint)]
    x.XGetGeometry.argtypes=[P,U,c.POINTER(U),c.POINTER(I),c.POINTER(I),c.POINTER(c.c_uint),c.POINTER(c.c_uint),c.POINTER(c.c_uint),c.POINTER(c.c_uint)]
    x.XTranslateCoordinates.argtypes=[P,U,U,I,I,c.POINTER(I),c.POINTER(I),c.POINTER(U)]
    x.XPending.argtypes=[P];x.XNextEvent.argtypes=[P,c.POINTER(Event)]
    x.XGetEventData.argtypes=[P,c.POINTER(Cookie)];x.XFreeEventData.argtypes=[P,c.POINTER(Cookie)]
    x.XConnectionNumber.argtypes=[P];x.XConnectionNumber.restype=I
    xi.XISelectEvents.argtypes=[P,U,c.POINTER(Mask),I]
    xi.XIQueryVersion.argtypes=[P,c.POINTER(I),c.POINTER(I)]
    xt.XTestFakeButtonEvent.argtypes=[P,c.c_uint,I,U]
    xt.XTestFakeMotionEvent.argtypes=[P,I,I,I,U]
    running=True
    stats=dict(emulatedMotionEvents=0,pointerSamples=0,bursts=0,rejectedBursts=0,wheelDown=0,wheelUp=0,centeredWheelSteps=0,nonEmulatedResets=0,errors=0)
    reasons={}
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    if args.parent_pid:
        libc=c.CDLL(None);libc.prctl.argtypes=[I,U,U,U,U]
        assert libc.prctl(1,signal.SIGTERM,0,0,0)==0
        if os.getppid()!=args.parent_pid:return
    cbtype=c.CFUNCTYPE(I,P,c.POINTER(Error))
    @cbtype
    def on_error(_,e):
        nonlocal running
        running=False;stats['errors']+=1
        print('X protocol error:',e.contents.error_code,flush=True)
        return 0
    x.XSetErrorHandler.argtypes=[cbtype];x.XSetErrorHandler(on_error)
    d=x.XOpenDisplay(os.environ.get('DISPLAY',':1').encode());assert d
    lock=os.open(f'/run/user/{os.getuid()}/wechat-motion-wheel-{args.window}.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def owner():
        atom=x.XInternAtom(d,b'_NET_WM_PID',1);typ=U();fmt=I();n=U();after=U();data=P()
        x.XGetWindowProperty(d,args.window,atom,0,1,0,6,c.byref(typ),c.byref(fmt),c.byref(n),c.byref(after),c.byref(data))
        try:pid=int(c.cast(data,c.POINTER(U))[0]) if data and n.value else None
        finally:
            if data:x.XFree(data)
        if pid is None:return None
        f=pathlib.Path('/proc')/str(pid)
        try:
            if f.stat().st_uid==os.getuid() and (f/'exe').resolve(strict=True) in [pathlib.Path('/opt/wechat/wechat'),pathlib.Path('/opt/wechat/RadiumWMPF/runtime/WeChatAppEx')]:return pid
        except (FileNotFoundError,PermissionError):pass
        return None
    expected=owner();assert expected,'Target is not an owned WeChat window'
    root=x.XDefaultRootWindow(d)
    def pointer():
        r=U();child=U();rx=I();ry=I();wx=I();wy=I();mask=c.c_uint()
        if not x.XQueryPointer(d,root,c.byref(r),c.byref(child),c.byref(rx),c.byref(ry),c.byref(wx),c.byref(wy),c.byref(mask)):return None
        if child.value!=args.window:return None
        return rx.value,ry.value,bool(mask.value&256)
    start=time.monotonic();points=[];last_move=0.;active_until=0.;last_save=0.;dirty=True
    state=pathlib.Path.home()/'.local/state/wechat-mobile/windows'
    state.mkdir(parents=True,mode=0o700,exist_ok=True);state.chmod(0o700)
    out=state/(str(args.window)+'.json')
    def save():
        tmp=out.with_suffix('.next')
        with tmp.open('w') as f:json.dump({'version':3,'running':running,'elapsedSeconds':round(time.monotonic()-start),'stats':stats,'rejectionReasons':reasons,'keyboardObserved':False,'inputGrabbed':False,'coordinatesStored':False},f,indent=2);f.write('\n')
        tmp.chmod(0o600);os.replace(tmp,out)
    def add(px,py,now):
        nonlocal points,last_move,dirty
        if points and (px,py)==points[-1][:2]:return
        if points and now-last_move>.25:finish(now)
        points.append((px,py,now));last_move=now;stats['pointerSamples']+=1;dirty=True
    def finish(now):
        nonlocal points,dirty,active_until
        if not points:return
        stats['bursts']+=1;button,reason=classify_reason(points);origin=points[0][:2];points=[];active_until=0.;dirty=True
        loc=pointer()
        if button and loc and not loc[2] and owner()==expected:
            assert button in (4,5)
            r=U();gx=I();gy=I();width=c.c_uint();height=c.c_uint();border=c.c_uint();depth=c.c_uint()
            rx=I();ry=I();child=U()
            if x.XGetGeometry(d,args.window,c.byref(r),c.byref(gx),c.byref(gy),c.byref(width),c.byref(height),c.byref(border),c.byref(depth)) and x.XTranslateCoordinates(d,args.window,root,0,0,c.byref(rx),c.byref(ry),c.byref(child)):
                if args.anchor=='center':target=(rx.value+width.value//2,ry.value+height.value//2)
                else:target=(min(max(origin[0],rx.value+4),rx.value+width.value-4),min(max(origin[1],ry.value+4),ry.value+height.value-4))
                xt.XTestFakeMotionEvent(d,-1,round(target[0]),round(target[1]),0)
                xt.XTestFakeButtonEvent(d,button,1,0);xt.XTestFakeButtonEvent(d,button,0,0);x.XSync(d,0)
                stats['wheelDown' if button==5 else 'wheelUp']+=1
                if args.anchor=='center':stats['centeredWheelSteps']+=1
                print('Converted thumb swipe to one wheel step.',flush=True)
                return
            reason='geometryUnavailable'
        elif button:
            reason='pointerAway' if not loc else 'buttonHeld' if loc[2] else 'wrongOwner'
        stats['rejectedBursts']+=1;reasons[reason]=reasons.get(reason,0)+1
    try:
        major=I(2);minor=I(2);assert xi.XIQueryVersion(d,c.byref(major),c.byref(minor))==0
        opcode=I();base=I();error=I();assert x.XQueryExtension(d,b'XInputExtension',c.byref(opcode),c.byref(base),c.byref(error))
        bits=(c.c_ubyte*1)(1<<6);mask=Mask(1,1,bits)
        assert xi.XISelectEvents(d,args.window,c.byref(mask),1)==0
        x.XSelectInput(d,args.window,1<<17);x.XSync(d,0);assert running
        save();print('READY: per-window motion-to-wheel helper; no input grabs, clicks or key injection.',flush=True)
        fd=x.XConnectionNumber(d)
        while running and (args.seconds==0 or time.monotonic()-start<args.seconds):
            while x.XPending(d) and running:
                event=Event();x.XNextEvent(d,c.byref(event))
                if event.type in (17,18):running=False;break
                if event.type!=35 or event.cookie.extension!=opcode.value:continue
                if not x.XGetEventData(d,c.byref(event.cookie)):continue
                try:
                    if event.cookie.evtype!=6:continue
                    e=c.cast(event.cookie.data,c.POINTER(Motion)).contents
                    if e.event!=args.window:continue
                    now=time.monotonic()
                    if e.flags&(1<<16):
                        stats['emulatedMotionEvents']+=1;add(round(e.root_x),round(e.root_y),now);active_until=now+2.
                    else:
                        if points:stats['nonEmulatedResets']+=1
                        points=[];active_until=0.
                finally:x.XFreeEventData(d,c.byref(event.cookie))
            now=time.monotonic()
            if points and now<active_until:
                loc=pointer()
                if loc:add(loc[0],loc[1],now)
                else:points=[];active_until=0.
            if points and now-last_move>=.20:
                loc=pointer()
                if not loc or not loc[2]:finish(now)
                elif now-last_move>1:points=[];active_until=0.
            if dirty and now-last_save>=1:save();last_save=now;dirty=False
            if running:select.select([fd],[],[],.016 if now<active_until else .5)
    finally:
        running=False;save();x.XCloseDisplay(d);os.close(lock)
        print('STOPPED:',json.dumps(stats),flush=True)

if __name__=='__main__':main()
