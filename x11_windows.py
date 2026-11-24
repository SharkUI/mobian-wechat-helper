"""Owned WeChat window metadata/placement; no titles, text or keys are read."""
import ctypes as c
import os
import pathlib

MAIN=pathlib.Path('/opt/wechat/wechat')
APPEX=pathlib.Path('/opt/wechat/RadiumWMPF/runtime/WeChatAppEx')

def usable_area(width,height,areas,desktop=0):
    """Prefer EWMH bounds; fall back to the verified Phosh 0.46 panel insets."""
    offset=desktop*4
    if len(areas)>=offset+4:
        left,top,w,h=areas[offset:offset+4]
        if left>=0 and top>0 and w>0 and h>0 and left+w<=width and top+h<=height:
            return (left,top,w,h),'ewmh'
    if width>0 and height>47:return (0,32,width,height-47),'phosh-0.46-insets'
    return None,None

def main_pids():
    result=[]
    for p in pathlib.Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid==os.getuid() and (p/'exe').resolve(strict=True)==MAIN:result.append(int(p.name))
        except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    return result

P,U,I=c.c_void_p,c.c_ulong,c.c_int
class Attr(c.Structure):
    _fields_=[('x',I),('y',I),('width',I),('height',I),('border',I),('depth',I),('visual',P),('root',U),('klass',I),('bit_gravity',I),('win_gravity',I),('backing_store',I),('backing_planes',U),('backing_pixel',U),('save_under',I),('colormap',U),('map_installed',I),('map_state',I),('all_event_masks',c.c_long),('your_event_mask',c.c_long),('do_not_propagate_mask',c.c_long),('override_redirect',I),('screen',P)]

class Error(c.Structure):
    _fields_=[('type',I),('display',P),('resourceid',U),('serial',U),('error_code',c.c_ubyte),('request_code',c.c_ubyte),('minor_code',c.c_ubyte)]

class ClientData(c.Union):
    _fields_=[('bytes',c.c_char*20),('longs',c.c_long*5)]

class ClientMessage(c.Structure):
    _fields_=[('type',I),('serial',U),('send_event',I),('display',P),('window',U),('message_type',U),('format',I),('data',ClientData)]

class ClientEvent(c.Union):
    _fields_=[('client',ClientMessage),('pad',c.c_long*24)]

