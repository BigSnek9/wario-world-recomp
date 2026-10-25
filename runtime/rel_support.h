/* Project-specific REL address and immutable-code verification support. */
#ifndef WARIO_REL_SUPPORT_H
#define WARIO_REL_SUPPORT_H
#include "core/cpu.h"
#if defined(_WIN32)
#define WARIO_REL_EXPORT __declspec(dllexport)
#else
#define WARIO_REL_EXPORT __attribute__((visibility("default")))
#endif
typedef struct {
    u32 offset, kind, target_module, target_section, addend;
} WarioRelFixup;
typedef struct {
    u32 linked_start, size, executable;
    const u8* original_code;
    const WarioRelFixup* fixups;
    u32 fixup_count;
} WarioRelSection;
typedef struct {
    u32 id, version, section_count, table_offset, file_size;
    const WarioRelSection* sections;
} WarioRelModule;
extern const WarioRelModule wario_rel_modules[];
extern const u32 wario_rel_module_count;
WARIO_REL_EXPORT u32 wario_rel_symbol(CPUState* ctx, u32 module_id, u32 section, u32 addend);
u32 wario_rel_to_runtime(CPUState* ctx, u32 module_id, u32 linked);
u32 wario_rel_to_linked(CPUState* ctx, u32 module_id, u32 runtime);
WARIO_REL_EXPORT u64 wario_expected_chunk_hash(CPUState* ctx, u32 linked_start, u32 linked_end);
#endif
