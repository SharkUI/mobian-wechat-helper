#!/usr/bin/python3
"""Request termination only for this user's processes from the WeChat bundle."""
import os
import pathlib
import signal
import subprocess
import sys
import time

BUNDLE = pathlib.Path('/opt/wechat')

def processes():
    result = {}
    for entry in pathlib.Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            exe = (entry / 'exe').resolve(strict=True)
            if entry.stat().st_uid != os.getuid() or not exe.is_relative_to(BUNDLE):
                continue
            result[int(entry.name)] = exe
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return result

def terminate(pid, expected_exe):
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        entry = pathlib.Path('/proc') / str(pid)
        if entry.stat().st_uid == os.getuid() and (entry / 'exe').resolve(strict=True) == expected_exe:
            signal.pidfd_send_signal(fd, signal.SIGTERM)
    except (FileNotFoundError, ProcessLookupError):
        pass
    finally:
        os.close(fd)

def wait_until(predicate, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()

def main():
    control = pathlib.Path.home() / '.local/lib/wechat-mobile/control.py'
    if control.is_file():
        try:subprocess.run([sys.executable, str(control), 'stop', '--quiet'], timeout=8)
        except (OSError, subprocess.TimeoutExpired):pass
    for pid, exe in processes().items():
        if exe == BUNDLE / 'wechat':
            terminate(pid, exe)
    wait_until(lambda: BUNDLE / 'wechat' not in processes().values(), 3)
    for pid, exe in processes().items():
        if exe != BUNDLE / 'wechat':
            terminate(pid, exe)
    if wait_until(lambda: not processes(), 3):
        print('WeChat and its helper processes exited.')
        return 0
    try:
        from gi.repository import Gio, GLib
        Gio.bus_get_sync(Gio.BusType.SESSION, None).call_sync(
            'org.freedesktop.Notifications', '/org/freedesktop/Notifications',
            'org.freedesktop.Notifications', 'Notify',
            GLib.Variant('(susssasa{sv}i)', ('微信', 0, 'dialog-warning', '微信未完全退出',
                '仍有后台进程；未执行强制结束，请稍后重试。', [], {}, 6000)),
            None, Gio.DBusCallFlags.NONE, 3000, None)
    except Exception:
        pass
    print('WeChat still has running processes; no SIGKILL was sent.', file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
