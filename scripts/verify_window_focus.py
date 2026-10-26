"""Compile the production Win32 focus predicate and virtual dispatch; no UI."""
import json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'build/verify-window-focus';folder.mkdir(parents=True,exist_ok=True)
platform=ROOT/'third_party/ModernGekko/vendor/dolphin/Source/Core/DolphinNoGUI'
base=re.search(r'  virtual bool IsWindowFocused\(\) const \{[^}]+\}',(platform/'Platform.h').read_text()).group()
method=re.search(r'  bool IsWindowFocused\(\) const override\s*\{[^}]+\}',(platform/'PlatformWin32.cpp').read_text()).group()
header='#include <cstddef>\nusing HWND=void*; HWND foreground=nullptr; bool minimized=false; HWND GetForegroundWindow(){return foreground;} bool IsIconic(HWND){return minimized;}\n'
tests="""
int main(){PlatformWin32 window;Platform* host=&window;int failed=0;
auto check=[&](bool expected){failed+=(host->IsWindowFocused()!=expected);};
window.m_hwnd=reinterpret_cast<void*>(1);foreground=window.m_hwnd;check(true);
window.m_hidden=true;check(false);window.m_hidden=false;
window.m_hwnd=nullptr;check(false);window.m_hwnd=reinterpret_cast<void*>(1);
foreground=reinterpret_cast<void*>(2);check(false);
foreground=window.m_hwnd;minimized=true;check(false);
minimized=false;check(true);return failed;}
"""
for name in ['before','after']:
    b=base if name=='after' else base.replace('virtual ','')
    m=method if name=='after' else method.replace(' override','')
    (folder/(name+'.cpp')).write_text(header+'struct Platform{bool m_window_focus=true;'+b+'};\nstruct PlatformWin32:Platform{bool m_hidden=false;HWND m_hwnd=nullptr;'+m+'};\n'+tests)
vs=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat')
lines=['@echo off',f'call "{vs}" -no_logo -arch=x64 -host_arch=x64','if errorlevel 1 exit /b 1']
for name in ['before','after']:
    lines += [f'cl.exe /nologo /EHsc /std:c++20 "{folder/(name+".cpp")}" /Fo"{folder/(name+".obj")}" /Fe"{folder/(name+".exe")}"','if errorlevel 1 exit /b 1']
(folder/'build.cmd').write_text('\n'.join(lines)+'\n')
subprocess.run(['cmd.exe','/d','/c',str(folder/'build.cmd')],cwd=folder,check=True,stdout=subprocess.DEVNULL)
result={name:subprocess.run([str(folder/(name+'.exe'))]).returncode for name in ['before','after']}
assert result=={'before':4,'after':0},result
report={'cases':6,'failed_before':4,'failed_after':0,'production_predicate_and_base_virtual_dispatch':True,'scope':'Owned foreground, hidden, uninitialized window, other foreground, minimized, regained focus. Stub Win32 answers; no real window or OS input; human Alt-Tab integration remains untested.'}
(ROOT/'reports/window-focus-regression.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
