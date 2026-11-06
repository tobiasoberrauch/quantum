// rates: per-gate count of shots in which the 3q gate acts non-trivially (AB!=0 / ABC / c&(x^y)).
// Usage: rates base.kmb shots.bin counts.u32 (accumulates into counts file) seed
#include "kmb.h"
#include <assert.h>
typedef uint64_t u64;
static int W; static u64 *Q, *B; static uint32_t nq, nb;
#define QW(i) (Q + (size_t)(i) * W)
#define BW(i) (B + (size_t)(i) * W)
static u64 xs[2];
static inline u64 rnd(void) { u64 a = xs[0], b = xs[1]; u64 r = a + b; b ^= a; xs[0] = ((a << 24) | (a >> 40)) ^ b ^ (b << 16); xs[1] = (b << 37) | (b >> 27); return r; }
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]);
    FILE *f = fopen(argv[2], "rb"); u64 hdr[4]; fread(hdr, 8, 4, f); nq = hdr[0]; nb = hdr[1]; W = hdr[2]; assert(W <= 64);
    Q = calloc((size_t)nq * W, 8); B = calloc((size_t)nb * W, 8); fread(Q, 8, (size_t)nq * W, f); fread(B, 8, (size_t)nb * W, f);
    u64 *phases = calloc(W, 8); fread(phases, 8, W, f); fclose(f);
    u64 *S0 = malloc(840ul * W * 8); memcpy(S0, Q, 840ul * W * 8);
    xs[0] = strtoull(argv[4], 0, 10) * 0x9E3779B97F4A7C15ull + 1; xs[1] = 0xD1B54A32D192ED03ull ^ xs[0];
    uint32_t *cnt = calloc(k.n3, 4); FILE *cf = fopen(argv[3], "rb"); if (cf) { fread(cnt, 4, k.n3, cf); fclose(cf); }
    const uint32_t *q3a = k.q3a, *q3b = k.q3b, *q3c = k.q3c, *q2a = k.q2a, *q2b = k.q2b, *q1 = k.q1, *b1 = k.b1, *bc = k.bc;
    u64 cond_stack[64][64]; int csp = 0; u64 base[64]; for (int i = 0; i < W; i++) base[i] = ~0ull;
    u64 cond[64]; long g = -1; u64 *ph = calloc(W, 8);
    for (uint64_t op = 0; op < k.nops; op++) {
        uint8_t ty = k.types[op];
        memcpy(cond, base, W * 8);
        if ((ty & 0x80) && ty != OP_PUSH) { const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) cond[i] &= c[i]; }
        switch (ty) {
        case OP_POP: csp--; if (csp > 0) memcpy(base, cond_stack[csp - 1], W * 8); else for (int i = 0; i < W; i++) base[i] = ~0ull; break;
        case OP_PUSH: { const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) base[i] &= c[i]; memcpy(cond_stack[csp++], base, W * 8); break; }
        case OP_TAG: break;
        case OP_NEG: case OP_NEGIF: for (int i = 0; i < W; i++) ph[i] ^= cond[i]; break;
        case OP_Z: case OP_ZIF: { const u64 *t = QW(*q1++); for (int i = 0; i < W; i++) ph[i] ^= t[i] & cond[i]; break; }
        case OP_X: case OP_XIF: { u64 *t = QW(*q1++); for (int i = 0; i < W; i++) t[i] ^= cond[i]; break; }
        case OP_R: case OP_RIF: { u64 *t = QW(*q1++); for (int i = 0; i < W; i++) { ph[i] ^= t[i] & rnd() & cond[i]; t[i] &= ~cond[i]; } break; }
        case OP_HMR: case OP_HMRIF: { u64 *t = QW(*q1++); u64 *b = BW(*b1++); for (int i = 0; i < W; i++) { u64 r = rnd(); ph[i] ^= t[i] & r & cond[i]; t[i] &= ~cond[i]; b[i] = (b[i] & ~cond[i]) | (r & cond[i]); } break; }
        case OP_CZ: case OP_CZIF: { const u64 *a = QW(*q2a++), *t = QW(*q2b++); for (int i = 0; i < W; i++) ph[i] ^= a[i] & t[i] & cond[i]; break; }
        case OP_CX: case OP_CXIF: { const u64 *a = QW(*q2a++); u64 *t = QW(*q2b++); for (int i = 0; i < W; i++) t[i] ^= a[i] & cond[i]; break; }
        case OP_SWAP: case OP_SWAPIF: { u64 *a = QW(*q2a++), *b = QW(*q2b++); for (int i = 0; i < W; i++) { u64 x = (a[i] ^ b[i]) & cond[i]; a[i] ^= x; b[i] ^= x; } break; }
        case OP_BS0: case OP_BS0IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] &= ~cond[i]; break; }
        case OP_BS1: case OP_BS1IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] |= cond[i]; break; }
        case OP_BINV: case OP_BINVIF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] ^= cond[i]; break; }
        case OP_CCX: { const u64 *A = QW(*q3a++), *Bv = QW(*q3b++); u64 *C = QW(*q3c++); g++; int n = 0; for (int i = 0; i < W; i++) { u64 x = A[i] & Bv[i] & base[i]; n += __builtin_popcountll(x); C[i] ^= x; } cnt[g] += n; break; }
        case OP_CCZ: { const u64 *A = QW(*q3a++), *Bv = QW(*q3b++), *C = QW(*q3c++); g++; int n = 0; for (int i = 0; i < W; i++) { u64 x = A[i] & Bv[i] & C[i] & base[i]; n += __builtin_popcountll(x); ph[i] ^= x; } cnt[g] += n; break; }
        case OP_CSWAP: { const u64 *A = QW(*q3a++); u64 *Bm = QW(*q3b++); u64 *C = QW(*q3c++); g++; int n = 0; for (int i = 0; i < W; i++) { u64 x = A[i] & base[i] & (Bm[i] ^ C[i]); n += __builtin_popcountll(x); Bm[i] ^= x; C[i] ^= x; } cnt[g] += n; break; }
        default: fprintf(stderr, "unknown op %x\n", ty); return 3;
        }
    }
    long vfail = 0, pfail = 0;
    u64 *v = calloc(W, 8);
    for (uint32_t q = 0; q < nq; q++) { const u64 *t = QW(q); for (int i = 0; i < W; i++) v[i] |= (q < 840) ? (t[i] ^ S0[(size_t)q * W + i]) : t[i]; }
    for (int i = 0; i < W; i++) { vfail += __builtin_popcountll(v[i]); pfail += __builtin_popcountll((ph[i] ^ phases[i]) & ~v[i]); }
    printf("%ld %ld\n", vfail, pfail);
    cf = fopen(argv[3], "wb"); fwrite(cnt, 4, k.n3, cf); fclose(cf);
    return 0;
}
