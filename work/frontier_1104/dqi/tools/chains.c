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

#define MAXC 40
typedef struct { int n; u64 *vec; uint32_t wires[MAXC]; uint64_t ops[MAXC]; int alive; uint64_t first_op; } Chain;
static Chain *CH; static long tot_chains=0,tot_gates=0,tot_rem=0,chains_rem=0; static FILE *out; static long hist[64];
static void close_chain(uint32_t t) {
    Chain *c=&CH[t]; if(!c->alive) return; c->alive=0;
    if(c->n<3) return;
    tot_chains++; tot_gates+=c->n-1;
    // greedy removal
    u64 f[64]; for(int i=0;i<W;i++) f[i]=~0ull; for(int j=0;j<c->n;j++) { const u64*v=c->vec+(size_t)j*W; for(int i=0;i<W;i++) f[i]&=v[i]; }
    int keep[MAXC]; for(int j=0;j<c->n;j++) keep[j]=1;
    int removed=0;
    for(int j=c->n-1;j>=0;j--){ u64 g[64]; for(int i=0;i<W;i++) g[i]=~0ull; for(int m=0;m<c->n;m++) if(keep[m]&&m!=j){ const u64*v=c->vec+(size_t)m*W; for(int i=0;i<W;i++) g[i]&=v[i]; }
        int eq=1; for(int i=0;i<W;i++) if(g[i]!=f[i]){eq=0;break;} if(eq){keep[j]=0;removed++;} }
    if(removed){ tot_rem+=removed; chains_rem++; }
    hist[removed]++;
    int fpop=0; for(int i=0;i<W;i++) fpop+=__builtin_popcountll(f[i]);
    fprintf(out,"%llu\t%d\t%d\t%d\t",(unsigned long long)c->first_op,c->n,removed,fpop);
    for(int j=0;j<c->n;j++) fprintf(out,"%s%u%s",j?",":"",c->wires[j],keep[j]?"":"*");
    fprintf(out,"\n");
}
int main(int argc, char **argv) {
    // chains base.kmb shots.bin out.tsv
    Kmb k; kmb_open(&k, argv[1]);
    FILE *f = fopen(argv[2], "rb"); u64 hdr[4]; fread(hdr, 8, 4, f); nq = hdr[0]; nb = hdr[1]; W = hdr[2]; assert(W <= 64);
    Q = calloc((size_t)nq * W, 8); B = calloc((size_t)nb * W, 8); fread(Q, 8, (size_t)nq * W, f); fread(B, 8, (size_t)nb * W, f); fclose(f);
    out = fopen(argv[3], "w");
    CH=calloc(nq,sizeof(Chain)); for(uint32_t i=0;i<nq;i++) CH[i].vec=malloc((size_t)MAXC*W*8);
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
        case OP_Z: case OP_ZIF: q1++; break;
        case OP_X: case OP_XIF: { uint32_t ti=*q1++; u64 *t = QW(ti); close_chain(ti); for (int i = 0; i < W; i++) t[i] ^= cond[i]; break; }
        case OP_R: case OP_RIF: { uint32_t ti=*q1++; u64 *t = QW(ti); close_chain(ti); for (int i = 0; i < W; i++) t[i] &= ~cond[i]; break; }
        case OP_HMR: case OP_HMRIF: { uint32_t ti=*q1++; u64 *t = QW(ti); close_chain(ti); u64 *b = BW(*b1++); for (int i = 0; i < W; i++) { t[i] &= ~cond[i]; b[i] = (b[i] & ~cond[i]) | (rnd() & cond[i]); } break; }
        case OP_CZ: case OP_CZIF: q2a++; q2b++; break;
        case OP_CX: case OP_CXIF: { const u64 *a = QW(*q2a++); uint32_t ti=*q2b++; u64 *t = QW(ti); close_chain(ti); for (int i = 0; i < W; i++) t[i] ^= a[i] & cond[i]; break; }
        case OP_SWAP: case OP_SWAPIF: { uint32_t ai=*q2a++,bi=*q2b++; u64 *a = QW(ai), *b = QW(bi); close_chain(ai); close_chain(bi); for (int i = 0; i < W; i++) { u64 x = (a[i] ^ b[i]) & cond[i]; a[i] ^= x; b[i] ^= x; } break; }
        case OP_BS0: case OP_BS0IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] &= ~cond[i]; break; }
        case OP_BS1: case OP_BS1IF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] |= cond[i]; break; }
        case OP_BINV: case OP_BINVIF: { u64 *b = BW(*b1++); for (int i = 0; i < W; i++) b[i] ^= cond[i]; break; }
        case OP_CCX: { uint32_t a = *q3a++, b = *q3b++, c = *q3c++; const u64 *A = QW(a), *Bv = QW(b); u64 *C = QW(c);
            close_chain(c);
            if (is_zero(C)) {
                Chain *n=&CH[c]; n->alive=1; n->n=0; n->first_op=op;
                int src=-1,other=-1; if(CH[a].alive) {src=a;other=b;} else if(CH[b].alive){src=b;other=a;}
                if(src>=0 && CH[src].n<MAXC-1){ Chain*s=&CH[src]; memcpy(n->vec,s->vec,(size_t)s->n*W*8); memcpy(n->wires,s->wires,s->n*4); n->n=s->n; n->first_op=s->first_op; s->alive=0; memcpy(n->vec+(size_t)n->n*W,QW(other),W*8); n->wires[n->n++]=other; }
                else { memcpy(n->vec,A,W*8); memcpy(n->vec+W,Bv,W*8); n->wires[0]=a; n->wires[1]=b; n->n=2; }
            }
            for (int i = 0; i < W; i++) C[i] ^= A[i] & Bv[i] & base[i]; break; }
        case OP_CCZ: q3a++; q3b++; q3c++; break;
        case OP_CSWAP: { uint32_t a = *q3a++, b = *q3b++, c = *q3c++; const u64 *A = QW(a); u64 *Bm = QW(b), *C = QW(c); close_chain(b); close_chain(c); for (int i = 0; i < W; i++) { u64 x = A[i] & base[i] & (Bm[i] ^ C[i]); Bm[i] ^= x; C[i] ^= x; } break; }
        default: fprintf(stderr, "unknown op %x\n", ty); return 3;
        }
    }
    for(uint32_t i=0;i<nq;i++) close_chain(i);
    fprintf(stderr,"chains(n>=3)=%ld gates=%ld removable=%ld chains_with_removal=%ld\n",tot_chains,tot_gates,tot_rem,chains_rem);
    for(int i=0;i<40;i++) if(hist[i]) fprintf(stderr,"rem=%d:%ld ",i,hist[i]);
    fprintf(stderr,"\n");
    return 0;
}
