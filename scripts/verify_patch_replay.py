"""Replay pinned source patches in isolated private fixtures, without game data."""
from pathlib import Path
import hashlib,json,re,subprocess
from uuid import uuid4
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'patches/manifest.json').read_text())
folder=ROOT/'private/patch-replay'/uuid4().hex
folder.mkdir(parents=True)
results=[]
for name,spec in manifest.items():
    repo=ROOT/spec['path'];patch=ROOT/'patches'/(name+'.patch')
    if hashlib.sha256(patch.read_bytes()).hexdigest()!=spec['patch_sha256']:raise RuntimeError('Patch digest differs: '+name)
    revision=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if revision!=spec['commit']:raise RuntimeError('Wrong checkout revision: '+name)
    fixture=folder/name;fixture.mkdir()
    subprocess.run(['git','init','--quiet',str(fixture)],check=True)
    paths=re.findall(r'^diff --git a/(.*?) b/.*$',patch.read_text(),re.M)
    for relative in paths:
        target=fixture/relative
        if not target.resolve().is_relative_to(fixture.resolve()):raise RuntimeError('Unsafe patch path')
        target.parent.mkdir(parents=True,exist_ok=True)
        original=subprocess.check_output(['git','-C',str(repo),'show','HEAD:'+relative])
        target.write_bytes(original)
    for extra in (['--check'],[]):
        subprocess.run(['git','-C',str(fixture),'apply',*extra,str(patch.resolve())],check=True,capture_output=True)
    for relative in paths:
        if (fixture/relative).read_text(encoding='utf-8')!=(repo/relative).read_text(encoding='utf-8'):
            raise RuntimeError('Replayed source differs: '+name+'/'+relative)
    results.append({'repository':name,'commit':revision,'files':len(paths),'replay_matches_current_source':True})
report={'results':results,'limitation':'Source reproduction only; does not establish game accuracy or public distribution clearance.'}
(ROOT/'reports/patch-replay.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
