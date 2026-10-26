"""Bounded standalone Dolphin comparison with a private user folder and synthetic pad movie."""
import argparse,hashlib,json,struct,subprocess,time
from datetime import datetime,timezone
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--exe',type=Path,required=True,help='Existing standalone Dolphin executable')
parser.add_argument('--iso',type=Path,required=True,help='User-supplied original disc image')
parser.add_argument('--seconds',type=int,default=180)
parser.add_argument('--movie-probe',action='store_true',help='Synthetic input-poll probe; omit for manual UI comparison')
args=parser.parse_args()
if not 1 <= args.seconds <= 600: parser.error('Duration must be 1..600 seconds')
if not args.exe.is_file() or not args.iso.is_file(): parser.error('Executable and disc image must exist')
folder=root/'private/dolphin-reference'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
user=folder/'user';(user/'Config').mkdir(parents=True)
(user/'Config/Dolphin.ini').write_text('[Core]\nCPUThread=False\nEnableCheats=False\nSkipIPL=True\nSlotA=1\nSlotB=255\nGFXBackend=OGL\n[Interface]\nConfirmStop=False\n[Analytics]\nEnabled=False\nPermissionAsked=True\n')
iso=args.iso.resolve()
exe=args.exe.resolve()
header=bytearray(256);header[:4]=b'DTM\x1a';header[4:10]=b'GWWE01';header[11]=1
count=18000
struct.pack_into('<QQQ',header,13,count,count,0)
header[49:49+17]=b'Local diagnostic '
with iso.open('rb') as stream: header[113:129]=hashlib.file_digest(stream,'md5').digest()
struct.pack_into('<Q',header,129,1700000000)
struct.pack_into('<Q',header,237,486000000*600)
buttons={'start':1,'a':2,'up':64,'down':128}
steps=[(900,'start')]+[(frame,button) for first in range(1020,12000,240) for frame,button in ((first,'up'),(first+90,'a'))]
inputs=bytearray()
for frame in range(count):
 flags=0x4000
 for first,button in steps:
  if first<=frame<first+12:flags|=buttons[button]
 inputs+=struct.pack('<H6B',flags,0,0,128,128,128,128)
movie=folder/'menu-probe.dtm';movie.write_bytes(header+inputs)
command=[str(exe),'--user',str(user),'--batch','--exec',str(iso)]
if args.movie_probe: command+=['--movie',str(movie)]
print('Reference output:',folder,flush=True)
start=time.monotonic();forced=False
with (folder/'process.log').open('w') as log:
 process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
 (folder/'process.json').write_text(json.dumps({'pid':process.pid,'exe':str(exe),'movie':str(movie) if args.movie_probe else None})+'\n')
 while process.poll() is None and time.monotonic()-start<args.seconds:time.sleep(0.2)
 if process.poll() is None:forced=True;process.terminate();process.wait(timeout=10)
report={'exit_code':process.returncode,'forced_stop':forced,'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'movie_probe':args.movie_probe,'limitation':'Independent emulator, not hardware. Manual UI inputs or synthetic input-poll movie; not synchronized parity evidence.'}
(folder/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(report)
