#!/usr/bin/python3
"""Install/restore only this user's WeChat launch helpers and desktop actions."""
import argparse
import ast
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
from gi.repository import Gio,GLib

HOME=pathlib.Path.home();BASE=HOME/'.local/lib/wechat-mobile';STATE=HOME/'.local/state/wechat-mobile'
DESKTOP=HOME/'.local/share/applications/wechat.desktop'
NAMES=['motion-wheel.py','touch-wheel.py','focus_repair.py','quit.py','x11_windows.py','controller.py','control.py','launch.py']
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def atomic(path,data,mode):
    fd,temp=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(data)
        os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def exec_arg(value):
    return '"'+str(value).replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$').replace('%','%%')+'"'

def restore(directory):
    directory=directory.resolve(strict=True)
    assert directory.is_relative_to(STATE/'installs')
    manifest=json.loads((directory/'manifest.json').read_text())
    allowed={str(BASE/name) for name in NAMES}|{str(DESKTOP)}
    assert {i['path'] for i in manifest['files']}==allowed
    for item in manifest['files']:
        p=pathlib.Path(item['path']);assert p.is_file() and not p.is_symlink() and sha(p)==item['sha256'],'Current files changed; review before restoring'
    subprocess.run([sys.executable,str(BASE/'control.py'),'stop','--quiet'],check=True)
    for item in reversed(manifest['files']):
        p=pathlib.Path(item['path'])
        if item['before'] is None:p.unlink()
        else:
            old=(directory/item['before']).resolve(strict=True);assert old.is_relative_to(directory)
            atomic(p,old.read_bytes(),item['beforeMode'])
    print('Previous WeChat helpers and desktop entry restored; private receipts retained.')

def install():
    source=pathlib.Path(__file__).resolve().parent
    package=pathlib.Path('/usr/share/applications/wechat.desktop')
    assert package.is_file();package_hash=sha(package)
    for name in NAMES:ast.parse((source/name).read_text())
    for directory in [BASE,STATE]:
        assert not directory.is_symlink();directory.mkdir(parents=True,mode=0o700,exist_ok=True);directory.chmod(0o700)
    if (BASE/'control.py').exists():subprocess.run([sys.executable,str(BASE/'control.py'),'stop','--quiet'],check=True)
    assert not DESKTOP.is_symlink()
    key=GLib.KeyFile();key.load_from_file(str(DESKTOP if DESKTOP.exists() else package),GLib.KeyFileFlags.KEEP_COMMENTS|GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    launch='/usr/bin/python3 '+exec_arg(BASE/'launch.py')+' %U'
    assert key.get_string('Desktop Entry','Exec') in ['/usr/bin/wechat %U','/usr/bin/env QT_QPA_PLATFORM=xcb /usr/bin/wechat %U',launch],'Review custom launcher before installing'
    key.set_string('Desktop Entry','Exec',launch)
    key.set_boolean('Desktop Entry','DBusActivatable',False)
    try:actions=list(key.get_string_list('Desktop Entry','Actions'))
    except GLib.Error:actions=[]
    entries=[('QuitWeChat','退出微信','quit.py',None),('EnableWechatSwipe','开启微信触控修复','control.py','start'),('PauseWechatSwipe','暂停微信触控修复','control.py','stop')]
    for ident,name,filename,argument in entries:
        command='/usr/bin/python3 '+exec_arg(BASE/filename)+((' '+argument) if argument else '')
        if ident in actions:
            old=key.get_string('Desktop Action '+ident,'Exec')
            assert old in [command,'/usr/bin/python3 '+str(BASE/filename)+((' '+argument) if argument else '')],'Review custom desktop action before installing'
        else:actions.append(ident)
        key.set_string('Desktop Action '+ident,'Name',name)
        key.set_string('Desktop Action '+ident,'Exec',command)
    key.set_string_list('Desktop Entry','Actions',actions)
    backup=STATE/'installs'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup.mkdir(parents=True,mode=0o700,exist_ok=False)
    files=[(BASE/name,(source/name).read_bytes(),0o700) for name in NAMES]+[(DESKTOP,key.to_data()[0].encode(),0o644)]
    manifest={'files':[],'systemDesktopSha256':package_hash}
    for index,(target,data,mode) in enumerate(files):
        assert not target.is_symlink()
        before=None;before_mode=None
        if target.exists():
            assert target.stat().st_uid==os.getuid() and target.is_file()
            before=f'before-{index}';shutil.copy2(target,backup/before);before_mode=stat.S_IMODE(target.stat().st_mode)
        manifest['files'].append(dict(path=str(target),before=before,beforeMode=before_mode,sha256=hashlib.sha256(data).hexdigest()))
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    written=[]
    try:
        for item,(target,data,mode) in zip(manifest['files'],files):
            target.parent.mkdir(parents=True,exist_ok=True);atomic(target,data,mode);written.append(item)
        info=Gio.DesktopAppInfo.new_from_filename(str(DESKTOP))
        assert info and set(i[0] for i in entries)<=set(info.list_actions())
        assert info.get_executable()=='/usr/bin/python3'
        for item in manifest['files']:assert sha(pathlib.Path(item['path']))==item['sha256']
        assert sha(package)==package_hash
    except BaseException:
        for item in reversed(written):
            target=pathlib.Path(item['path'])
            if item['before'] is None:target.unlink()
            else:atomic(target,(backup/item['before']).read_bytes(),item['beforeMode'])
        raise
    atomic(STATE/'installation.json',(json.dumps({'backup':str(backup),'source':str(source)},indent=2)+'\n').encode(),0o600)
    print('Installed user-only WeChat actions; restore snapshot: '+str(backup))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--restore',type=pathlib.Path);args=parser.parse_args()
    assert os.getuid()!=0,'Run as the phone desktop user, without sudo'
    restore(args.restore) if args.restore else install()
