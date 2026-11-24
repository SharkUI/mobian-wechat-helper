#!/usr/bin/python3
"""Start/pause only the WeChat gesture controller, without closing WeChat."""
import argparse
import fcntl
import json
import os
import pathlib
import select
import signal
import subprocess
import sys
import time
from x11_windows import main_pids

BASE=pathlib.Path(__file__).resolve().parent
STATE=pathlib.Path.home()/'.local/state/wechat-mobile'
META=STATE/'control-process.json'

def notify(summary,detail=''):
    try:
        from gi.repository import Gio,GLib
        Gio.bus_get_sync(Gio.BusType.SESSION,None).call_sync('org.freedesktop.Notifications','/org/freedesktop/Notifications','org.freedesktop.Notifications','Notify',GLib.Variant('(susssasa{sv}i)',('微信',0,'input-touchpad',summary,detail,[],{},5000)),None,Gio.DBusCallFlags.NONE,3000,None)
    except Exception:pass

def current():
    if not META.exists():return None
    value=json.loads(META.read_text());pid=value.get('pid')
    if not isinstance(pid,int) or pid<=1:return None
    p=pathlib.Path('/proc')/str(pid)
    try:
        argv=(p/'cmdline').read_bytes().split(b'\0')
        if p.stat().st_uid==os.getuid() and len(argv)>2 and argv[1]==b'-u' and argv[2]==str(BASE/'controller.py').encode() and (p/'exe').resolve(strict=True)==pathlib.Path(sys.executable).resolve():return pid
    except (FileNotFoundError,PermissionError):pass
    return None

def write(value):
    temp=META.with_suffix('.next')
    with temp.open('w') as f:json.dump(value,f,indent=2);f.write('\n')
    temp.chmod(0o600);os.replace(temp,META)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop']);parser.add_argument('--quiet',action='store_true');args=parser.parse_args()
    assert os.getuid()!=0,'Run as the phone desktop user'
    STATE.mkdir(parents=True,mode=0o700,exist_ok=True);STATE.chmod(0o700)
    fd=os.open(f'/run/user/{os.getuid()}/wechat-swipe-control.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX)
        pid=current()
        if args.action=='stop':
            if pid:
                procfd=os.pidfd_open(pid)
                try:
                    if current()==pid:signal.pidfd_send_signal(procfd,signal.SIGTERM)
                    if not select.select([procfd],[],[],6)[0]:raise RuntimeError('滑动修复尚未停止，请稍后重试。')
                finally:os.close(procfd)
            write(dict(active=False,stoppedAtEpoch=time.time()))
            if not args.quiet:notify('微信滑动修复已暂停','可从图标菜单恢复；下次从微信图标启动也会自动恢复。')
            return
        if not main_pids():raise RuntimeError('请先打开微信。')
        if not pid:
            log=os.open(STATE/'controller.log',os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
            with os.fdopen(log,'w') as out:proc=subprocess.Popen([sys.executable,'-u',str(BASE/'controller.py')],stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
            time.sleep(.4)
            if proc.poll() is not None:raise RuntimeError('滑动修复未能启动，请稍后重试。')
            write(dict(pid=proc.pid,active=True,startedAtEpoch=time.time(),version=5))
        if not args.quiet:notify('微信滑动修复已开启','当前微信窗口及之后打开的网页窗口都会应用；退出微信时自动停止。')
    finally:os.close(fd)

if __name__=='__main__':
    try:main()
    except Exception as error:
        notify('微信滑动修复未完成',str(error) if isinstance(error,RuntimeError) else '请稍后重试。')
        print(str(error),file=sys.stderr);sys.exit(1)
