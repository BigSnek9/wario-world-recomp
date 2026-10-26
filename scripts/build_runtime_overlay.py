"""Relink a workspace-only verifier fix against an existing read-only build."""
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
output=ROOT/'build/runtime-overlay'
output.mkdir(parents=True,exist_ok=True)
relative='vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp/StaticRecompLockstep_Check.cpp'
source=(project/'third_party/ModernGekko'/relative).read_text()
old='  ppc.msr.Hex = saved_msr;\n  power_pc.MSRUpdated();'
new='  StaticRecompCore::SetPPCStateFromGuestState(m_core.m_guest, ppc);\n  ppc.msr.Hex = m_core.m_guest.msr;\n  power_pc.MSRUpdated();'
if source.count(old)!=1 and new not in source: raise SystemExit('Unexpected restore preimage')
source=source.replace(old,new).replace('  const u64 saved_msr = ppc.msr.Hex;\n','')
unit=output/'StaticRecompLockstep_Check.cpp'
unit.write_text(source)
commands=(old_build/'vendor/dolphin/Source/Core/Core/core.dir/Release/core.tlog/CL.command.1.tlog').read_text(encoding='utf-16').splitlines()
command=next(commands[i+1] for i,line in enumerate(commands) if line.startswith('^') and line.endswith('STATICRECOMPLOCKSTEP_CHECK.CPP'))
command=command.rsplit(' /volatile:iso ',1)[0]+' /volatile:iso '
command,n=re.subn(r'/Fo"[^"]*"',lambda _: '/Fo"'+str(output/'check.obj')+'"',command,flags=re.I)
if n!=1: raise SystemExit('Unexpected object-output option')
command,n=re.subn(r'/Fd"[^"]*"',lambda _: '/Fd"'+str(output/'compile.pdb')+'"',command,flags=re.I)
if n!=1: raise SystemExit('Unexpected compiler-PDB option')
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
updated=[str(output/'check.obj')]
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
batch=['@echo off',f'call "{vs}" -no_logo -arch=x64 -host_arch=x64','if errorlevel 1 exit /b 1',f'cl.exe @"{output / "compile.rsp"}" > "{output / "compile.log"}" 2>&1','if errorlevel 1 exit /b 1',f'link.exe @"{output / "link.rsp"}" > "{output / "link.log"}" 2>&1','exit /b %errorlevel%']
(output/'build.cmd').write_text('\n'.join(batch)+'\n')
print(output/'build.cmd')
