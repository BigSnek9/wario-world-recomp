"""Live volume automation command (2026-10-26).

Adds `command=set_volume` with `volume=0..100` to the runner's automation
control folder (--automation-dir). It sets Dolphin's MAIN_AUDIO_VOLUME and calls
AudioCommon::UpdateSoundStream so the change is heard immediately. Used by the
playtest launcher's volume slider. No effect unless the command is sent.
"""

ENUM_OLD = "  WriteMemory,\n  Stop,\n};"
ENUM_NEW = "  WriteMemory,\n  Stop,\n  SetVolume,\n};"

FIELD_OLD = "  std::uint32_t frames = 0;\n"
FIELD_NEW = "  std::uint32_t frames = 0;\n  int volume = 100;\n"

PARSE_TYPE_OLD = """  if (text == "stop")
    return CommandType::Stop;"""
PARSE_TYPE_NEW = """  if (text == "stop")
    return CommandType::Stop;
  if (text == "set_volume")
    return CommandType::SetVolume;"""

PARSE_OLD = """  case CommandType::Pause:
  case CommandType::Resume:
  case CommandType::Stop:
    break;
  }

  *command = std::move(parsed);"""
PARSE_NEW = """  case CommandType::Pause:
  case CommandType::Resume:
  case CommandType::Stop:
    break;
  case CommandType::SetVolume:
  {
    const auto volume_it = values.find("volume");
    int volume = -1;
    if (volume_it != values.end())
    {
      const std::string text = Trim(volume_it->second);
      std::from_chars(text.data(), text.data() + text.size(), volume);
    }
    if (volume < 0 || volume > 100)
    {
      if (error)
        *error = "set_volume requires volume=0..100";
      return false;
    }
    parsed.volume = volume;
    break;
  }
  }

  *command = std::move(parsed);"""

EXEC_OLD = """  case automation::CommandType::Stop:
    runtime.RequestStop();
    break;
  }
  MarkAutomationCommand(state, command.source_name);"""
EXEC_NEW = """  case automation::CommandType::Stop:
    runtime.RequestStop();
    break;
  case automation::CommandType::SetVolume:
    Config::SetBaseOrCurrent(Config::MAIN_AUDIO_VOLUME, command.volume);
    AudioCommon::UpdateSoundStream(system);
    break;
  }
  MarkAutomationCommand(state, command.source_name);"""

READY_OLD = """  case automation::CommandType::Pad:
  case automation::CommandType::ClearPad:
  case automation::CommandType::Stop:
    return false;"""
READY_NEW = """  case automation::CommandType::Pad:
  case automation::CommandType::ClearPad:
  case automation::CommandType::Stop:
    return false;
  case automation::CommandType::SetVolume:
    return true;"""


def apply(replace, runtime):
    replace(runtime / "tools/automation_protocol.hpp", ENUM_OLD, ENUM_NEW)
    replace(runtime / "tools/automation_protocol.hpp", FIELD_OLD, FIELD_NEW)
    replace(runtime / "tools/automation_protocol.cpp", PARSE_TYPE_OLD, PARSE_TYPE_NEW)
    replace(runtime / "tools/automation_protocol.cpp", PARSE_OLD, PARSE_NEW)
    replace(runtime / "src/runtime/dolphin_runtime.cpp", EXEC_OLD, EXEC_NEW)
    replace(runtime / "src/runtime/dolphin_runtime.cpp", READY_OLD, READY_NEW)
