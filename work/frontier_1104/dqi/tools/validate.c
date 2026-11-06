// validate: per-candidate mismatch counts over a shot batch. validate base.kmb shots.bin cands.tsv accum.u32 fires.u32
// cands.tsv lines from census2: TAG op gate ty a b c pop L(comma separated, nq = const). Tags: AB, POST, CSWAP, CCZ_AB, CCZ_AC, CCZ_BC
#include "kmb.h"
#include <assert.h>
typedef uint64_t u64;
static int W; static u64 *Q, *B; static uint32_t nq, nb;
#define QW(i) (Q + (size_t)(i) * W)
#define BW(i) (B + (size_t)(i) * W)
static u64 xs[2];
static inline u64 rnd(void) { u64 a = xs[0], b = xs[1]; u64 r = a + b; b ^= a; xs[0] = ((a << 24) | (a >> 40)) ^ b ^ (b << 16); xs[1] = (b << 37) | (b >> 27); return r; }
typedef struct { int tag; uint64_t op; int n; uint32_t *L; } Cand;
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]);
    FILE *f = fopen(argv[2], "rb"); u64 hdr[4]; fread(hdr, 8, 4, f); nq = hdr[0]; nb = hdr[1]; W = hdr[2]; assert(W <= 64);
    Q = calloc((size_t)nq * W, 8); B = calloc((size_t)nb * W, 8); fread(Q, 8, (size_t)nq * W, f); fread(B, 8, (size_t)nb * W, f); fclose(f);
    // load candidates in op order
    long cap = 100000, nc = 0; Cand *C_ = malloc(cap * sizeof(Cand));
    f = fopen(argv[3], "r"); static char line[1 << 20];
    while (fgets(line, sizeof line, f)) {
        char tag[16]; unsigned long long op; long g; unsigned ty, a, b, c; int pop; char *rest = line; int off = 0;
        if (sscanf(rest, "%15s %llu %ld %x %u %u %u %d%n", tag, &op, &g, &ty, &a, &b, &c, &pop, &off) < 8) continue;
        rest += off; while (*rest == '\t' || *rest == ' ') rest++;
        Cand *cd = &C_[nc++]; cd->op = op; cd->tag = !strcmp(tag, "AB") ? 0 : !strcmp(tag, "POST") ? 1 : !strcmp(tag, "CSWAP") ? 2 : !strcmp(tag, "CCZ_AB") ? 3 : !strcmp(tag, "CCZ_AC") ? 4 : 5;
        int n = 0; uint32_t tmp[1024]; char *p = rest; while (*p && *p != '\n') { tmp[n++] = strtoul(p, &p, 10); if (*p == ',') p++; } cd->n = n; cd->L = malloc(n * 4 + 4); memcpy(cd->L, tmp, n * 4);
    }
    fclose(f);
    uint32_t *mis = calloc(nc, 4), *fires = calloc(nc, 4);
    f = fopen(argv[4], "rb"); if (f) { fread(mis, 4, nc, f); fclose(f); }
    f = fopen(argv[5], "rb"); if (f) { fread(fires, 4, nc, f); fclose(f); }
    xs[0] = hdr[3] * 0x9E3779B97F4A7C15ull + (u64)Q[0] + 1; xs[1] = 0xD1B54A32D192ED03ull ^ xs[0];
    const uint32_t *q3a = k.q3a, *q3b = k.q3b, *q3c = k.q3c, *q2a = k.q2a, *q2b = k.q2b, *q1 = k.q1, *b1 = k.b1, *bc = k.bc;
    u64 cond_stack[64][64]; int csp = 0; u64 base[64]; for (int i = 0; i < W; i++) base[i] = ~0ull;
    u64 cond[64], v[64], w[64]; long ci = 0;
    for (uint64_t op = 0; op < k.nops; op++) {
        uint8_t ty = k.types[op];
        memcpy(cond, base, W * 8);
        if ((ty & 0x80) && ty != OP_PUSH) { const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) cond[i] &= c[i]; }
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
        case OP_CCX: case OP_CCZ: case OP_CSWAP: {
            uint32_t a = *q3a++, b = *q3b++, c = *q3c++;
            const u64 *A = QW(a); u64 *Bv = QW(b), *Cv = QW(c);
            if (ci < nc && C_[ci].op == op) {
                Cand *cd = &C_[ci];
                for (int i = 0; i < W; i++) {
                    switch (cd->tag) {
                    case 0: case 3: v[i] = A[i] & Bv[i]; break;
                    case 1: v[i] = (A[i] & Bv[i]) ^ Cv[i]; break;
                    case 2: v[i] = A[i] & (Bv[i] ^ Cv[i]); break;
                    case 4: v[i] = A[i] & Cv[i]; break;
                    default: v[i] = Bv[i] & Cv[i]; break;
                    }
                }
                int fp = 0; for (int i = 0; i < W; i++) fp += __builtin_popcountll(v[i]);
                memset(w, 0, W * 8);
                for (int j = 0; j < cd->n; j++) { uint32_t q_ = cd->L[j]; if (q_ == nq) { for (int i = 0; i < W; i++) w[i] = ~w[i]; } else { const u64 *x = QW(q_); for (int i = 0; i < W; i++) w[i] ^= x[i]; } }
                int mm = 0; for (int i = 0; i < W; i++) mm += __builtin_popcountll(v[i] ^ w[i]);
                mis[ci] += mm; fires[ci] += fp;
                ci++;
            }
            if (ty == OP_CCX) { for (int i = 0; i < W; i++) Cv[i] ^= A[i] & Bv[i] & base[i]; }
            else if (ty == OP_CSWAP) { for (int i = 0; i < W; i++) { u64 x = A[i] & base[i] & (Bv[i] ^ Cv[i]); Bv[i] ^= x; Cv[i] ^= x; } }
            break; }
        default: fprintf(stderr, "unknown op %x\n", ty); return 3;
        }
    }
    if (ci != nc) { fprintf(stderr, "cand mismatch %ld %ld\n", ci, nc); return 4; }
    f = fopen(argv[4], "wb"); fwrite(mis, 4, nc, f); fclose(f);
    f = fopen(argv[5], "wb"); fwrite(fires, 4, nc, f); fclose(f);
    return 0;
}
