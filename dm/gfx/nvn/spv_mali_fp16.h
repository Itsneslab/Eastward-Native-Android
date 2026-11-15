// Adds RelaxedPrecision decorations to 32-bit float arithmetic and local Function temporaries in Fragment shaders on Arm Mali
// (Bifrost / Valhall), enabling native dual-issue FP16 ALU while preserving full FP32 precision for texture coordinates,
// derivatives, bitcasts, conversions, BuiltIns, and Uniform/Input loads. Self-contained (no libc).
#pragma once
#include <stddef.h>
#include <stdint.h>

enum {
    SPV_F16_F32 = 1u << 0,
    SPV_F16_PTR_FN = 1u << 1,
    SPV_F16_FN_VAR = 1u << 2,
    SPV_F16_STRICT = 1u << 3,
    SPV_F16_RELAXED = 1u << 4,
    SPV_F16_DEC = 1u << 5,
};

static int spv_f16_head(uint32_t op) {
    return (op >= 2 && op <= 8) || op == 10 || op == 11 || op == 14 || op == 15 || op == 16 || op == 17 ||
           op == 330 || op == 331 || (op >= 71 && op <= 75) || op == 332 || op == 5632 || op == 5633;
}

static int spv_f16_img_sample(uint32_t op) { return (op >= 87 && op <= 95); }

static int spv_f16_arith_op(uint32_t op) {
    return op == 12 || op == 79 || op == 80 || op == 81 || op == 82 ||
           op == 127 || op == 129 || op == 131 || op == 133 || op == 136 ||
           (op >= 142 && op <= 148) || op == 169 || op == 245;
}

static int spv_mali_fp16_wanted(const uint32_t *w, size_t n) {
    if (n < 5 || w[0] != 0x07230203) return 0;
    for (size_t i = 5; i < n; ) {
        uint32_t len = w[i] >> 16, op = w[i] & 0xffff;
        if (!len || i + len > n) return 0;
        if (op == 15 && len >= 2 && w[i + 1] == 4) return 1;   // OpEntryPoint Fragment
        if (!spv_f16_head(op)) return 0;
        i += len;
    }
    return 0;
}

