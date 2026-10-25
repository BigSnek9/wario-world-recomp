"""Compile the actual patched loop-boundary detector and test synthetic PPC CFGs."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
source_path = root / "third_party/ModernGekko/vendor/dolphin/Source/Core/Core/PowerPC/StaticRecomp/StaticRecompLockstep_Check.cpp"
source = source_path.read_text()
begin = source.index("bool LsEndCanRepeat(")
first_brace = source.index("{", begin)
depth = 1
end = first_brace + 1
while depth:
    depth += (source[end] == "{") - (source[end] == "}")
    end += 1
function = source[begin:end]
folder = root / "build/lockstep-boundary-test"
folder.mkdir(parents=True, exist_ok=True)
test = r'''
#include <cstdint>
#include <cstdio>
using u8 = std::uint8_t; using u32 = std::uint32_t;
using s16 = std::int16_t; using s32 = std::int32_t;
namespace Common {
u32 swap32(const u8* p) { return (u32(p[0]) << 24) | (u32(p[1]) << 16) | (u32(p[2]) << 8) | p[3]; }
}
ACTUAL_FUNCTION
int main() {
    constexpr u32 b = 0x80000000u;
    u8 ram[256] = {};
    auto put = [&](u32 off, u32 word) {
        ram[off] = u8(word >> 24); ram[off+1] = u8(word >> 16);
        ram[off+2] = u8(word >> 8); ram[off+3] = u8(word);
    };
    auto check = [&](bool cond, const char* name) {
        if (!cond) { std::fprintf(stderr, "%s failed\n", name); return false; }
        return true;
    };
    bool ok = true;
    put(0x2c, 0x4081ffecu); // Conditional branch from 0x2c back to 0x18.
    ok &= check(LsEndCanRepeat(ram, sizeof ram, b+4, b+0x20), "call continuation inside loop");
    ok &= check(LsEndCanRepeat(ram, sizeof ram, b+0x18, b+0x18), "loop header");
    ok &= check(!LsEndCanRepeat(ram, sizeof ram, b+4, b+0x10), "unrelated later loop");
    put(0x2c, 0x4bffffecu); // Unconditional backward branch.
    ok &= check(LsEndCanRepeat(ram, sizeof ram, b+4, b+0x20), "unconditional interior");
    put(0x2c, 0x4bffffedu); // Same encoding, but link bit denotes a call.
    ok &= check(!LsEndCanRepeat(ram, sizeof ram, b+4, b+0x20), "backward call is not loop edge");
    put(0x2c, 0x4081ffecu);
    ok &= check(!LsEndCanRepeat(ram, sizeof ram, b+0x1c, b+0x20), "loop before dispatch floor");
    ok &= check(!LsEndCanRepeat(ram, sizeof ram, b+4, b+0x1000), "out of RAM");
    ok &= check(!LsEndCanRepeat(ram, sizeof ram, 4, 0x20), "outside cached RAM");
    if (ok) std::puts("8 actual-detector regression cases passed");
    return ok ? 0 : 1;
}
'''.replace("ACTUAL_FUNCTION", function)
(folder / "test.cpp").write_text(test)
(folder / "CMakeLists.txt").write_text('cmake_minimum_required(VERSION 3.16)\nproject(loop_boundary CXX)\nadd_executable(loop_boundary test.cpp)\nset_property(TARGET loop_boundary PROPERTY CXX_STANDARD 17)\n')
subprocess.run(["cmake", "-S", str(folder), "-B", str(folder / "build"), "-G", "Visual Studio 17 2022", "-A", "x64"], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["cmake", "--build", str(folder / "build"), "--config", "Release"], check=True, stdout=subprocess.DEVNULL)
subprocess.run([str(folder / "build/Release/loop_boundary.exe")], check=True)
