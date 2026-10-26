# Physics and gameplay

No confirmed findings yet. Observed: Greenhorn Forest stage update in main.dol at 0x8015BF2C. Movement/jump/attack inputs respond in hidden tests; no trajectory measurements yet.

## G-0001 Player object pointer (probable)

- Global `0x801FDA00` holds the player (Wario) actor pointer (0x804AF400 in the
  Greenhorn Forest checkpoint). World position f32 vec3 at `+0x14` (x, y-up, z).
- Evidence and caveats: research/FUNCTION_DATABASE.json `globals` G-0001.
- Use: automated navigation/test assertions can read this instead of relying on
  screenshots. Do not write it in tests that claim gameplay parity.