// Rewrites w (n words) into o (cap words), adding OpDecorate <id> RelaxedPrecision for safe FP16 fragment operations.
// flags scratch buffer must hold at least bound (= w[3]) bytes. Returns words written, or 0 if unchanged / invalid / too small.
static size_t spv_mali_fp16(const uint32_t *w, size_t n, uint8_t *flags, uint32_t *o, size_t cap, size_t *need, int *marked) {
    *need = 0; *marked = 0;
    if (n < 5 || w[0] != 0x07230203 || !spv_mali_fp16_wanted(w, n)) return 0;
    uint32_t bound = w[3];
    if (!bound) return 0;
    for (uint32_t k = 0; k < bound; k++) flags[k] = 0;

    size_t at = 0, i = 5;
    int head = 1;
    while (i < n) {
        uint32_t len = w[i] >> 16, op = w[i] & 0xffff;
        if (!len || i + len > n) return 0;
        if (head && !spv_f16_head(op)) { head = 0; at = i; }
        if (op == 71 && len >= 3 && w[i + 1] < bound) {
            uint32_t dec = w[i + 2];
            if (dec == 0) flags[w[i + 1]] |= SPV_F16_RELAXED;
            else if (dec == 11 || dec == 42) flags[w[i + 1]] |= SPV_F16_STRICT;   // BuiltIn or NoContraction
        } else if (op == 22 && len >= 3 && w[i + 1] < bound && w[i + 2] == 32) {
            flags[w[i + 1]] |= SPV_F16_F32;
        } else if (op == 23 && len >= 4 && w[i + 1] < bound && w[i + 2] < bound && (flags[w[i + 2]] & SPV_F16_F32)) {
            flags[w[i + 1]] |= SPV_F16_F32;
        } else if (op == 32 && len >= 4 && w[i + 1] < bound && w[i + 2] == 7 && w[i + 3] < bound && (flags[w[i + 3]] & SPV_F16_F32)) {
            flags[w[i + 1]] |= SPV_F16_PTR_FN;
        } else if (op == 59 && len >= 4 && w[i + 2] < bound && w[i + 3] == 7 && w[i + 1] < bound && (flags[w[i + 1]] & SPV_F16_PTR_FN)) {
            flags[w[i + 2]] |= SPV_F16_FN_VAR;
        } else if (spv_f16_img_sample(op) && len >= 5) {
            // Keep texture coordinates, dref, lod, gradients, bias, and offsets in full FP32
            uint32_t mask_idx = (op == 89 || op == 90 || op == 93 || op == 94) ? 6u : 5u;
            if (w[i + 4] < bound) flags[w[i + 4]] |= SPV_F16_STRICT;
            for (uint32_t k = 5; k < len; k++) {
                if (k == mask_idx) continue;
                if (w[i + k] < bound) flags[w[i + k]] |= SPV_F16_STRICT;
            }
        } else if (op == 99 && len >= 4) {   // OpImageWrite
            for (uint32_t k = 2; k < len; k++) {
                if (k == 4) continue;   // ImageOperands literal mask
                if (w[i + k] < bound) flags[w[i + k]] |= SPV_F16_STRICT;
            }
        } else if (op == 124 || op == 109 || op == 110 || op == 116 || op == 65 || op == 66 || (op >= 207 && op <= 215)) {
            for (uint32_t k = 3; k < len; k++) {
                if (w[i + k] < bound) flags[w[i + k]] |= SPV_F16_STRICT;
            }
        }
        i += len;
    }
    if (head) return 0;

    // Backward taint propagation to preserve FP32 across coordinate/bitcast dependencies
    for (int pass = 0; pass < 32; pass++) {
        int changed = 0;
        for (i = at; i < n; ) {
            uint32_t len = w[i] >> 16, op = w[i] & 0xffff;
            if (op == 62 && len >= 3) {   // OpStore ptr obj
                if (w[i + 1] < bound && (flags[w[i + 1]] & SPV_F16_STRICT) && w[i + 2] < bound && !(flags[w[i + 2]] & SPV_F16_STRICT)) {
                    flags[w[i + 2]] |= SPV_F16_STRICT; changed = 1;
                }
            } else if (op == 61 && len >= 4) {   // OpLoad res_t res ptr
                if (w[i + 2] < bound && (flags[w[i + 2]] & SPV_F16_STRICT) && w[i + 3] < bound && !(flags[w[i + 3]] & SPV_F16_STRICT)) {
                    flags[w[i + 3]] |= SPV_F16_STRICT; changed = 1;
                }
            } else if (spv_f16_arith_op(op) && len >= 3 && w[i + 2] < bound && (flags[w[i + 2]] & SPV_F16_STRICT)) {
                uint32_t first = (op == 12) ? 5u : 3u;
                uint32_t end = (op == 81) ? 4u : (op == 79 || op == 82) ? 5u : len;
                uint32_t step = (op == 245) ? 2u : 1u;
                if (end > len) end = len;
                for (uint32_t k = first; k < end; k += step) {
                    if (w[i + k] < bound && !(flags[w[i + k]] & SPV_F16_STRICT)) {
                        flags[w[i + k]] |= SPV_F16_STRICT; changed = 1;
                    }
                }
            }
            i += len;
        }
        if (!changed) break;
    }

    int count = 0;
    for (i = at; i < n; ) {
        uint32_t len = w[i] >> 16, op = w[i] & 0xffff;
        if (op == 59 && len >= 4 && w[i + 2] < bound && (flags[w[i + 2]] & SPV_F16_FN_VAR)) {
            uint32_t r = w[i + 2];
            if (!(flags[r] & (SPV_F16_STRICT | SPV_F16_RELAXED | SPV_F16_DEC))) { flags[r] |= SPV_F16_DEC; count++; }
        } else if (op == 61 && len >= 4 && w[i + 1] < bound && (flags[w[i + 1]] & SPV_F16_F32) &&
                   w[i + 3] < bound && (flags[w[i + 3]] & SPV_F16_FN_VAR) && w[i + 2] < bound) {
            uint32_t r = w[i + 2];
            if (!(flags[r] & (SPV_F16_STRICT | SPV_F16_RELAXED | SPV_F16_DEC))) { flags[r] |= SPV_F16_DEC; count++; }
        } else if ((spv_f16_arith_op(op) || spv_f16_img_sample(op)) && len >= 3 && w[i + 1] < bound && (flags[w[i + 1]] & SPV_F16_F32) && w[i + 2] < bound) {
            uint32_t r = w[i + 2];
            if (!(flags[r] & (SPV_F16_STRICT | SPV_F16_RELAXED | SPV_F16_DEC))) { flags[r] |= SPV_F16_DEC; count++; }
        }
        i += len;
    }
    if (!count) return 0;

    *need = n + 3 * (size_t)count; *marked = count;
    if (!o || cap < *need) return 0;
    for (i = 0; i < at; i++) o[i] = w[i];
    size_t q = at;
    for (i = at; i < n; ) {
        uint32_t len = w[i] >> 16, op = w[i] & 0xffff;
        if (((op == 59 || op == 61) || spv_f16_arith_op(op) || spv_f16_img_sample(op)) && len >= 3 && w[i + 2] < bound) {
            uint32_t r = w[i + 2];
            if (flags[r] & SPV_F16_DEC) {
                flags[r] &= (uint8_t)~SPV_F16_DEC;
                o[q++] = (3u << 16) | 71u; o[q++] = r; o[q++] = 0u;   // OpDecorate r RelaxedPrecision
            }
        }
        i += len;
    }
    for (i = at; i < n; i++) o[q++] = w[i];
    return q == *need ? q : 0;
}