class Windows:
    def __init__(self):
        x=self.x=c.CDLL('libX11.so.6')
        x.XOpenDisplay.argtypes=[c.c_char_p];x.XOpenDisplay.restype=P;x.XCloseDisplay.argtypes=[P]
        x.XDefaultRootWindow.argtypes=[P];x.XDefaultRootWindow.restype=U
        x.XQueryTree.argtypes=[P,U,c.POINTER(U),c.POINTER(U),c.POINTER(c.POINTER(U)),c.POINTER(c.c_uint)]
        x.XInternAtom.argtypes=[P,c.c_char_p,I];x.XInternAtom.restype=U
        x.XGetWindowProperty.argtypes=[P,U,U,c.c_long,c.c_long,I,U,c.POINTER(U),c.POINTER(I),c.POINTER(U),c.POINTER(U),c.POINTER(P)]
        x.XGetWindowAttributes.argtypes=[P,U,c.POINTER(Attr)];x.XFree.argtypes=[P]
        x.XMoveResizeWindow.argtypes=[P,U,I,I,c.c_uint,c.c_uint]
        x.XMoveWindow.argtypes=[P,U,I,I];x.XSync.argtypes=[P,I]
        x.XSendEvent.argtypes=[P,U,I,c.c_long,c.POINTER(ClientEvent)]
        callback=c.CFUNCTYPE(I,P,c.POINTER(Error))
        self.errors=0
        @callback
        def handle(_,error):
            if error.contents.error_code!=3:self.errors+=1
            return 0
        self.handler=handle;x.XSetErrorHandler.argtypes=[callback];x.XSetErrorHandler(handle)
        self.d=x.XOpenDisplay(os.environ.get('DISPLAY',':1').encode())
        if not self.d:raise RuntimeError('本机XWayland尚未就绪。')
        self.atom=x.XInternAtom(self.d,b'_NET_WM_PID',1)

    def property32(self,window,name):
        x=self.x;atom=x.XInternAtom(self.d,name,1)
        if not atom:return []
        typ=U();fmt=I();n=U();after=U();data=P()
        result=x.XGetWindowProperty(self.d,window,atom,0,128,0,0,c.byref(typ),c.byref(fmt),c.byref(n),c.byref(after),c.byref(data))
        try:return [int(c.cast(data,c.POINTER(U))[i]) for i in range(n.value)] if result==0 and data and fmt.value==32 else []
        finally:
            if data:x.XFree(data)

    def align_maximized_main(self,window,pid,apply=False):
        """Only align a mapped, maximized main window; never enlarge it for OSK."""
        proc=pathlib.Path('/proc')/str(pid)
        try:
            if proc.stat().st_uid!=os.getuid() or (proc/'exe').resolve(strict=True)!=MAIN:return None
        except (FileNotFoundError,PermissionError):return None
        if self.property32(window,b'_NET_WM_PID')!=[pid] or self.property32(window,b'WM_TRANSIENT_FOR'):return None
        x=self.x
        types=self.property32(window,b'_NET_WM_WINDOW_TYPE')
        normal=x.XInternAtom(self.d,b'_NET_WM_WINDOW_TYPE_NORMAL',1)
        dialog=x.XInternAtom(self.d,b'_NET_WM_WINDOW_TYPE_DIALOG',1)
        if not normal or normal not in types or dialog in types:return None
        states=set(self.property32(window,b'_NET_WM_STATE'))
        required={x.XInternAtom(self.d,name,1) for name in (b'_NET_WM_STATE_MAXIMIZED_HORZ',b'_NET_WM_STATE_MAXIMIZED_VERT')}
        if 0 in required or not required<=states:return None
        excluded={x.XInternAtom(self.d,name,1) for name in (b'_NET_WM_STATE_FULLSCREEN',b'_NET_WM_STATE_MODAL')}
        if states&excluded:return None
        attr=Attr();root=Attr();root_window=x.XDefaultRootWindow(self.d)
        if not x.XGetWindowAttributes(self.d,window,c.byref(attr)) or attr.map_state!=2 or attr.override_redirect:return None
        if not x.XGetWindowAttributes(self.d,root_window,c.byref(root)):return None
        desktops=self.property32(root_window,b'_NET_CURRENT_DESKTOP')
        area,source=usable_area(root.width,root.height,self.property32(root_window,b'_NET_WORKAREA'),desktops[0] if desktops else 0)
        if area is None:return None
        left,top,width,height=area
        before=(attr.x,attr.y,attr.width,attr.height)
        target=(left,top,min(attr.width,width),min(attr.height,height))
        result=dict(before=before,target=target,area=area,source=source,changed=before!=target)
        if apply and result['changed'] and self.property32(window,b'_NET_WM_PID')==[pid]:
            if before[2:]==target[2:]:x.XMoveWindow(self.d,window,left,top)
            else:x.XMoveResizeWindow(self.d,window,*target)
            x.XSync(self.d,0)
        return result

    def request_startup_maximize(self,window,pid):
        """Maximize an ordinary main-process window once, leaving later restores alone."""
        proc=pathlib.Path('/proc')/str(pid)
        try:
            if proc.stat().st_uid!=os.getuid() or (proc/'exe').resolve(strict=True)!=MAIN:return False
        except (FileNotFoundError,PermissionError):return False
        if self.property32(window,b'_NET_WM_PID')!=[pid] or self.property32(window,b'WM_TRANSIENT_FOR'):return False
        x=self.x;attr=Attr()
        if not x.XGetWindowAttributes(self.d,window,c.byref(attr)) or attr.map_state!=2 or attr.override_redirect or min(attr.width,attr.height)<200:return False
        normal=x.XInternAtom(self.d,b'_NET_WM_WINDOW_TYPE_NORMAL',1)
        dialog=x.XInternAtom(self.d,b'_NET_WM_WINDOW_TYPE_DIALOG',1)
        types=self.property32(window,b'_NET_WM_WINDOW_TYPE')
        if not normal or normal not in types or dialog in types:return False
        states=set(self.property32(window,b'_NET_WM_STATE'))
        excluded={x.XInternAtom(self.d,name,1) for name in (b'_NET_WM_STATE_FULLSCREEN',b'_NET_WM_STATE_MODAL')}
        if states&excluded:return False
        horz=x.XInternAtom(self.d,b'_NET_WM_STATE_MAXIMIZED_HORZ',0);vert=x.XInternAtom(self.d,b'_NET_WM_STATE_MAXIMIZED_VERT',0)
        if {horz,vert}<=states:return True
        event=ClientEvent();event.client.type=33;event.client.display=self.d;event.client.window=window
        event.client.message_type=x.XInternAtom(self.d,b'_NET_WM_STATE',0);event.client.format=32
        event.client.data.longs[0]=1;event.client.data.longs[1]=horz;event.client.data.longs[2]=vert;event.client.data.longs[3]=2
        x.XSendEvent(self.d,x.XDefaultRootWindow(self.d),0,(1<<19)|(1<<20),c.byref(event));x.XSync(self.d,0)
        return True

    def mapped(self):
        x=self.x;root=x.XDefaultRootWindow(self.d);r=U();p=U();children=c.POINTER(U)();count=c.c_uint()
        result={};owners={}
        if not x.XQueryTree(self.d,root,c.byref(r),c.byref(p),c.byref(children),c.byref(count)):return result
        try:
            for i in range(count.value):
                w=children[i];typ=U();fmt=I();n=U();after=U();data=P()
                x.XGetWindowProperty(self.d,w,self.atom,0,1,0,6,c.byref(typ),c.byref(fmt),c.byref(n),c.byref(after),c.byref(data))
                try:pid=int(c.cast(data,c.POINTER(U))[0]) if data and n.value else None
                finally:
                    if data:x.XFree(data)
                if not pid:continue
                if pid not in owners:
                    proc=pathlib.Path('/proc')/str(pid)
                    try:
                        exe=(proc/'exe').resolve(strict=True)
                        owners[pid]=exe if proc.stat().st_uid==os.getuid() and exe in (MAIN,APPEX) else None
                    except (FileNotFoundError,PermissionError):owners[pid]=None
                if owners[pid] is None:continue
                a=Attr()
                if x.XGetWindowAttributes(self.d,w,c.byref(a)) and a.map_state==2 and a.klass==1 and a.width>=64 and a.height>=64:result[w]=pid
        finally:
            if children:x.XFree(children)
        return result

    def close(self):
        if self.d:self.x.XCloseDisplay(self.d);self.d=None
