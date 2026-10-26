"""Opt-in texture dumping for the runtime (2026-10-26).

Dolphin's UICommon::Init forces GFX DumpTextures off on every start (dumping is
meant to be a session toggle in the Qt UI, which the runner does not have), so
the GFX.ini setting alone never takes effect. With MODERNGEKKO_DUMP_TEXTURES=1
in the environment the runtime re-enables it right after init. Default
behaviour is unchanged. Used by the playtest launcher's texture dump mode
(scripts/texture_tools.py).
"""

INIT_OLD = """  Config::SetBase(Config::MAIN_FULLSCREEN, impl->config.fullscreen);
"""

INIT_NEW = """  Config::SetBase(Config::MAIN_FULLSCREEN, impl->config.fullscreen);
  // UICommon::Init forces texture dumping off each start; allow an explicit opt-in.
  if (const char *dump = std::getenv("MODERNGEKKO_DUMP_TEXTURES"); dump && *dump == '1')
    Config::SetBaseOrCurrent(Config::GFX_DUMP_TEXTURES, true);
"""


def apply(replace, runtime):
    replace(runtime / "src/runtime/dolphin_runtime.cpp", INIT_OLD, INIT_NEW)
