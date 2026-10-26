# Hidden test probes

User requires invisible and inaudible testing. smoke_boot.py uses hidden
rendering, passes --mute, and rejects --windowed. Screenshots are private files.

Probe JSON is an increasing list of [guest_frame_callback, control] pairs.
Optionally use [frame, control, hold_frames] or [frame, control, hold_frames, value].
Holds default to --pad-hold (12 is useful for menu input), at most 3600 per step.
Stick values main_x/main_y are -1..1; buttons are 0/1. Commands are serialized,
so a long hold can delay a later step; leave a neutral gap between planned holds.
A frame callback is the runtime's counter, not established simulation cadence.
These probes are behavioral exploration, not a deterministic parity replay.

Corrected save creation requires main_y=1 to choose Yes; dpad_up did not select
it. repeated_analog_yes.json creates the original guest save. start_adventure.json
also presses Start/B and reaches the hub, then repeatedly opens/closes pause.
hub_movement.json tries movement after the same initial menu sequence; it is
exploratory and does not assert a destination. Saves, movies, captures and memory
snapshots must remain private. Each run has an isolated user directory and unique
random run suffix; never merge concurrent runs or reuse the user's normal saves.

Private resume support: --load-state <file> --seed-user <prior run/user>.
The seed folder is copied and must be under this project's private/. Optional
--save-state-at <seconds> writes control/checkpoint.savestate. Frame thresholds
become relative to settled post-load status; do not treat them as deterministic
input-poll timestamps. A savestate contains game-derived data and stays private.

--dump-audio writes private DSP/DTK WAVs while output remains No Audio Output.
Do not play or render these files during silent tests. Compare with
scripts/compare_audio.py; leading-silence alignment is explicit and does not
establish onset timing. Six negative controls verify bit/length/rate differences.
