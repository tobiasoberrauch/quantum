// census: replay circuit on bit-sliced shots, at each 3q gate test value-level redundancies.
// Usage: census base.kmb shots.bin part nparts out.tsv
#include "kmb.h"
#include <assert.h>
#ifndef WMAX
#define WMAX 16
#endif
typedef uint64_t u64;
static int W; static u64 *Q, *B; static uint32_t nq, nb;
#define QW(i) (Q + (size_t)(i) * W)
#define BW(i) (B + (size_t)(i) * W)
static u64 xs[2] = {0x9E3779B97F4A7C15ull, 0xD1B54A32D192ED03ull};
static inline u64 rnd(void) { u64 a = xs[0], b = xs[1]; u64 r = a + b; b ^= a; xs[0] = ((a << 24) | (a >> 40)) ^ b ^ (b << 16); xs[1] = (b << 37) | (b >> 27); return r; }
// linear basis
static u64 *basis; static int *piv; static int nbasis;
static inline void basis_reset(void) { nbasis = 0; }
static inline int reduce(u64 *v) {
    for (int i = 0; i < nbasis; i++) { if ((v[piv[i] >> 6] >> (piv[i] & 63)) & 1) { const u64 *b = basis + (size_t)i * W; for (int k = 0; k < W; k++) v[k] ^= b[k]; } }
    for (int k = 0; k < W; k++) if (v[k]) return 0;
    return 1;
}
static inline void insert(const u64 *src) {
    u64 *v = basis + (size_t)nbasis * W; memcpy(v, src, W * 8);
    if (reduce(v)) return;
    for (int k = 0; k < W; k++) if (v[k]) { piv[nbasis] = k * 64 + __builtin_ctzll(v[k]); break; }
    nbasis++;
}
static inline int is_zero(const u64 *v) { for (int k = 0; k < W; k++) if (v[k]) return 0; return 1; }
static inline int is_equal(const u64 *a, const u64 *b) { return memcmp(a, b, W * 8) == 0; }
static inline void build_basis(int ex1, int ex2, int ex3) {
    basis_reset();
    static u64 ones[64]; for (int k = 0; k < W; k++) ones[k] = ~0ull; insert(ones);
    for (uint32_t i = 0; i < nq; i++) { if ((int)i == ex1 || (int)i == ex2 || (int)i == ex3) continue; const u64 *v = QW(i); if (is_zero(v)) continue; insert(v); }
}
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]);
    FILE *f = fopen(argv[2], "rb"); u64 hdr[4]; fread(hdr, 8, 4, f); nq = hdr[0]; nb = hdr[1]; W = hdr[2]; assert(W <= 64);
    Q = calloc((size_t)nq * W, 8); B = calloc((size_t)nb * W, 8); fread(Q, 8, (size_t)nq * W, f); fread(B, 8, (size_t)nb * W, f); fclose(f);
    int part = atoi(argv[3]), nparts = atoi(argv[4]);
    FILE *out = fopen(argv[5], "w");
    basis = malloc((size_t)(nq + 2) * W * 8); piv = malloc((nq + 2) * sizeof(int));
    const uint32_t *q3a = k.q3a, *q3b = k.q3b, *q3c = k.q3c, *q2a = k.q2a, *q2b = k.q2b, *q1 = k.q1, *b1 = k.b1, *bc = k.bc;
    u64 cond_stack[64][64]; int csp = 0; u64 base[64]; for (int i = 0; i < W; i++) base[i] = ~0ull;
    u64 cond[64], ab[64], tx[64], tv[64]; long gate_idx = -1;
    for (uint64_t op = 0; op < k.nops; op++) {
        uint8_t ty = k.types[op];
        int hascond = 0;
        memcpy(cond, base, W * 8);
        if (ty & 0x80) { if (ty != OP_PUSH) { hascond = 1; const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) cond[i] &= c[i]; } }
        (void)hascond;
        switch (ty) {
        case OP_POP: csp--; if (csp > 0) memcpy(base, cond_stack[csp - 1], W * 8); else for (int i = 0; i < W; i++) base[i] = ~0ull; break;
        case OP_PUSH: { const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) base[i] &= c[i]; memcpy(cond_stack[csp++], base, W * 8); break; }
        case OP_TAG: case OP_NEG: case OP_NEGIF: break;
        case OP_Z: case OP_ZIF: q1++; break;
        case OP_X: case OP_XIF: { u64 *t = QW(*q1++); for (int i = 0; i < W; i++) t[i] ^= cond[i]; break; }
        case OP_R: case OP_RIF: { u64 *t = QW(*q1++); for (int i = 0; i < W; i++) t[i] &= ~cond[i]; break; }
        case OP_HMR: case OP_HMRIF: { u64 *t = QW(*q1++); u64 *b = BW(*b1++); for (int i = 0; i < W; i++) { t[i] &= ~cond[i]; b[i] = (b[i] & ~cond[i]) | (rnd() & cond[i]); } break; }
        case OP_CZ: case OP_CZIF: q2a++; q2b++; break;
        case OP_CX: case OP_CXIF: { const u64 *a = QW(*q2a++); u64 *t = QW(*q2b++); for (int i = 0; i < W; i++) t[i] ^= a[i] & cond[i]; break; }
        case OP_SWAP: case OP_SWAPIF: { u64 *a = QW(*q2a++), *b = QW(*q2b++); for (int i = 0; i < W; i++) { u64 x = (a[i] ^ b[i]) & cond[i]; a[i] ^= x; b[i] ^= x; } break; }
        case OP_BS0: case OP_BS0IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] &= ~cond[i]; break; }
        case OP_BS1: case OP_BS1IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] |= cond[i]; break; }
        case OP_BINV: case OP_BINVIF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] ^= cond[i]; break; }
        case OP_CCX: case OP_CCZ: case OP_CSWAP: case OP_CCXIF: case OP_CCZIF: case OP_CSWAPIF: {
            uint32_t a = *q3a++, b = *q3b++, c = *q3c++; gate_idx++;
            const u64 *A = QW(a), *Bv = QW(b); u64 *C = QW(c);
            if (gate_idx % nparts == part) {
                int f_zero = 0, f_one = 0, span_ab = 0, span_post = 0, t_zero = 0, post_zero = 0, eq_ctrl = 0;
                if (ty == OP_CCX || ty == OP_CCXIF) {
                    for (int i = 0; i < W; i++) { ab[i] = A[i] & Bv[i]; tx[i] = ab[i] ^ C[i]; }
                    f_zero = is_zero(ab); t_zero = is_zero(C); post_zero = is_zero(tx); eq_ctrl = is_equal(A, Bv);
                    build_basis(c, -1, -1);
                    memcpy(tv, ab, W * 8); span_ab = reduce(tv);
                    memcpy(tv, tx, W * 8); span_post = reduce(tv);
                } else if (ty == OP_CCZ || ty == OP_CCZIF) {
                    for (int i = 0; i < W; i++) ab[i] = A[i] & Bv[i];
                    f_zero = is_zero(ab);
                    build_basis(-1, -1, -1);
                    memcpy(tv, ab, W * 8); span_ab = reduce(tv);
                    for (int i = 0; i < W; i++) tv[i] = A[i] & C[i]; if (reduce(tv)) span_ab |= 2;
                    for (int i = 0; i < W; i++) tv[i] = Bv[i] & C[i]; if (reduce(tv)) span_ab |= 4;
                    u64 tmp[64]; for (int i = 0; i < W; i++) tmp[i] = A[i] & Bv[i] & C[i]; f_one = is_zero(tmp);
                } else {
                    for (int i = 0; i < W; i++) ab[i] = A[i] & (Bv[i] ^ C[i]);
                    f_zero = is_zero(ab);
                    build_basis(-1, -1, -1);
                    memcpy(tv, ab, W * 8); span_ab = reduce(tv);
                }
                fprintf(out, "%llu\t%ld\t%x\t%u\t%u\t%u\t%d\t%d\t%d\t%d\t%d\t%d\t%d\n", (unsigned long long)op, gate_idx, ty, a, b, c, f_zero, f_one, span_ab, span_post, t_zero, post_zero, eq_ctrl);
            }
            if (ty == OP_CCX || ty == OP_CCXIF) { for (int i = 0; i < W; i++) C[i] ^= A[i] & Bv[i] & cond[i]; }
            else if (ty == OP_CSWAP || ty == OP_CSWAPIF) { u64 *Bm = QW(b); for (int i = 0; i < W; i++) { u64 x = A[i] & cond[i] & (Bm[i] ^ C[i]); Bm[i] ^= x; C[i] ^= x; } }
            break; }
        default: fprintf(stderr, "unknown op %x at %llu\n", ty, (unsigned long long)op); return 3;
        }
    }
    // final check: all ancilla zero count
    long nz = 0; for (uint32_t i = 840; i < nq; i++) if (!is_zero(QW(i))) nz++;
    fprintf(stderr, "part %d done gates=%ld nonzero_anc=%ld\n", part, gate_idx + 1, nz);
    fclose(out);
    return 0;
}
