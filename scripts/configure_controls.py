"""Install GameCube-layout Xbox/XInput Player 1 bindings with keyboard fallback and rumble.

Defaults follow the GameCube pad's physical layout, not the button labels (docs/CONTROLS.md):
A bottom (Xbox A / PS Cross), B left (X / Square), X right (B / Circle), Y top (Y / Triangle),
Z = RB, L / R = LT / RT (analog, near-full press clicks), Start = Menu, C-stick = right stick,
and rumble on both motors. The in-game menu (scripts/tool_fix_wario_menu.py, kPadControls) builds
the same expressions and adds every connected SDL gamepad (DualShock / DualSense) at runtime.

--migrate updates an existing profile: bindings still equal to the old by-label defaults move to
the new ones, custom bindings stay, a backup is written first.
"""
import argparse,configparser,ctypes,json,shutil
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
KEYBOARD='DInput/0/Keyboard Mouse'
# (ini key, XInput controls, keyboard key); same table as kPadControls in tool_fix_wario_menu.py.
CONTROLS=[('Buttons/A',['Button A'],'X'),('Buttons/B',['Button X'],'Z'),
    ('Buttons/X',['Button B'],'C'),('Buttons/Y',['Button Y'],'S'),
    ('Buttons/Z',['Shoulder R'],'D'),('Buttons/Start',['Start'],'RETURN'),
    ('Triggers/L',['Shoulder L','Trigger L'],'Q'),('Triggers/R',['Trigger R'],'W'),
    ('D-Pad/Up',['Pad N'],'T'),('D-Pad/Down',['Pad S'],'G'),('D-Pad/Left',['Pad W'],'F'),('D-Pad/Right',['Pad E'],'H'),
    ('Triggers/L-Analog',['Trigger L'],'Q'),('Triggers/R-Analog',['Trigger R'],'W'),
    ('Main Stick/Up',['Left Y+'],'UP'),('Main Stick/Down',['Left Y-'],'DOWN'),
    ('Main Stick/Left',['Left X-'],'LEFT'),('Main Stick/Right',['Left X+'],'RIGHT'),
    ('C-Stick/Up',['Right Y+'],'I'),('C-Stick/Down',['Right Y-'],'K'),
    ('C-Stick/Left',['Right X-'],'J'),('C-Stick/Right',['Right X+'],'L'),
    ('Rumble/Motor',['Motor L','Motor R'],'')]
SETTINGS={'Options/Always Connected':'True','Main Stick/Dead Zone':'12.0','C-Stick/Dead Zone':'12.0',
    'Main Stick/Calibration':'100.0 100.0 100.0 100.0 100.0 100.0 100.0 100.0',
    'C-Stick/Calibration':'100.0 100.0 100.0 100.0 100.0 100.0 100.0 100.0'}

def digital(key):
    """Digital GameCube inputs take a trigger only when pressed nearly fully (the GC L/R click)."""
    return key.startswith(('Buttons/','D-Pad/')) or key in ('Triggers/L','Triggers/R')

def binding(key,pads,keyboard_key):
    plain,click=[],[]
    for pad in pads:
        (click if digital(key) and pad.startswith('Trigger ') else plain).extend(f'`XInput/{i}/Gamepad:{pad}`' for i in range(4))
    expression=' | '.join(plain)
    if click:expression+=(' | ' if expression else '')+'(('+' | '.join(click)+') > 0.9)'
    if keyboard_key:expression+=(' | ' if expression else '')+f'`{KEYBOARD}:{keyboard_key}`'
    return expression

def profile():
    result={'Device':KEYBOARD,**SETTINGS}
    for key,pads,keyboard_key in CONTROLS:result[key]=binding(key,pads,keyboard_key)
    return result

