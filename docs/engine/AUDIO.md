# Audio

DSP runs in HLE in the runtime. One 16 s idle-stage DSP capture matched the
original-code JIT path after alignment (../HANDOFF.md).

The game uses Factor 5 MusyX (GameCube library linked at about 0x8016D100..0x8018B000)
plus a small game-side sound manager. Names below are MusyX API names inferred from
the code shape and arguments (no symbols); the dtk labels are authoritative.

## AU-001 Sound system layout (confirmed)

- `fn_8005908C` (from main) builds the sound manager: sndSetHooks (`fn_80189A98`),
  sndInit `fn_801868EC(voices 0x40, music 0, sfx 0x38, studios 1, ...)`,
  sndVolume `fn_801754C8(127, 0, 0xFF)`, then allocates the manager object
  (`fn_800591D0`, 0x200 bytes, global `[0x801FDB08]`).
- Disc data: `SFX/wario_gc.proj/.sdir/.pool/.samp` (one SFX group, 1013 SFX ids,
  766 DSP-ADPCM samples, no MusyX songs) pushed by `fn_80045B28` -> sndPushGroup
  `fn_801802E0`; `BGM/<NAME>_0.dsp` / `_1.dsp` (57 left/right pairs, table
  `lbl_801BBF30`) are streamed. There are no voice streams on the disc.
- Game wrappers on the manager (`r3 = [0x801FDB08]`): `fn_800594B0(fid, vol, pan)`
  -> sndFXStartEx `fn_801753CC` (65 call sites), `fn_800594E0(vid)` -> sndFXKeyOff
  `fn_8017538C`, `fn_8005944C` -> sndFXCheck, `fn_80059518(vid, value)` ->
  sndFXCtrl(vid, 7 = volume, value) `fn_8017532C`, `fn_80059558` -> sndSilence.
  3D actor sounds use emitters: `fn_8003F6F8/798/83C` -> sndAddEmitterEx
  `fn_80185958`; the per-actor sound-channel helper `fn_800CC658/6D4` stores the fid
  per channel. Both paths reach fxStart `fn_801741F8`.
- BGM: three slots (`fn_80059894` selects, manager +0x10.. current BGM,
  +0x28.. paused flag). Commands go to a stream thread through `fn_80058150`:
  1 play (`fn_80059634`), 2 stop/fade (`fn_80059730`), 3 pause (`fn_800597C0`),
  4 resume (`fn_800597EC`), 6 set volume with fade (`fn_80059818`, 13 callers).
  Stream objects (vtable `lbl_801BBE40`) are allocated by `fn_800568FC`
  (sndStreamAllocEx `fn_801768BC`); MusyX stream table `0x801E3350` (8 x 0x64).
- The game has no volume options. The only sound option is the output mode
  (`fn_800593B4` -> sndOutputMode `fn_80175528`, mono/stereo/surround from
  OSGetSoundMode).

## AU-002 Synth volume groups (confirmed)

synthVolume `fn_80174708(vol, time, group, mode, seqId)` drives 32 volume groups at
`0x801E233C + g*0x30` (f32 +0 current, +4 target, +8 start, +0xC/+0x10 ramp,
+0x14 extra factor, +0x2D type). The voice volume (`fn_8017334C`, 0x801734E0..0x80173548)
is `group[g].+0x14 * group[g].+0 * group[21 music | 22 fx master].+0 * studio`.

- Groups 21 (0x15) and 22 (0x16) are MusyX's sndMasterVolume music/fx masters
  (`0x801E272C`, `0x801E275C`, 1.0). sndMasterVolume is not linked: nothing writes them.
- sndPushGroup's SFX registration `fn_80178C88` forces every SFX entry's group byte
  (+9) to 31, so every SFX voice (including 3D emitters and the pause music) uses group
  31 (`0x801E290C`, 1.0, type 1). Groups 23..30 are type 0 at 1.0 and unused; 0..20
  type 4 (unused, 0.0). Memory snapshot (stage, 64 voices): all voices group 31.
- Groups only change through synthVolume; the game calls it once (sndVolume at init),
  so groups 21/22/29/30/31 stay 1.0 for the whole game.
- Aux (reverb) sends: aux A `f28` (0x801738D0) and aux B `f3` (0x80173950) add
  controller/velocity terms that do not include the group volume, so lowering a group
  alone leaves a reverb tail (measured: about 6 % RMS residual with SFX at 0).

## AU-003 Music is the BGM stream volume (confirmed)

