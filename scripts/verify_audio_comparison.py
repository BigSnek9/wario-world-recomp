"""Negative controls for exact PCM comparison and permitted onset alignment."""
from pathlib import Path
import array,json,subprocess,sys,wave
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'build/verify-audio-comparison';folder.mkdir(parents=True,exist_ok=True)
def wav(name,leading=0,flip=False,trailing=2,rate=32028):
    samples=[0,0]*leading+[100,-100,200,-200,32767,-32768,12,13]+[0,0]*trailing
    if flip:samples[leading*2+3]^=1
    path=folder/(name+'.wav')
    with wave.open(str(path),'wb') as w:
        w.setparams((2,2,rate,0,'NONE','not compressed'));w.writeframes(array.array('h',samples).tobytes())
    return path
a=wav('native',leading=3);b=wav('offset',leading=9)
c=wav('bitflip',leading=9,flip=True);d=wav('tail',leading=9,trailing=3);e=wav('rate',leading=9,rate=48042)
cases=[(a,a,False,0),(a,b,False,1),(a,b,True,0),(a,c,True,1),(a,d,True,1),(a,e,True,1)]
results=[]
for i,(first,second,align,wanted) in enumerate(cases):
    command=[sys.executable,str(ROOT/'scripts/compare_audio.py'),str(first),str(second),'--output',str(folder/(str(i)+'.json'))]
    if align:command.append('--align-leading-silence')
    result=subprocess.run(command,capture_output=True)
    assert result.returncode==wanted,(i,result.returncode,result.stderr.decode())
    results.append(dict(case=i,exit_code=result.returncode,expected=wanted))
report={'cases':len(results),'failed':0,'controls':'Exact match, onset offset with/without alignment, single PCM bit difference, meaningful trailing silence, sample-rate mismatch'}
(ROOT/'reports/audio-comparison-regression.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
