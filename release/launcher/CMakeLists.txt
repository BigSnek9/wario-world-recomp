# WarioWorldRecomp.exe - the native release starter (no Python needed at run time).
#   cmake -S release/launcher -B build/release-launcher -G Ninja -DCMAKE_BUILD_TYPE=Release
#   cmake --build build/release-launcher
# Needs the MSVC x64 environment (cl or clang-cl) and Python at build time (it draws the icon).
# The disc pins (ISO / DOL / REL SHA-256) are read from config/project.json and compiled in.
cmake_minimum_required(VERSION 3.20)
project(WarioWorldRecompLauncher LANGUAGES CXX RC)

set(WARIO_RELEASE_VERSION "1.0" CACHE STRING "Release version shown in the exe")
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")  # static CRT: the exe needs no DLLs
find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(REPO "${CMAKE_CURRENT_SOURCE_DIR}/../..")
file(READ "${REPO}/config/project.json" PROJECT_JSON)
string(JSON ISO_SHA GET "${PROJECT_JSON}" iso_sha256)
string(JSON DOL_SHA GET "${PROJECT_JSON}" dol_sha256)
string(JSON REVISION GET "${PROJECT_JSON}" revision)
string(JSON REL_COUNT LENGTH "${PROJECT_JSON}" rel_sha256)
set(REL_LINES "")
math(EXPR REL_LAST "${REL_COUNT} - 1")
foreach(i RANGE ${REL_LAST})
  string(JSON REL_PATH MEMBER "${PROJECT_JSON}" rel_sha256 ${i})
  string(JSON REL_SHA GET "${PROJECT_JSON}" rel_sha256 "${REL_PATH}")
  string(REPLACE "/" "\\\\" REL_PATH "${REL_PATH}")
  string(APPEND REL_LINES "    {L\"${REL_PATH}\", L\"${REL_SHA}\"},\n")
endforeach()
set(PINS "${CMAKE_CURRENT_BINARY_DIR}/project_pins.h")
file(WRITE "${PINS}.new" "// Generated from config/project.json by CMake. Do not edit.
#pragma once
#include <cstdint>
namespace pins {
constexpr int kRevision = ${REVISION};
constexpr std::uint64_t kIsoSize = 1459978240ull;  // a full GameCube disc
constexpr const wchar_t* kIsoSha256 = L\"${ISO_SHA}\";
constexpr const wchar_t* kDolSha256 = L\"${DOL_SHA}\";
struct Rel { const wchar_t* path; const wchar_t* sha256; };
constexpr Rel kRels[] = {
${REL_LINES}};
}  // namespace pins
")
file(COPY_FILE "${PINS}.new" "${PINS}" ONLY_IF_DIFFERENT)
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS "${REPO}/config/project.json")

set(EXE_ICON "${CMAKE_CURRENT_BINARY_DIR}/WarioWorldRecomp.ico")
add_custom_command(
  OUTPUT "${EXE_ICON}"
  COMMAND "${Python3_EXECUTABLE}" "${CMAKE_CURRENT_SOURCE_DIR}/make_exe_icon.py" --out "${EXE_ICON}"
  DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/make_exe_icon.py" "${REPO}/installer/coin_icon.py"
  COMMENT "Drawing the launcher icon")
set(EXE_ICON_RC "${EXE_ICON}")
set(GCPAD_RC "${CMAKE_CURRENT_SOURCE_DIR}/defaults/GCPadNew.ini")
string(REPLACE "/" "\\\\" EXE_ICON_RC "${EXE_ICON_RC}")
string(REPLACE "/" "\\\\" GCPAD_RC "${GCPAD_RC}")
string(REPLACE "." "," RC_VERSION "${WARIO_RELEASE_VERSION},0,0")
configure_file(launcher.rc.in "${CMAKE_CURRENT_BINARY_DIR}/launcher.rc" @ONLY)
set_source_files_properties("${CMAKE_CURRENT_BINARY_DIR}/launcher.rc" PROPERTIES
  OBJECT_DEPENDS "${EXE_ICON};${CMAKE_CURRENT_SOURCE_DIR}/defaults/GCPadNew.ini")

add_executable(WarioWorldRecomp WIN32 main.cpp coin_icon.h resource.h "${CMAKE_CURRENT_BINARY_DIR}/launcher.rc"
               "${EXE_ICON}")
target_include_directories(WarioWorldRecomp PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}" "${CMAKE_CURRENT_BINARY_DIR}")
target_compile_definitions(WarioWorldRecomp PRIVATE UNICODE _UNICODE
  $<$<COMPILE_LANGUAGE:CXX>:WARIO_RELEASE_VERSION="${WARIO_RELEASE_VERSION}">)
target_compile_options(WarioWorldRecomp PRIVATE $<$<COMPILE_LANGUAGE:CXX>:/W4 /permissive- /utf-8 /fp:precise>)
target_link_libraries(WarioWorldRecomp PRIVATE bcrypt comctl32 shell32 ole32 user32)
target_link_options(WarioWorldRecomp PRIVATE "/MANIFEST:EMBED"
  "/MANIFESTINPUT:${CMAKE_CURRENT_SOURCE_DIR}/app.manifest" /MANIFESTUAC:NO)