Stream volume does not use synth groups: sndStreamMixParameterEx `fn_80176F64`
stores vol/pan/span/auxA/auxB (+0x55..0x59) and calls hwSetVolume `fn_80189330`
directly. The stream object's mix method `fn_80056FE8` (vtable +0x28) passes its
volume byte (r4) and is called on every buffer refill (`fn_80056AAC`, the stream
callback, from the object's fade at +0x14), at start (`fn_80056C40`) and stop
(`fn_80056404`), so a scale at the 0x80057008 call applies within one refill.
Music aux sends are 0 (snapshot). Every stream belongs to the BGM manager
(`fn_800568FC`'s only caller is `fn_800584D0`).

## AU-004 Volume curve (measured)

MusyX's DSP output follows the square of the volume value: 50 % of the group float
or of the stream byte gave 0.24x amplitude (hidden dumps, idle stage). A menu
percent therefore maps to factor `sqrt(pct/100)` (measured 0.47-0.48x amplitude at
50 %; the stream byte is quantized to 1/127).

## AU-005 Voice clips (Wario's voice) are ordinary SFX (confirmed); not separable yet

Voices are MusyX SFX in the same pool as every other effect: no stream, no own volume
group (AU-002 forces group 31), no flag in the SFX table (fields: id, macro, voices,
priority, volume 127, pan 64, key 60, group). They can only be separated by SFX id.
The mixer supports a per-id voice table (`wario_audio_voice_fid`, routed to group 30),
but the table is empty: the voice ids are not identified. Evidence collected:

- Trace (`WARIO_AUDIO_TRACE`) of the first stage with jump/attack input: actor sounds
  go through `fn_800CC6D4` channels; channel 0 = footsteps (fid 2/6, noise, 0.13-0.25 s),
  channel 1 = fids 400/443 (samples 484/485, 0.2 s) and layer SFX 1005..1010
  (layer 2, six short samples keyed per surface), channel 3 = 452, 4 = 422.
- A pitch/voicing scan of all 766 decoded samples gives about 110 "voice-like"
  candidates, but many are musical (exact note pitches, jingles); it cannot tell
  speech from instruments without listening.

Filling the table needs a listening pass (the user, not automated tests): trace a
session, play the candidate samples, list the voice SFX ids. Until then the menu
should not show a Voice slider (the variable is inert while the table is empty).

## AU-006 Pause-menu music (confirmed)

The pause book's music is SFX 0x3BF (macro 444, a macro-sequenced multi-voice piece
using samples 183/184/186/187), not a BGM. Sequence (`r4` = pause object):
- `fn_8006CB04` (open): sets the pause bit (`fn_8003195C`, 0x8 of `0x801FD930`),
  SFX 0x73 (book open, vol 0x70) and 0x223 (vol 0x60), listener volume
  `[0x801FDA00]+0xA0 = 0` (3D emitters silent while paused; fn_8003FCE4 passes it to
  sndUpdateListener `fn_80185B74`), pauses BGM slots 0..2 (`fn_800598B0`).
- `fn_8006CC58` (book opened): SFX 0x1FE and `0x3BF` (vol 0x60, pan 0x20); the vid is
  stored at pause object +0x70.
- `fn_8006EB74` (pause update): toggles that vid's volume with sndFXCtrl(7, 0x7F/0)
  on edges of `[0x801FD938]` (flag via `fn_80031908`).
- `fn_8006DB4C` (close start): SFX 0x222, sndFXKeyOff(+0x70), +0x70 = -1.
- `fn_8006DC4C` (close finished, counter 0): SFX 0x74 at count 0x12, clears the
  pause bit, listener volume 0x7F, resumes BGM slots (`fn_80059920`).
Muting it by routing 0x3BF to its own group keeps the keyoff/volume edges valid and
does not touch the BGM pause/resume, so the stage music resumes as before.

## AU-007 Runtime mixer (prototype, `scripts/build_rel_bundle.py` AUDIO_SITES)

Exported module variables (GetProcAddress on the game DLL, like
`wario_fullscreen_half_width`):

| Variable | Range | Default | Effect |
|---|---|---|---|
| `wario_audio_music` | 0..100 (% amplitude) | 100 | BGM streams; also the pause music |
| `wario_audio_sfx` | 0..100 | 100 | every SFX (group 31) incl. reverb sends |
| `wario_audio_voice` | 0..100 | 100 | SFX ids in `wario_audio_voice_fid` (empty, AU-005) |
| `wario_audio_mute_pause_music` | 0/1 | 0 | SFX 0x3BF silent |
| `wario_audio_voice_fid` | u32[32] bitmap of SFX ids | empty | voice table |

Hooks: 0x80057008 (stream volume byte x factor), 0x80174254 (fxStart group byte:
while any setting is non-default, 0x3BF -> group 29, voice ids -> group 30),
fn_80173EAC entry (synth tick: groups 29/30/31 +0/+4 = mute ? 0 : music, voice, sfx
factors), 0x801738D0 / 0x80173950 (aux terms scaled by the voice's group factor
for groups 29..31 when it is not 1.0). Values are clamped; the runtime may write them
at any time (every frame or on change). Dolphin's MAIN_AUDIO_VOLUME still scales
the final mix on top.

Properties:
- Inert at defaults: all factors are exactly 1.0, nothing is routed and no guest
  memory is written. Measured: idle-stage DSP dump identical to the stock module
  (474248+ frames, bit-exact).
- Live: groups are re-applied every synth tick and voices recompute their volume
  from the group (0x80173548 change test), the stream byte on every refill.
  Measured: SFX set to 0 at 8 s -> identical to the original before, identical to the
  SFX=0 run after.
- Savestates: the applied state lives in guest memory (group floats, voice group
  bytes); after a load the tick re-applies the current settings. A voice started while
  routing was off stays in group 31 (SFX slider) until it ends; the pause music only
  follows the mute checkbox if a setting was non-default when the book opened.
- Separation measured (idle stage, 20 s): music=0 and sfx=0 dumps sum exactly to
  the original minus the all-zero dump; all-zero dump is a constant DC offset
  (DSP output, also present in the original) with no AC signal.
- Pause probe: with the mute checkbox the paused interval drops from about 2000 RMS
  to the DC level while book SFX before/after remain; with music=0 the pause music
  is silent too.

Diagnostics: `WARIO_AUDIO_TEST="music,sfx,voice,mute[,delay_ms]"` sets the variables
after a delay; `WARIO_AUDIO_TRACE=<file>` logs every fxStart (frame, fid, group,
return addresses with saved words). Test module: `--build-dir module-audio-test`.
