#include "rel_support.h"
#include <string.h>

static u32 read32(const CPUState* ctx, u32 address) {
    if (address < 0x80000000u) return 0;
    u32 offset = address - 0x80000000u;
    if (!ctx->ram || ctx->ram_size < 4 || offset > ctx->ram_size - 4) return 0;
    const u8* p = ctx->ram + offset;
    return ((u32)p[0] << 24) | ((u32)p[1] << 16) | ((u32)p[2] << 8) | p[3];
}

static const WarioRelModule* module_info(u32 id) {
    for (u32 i=0; i<wario_rel_module_count; ++i)
        if (wario_rel_modules[i].id == id) return &wario_rel_modules[i];
    return NULL;
}

/* OSLink's queue is authoritative. Never accept an unlinked file image left
   in RAM, and never cache an address across module unload/reload. */
static u32 linked_header(CPUState* ctx, const WarioRelModule* module) {
    if (!module) return 0;
    u32 header = read32(ctx, 0x800030C8u);
    for (u32 count=0; header && count<32; ++count) {
        if ((header & 3u) || header < 0x80000000u ||
            ctx->ram_size < 0x40 || header - 0x80000000u > ctx->ram_size - 0x40) return 0;
        if (read32(ctx, header) == module->id) {
            if (read32(ctx, header + 12) != module->section_count ||
                read32(ctx, header + 28) != module->version ||
                read32(ctx, header + 16) != header + module->table_offset) return 0;
            return header;
        }
        header = read32(ctx, header + 4);
    }
    return 0;
}

static u32 section_start(CPUState* ctx, const WarioRelModule* module, u32 header, u32 index) {
    if (!header || index >= module->section_count) return 0;
    u32 entry = header + module->table_offset + index*8;
    u32 raw = read32(ctx, entry), size = read32(ctx, entry + 4);
    const WarioRelSection* section = &module->sections[index];
    if (size != section->size || (raw & 1u) != section->executable) return 0;
    if (size == 0) return 0;
    u32 start = raw & ~3u;
    if (start < 0x80000000u || start - 0x80000000u > ctx->ram_size ||
        size > ctx->ram_size - (start - 0x80000000u)) return 0;
    return start;
}

u32 wario_rel_symbol(CPUState* ctx, u32 module_id, u32 section, u32 addend) {
    if (module_id == 0) return addend;
    const WarioRelModule* module = module_info(module_id);
    if (!module || section >= module->section_count) return 0;
    /* Empty sections have zero base, including the nonzero addend case. */
    if (module->sections[section].size == 0) return addend;
    u32 base = section_start(ctx, module, linked_header(ctx, module), section);
    return base ? base + addend : 0;
}

u32 wario_rel_to_runtime(CPUState* ctx, u32 module_id, u32 linked) {
    const WarioRelModule* module = module_info(module_id);
    if (!module) return 0;
    u32 header = linked_header(ctx, module);
    if (!header) return 0;
    for (u32 i=0; i<module->section_count; ++i) {
        const WarioRelSection* section = &module->sections[i];
        if (section->executable && linked >= section->linked_start &&
            linked - section->linked_start <= section->size) {
            u32 base = section_start(ctx, module, header, i);
            return base ? base + (linked - section->linked_start) : 0;
        }
    }
    return 0;
}

u32 wario_rel_to_linked(CPUState* ctx, u32 module_id, u32 runtime) {
    const WarioRelModule* module = module_info(module_id);
    if (!module) return 0;
    u32 header = linked_header(ctx, module);
    if (!header) return 0;
    for (u32 i=0; i<module->section_count; ++i) {
        const WarioRelSection* section = &module->sections[i];
        if (!section->executable || !section->size) continue;
        u32 base = section_start(ctx, module, header, i);
        if (base && runtime >= base && runtime - base < section->size)
            return section->linked_start + (runtime - base);
    }
    return 0;
}

u64 wario_expected_chunk_hash(CPUState* ctx, u32 begin, u32 end) {
    u8 expected[16384];
    if (end <= begin || end - begin > sizeof expected) return 0;
    for (u32 m=0; m<wario_rel_module_count; ++m) {
        const WarioRelModule* module = &wario_rel_modules[m];
        for (u32 i=0; i<module->section_count; ++i) {
            const WarioRelSection* section = &module->sections[i];
            if (!section->original_code || begin < section->linked_start ||
                end - section->linked_start > section->size) continue;
            u32 first = begin - section->linked_start, length = end - begin;
            u32 runtime = section_start(ctx, module, linked_header(ctx, module), i);
            if (!runtime) return 0;
            memcpy(expected, section->original_code + first, length);
            for (u32 r=0; r<section->fixup_count; ++r) {
                const WarioRelFixup* fix = &section->fixups[r];
                u32 width = fix->kind == 4 || fix->kind == 6 ? 2 : 4;
                if (fix->offset < first || fix->offset - first >= length) continue;
                u32 offset = fix->offset - first;
                if (width > length - offset) return 0;
                u32 symbol = wario_rel_symbol(ctx, fix->target_module, fix->target_section, fix->addend);
                u32 value;
                if (fix->kind == 4) value = symbol;
                else if (fix->kind == 6) value = (symbol + 0x8000u) >> 16;
                else if (fix->kind == 1) value = symbol;
                else if (fix->kind == 10) {
                    u32 delta = symbol - (runtime + fix->offset);
                    s32 signed_delta = (s32)delta;
                    if ((delta & 3u) || signed_delta < -0x2000000 || signed_delta > 0x1fffffc) return 0;
                    u8* p = expected + offset;
                    u32 original = ((u32)p[0]<<24)|((u32)p[1]<<16)|((u32)p[2]<<8)|p[3];
                    value = (original & ~0x03fffffcu) | (delta & 0x03fffffcu);
                } else return 0;
                for (u32 b=0; b<width; ++b)
                    expected[offset+b] = (u8)(value >> (8*(width-1-b)));
            }
            u64 hash = 0xcbf29ce484222325ull;
            for (u32 b=0; b<length; ++b) hash = (hash ^ expected[b]) * 0x100000001b3ull;
            return hash;
        }
    }
    return 0;
}
