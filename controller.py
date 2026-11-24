#!/usr/bin/python3
"""Keep WeChat touch helpers and maximized placement within the phone workarea."""
import fcntl
import json
import os
import pathlib
import signal
import select
import socket
import stat
import subprocess
import sys
import time
from x11_windows import Windows,main_pids
from focus_repair import FocusRepair,parse_tap

def main():
    assert os.getuid()!=0
    root=pathlib.Path.home()/'.local/state/wechat-mobile'
    root.mkdir(parents=True,mode=0o700,exist_ok=True);root.chmod(0o700)
    lock=os.open(f'/run/user/{os.getuid()}/wechat-swipe-controller.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    reader=Windows();workers={};failures={};retry={};geometry={};startup_maximized=set();running=True;last_check=0
    boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    focus=FocusRepair(reader);pending={};focus_requests=0
    socket_path=pathlib.Path(f'/run/user/{os.getuid()}/wechat-focus-requests.sock')
    if socket_path.exists() or socket_path.is_symlink():
        previous=socket_path.lstat()
        assert stat.S_ISSOCK(previous.st_mode) and previous.st_uid==os.getuid()
        socket_path.unlink()
    receiver=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);receiver.bind(str(socket_path));socket_path.chmod(0o600);receiver.setblocking(False)
    socket_inode=socket_path.stat().st_ino
    helper=pathlib.Path(__file__).resolve().parent/'touch-wheel.py'
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    def end_worker(proc):
        if proc.poll() is not None:return
        proc.terminate()
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            # This is only our input helper, never a WeChat/account process.
            proc.kill();proc.wait(timeout=2)
    def save():
        out=root/'controller-status.json';temp=out.with_suffix('.next')
        with temp.open('w') as f:json.dump({'running':running,'bootId':boot_id,'controllerPid':os.getpid(),'workers':{str(w):p.pid for w,p in workers.items()},'windowFailures':failures,'geometryFixes':{str(w):v['attempts'] for w,v in geometry.items() if v['attempts']},'focusRepairAvailable':focus.available,'focusRequests':focus_requests,'focusRepairs':focus.repaired,'lastFocusRepair':focus.last_result,'version':5,'keyboardEventsObserved':False,'inputGrabbed':'per-window touch only'},f,indent=2);f.write('\n')
        temp.chmod(0o600);os.replace(temp,out)
    try:
        while running:
            now=time.monotonic()
            if now-last_check>=3:
                if not main_pids():break
                last_check=now
            mapped=reader.mapped()
            while True:
                try:raw=receiver.recv(512)
                except BlockingIOError:break
                value=parse_tap(raw,time.monotonic(),mapped)
                if value:pending[value[0]]=value[1];focus_requests+=1
            for w,stamp in list(pending.items()):
                if now-stamp<.12:continue
                pending.pop(w,None)
                if w in mapped:focus.attempt(w,mapped[w],stamp)
            mapped=reader.mapped()
            for w,proc in list(workers.items()):
                if w not in mapped or proc.poll() is not None:
                    code=proc.poll();end_worker(proc);workers.pop(w)
                    if w in mapped and code not in (None,0):failures[w]=failures.get(w,0)+1;retry[w]=now+10
            for w in list(failures):
                if w not in mapped:failures.pop(w,None);retry.pop(w,None)
            for w in list(geometry):
                if w not in mapped:geometry.pop(w)
            for w,pid in mapped.items():
                entry=geometry.setdefault(w,dict(seen=now,signature=None,attempts=0,next=0))
                if now-entry['seen']<1.5 or now<entry['next']:continue
                # Moments is another ordinary window in the main process.
                # Remember each XID/PID pair so later windows are not skipped.
                key=(w,pid)
                if key not in startup_maximized and reader.request_startup_maximize(w,pid):
                    startup_maximized.add(key);entry['next']=now+1;continue
                placement=reader.align_maximized_main(w,pid)
                if placement is None:entry['signature']=None;entry['attempts']=0;continue
                signature=placement['area']
                if entry['signature']!=signature:entry.update(signature=signature,attempts=0)
                if placement['changed'] and entry['attempts']<3:
                    reader.align_maximized_main(w,pid,apply=True)
                    entry['attempts']+=1;entry['next']=now+2
            for w in mapped:
                if w in workers or failures.get(w,0)>=3 or retry.get(w,0)>now:continue
                workers[w]=subprocess.Popen([sys.executable,'-u',str(helper),'--window',str(w),'--seconds','0','--anchor','start','--parent-pid',str(os.getpid()),'--focus-socket',str(socket_path)])
            save()
            wait=min(.75,max(0,min(pending.values())+.12-time.monotonic())) if pending else .75
            select.select([receiver],[],[],wait)
    finally:
        running=False
        for proc in workers.values():end_worker(proc)
        workers.clear();save();receiver.close()
        if socket_path.exists() and socket_path.lstat().st_ino==socket_inode:socket_path.unlink()
        reader.close();os.close(lock)

if __name__=='__main__':main()
