"""Independently compare loaded main DOL text sections to original file bytes."""
from pathlib import Path
from build import check_game
import argparse,hashlib,json,struct
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('run',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
check_game()
dol=(ROOT/'original/GWWE01/sys/main.dol').read_bytes()
m=(a.run/'control/mem1-low.bin').read_bytes()+(a.run/'control/mem1-high.bin').read_bytes()
w=lambda offset:struct.unpack_from('>I',dol,offset)[0]
checks=[]
for index in range(7):
    offset,address,size=w(index*4),w(0x48+index*4),w(0x90+index*4)
    if not size:continue
    begin=address-0x80000000
    if not 0<=begin<begin+size<=len(m) or not 0<=offset<offset+size<=len(dol):raise ValueError('DOL section outside file or MEM1')
    expected,actual=dol[offset:offset+size],m[begin:begin+size]
    differences=[i for i,(x,y) in enumerate(zip(expected,actual)) if x!=y]
    checks.append({'section':index,'address':f'0x{address:08X}','bytes':size,'mismatched_bytes':len(differences),'first_offsets':differences[:32],'expected_sha256':hashlib.sha256(expected).hexdigest(),'actual_sha256':hashlib.sha256(actual).hexdigest()})
report={'run':str(a.run),'sections':checks,'bytes_compared':sum(c['bytes'] for c in checks),'limitation':'Loaded text-byte comparison only; mutable data, CPU semantics, GPU/audio parity and unvisited execution remain outside this audit.'}
a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));raise SystemExit(any(c['mismatched_bytes'] for c in checks))
