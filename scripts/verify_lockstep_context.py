"""Compile production verifier predicates against code-reuse/window regressions."""
from pathlib import Path
import json,subprocess
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'third_party/ModernGekko/vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp/StaticRecompLockstep.cpp').read_text()
def method(signature):
    start=source.index(signature);brace=source.index('{',start);depth=1;end=brace+1
    while depth:
        depth += (source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]
functions='\n'.join(method('bool StaticRecompLockstepVerifier::'+name) for name in ['ShouldCheck(u32 address) const','LockstepWindowOpen() const'])
before=functions.replace('  const auto checked = m_ls_checked.find(address);\n','').replace('         checked == m_ls_checked.end() || checked->second != m_core.m_rel_mapping_generation;','         m_ls_checked.find(address) == m_ls_checked.end();')
header='#include <cstdint>\n#include <unordered_map>\nusing u32=std::uint32_t;using u64=std::uint64_t;\nstruct Core {u64 m_native_dispatches=10,m_rel_mapping_generation=1;};\nstruct StaticRecompLockstepVerifier {\nCore m_core;bool m_lockstep=true,m_ls_nodedup=false;u32 m_ls_repeat_pc=0;\nu64 m_ls_start=0,m_ls_limit=0;std::unordered_map<u32,u64> m_ls_checked;\nbool ShouldCheck(u32) const;bool LockstepWindowOpen() const;\n};\n'
tests='\nint main(){StaticRecompLockstepVerifier v;int failed=0;\nauto expect=[&](bool actual,bool wanted){failed+=(actual!=wanted);};\nexpect(v.ShouldCheck(0x804af678),true);\nv.m_ls_checked[0x804af678]=1;expect(v.ShouldCheck(0x804af678),false);\nv.m_core.m_rel_mapping_generation=2;expect(v.ShouldCheck(0x804af678),true);\nv.m_ls_checked[0x804af678]=2;expect(v.ShouldCheck(0x804af678),false);\nv.m_ls_nodedup=true;expect(v.ShouldCheck(0x804af678),true);v.m_ls_nodedup=false;\nv.m_ls_repeat_pc=0x804af678;expect(v.ShouldCheck(0x804af678),true);\nv.m_ls_start=11;expect(v.ShouldCheck(0x804af678),false);v.m_ls_start=0;\nv.m_ls_limit=10;expect(v.ShouldCheck(0x804af678),false);v.m_ls_limit=0;\nv.m_lockstep=false;expect(v.ShouldCheck(0x804af678),false);\nreturn failed;\n}\n'
folder=ROOT/'build/verify-lockstep-context';folder.mkdir(parents=True,exist_ok=True)
for name,body in [('before',before),('after',functions)]:
    (folder/(name+'.cpp')).write_text(header+body+tests)
vs=Path('C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat')
lines=['@echo off',f'call "{vs}" -no_logo -arch=x64 -host_arch=x64','if errorlevel 1 exit /b 1']
for name in ['before','after']:
    lines += [f'cl.exe /nologo /EHsc /std:c++20 "{folder/(name+".cpp")}" /Fo"{folder/(name+".obj")}" /Fe"{folder/(name+".exe")}"','if errorlevel 1 exit /b 1']
(folder/'build.cmd').write_text('\n'.join(lines)+'\n')
subprocess.run(['cmd.exe','/d','/c',str(folder/'build.cmd')],cwd=folder,check=True,stdout=subprocess.DEVNULL)
result={name:subprocess.run([str(folder/(name+'.exe'))]).returncode for name in ['before','after']}
assert result=={'before':1,'after':0},result
report={'cases':9,'failed_before':result['before'],'failed_after':result['after'],'production_predicates_compiled':True,'scope':'Address reuse across code-map generations and existing window/override controls'}
(ROOT/'reports/lockstep-context-regression.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
