"""Compile actual reference compare helpers and check all prior FPCC transitions."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
base = root / "third_party/ModernGekko/vendor/dolphin/Source/Core/Core/PowerPC"
source = (base / "Interpreter/Interpreter_FloatCompare.cpp").read_text()
gekko = (base / "Gekko.h").read_text()
macros = "\n".join(re.findall(r"^#define (?:FPRF_SHIFT|FPCC_MASK) .*$", gekko, re.M))
functions = []
for name in ("Ordered", "Unordered"):
    begin = source.index("void Interpreter::Helper_FloatCompare" + name)
    end = source.index("\n}", begin) + 2
    functions.append(source[begin:end])
test = r'''
#include <cstdint>
#include <cmath>
#include <cstdio>
#include <limits>
#include <initializer_list>
using u32 = std::uint32_t;
MACROS
enum class FPCC : u32 { FU=1, FE=2, FG=4, FL=8 };
constexpr u32 FPSCR_VXSNAN=1, FPSCR_VXVC=2;
namespace Common { bool IsSNAN(double) { return false; } }
namespace PowerPC {
struct PowerPCState {
    struct { u32 FPRF=0, VE=0; } fpscr;
    struct { u32 field=0; void SetField(u32, u32 v) { field=v; } } cr;
};
}
struct UGeckoInstruction { u32 CRFD=0; };
void SetFPException(PowerPC::PowerPCState&, u32) {}
struct Interpreter {
    static void Helper_FloatCompareOrdered(PowerPC::PowerPCState&, UGeckoInstruction, double, double);
    static void Helper_FloatCompareUnordered(PowerPC::PowerPCState&, UGeckoInstruction, double, double);
};
FUNCTIONS
int main() {
    struct Case { double a, b; u32 expected; } cases[] = {
        {-2, 1, 8}, {2, 1, 4}, {1, 1, 2},
        {std::numeric_limits<double>::quiet_NaN(), 1, 1}
    };
    unsigned failures=0;
    for (auto function : {Interpreter::Helper_FloatCompareOrdered, Interpreter::Helper_FloatCompareUnordered})
        for (u32 old=0; old<32; ++old)
            for (const auto& c : cases) {
                PowerPC::PowerPCState state; state.fpscr.FPRF=old;
                function(state, {}, c.a, c.b);
                const u32 expected = (old >= 16 ? 16u : 0u) + c.expected;
                if (state.fpscr.FPRF != expected || state.cr.field != c.expected)
                    ++failures;
            }
    std::printf("256 production-helper FPCC transition cases: %u failures\n", failures);
    return failures ? 1 : 0;
}
'''.replace("MACROS", macros).replace("FUNCTIONS", "\n".join(functions))
folder = root / "build/float-compare-test"
folder.mkdir(parents=True, exist_ok=True)
(folder / "test.cpp").write_text(test)
(folder / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.16)\nproject(float_compare CXX)\nadd_executable(float_compare test.cpp)\nset_property(TARGET float_compare PROPERTY CXX_STANDARD 17)\n")
subprocess.run(["cmake", "-S", str(folder), "-B", str(folder / "build"), "-G", "Visual Studio 17 2022", "-A", "x64"], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["cmake", "--build", str(folder / "build"), "--config", "Release"], check=True)
subprocess.run([str(folder / "build/Release/float_compare.exe")], check=True)
