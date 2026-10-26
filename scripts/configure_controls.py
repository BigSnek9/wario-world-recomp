"""Install explicit Xbox-to-GameCube Player 1 bindings with keyboard fallback."""
import argparse,configparser,ctypes,json,shutil
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
def profile():
    keyboard='DInput/0/Keyboard Mouse'
    def binding(xbox,key=None):
        values=[f'`XInput/{i}/Gamepad:{xbox}`' for i in range(4)]
        if key:values.append(f'`{keyboard}:{key}`')
        return ' | '.join(values)
    result={'Device':keyboard,'Options/Always Connected':'True',
        'Buttons/A':binding('Button A','X'),'Buttons/B':binding('Button B','Z'),
        'Buttons/X':binding('Button X','C'),'Buttons/Y':binding('Button Y','S'),
        'Buttons/Z':binding('Shoulder R','D'),'Buttons/Start':binding('Start','RETURN'),
        'Main Stick/Up':binding('Left Y+','UP'),'Main Stick/Down':binding('Left Y-','DOWN'),
        'Main Stick/Left':binding('Left X-','LEFT'),'Main Stick/Right':binding('Left X+','RIGHT'),
        'C-Stick/Up':binding('Right Y+','I'),'C-Stick/Down':binding('Right Y-','K'),
        'C-Stick/Left':binding('Right X-','J'),'C-Stick/Right':binding('Right X+','L'),
        'D-Pad/Up':binding('Pad N','T'),'D-Pad/Down':binding('Pad S','G'),
        'D-Pad/Left':binding('Pad W','F'),'D-Pad/Right':binding('Pad E','H'),
        'Triggers/L':binding('Shoulder L','Q')+' | (('+binding('Trigger L')+') > 0.9)',
        'Triggers/R':binding('Trigger R','W')+' > 0.9',
        'Triggers/L-Analog':binding('Trigger L','Q'),'Triggers/R-Analog':binding('Trigger R','W'),
        'Main Stick/Dead Zone':'12.0','C-Stick/Dead Zone':'12.0',
        'Main Stick/Calibration':'100.0 100.0 100.0 100.0 100.0 100.0 100.0 100.0',
        'C-Stick/Calibration':'100.0 100.0 100.0 100.0 100.0 100.0 100.0 100.0'}
    # Parenthesize analog combination before threshold; keep keyboard R a digital click.
    result['Triggers/R']='(('+binding('Trigger R')+') > 0.9) | `'+keyboard+':W`'
    return result

def settings(path):
    c=configparser.ConfigParser(interpolation=None,strict=False);c.optionxform=str
    if path.exists():c.read(path,encoding='utf-8')
    return c

def install(user):
    folder=user/'Config';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'GCPadNew.ini';c=settings(target)
    before=target.read_bytes() if target.exists() else None
    if not c.has_section('GCPad1'):c.add_section('GCPad1')
    for key,value in profile().items():c.set('GCPad1',key,value)
    from io import StringIO
    buffer=StringIO();c.write(buffer);data=buffer.getvalue().encode('utf-8')
    backup=None
    if before!=data:
        if before is not None:
            backup=folder/('GCPadNew.before-xinput-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex[:8]+'.ini')
            shutil.copy2(target,backup)
        target.write_bytes(data)
    core=folder/'Dolphin.ini';dc=settings(core)
    if not dc.has_section('Core'):dc.add_section('Core')
    if dc.get('Core','SIDevice0',fallback=None)!='6':
        if core.exists():shutil.copy2(core,folder/('Dolphin.before-xinput-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex[:8]+'.ini'))
        dc.set('Core','SIDevice0','6')
        with core.open('w',encoding='utf-8') as out:dc.write(out)
    return {'profile':str(target),'previous_profile_backup':str(backup) if backup else None,'controller':'Xbox/XInput (any of four slots) + keyboard fallback','port':1,'rumble':'Existing rumble setting preserved; not exercised by tests'}

def xinput_slots():
    try:dll=ctypes.WinDLL('xinput1_4.dll')
    except OSError:return []
    dll.XInputGetState.argtypes=[ctypes.c_uint,ctypes.c_void_p]
    return [i for i in range(4) if dll.XInputGetState(i,ctypes.create_string_buffer(16))==0]

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--user-dir',type=Path,default=ROOT/'private/playtest-user');a=p.parse_args()
    report=install(a.user_dir.resolve());report['connected_xinput_slots']=xinput_slots();print(json.dumps(report,indent=2))
