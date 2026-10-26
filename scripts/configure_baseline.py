"""Pin presentation settings for Wario World validation; preserve other settings.

This is a presentation baseline, not an assertion of hardware accuracy. Other
runtime defaults remain subject to the review in docs/ACCURACY_REVIEW.md.
"""
import argparse, configparser, io, json, shutil
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

def install(user):
    changes=[]
    specs={
        'config.ini':{'Video':{'resolution':'640x528','backend':'OpenGL'}},
        'Config/GFX.ini':{'Settings':{'AspectRatio':'2','InternalResolution':'1','wideScreenHack':'False','Crop':'False'}},
    }
    for relative,sections in specs.items():
        path=user/relative
        c=configparser.ConfigParser(interpolation=None,strict=False);c.optionxform=str
        if path.exists():c.read(path,encoding='utf-8-sig')
        elif relative=='config.ini':
            c.read_string('[Video]\nfullscreen=false\nshow_fps_in_title=true\n[Input]\n[Netplay]\nnickname=Player\naddress=127.0.0.1\nport=2626\nbuffer=auto\n')
        changed=False
        for section,values in sections.items():
            if not c.has_section(section):c.add_section(section)
            for key,value in values.items():
                # Case-insensitive matching avoids conflicting duplicate INI keys.
                existing=next((k for k in c[section] if k.lower()==key.lower()),key)
                if c.get(section,existing,fallback=None)!=value:
                    c.set(section,existing,value);changed=True
        if not changed:continue
        path.parent.mkdir(parents=True,exist_ok=True)
        backup=None
        if path.exists():
            backup=path.with_name(path.stem+'.before-baseline-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex[:8]+path.suffix)
            shutil.copy2(path,backup)
        buffer=io.StringIO();c.write(buffer);path.write_text(buffer.getvalue(),encoding='utf-8')
        changes.append({'file':str(path),'backup':str(backup) if backup else None})
    return changes

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--user-dir',type=Path,required=True)
    a=p.parse_args();print(json.dumps({'changes':install(a.user_dir),'presentation':'4:3, native 1x; other runtime behavior unvalidated'},indent=2))
