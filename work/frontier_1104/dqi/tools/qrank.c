// qrank: for each wire, group consecutive Toffolis that target it while it is not read; rank of the quadratic form sum A_i B_i.
// Usage: qrank base.kmb shots.bin out.tsv
#include "kmb.h"
#include <assert.h>
typedef uint64_t u64;
static int W; static u64 *Q, *B; static uint32_t nq, nb;
#define QW(i) (Q + (size_t)(i) * W)
#define BW(i) (B + (size_t)(i) * W)
static u64 xs[2] = {12345, 67890};
static inline u64 rnd(void) { u64 a = xs[0], b = xs[1]; u64 r = a + b; b ^= a; xs[0] = ((a << 24) | (a >> 40)) ^ b ^ (b << 16); xs[1] = (b << 37) | (b >> 27); return r; }
#define MAXG 256
typedef struct { int k; u64 *vecs; uint64_t first_op; uint64_t ops[MAXG]; } Group;
static Group *G;
static long tot_groups = 0, tot_k = 0, tot_save = 0, tot_save_k2 = 0; static FILE *out;
static int gf2_rank_form(int k, u64 *vecs, int *rank_out) {
    // vecs: 2k vectors each W words. Find span basis, express each in the basis, form alternating matrix, rank.
    int n = 2 * k; static u64 basis[2 * MAXG * 64]; static int piv[2 * MAXG]; static u64 comb[2 * MAXG][8]; int nb_ = 0; // comb: combination of basis in terms of orig basis index
    static int coords[2 * MAXG][2 * MAXG];
    int cw = (2 * MAXG + 63) / 64; (void)cw;
    static u64 rep[2 * MAXG][8]; // representation of vec in basis vectors
    for (int i = 0; i < n; i++) {
        u64 v[64]; memcpy(v, vecs + (size_t)i * W, W * 8);
        u64 r[8] = {0};
        for (int j = 0; j < nb_; j++) if ((v[piv[j] >> 6] >> (piv[j] & 63)) & 1) { for (int x = 0; x < W; x++) v[x] ^= basis[(size_t)j * W + x]; for (int x = 0; x < 8; x++) r[x] ^= comb[j][x]; }
        int nz = -1; for (int x = 0; x < W; x++) if (v[x]) { nz = x * 64 + __builtin_ctzll(v[x]); break; }
        if (nz >= 0) { memcpy(basis + (size_t)nb_ * W, v, W * 8); piv[nb_] = nz; memcpy(comb[nb_], r, 64); comb[nb_][nb_ >> 6] ^= 1ull << (nb_ & 63); r[nb_ >> 6] ^= 1ull << (nb_ & 63); nb_++; }
        memcpy(rep[i], r, 64);
    }
    (void)coords;
    // alternating matrix M over nb_ dims: for each pair (A_i,B_i): M += a b^T + b a^T
    static u64 M[2 * MAXG][8]; for (int i = 0; i < nb_; i++) memset(M[i], 0, 64);
    for (int i = 0; i < k; i++) {
        u64 *a = rep[2 * i], *b = rep[2 * i + 1];
        for (int r = 0; r < nb_; r++) {
            if ((a[r >> 6] >> (r & 63)) & 1) for (int x = 0; x < 8; x++) M[r][x] ^= b[x];
            if ((b[r >> 6] >> (r & 63)) & 1) for (int x = 0; x < 8; x++) M[r][x] ^= a[x];
        }
    }
    int rank = 0;
    for (int c = 0; c < nb_; c++) {
        int p = -1; for (int r = rank; r < nb_; r++) if ((M[r][c >> 6] >> (c & 63)) & 1) { p = r; break; }
        if (p < 0) continue;
        if (p != rank) { u64 t[8]; memcpy(t, M[p], 64); memcpy(M[p], M[rank], 64); memcpy(M[rank], t, 64); }
        for (int r = 0; r < nb_; r++) if (r != rank && ((M[r][c >> 6] >> (c & 63)) & 1)) for (int x = 0; x < 8; x++) M[r][x] ^= M[rank][x];
        rank++;
    }
    *rank_out = rank; return nb_;
}
static void close_group(uint32_t t, uint64_t op) {
    Group *g = &G[t]; if (g->k >= 2) {
        int rank; int dim = gf2_rank_form(g->k, g->vecs, &rank);
        int need = rank / 2; int save = g->k - need; tot_groups++; tot_k += g->k; if (save > 0) { tot_save += save; if (g->k == 2) tot_save_k2 += save; fprintf(out, "%u\t%d\t%d\t%d\t%llu\t%llu\n", t, g->k, dim, need, (unsigned long long)g->ops[0], (unsigned long long)g->ops[g->k - 1]); }
    }
    g->k = 0;
}
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]);
    FILE *f = fopen(argv[2], "rb"); u64 hdr[4]; fread(hdr, 8, 4, f); nq = hdr[0]; nb = hdr[1]; W = hdr[2]; assert(W <= 64);
    Q = calloc((size_t)nq * W, 8); B = calloc((size_t)nb * W, 8); fread(Q, 8, (size_t)nq * W, f); fread(B, 8, (size_t)nb * W, f); fclose(f);
    out = fopen(argv[3], "w");
    G = calloc(nq, sizeof(Group)); for (uint32_t i = 0; i < nq; i++) G[i].vecs = malloc((size_t)2 * MAXG * W * 8);
    const uint32_t *q3a = k.q3a, *q3b = k.q3b, *q3c = k.q3c, *q2a = k.q2a, *q2b = k.q2b, *q1 = k.q1, *b1 = k.b1, *bc = k.bc;
    u64 cond_stack[64][64]; int csp = 0; u64 base[64]; for (int i = 0; i < W; i++) base[i] = ~0ull;
    u64 cond[64];
    for (uint64_t op = 0; op < k.nops; op++) {
        uint8_t ty = k.types[op];
        memcpy(cond, base, W * 8);
        if ((ty & 0x80) && ty != OP_PUSH) { const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) cond[i] &= c[i]; }
        switch (ty) {
        case OP_POP: csp--; if (csp > 0) memcpy(base, cond_stack[csp - 1], W * 8); else for (int i = 0; i < W; i++) base[i] = ~0ull; break;
        case OP_PUSH: { const u64 *c = BW(*bc++); for (int i = 0; i < W; i++) base[i] &= c[i]; memcpy(cond_stack[csp++], base, W * 8); break; }
        case OP_TAG: case OP_NEG: case OP_NEGIF: break;
        case OP_Z: case OP_ZIF: { uint32_t t = *q1++; close_group(t, op); break; }
        case OP_X: case OP_XIF: { u64 *t = QW(*q1++); for (int i = 0; i < W; i++) t[i] ^= cond[i]; break; }
        case OP_R: case OP_RIF: { uint32_t ti = *q1++; close_group(ti, op); u64 *t = QW(ti); for (int i = 0; i < W; i++) t[i] &= ~cond[i]; break; }
        case OP_HMR: case OP_HMRIF: { uint32_t ti = *q1++; close_group(ti, op); u64 *t = QW(ti); u64 *b = BW(*b1++); for (int i = 0; i < W; i++) { t[i] &= ~cond[i]; b[i] = (b[i] & ~cond[i]) | (rnd() & cond[i]); } break; }
        case OP_CZ: case OP_CZIF: { uint32_t a = *q2a++, b = *q2b++; close_group(a, op); close_group(b, op); break; }
        case OP_CX: case OP_CXIF: { uint32_t ai = *q2a++, ti = *q2b++; close_group(ai, op); const u64 *a = QW(ai); u64 *t = QW(ti); for (int i = 0; i < W; i++) t[i] ^= a[i] & cond[i]; break; }
        case OP_SWAP: case OP_SWAPIF: { uint32_t ai = *q2a++, bi = *q2b++; close_group(ai, op); close_group(bi, op); u64 *a = QW(ai), *b = QW(bi); for (int i = 0; i < W; i++) { u64 x = (a[i] ^ b[i]) & cond[i]; a[i] ^= x; b[i] ^= x; } break; }
        case OP_BS0: case OP_BS0IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] &= ~cond[i]; break; }
        case OP_BS1: case OP_BS1IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] |= cond[i]; break; }
        case OP_BINV: case OP_BINVIF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] ^= cond[i]; break; }
        case OP_CCX: { uint32_t ai = *q3a++, bi = *q3b++, ci = *q3c++; close_group(ai, op); close_group(bi, op); const u64 *A = QW(ai), *Bv = QW(bi); u64 *C = QW(ci);
            Group *g = &G[ci]; if (g->k < MAXG) { memcpy(g->vecs + (size_t)(2 * g->k) * W, A, W * 8); memcpy(g->vecs + (size_t)(2 * g->k + 1) * W, Bv, W * 8); g->ops[g->k] = op; g->k++; }
            for (int i = 0; i < W; i++) C[i] ^= A[i] & Bv[i] & cond[i]; break; }
        case OP_CCZ: { uint32_t ai = *q3a++, bi = *q3b++, ci = *q3c++; close_group(ai, op); close_group(bi, op); close_group(ci, op); break; }
        case OP_CSWAP: { uint32_t ai = *q3a++, bi = *q3b++, ci = *q3c++; close_group(ai, op); close_group(bi, op); close_group(ci, op); const u64 *A = QW(ai); u64 *Bm = QW(bi); u64 *C = QW(ci); for (int i = 0; i < W; i++) { u64 x = A[i] & cond[i] & (Bm[i] ^ C[i]); Bm[i] ^= x; C[i] ^= x; } break; }
        default: fprintf(stderr, "unknown op %x\n", ty); return 3;
        }
    }
    fprintf(stderr, "groups=%ld tot_k=%ld save=%ld save_from_k2=%ld\n", tot_groups, tot_k, tot_save, tot_save_k2);
    return 0;
}
