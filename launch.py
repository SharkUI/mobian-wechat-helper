#!/usr/bin/python3
"""Launch WeChat with the tested display backend and enable its swipe helper."""
import os
import pathlib
import subprocess
import sys
import time
from x11_windows import main_pids

def main():
    assert os.getuid()!=0
    subprocess.Popen(['/usr/bin/wechat',*sys.argv[1:]],env=dict(os.environ,QT_QPA_PLATFORM='xcb'),start_new_session=True)
    for _ in range(100):
        if main_pids():
            subprocess.run([sys.executable,str(pathlib.Path(__file__).resolve().parent/'control.py'),'start','--quiet'],check=True)
            return
        time.sleep(.1)

if __name__=='__main__':main()