def legacy_profile():
    """The previous by-label defaults (Xbox B = GC B, Xbox X = GC X, no rumble), for --migrate."""
    def old(xbox,key=None):
        values=[f'`XInput/{i}/Gamepad:{xbox}`' for i in range(4)]
        if key:values.append(f'`{KEYBOARD}:{key}`')
        return ' | '.join(values)
    result={'Buttons/A':old('Button A','X'),'Buttons/B':old('Button B','Z'),
        'Buttons/X':old('Button X','C'),'Buttons/Y':old('Button Y','S'),
        'Buttons/Z':old('Shoulder R','D'),'Buttons/Start':old('Start','RETURN'),
        'Main Stick/Up':old('Left Y+','UP'),'Main Stick/Down':old('Left Y-','DOWN'),
        'Main Stick/Left':old('Left X-','LEFT'),'Main Stick/Right':old('Left X+','RIGHT'),
        'C-Stick/Up':old('Right Y+','I'),'C-Stick/Down':old('Right Y-','K'),
        'C-Stick/Left':old('Right X-','J'),'C-Stick/Right':old('Right X+','L'),
        'D-Pad/Up':old('Pad N','T'),'D-Pad/Down':old('Pad S','G'),
        'D-Pad/Left':old('Pad W','F'),'D-Pad/Right':old('Pad E','H'),
        'Triggers/L':old('Shoulder L','Q')+' | (('+old('Trigger L')+') > 0.9)',
        'Triggers/R':'(('+old('Trigger R')+') > 0.9) | `'+KEYBOARD+':W`',
        'Triggers/L-Analog':old('Trigger L','Q'),'Triggers/R-Analog':old('Trigger R','W')}
    return result

def settings(path):
    c=configparser.ConfigParser(interpolation=None,strict=False);c.optionxform=str
    if path.exists():c.read(path,encoding='utf-8')
    return c

def stamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid4().hex[:8]

def write_profile(target,c,label):
    """Writes the profile, backing up a changed pre-existing file; returns the backup path."""
    from io import StringIO
    before=target.read_bytes() if target.exists() else None
    buffer=StringIO();c.write(buffer);data=buffer.getvalue().encode('utf-8')
    backup=None
    if before!=data:
        if before is not None:
            backup=target.parent/(f'GCPadNew.before-{label}-'+stamp()+'.ini')
            shutil.copy2(target,backup)
        target.write_bytes(data)
    return backup

def gamecube_port(folder):
    core=folder/'Dolphin.ini';dc=settings(core)
    if not dc.has_section('Core'):dc.add_section('Core')
    if dc.get('Core','SIDevice0',fallback=None)!='6':
        if core.exists():shutil.copy2(core,folder/('Dolphin.before-xinput-'+stamp()+'.ini'))
        dc.set('Core','SIDevice0','6')
        with core.open('w',encoding='utf-8') as out:dc.write(out)

def install(user):
    """Explicitly restores the defaults for Player 1 (other players and settings are kept)."""
    folder=user/'Config';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'GCPadNew.ini';c=settings(target)
    if not c.has_section('GCPad1'):c.add_section('GCPad1')
    for key,value in profile().items():c.set('GCPad1',key,value)
    backup=write_profile(target,c,'xinput')
    gamecube_port(folder)
    return {'profile':str(target),'previous_profile_backup':str(backup) if backup else None,
        'controller':'Xbox/XInput (any of four slots) + keyboard fallback; SDL pads added by the in-game menu',
        'layout':'GameCube positions','port':1,'rumble':'Motor L + Motor R on every XInput slot'}

def migrate(user):
    """Moves Player 1 bindings that still equal the old by-label defaults to the GameCube layout
    and adds missing ones (rumble); custom bindings are kept. Idempotent."""
    folder=user/'Config';target=folder/'GCPadNew.ini'
    if not target.exists():return install(user)
    c=settings(target)
    if not c.has_section('GCPad1'):c.add_section('GCPad1')
    legacy,new=legacy_profile(),profile()
    updated,kept=[],[]
    for key,value in new.items():
        current=c.get('GCPad1',key,fallback=None)
        if current==value:continue
        if current is None or (key in legacy and current.strip()==legacy[key]):
            c.set('GCPad1',key,value);updated.append(key)
        elif key in legacy or key=='Rumble/Motor':kept.append(key)
    backup=write_profile(target,c,'gamecube-layout') if updated else None
    gamecube_port(folder)
    return {'profile':str(target),'previous_profile_backup':str(backup) if backup else None,
        'updated':updated,'kept_custom':kept}

def xinput_slots():
    try:dll=ctypes.WinDLL('xinput1_4.dll')
    except OSError:return []
    dll.XInputGetState.argtypes=[ctypes.c_uint,ctypes.c_void_p]
    return [i for i in range(4) if dll.XInputGetState(i,ctypes.create_string_buffer(16))==0]

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--user-dir',type=Path,default=ROOT/'private/playtest-user')
    p.add_argument('--migrate',action='store_true',help='update an existing profile to the GameCube layout, keeping custom bindings')
    a=p.parse_args()
    report=(migrate if a.migrate else install)(a.user_dir.resolve());report['connected_xinput_slots']=xinput_slots();print(json.dumps(report,indent=2))
