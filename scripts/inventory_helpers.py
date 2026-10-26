"""Inventory first-seen instruction-helper sites and measured helper tiers."""
import argparse,json,re
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('run',type=Path,nargs='+')
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
header=(ROOT/'third_party/ModernGekko/vendor/dolphin/Source/Core/Core/PowerPC/Gekko.h').read_text()
spr_names={}
for name,value in re.findall(r'\b(SPR_\w+)\s*=\s*(0x[0-9a-fA-F]+|\d+)\s*[,;]',header):
    spr_names.setdefault(int(value,0),[]).append(name)
xo_names={54:'dcbst',86:'dcbf',470:'dcbi',982:'icbi',339:'mfspr',467:'mtspr',83:'mfmsr',146:'mtmsr',210:'mtsr',595:'mfsr',306:'tlbie',566:'tlbsync',598:'sync',854:'eieio',371:'mftb',1014:'dcbz'}
reports=[]
for run in args.run:
    log=(run/'runner.log').read_text(encoding='utf-8',errors='replace')
    pairs=sorted(set((int(pc,16),int(raw,16)) for pc,raw in re.findall(r'\[wario-helper\] pc=([0-9a-f]+) raw=([0-9a-f]+)',log)))
    sites=[]
    for pc,raw in pairs:
        op=raw>>26;xo=(raw>>1)&1023
        name=xo_names.get(xo,'unclassified') if op==31 else ('rfi' if op==19 and xo==50 else 'sc' if op==17 else 'unclassified')
        site={'pc':f'0x{pc:08X}','raw':f'0x{raw:08X}','instruction':name,'primary':op,'xo':xo}
        if op==31 and xo in (339,467,371):
            spr=((raw>>16)&31)|(((raw>>11)&31)<<5)
            site.update(spr=spr,spr_names=spr_names.get(spr,[]))
        site['tier']='cache fast path eligible; actual mode-dependent' if name in ('dcbf','dcbst','dcbi','icbi') else 'interpreter single-step path'
        sites.append(site)
    shutdown=next((line for line in log.splitlines() if line.startswith('[staticrecomp] shutdown:')),None)
    counters={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',shutdown)} if shutdown else None
    if counters is not None and 'hook_cache' in counters:
        assert counters['hook_fb']==counters['hook_cache']+counters['hook_interp']+counters.get('hook_spr',0),counters
    reports.append({'run':str(run),'distinct_sites':len(sites),'unique_sites_by_instruction':dict(Counter(s['instruction'] for s in sites)),'counters':counters,'sites':sites})
report={'runs':reports,'limitation':'First-seen sites are not per-site invocation counts. Fast-cache eligibility is not proof of live cache mode. Counters distinguish actual tiers when available. No full-game coverage claim.'}
args.output.write_text(json.dumps(report,indent=2)+'\n')
for r in reports:print(json.dumps({k:r[k] for k in ('run','distinct_sites','unique_sites_by_instruction','counters')},indent=2))
