"""Compile the actual native REL support against private captured-code evidence."""
from pathlib import Path
import subprocess
from relocation_model import parse
from emit_rel_metadata import emit

root = Path(__file__).resolve().parents[1]
folder = root / "build/rel-support-test"
folder.mkdir(parents=True, exist_ok=True)
model = parse((root / "original/GWWE01/files/dll/WWUSTT.rel").read_bytes())
model["linked_base"] = 0x808c0000
(folder / "metadata.c").write_text(emit([model]))
test = r'''
#include "rel_support.h"
#include <stdio.h>
#include <stdlib.h>
static u64 fnv(const u8* p, u32 length) { u64 h=0xcbf29ce484222325ull; while(length--) h=(h^*p++)*0x100000001b3ull; return h; }
static void put(CPUState* ctx, u32 address, u32 value) {
    u8* p=ctx->ram+address-0x80000000u;
    p[0]=(u8)(value>>24);p[1]=(u8)(value>>16);p[2]=(u8)(value>>8);p[3]=(u8)value;
}
int main(int argc, char** argv) {
    CPUState ctx={0}; ctx.ram_size=0x1800000; ctx.ram=(u8*)malloc(ctx.ram_size);
    if(argc!=3 || !ctx.ram) return 2;
    FILE* low=fopen(argv[1],"rb"), *high=fopen(argv[2],"rb");
    if(!low || !high) return 2;
    size_t n=fread(ctx.ram,1,0x1000000,low), m=fread(ctx.ram+0x1000000,1,0x800000,high);
    fclose(low); fclose(high); if(n!=0x1000000 || m!=0x800000) return 2;
    unsigned checks=0;
#define CHECK(c) do { ++checks; if(!(c)) { printf("FAILED line %d\n",__LINE__); return 1; } } while(0)
    CHECK(wario_rel_to_runtime(&ctx,8,0x808c00f8)==0x804af678);
    CHECK(wario_rel_to_linked(&ctx,8,0x804af678)==0x808c00f8);
    CHECK(wario_rel_symbol(&ctx,0,0,0x80123456)==0x80123456);
    CHECK(wario_rel_symbol(&ctx,8,2,0x1b78)==0x1b78);
    CHECK(wario_rel_symbol(&ctx,8,3,4)==0x804af67c);
    for(u32 off=0;off<39244;off+=16384) {
        u32 len=39244-off; if(len>16384) len=16384;
        CHECK(wario_expected_chunk_hash(&ctx,0x808c00f8+off,0x808c00f8+off+len)==fnv(ctx.ram+0x4af678+off,len));
    }
    CHECK(wario_expected_chunk_hash(&ctx,0x808c00f8,0x808d00f8)==0);
    /* Stale bytes remain in RAM after unlink; the live queue must win. */
    put(&ctx,0x800030c8,0);
    CHECK(wario_rel_to_runtime(&ctx,8,0x808c00f8)==0);
    CHECK(wario_expected_chunk_hash(&ctx,0x808c00f8,0x808c00fc)==0);
    put(&ctx,0x800030c8,0x804af580);
    put(&ctx,0x804af590,0x48); /* Unlinked file-offset table cannot execute. */
    CHECK(wario_rel_to_runtime(&ctx,8,0x808c00f8)==0);
    put(&ctx,0x804af590,0x804af5c8);
    put(&ctx,0x804af580,7); /* Reuse the same allocation for a different module. */
    CHECK(wario_rel_to_runtime(&ctx,8,0x808c00f8)==0);
    printf("%u native REL mapping/hash/lifetime checks passed\n",checks);
    free(ctx.ram);return 0;
}
'''
(folder / "test.c").write_text(test)
cmake = "cmake_minimum_required(VERSION 3.16)\nproject(rel_support_check C)\nset(CMAKE_C_STANDARD 11)\n"
cmake += 'add_executable(rel_support_check test.c metadata.c "' + (root / "runtime/rel_support.c").as_posix() + '")\n'
cmake += 'target_include_directories(rel_support_check PRIVATE "' + (root / "runtime").as_posix() + '" "' + (root / "third_party/ModernGekko/vendor/dolphin/GXRuntime/include").as_posix() + '")\n'
(folder / "CMakeLists.txt").write_text(cmake)
subprocess.run(["cmake", "-S", str(folder), "-B", str(folder / "build"), "-G", "Visual Studio 17 2022", "-A", "x64"], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["cmake", "--build", str(folder / "build"), "--config", "Release"], check=True)
run = root / "private/runs/20261025T103819667331Z/control"
subprocess.run([str(folder / "build/Release/rel_support_check.exe"), str(run / "mem1-low.bin"), str(run / "mem1-high.bin")], check=True)
