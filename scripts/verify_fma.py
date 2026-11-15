"""Compare generated-code FMA helper with the runtime's opcode helper."""
from pathlib import Path
from build import run_check_program

root = Path(__file__).resolve().parents[1]
gx = root / "third_party/ModernGekko/vendor/dolphin/GXRuntime"
folder = root / "build/fma-test"
folder.mkdir(parents=True, exist_ok=True)
(folder / "test.c").write_text(r'''
#include "core/cpu.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static unsigned long long bits(double x) { unsigned long long u; memcpy(&u,&x,8); return u; }
int main(void) {
    const double inputs[][3] = {
        {1.0,1.0,0x1p-25}, {1.0,1.0,0.0}, {-1.0,1.0,-0x1p-25},
        {1.25,1.5,0.00000001}, {0.0,INFINITY,1.0}, {NAN,1.0,2.0},
        {INFINITY,1.0,2.0}, {0x1p-70,0x1p-70,0.0}
    };
    unsigned failures=0, cases=0;
    for (unsigned mode=0; mode<8; ++mode)
        for (unsigned flags=0; flags<4; ++flags)
            for (unsigned ni=0; ni<2; ++ni)
                for (unsigned v=0; v<sizeof(inputs)/sizeof(inputs[0]); ++v) {
                    CPUState native={0}, opcode={0};
                    native.fpscr=opcode.fpscr=(flags<<17)|(ni<<2);
                    opcode.fpr[1]=inputs[v][0]; opcode.fpr[2]=inputs[v][1]; opcode.fpr[3]=inputs[v][2];
                    double result=0;
                    ppc_fma(&native,inputs[v][0],inputs[v][1],inputs[v][2],mode&1,mode&2,mode&4,&result);
                    ppc_fmadd_op(&opcode,0,1,2,3,mode&1,mode&2,mode&4);
                    ++cases;
                    if (bits(result)!=bits(opcode.fpr[0]) || native.fpscr!=opcode.fpscr) {
                        if (failures<5) printf("mode=%u flags=%u ni=%u input=%u FPSCR=%08x/%08x bits=%llx/%llx\n",mode,flags,ni,v,native.fpscr,opcode.fpscr,bits(result),bits(opcode.fpr[0]));
                        ++failures;
                    }
                }
    printf("%u FMA helper comparisons: %u failures\n",cases,failures);
    return failures ? 1 : 0;
}
''')
sources = ["cpu.c", "cpu_exception.c", "cpu_interpreter.c", "cpu_interpreter_table.c", "cpu_interpreter_float.c", "cpu_interpreter_integer.c"]
cmake = "cmake_minimum_required(VERSION 3.16)\nproject(fma_check C)\nset(CMAKE_C_STANDARD 11)\nadd_executable(fma_check test.c\n"
cmake += "\n".join('"' + (gx / "src/core" / s).as_posix() + '"' for s in sources) + ")\n"
cmake += 'target_include_directories(fma_check PRIVATE "' + (gx / "include").as_posix() + '")\n'
# Strict floating point as in module-template/CMakeLists.txt (MSVC /fp:strict, otherwise no
# contraction); outside MSVC fma() and fmod() come from libm.
cmake += "if(MSVC)\n  target_compile_options(fma_check PRIVATE /fp:strict)\nelse()\n"
cmake += "  target_compile_options(fma_check PRIVATE -ffp-contract=off -fno-fast-math)\n"
cmake += "  target_link_libraries(fma_check PRIVATE m)\nendif()\n"
(folder / "CMakeLists.txt").write_text(cmake)
run_check_program(folder, "fma_check")
