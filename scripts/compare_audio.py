"""Compare private 16-bit PCM WAV captures without playing audio."""
import argparse,array,hashlib,json,wave
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('native',type=Path);p.add_argument('reference',type=Path)
p.add_argument('--align-leading-silence',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
streams=[];details=[]
for path in [a.native,a.reference]:
    with wave.open(str(path),'rb') as w:
        channels,width,rate,frames=w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes()
        if width!=2 or w.getcomptype()!='NONE':raise ValueError('Only uncompressed signed 16-bit PCM is supported')
        data=w.readframes(frames)
        if len(data)!=frames*channels*width:raise ValueError('Truncated PCM data')
    start=0
    if a.align_leading_silence:
        stride=channels*width;zero=bytes(stride)
        while start<frames and data[start*stride:(start+1)*stride]==zero:start+=1
        if start==frames:raise ValueError("No nonzero audio to align")
        data=data[start*stride:]
    details.append({'path':str(path),'channels':channels,'sample_rate':rate,'frames':frames,'removed_leading_silent_frames':start,'compared_frames':len(data)//(channels*width),'pcm_sha256':hashlib.sha256(data).hexdigest()})
    streams.append(data)
if (details[0]['channels'],details[0]['sample_rate'])!=(details[1]['channels'],details[1]['sample_rate']):raise ValueError('WAV channel count or sample rate differs')
stride=details[0]['channels']*2;length=min(map(len,streams));differences=[];count=0
for off in range(0,length,stride):
    if streams[0][off:off+stride]!=streams[1][off:off+stride]:
        count+=1
        if len(differences)<32:differences.append(off//stride)
match=streams[0]==streams[1]
report={'streams':details,'overlap_frames':length//stride,'overlap_seconds':length/stride/details[0]['sample_rate'],'mismatched_overlap_frames':count,'first_mismatch_offsets':differences,'exact_match_after_requested_alignment':match,'limitation':'One captured stream comparison against the runtime CPU reference. Optional leading-silence alignment removes initial timing evidence; no resampling, gain change or other alignment. Trailing silence is retained. No full-game/hardware/audio-quality claim.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(not match)
