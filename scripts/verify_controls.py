"""Test generated bindings through production ControllerEmu/GCPad without hardware."""
import ctypes,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
project=ROOT
old_build=ROOT/'build/moderngekko'
output=ROOT/'build/verify-controls';output.mkdir(parents=True,exist_ok=True)
unit=ROOT/'tools/verify_controls.cpp'
tlog=old_build/'moderngekko-run.dir/Release/moderngekko-run.tlog/CL.command.1.tlog'
lines=tlog.read_text(encoding='utf-16').splitlines()
command=next(lines[i+1] for i,line in enumerate(lines) if line.startswith('^') and line.endswith('MODERNGEKKO_RUN.CPP'))
command=command.rsplit(' /utf-8 ',1)[0]+' /utf-8 '
command,n=re.subn(r'/Fo"[^\"]*"',lambda _: '/Fo"'+str(output/'controls.obj')+'"',command,flags=re.I)
assert n==1
command,n=re.subn(r'/Fd"[^\"]*"',lambda _: '/Fd"'+str(output/'compile.pdb')+'"',command,flags=re.I)
assert n==1
(output/'compile.rsp').write_text(command+'"'+str(unit)+'"\n',encoding='utf-8-sig')
linklog=old_build/'moderngekko-run.dir/Release/moderngekko-run.tlog/link.command.1.tlog'
linkcommand=' '.join(s for s in linklog.read_text(encoding='utf-16').splitlines() if s and not s.startswith('^'))
shell32=ctypes.WinDLL('shell32',use_last_error=True)
shell32.CommandLineToArgvW.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
shell32.CommandLineToArgvW.restype=ctypes.POINTER(ctypes.c_wchar_p)
kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
kernel32.LocalFree.argtypes=[ctypes.c_void_p]
count=ctypes.c_int()
pointer=shell32.CommandLineToArgvW('link '+linkcommand,ctypes.byref(count))
tokens=[pointer[i] for i in range(1,count.value)]
kernel32.LocalFree(pointer)
updated=[str(output/'controls.obj')]
for token in tokens:
    if token.replace(chr(92),"/").lower().endswith("/moderngekko_run.obj"): continue
    upper=token.upper()
    if upper in ('/INCLUDE:ENABLECOMPATPATCHES','-INCLUDE:ENABLECOMPATPATCHES'): token='/INCLUDE:enableCompatPatches'
    elif upper.startswith('/OUT:'): token='/OUT:'+str(output/'verify-controls.exe')
    elif upper.startswith('/PDB:'): token='/PDB:'+str(output/'verify-controls.pdb')
    elif upper.startswith('/IMPLIB:'): token='/IMPLIB:'+str(output/'verify-controls.lib')
    elif not token.startswith(('/','-')):
        candidate=old_build/token
        if candidate.is_file(): token=str(candidate)
    updated.append(token)
updated+=['/DEBUG:FULL','/OPT:REF','/OPT:ICF','/MAP:'+str(output/'verify-controls.map')]
(output/'link.rsp').write_text(subprocess.list2cmdline(updated)+'\n',encoding='utf-8-sig')
vs=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat')
batch=['@echo off',f'call "{vs}" -no_logo -arch=x64 -host_arch=x64','if errorlevel 1 exit /b 1',f'cl.exe @"{output/"compile.rsp"}" > "{output/"compile.log"}" 2>&1','if errorlevel 1 exit /b 1',f'link.exe @"{output/"link.rsp"}" > "{output/"link.log"}" 2>&1','exit /b %errorlevel%']
(output/'build.cmd').write_text('\n'.join(batch)+'\n')
subprocess.run(['cmd.exe','/d','/c',str(output/'build.cmd')],cwd=old_build,check=True)
from configure_controls import install
fixture=ROOT/'private/control-fixture';fixture.mkdir(exist_ok=True);install(fixture)
result=subprocess.run([str(output/'verify-controls.exe'),str(fixture/'Config/GCPadNew.ini')],capture_output=True,text=True)
print(result.stdout,flush=True)
if result.returncode:print(result.stderr);raise SystemExit(result.returncode)
(ROOT/'reports/controller-mapping-test.json').write_text(json.dumps({'production_GCPad_test':result.stdout.strip(),'physical_controller_button_presses_tested':False,'scope':'Synthetic XInput slots 0..3 and keyboard through real production expression parser/GameCube conversion; no OS input injection, window or sound'},indent=2)+'\n')

import shutil
if not (output/'Sys').exists():shutil.copytree(ROOT/'third_party/ModernGekko/vendor/dolphin/Data/Sys',output/'Sys')
real_fixture=ROOT/'private/control-runtime-fixture';real_fixture.mkdir(exist_ok=True)
(real_fixture/'Config').mkdir(exist_ok=True)
for name in ['GCPadNew.ini','Dolphin.ini']:
    shutil.copy2(ROOT/'private/playtest-user/Config'/name,real_fixture/'Config'/name)
with (ROOT/'reports/controller-runtime-bindings.log').open('w') as log:
    actual=subprocess.run([str(output/'verify-controls.exe'),'--inspect-runtime',str(ROOT),str(real_fixture)],stdout=log,stderr=subprocess.STDOUT,timeout=30)
print((ROOT/'reports/controller-runtime-bindings.log').read_text(),flush=True)
if actual.returncode:raise SystemExit(actual.returncode)
