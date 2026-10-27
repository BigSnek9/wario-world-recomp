# Native REL integration

Status 2026-10-27: this is how the shipping module works.
build_rel_bundle.py --clean --vectors (with --clang --pgo-use for the shipped
build) builds main plus all eight RELs; the checked twin without --clean
carries the lockstep journal. The run notes below
are the 2026-10-25 bring-up history; their "not yet exercised" remarks are
superseded by later routes and the full playthrough.

Originally a separate diagnostic build, preserving the main-only baseline DLL.
Run scripts/build_rel_bundle.py to prepare and compile it. Bounded diagnostics:
smoke_boot.py --rel-bundle --lockstep --lockstep-limit 0 --seconds 90
--graphics OpenGL --capture --menu-probe --pad-hold 12 (smoke_boot.py now
rejects --windowed; tests are hidden).
Do not treat compilation as execution coverage or whole-game accuracy.
scripts/build_rel_bundle.py --clean emits the same integration without
instruction counters as the shipping port (build/module-full), selected by
smoke_boot.py --full; see PROGRESS.md for its verification status.

## Address contract

Guest registers, LR, CTR, exception instruction addresses and memory pointers
always hold actual runtime guest addresses. Synthetic translator addresses are
only labels and lookup keys. prepare_rel_sources.py rewrites explicit HA/LO
operands using original relocation records, retaining register arithmetic and
signed 16-bit semantics. All 111398 such operands are accounted for. REL24 calls
target fixed main addresses; their LR and other code-address operands become
runtime addresses. Per-function switches normalize runtime PCs into the private
label namespace. Bit masks, raw instruction words and case labels are preserved.
Five synthetic transformation checks verify these distinctions and reject
unreviewed opcodes or ambiguous immediates.

runtime/rel_support.c consults OSLink's module queue at 0x800030C8 and validates
module ID/version/section count plus the linked absolute section-table pointer.
It reads actual code/data/BSS section bases. Empty target sections contribute
zero plus addend. No runtime allocation base is guessed or retained after unlink.
Thirteen compiled mapping/hash/lifetime checks pass against the title snapshot.

The DLL exports wario_runtime_pc_module as an opt-in contract. The patched host
requires both wario_rel_symbol and wario_expected_chunk_hash for that contract.
It keeps architectural PCs unchanged, bypasses legacy synthetic-memory-address
translation, and refreshes active REL mappings before accepting cached REL hits.
Old descriptors remain on their original route. This adapter is project-specific.

## Independent executable-byte verification

The bundle contains immutable original executable bytes plus their relocation
records, generated privately from the original game files. For each code chunk,
the expected-hash callback constructs relocated bytes using the currently linked
section bases and the independent relocation model. The host compares their
FNV-1a hash with guest RAM. A missing expected hash fails closed. It never learns
an arbitrary first runtime hash as proof. Original disc/REL files are unchanged.
Generated metadata contains game code and must remain ignored/private.

The independent Python model matches all 39244 executable title bytes after
OSLink. The bundle's C implementation matches all three title chunk hashes from
that captured image. Bounds, unsupported relocation types and stale/unlinked
headers are rejected. This establishes the observed title case only; every
module's loads, BSS, transitions and runtime code writes still need coverage.

## Validation and remaining work

The bundle includes 99 main chunks plus 152 REL chunks and instruments 1014689
instruction sites, including counted-loop copies. This allows exact native/shadow
boundaries without a cycle-estimate guess. Preserve skipped helper counts,
JIT-entry counts, failed chunk hashes and all discrepancy logs. Verify no fallback
is hidden before claiming a fully static game. Host hardware/system-register
helpers remain a separate accuracy obligation.

Run 20261025T111939416970Z exits cleanly after 90 seconds, rendering the save
prompt at original speed: 6010 CPU checks, zero reports/filters/cap hits,
24 helper skips, 45 zero skips, 133 verifications, no failed SMC chunks. The
remaining 104943 JIT entries are five physical entry PCs: vectors 0x500, 0x800,
0x900, 0xC00 and Config24MB at 0x001A146C. Title REL entry PCs no longer use JIT.
Other compiled modules have not yet been exercised. Full gameplay, saves,
audio/pixel equivalence and frame/interrupt parity remain pending.
Performance improvements to repeated module-list lookups must retain unload,
reload and same-allocation/different-module correctness.

## Separate SDK-vector experiment

build_rel_bundle.py --vectors and smoke_boot.py --vectors select a separate
build/module-rel-bundle-vectors DLL. The default --rel-bundle retains the checked
REL milestone. prepare_vector_sources.py derives 14 common vector copies from
original DOL 0x8019CFE4..0x8019D07C, changing only the li-r3 exception ID at
offset 0x68, plus the 28-byte syscall stub at 0x801A2EB4 and Config24MB's physical
copy at 0x001A146C. All generic copies match the paused snapshot exactly.
No guest-memory patch is performed. Physical lookup/hash verification preserves
physical architectural PCs rather than silently converting them to virtual PCs.

20-second normal run 20261025T113516203507Z exits cleanly with zero JIT entries,
78 verifications, no SMC failures and 736 frame callbacks. Its 15-second capture
is black; title rendering is not established by that run. With shadow checking,
run 20261025T113215221518Z stalls before any frames after entering the physical
FP-unavailable vector, requiring bounded child termination. No accuracy claim
for the new SDK path until that stall is explained. A targeted 0x810 shadow trace
is being prepared; --lockstep-trace accepts one entry PC for private step logs.
