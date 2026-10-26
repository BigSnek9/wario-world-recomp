"""Relink changed diagnostic units against an existing pinned build."""
import argparse
import ctypes
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('project',type=Path)
args=parser.parse_args()
project=args.project.resolve()
old_build=project/'build/moderngekko'
output=ROOT/'build/silent-runtime'
output.mkdir(parents=True,exist_ok=True)
units=[
 ('check','vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp/StaticRecompLockstep_Check.cpp','vendor/dolphin/Source/Core/Core/core.dir/Release/core.tlog/CL.command.1.tlog',' /volatile:iso '),
 ('runtime','src/runtime/dolphin_runtime.cpp','moderngekko.dir/Release/moderngekko.tlog/CL.command.1.tlog',' /utf-8 '),
 ('platform','vendor/dolphin/Source/Core/DolphinNoGUI/PlatformWin32.cpp','moderngekko.dir/Release/moderngekko.tlog/CL.command.1.tlog',' /utf-8 '),
]
for name,relative,tlog,final_option in units:
    unit=project/'third_party/ModernGekko'/relative
    commands=(old_build/tlog).read_text(encoding='utf-16').splitlines()
    command=next(commands[i+1] for i,line in enumerate(commands) if line.startswith('^') and line.endswith(unit.name.upper()))
    if final_option not in command: raise SystemExit('Missing final compiler option for '+name)
    command=command.rsplit(final_option,1)[0]+final_option
    command,n=re.subn(r'/Fo"[^\"]*"',lambda _: '/Fo"'+str(output/(name+'.obj'))+'"',command,flags=re.I)
    if n!=1: raise SystemExit('Unexpected object-output option')
    command,n=re.subn(r'/Fd"[^\"]*"',lambda _: '/Fd"'+str(output/(name+'.pdb'))+'"',command,flags=re.I)
    if n!=1: raise SystemExit('Unexpected compiler-PDB option')
    (output/(name+'.rsp')).write_text(command+'"'+str(unit)+'"\n',encoding='utf-8-sig')
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
updated=[str(output/(name+'.obj')) for name,_,_,_ in units]
for token in tokens:
    upper=token.upper()
    if upper in ('/INCLUDE:ENABLECOMPATPATCHES','-INCLUDE:ENABLECOMPATPATCHES'): token='/INCLUDE:enableCompatPatches'
    elif upper.startswith('/OUT:'): token='/OUT:'+str(output/'moderngekko-run.exe')
    elif upper.startswith('/PDB:'): token='/PDB:'+str(output/'moderngekko-run.pdb')
    elif upper.startswith('/IMPLIB:'): token='/IMPLIB:'+str(output/'moderngekko-run.lib')
    elif not token.startswith(('/','-')):
        candidate=old_build/token
        if candidate.is_file(): token=str(candidate)
    updated.append(token)
updated+=['/DEBUG:FULL','/OPT:REF','/OPT:ICF','/MAP:'+str(output/'moderngekko-run.map')]
(output/'link.rsp').write_text(subprocess.list2cmdline(updated)+'\n',encoding='utf-8-sig')
vs=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat')
batch=['@echo off',f'call "{vs}" -no_logo -arch=x64 -host_arch=x64','if errorlevel 1 exit /b 1']
for name,_,_,_ in units:
    batch += [f'cl.exe @"{output / (name+".rsp")}" > "{output / (name+".log")}" 2>&1','if errorlevel 1 exit /b 1']
batch += [f'link.exe @"{output / "link.rsp"}" > "{output / "link.log"}" 2>&1','exit /b %errorlevel%']
(output/'build.cmd').write_text('\n'.join(batch)+'\n')
print(output/'build.cmd',flush=True)
subprocess.run(['cmd.exe','/d','/c',str(output/'build.cmd')],cwd=old_build,check=True)
import shutil
if not (output/'Sys').exists(): shutil.copytree(project/'third_party/ModernGekko/vendor/dolphin/Data/Sys',output/'Sys')
print('Built hidden-rendering diagnostic runtime',flush=True)
