"""Read-only accuracy review: settings provenance, input and artifact identities.

This records configuration evidence, not full effective-after-boot settings or
hardware parity. Reports contain private local paths and remain ignored.
"""
import configparser, hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    if not path.is_file(): return None
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()

def ini(path):
    result=configparser.ConfigParser(interpolation=None,strict=False)
    if path.exists(): result.read(path,encoding='utf-8-sig')
    return result

def review():
    vendor=ROOT/'third_party/ModernGekko'
    settings=vendor/'vendor/dolphin/Source/Core/Core/Config'
    user=ROOT/'private/playtest-user'
    defaults=[]
    for source,filename in [('GraphicsSettings.cpp','GFX.ini'),('MainSettings.cpp','Dolphin.ini')]:
        text=(settings/source).read_text()
        pattern=r'const Info<[^>]+> (\w+)\s*\{\{System::\w+,\s*"([^"]+)",\s*"([^"]+)"\},\s*(.*?)\};'
        config=ini(user/'Config'/filename)
        for symbol,section,key,value in re.findall(pattern,text,re.S):
            defaults.append(dict(symbol=symbol,file=filename,section=section,key=key,
                pinned_source_default=' '.join(value.split()),
                user_override=config.get(section,key,fallback=None),
                source=f'third_party/ModernGekko/vendor/dolphin/Source/Core/Core/Config/{source}'))
    identities={}
    expected=json.loads((ROOT/'config/project.json').read_text())
    inputs={'sys/main.dol':expected['dol_sha256'],**expected['rel_sha256']}
    for name,wanted in inputs.items():
        actual=sha(ROOT/'original/GWWE01'/name)
        identities[name]=dict(expected_sha256=wanted,actual_sha256=actual,match=actual==wanted)
    binaries={name:sha(ROOT/name) for name in [
        'build/moderngekko/Release/moderngekko-run.exe',
        'build/module-full-vectors/Release/gGWWE01_recomp.dll',
        'build/module-rel-bundle-vectors/Release/gGWWE01_recomp.dll']}
    configurations={}
    for relative in ['config.ini','Config/GFX.ini','Config/Dolphin.ini']:
        path=user/relative;c=ini(path)
        configurations[relative]={'sha256':sha(path),'settings':{s:dict(c[s]) for s in c.sections()}}
    game_ini=vendor/'vendor/dolphin/Data/Sys/GameSettings/GWWE01.ini'
    return dict(schema=1,time_utc=datetime.now(timezone.utc).isoformat(),
        original_inputs=identities,binaries=binaries,user_config=configurations,
        settings_provenance=defaults,
        per_game_ini={'sha256':sha(game_ini),'content':game_ini.read_text()},
        installed_game_ini={'sha256':sha(ROOT/'build/moderngekko/Release/Sys/GameSettings/GWWE01.ini'),'matches_pinned_source':sha(ROOT/'build/moderngekko/Release/Sys/GameSettings/GWWE01.ini')==sha(game_ini)},
        launcher_sha256=sha(ROOT/'Play-WarioWorld.cmd'),
        runtime_forced_settings={'CPUCore':'StaticRecomp (native) or JIT for --reference',
            'backend':'OpenGL from manual launcher',
            'EFB_scale':'frontend config.ini overrides GFX.ini',
            'shader_mode':'AsynchronousUberShaders','wait_for_shaders':True,'shader_cache':True,
            'background_input':False},
        limitations=[
            'Source defaults plus user overrides are provenance, not effective-after-boot telemetry.',
            'Source patch replay does not prove a binary was built from those exact sources.',
            'Identical original game bytes do not prove CPU, rendering, audio or scheduling parity.',
            'Reference JIT shares renderer, DSP, hardware emulation and configuration; common bugs can pass comparisons.',
            'CPU checks skip hardware-helper blocks and unvisited contexts; counts are not whole-game coverage.',
            'No deterministic SI-poll replay or original-hardware framebuffer/audio comparison exists.',
            'GameINI contains widescreen cheat definitions; their presence does not mean they are enabled.'])

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=ROOT/'reports/accuracy-review.json')
    args=parser.parse_args();report=review();args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'report':str(args.out),'original_input_hashes_match':all(x['match'] for x in report['original_inputs'].values()),'settings_recorded':len(report['settings_provenance']),'hardware_accuracy':'not established'},indent=2))
