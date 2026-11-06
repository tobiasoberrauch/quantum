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

#include <stdbool.h>
typedef struct { uint64_t key, op; } HE;
#define HSZ (1u<<22)
static HE *H;
static inline HE *hfind(uint64_t key){ uint32_t h=(uint32_t)((key*0x9E3779B97F4A7C15ull)>>42); while(H[h].key && H[h].key!=key) h=(h+1)&(HSZ-1); return &H[h]; }
typedef struct { uint64_t op1, op2; uint32_t a,b,d; } Pair;
static Pair *P; static long np=0;
int main(int argc,char**argv){
    Kmb k; kmb_open(&k, argv[1]);
    uint64_t *lastw=calloc(k.nq,8), *lastr=calloc(k.nq,8);
    H=calloc(HSZ,sizeof(HE)); P=malloc(sizeof(Pair)*400000);
    const uint32_t *q3a = k.q3a, *q3b = k.q3b, *q3c = k.q3c, *q2a = k.q2a, *q2b = k.q2b, *q1 = k.q1;
    // pass 1
    #define W_(q) lastw[q]=op+1
    #define R_(q) lastr[q]=op+1
    for(uint64_t op=0;op<k.nops;op++){ uint8_t ty=k.types[op];
        switch(ty&0x70){
        case 0x30: { uint32_t a=*q3a++,b=*q3b++,c=*q3c++;
            if(ty==OP_CCX){ uint32_t x=a<b?a:b,y=a<b?b:a; uint64_t key=((uint64_t)x<<40)|((uint64_t)y<<20)|c; key+=1; HE*e=hfind(key);
                if(e->key==key && lastw[a]<=e->op && lastw[b]<=e->op && lastw[c]==e->op && lastr[c]>e->op){ P[np++]=(Pair){e->op-1,op,a,b,c}; }
                e->key=key; e->op=op+1;
                R_(a);R_(b);W_(c);
            } else if(ty==OP_CSWAP){ R_(a);W_(b);W_(c);R_(b);R_(c);} else {R_(a);R_(b);R_(c);}
            break;}
        case 0x20: { uint32_t a=*q2a++,b=*q2b++; if((ty&0x7f)==OP_CX){R_(a);W_(b);} else if((ty&0x7f)==OP_CZ){R_(a);R_(b);} else {W_(a);W_(b);R_(a);R_(b);} break;}
        case 0x10: { uint32_t a=*q1++; uint8_t t=ty&0x7f; if(t==OP_X||t==OP_R){W_(a);} else {R_(a);} break;}
        case 0x50: { uint32_t a=*q1++; W_(a); break;}
        }
    }
    fprintf(stderr,"pairs=%ld\n",np);
    // pass 2: values at op1
    FILE *f = fopen(argv[2], "rb"); u64 hdr[4]; fread(hdr, 8, 4, f); nq = hdr[0]; nb = hdr[1]; W = hdr[2];
    Q = calloc((size_t)nq * W, 8); B = calloc((size_t)nb * W, 8); fread(Q, 8, (size_t)nq * W, f); fread(B, 8, (size_t)nb * W, f); fclose(f);
    FILE *out=fopen(argv[3],"w");
    basis = malloc((size_t)(nq + 2) * W * 8); piv = malloc((nq + 2) * sizeof(int));
    // sort pairs by op1 (insertion order is by op2): simple qsort
        extern int cmp_pair(const void*,const void*);
    qsort(P,np,sizeof(Pair),cmp_pair);
    q3a=k.q3a;q3b=k.q3b;q3c=k.q3c;q2a=k.q2a;q2b=k.q2b;q1=k.q1; const uint32_t *b1=k.b1,*bc=k.bc;
    u64 cond_stack[64][64]; int csp=0; u64 base[64]; for(int i=0;i<W;i++)base[i]=~0ull; u64 cond[64];
    long pi=0; uint8_t *touched=calloc(nq,1);
    long clean_avail=0,span_dep=0,dzero=0;
    for(uint64_t op=0;op<k.nops;op++){ uint8_t ty=k.types[op];
        while(pi<np && P[pi].op1==op){ Pair *p=&P[pi++];
            // touched set in window by rescanning via a small replay of types: use offsets snapshot
            memset(touched,0,nq);
            const uint32_t *a3=q3a,*b3=q3b,*c3=q3c,*a2=q2a,*b2=q2b,*a1=q1; uint64_t span=p->op2-p->op1;
            int written_only=1; (void)written_only;
            if(span<20000){ for(uint64_t o=op;o<=p->op2;o++){ uint8_t t=k.types[o]; switch(t&0x70){case 0x30: touched[*a3++]=1;touched[*b3++]=1;touched[*c3++]=1;break;case 0x20:touched[*a2++]=1;touched[*b2++]=1;break;case 0x10:case 0x50:touched[*a1++]=1;break;} }
            int z=0; for(uint32_t i=0;i<nq;i++) if(!touched[i]&&is_zero(QW(i))) z++;
            int dz=is_zero(QW(p->d));
            int dep=0; if(!dz){ build_basis(p->d,-1,-1); u64 tv[64]; memcpy(tv,QW(p->d),W*8); dep=reduce(tv); }
            if(dz) dzero++; else { if(z>0) clean_avail++; if(dep) span_dep++; }
            fprintf(out,"%llu\t%llu\t%u\t%u\t%u\t%d\t%d\t%d\n",(unsigned long long)p->op1,(unsigned long long)p->op2,p->a,p->b,p->d,dz,z,dep);
            }
        }
        memcpy(cond,base,W*8);
        if((ty&0x80)&&ty!=OP_PUSH){const u64*c=BW(*bc++);for(int i=0;i<W;i++)cond[i]&=c[i];}
        switch(ty){
        case OP_POP: csp--; if(csp>0)memcpy(base,cond_stack[csp-1],W*8); else for(int i=0;i<W;i++)base[i]=~0ull; break;
        case OP_PUSH: {const u64*c=BW(*bc++);for(int i=0;i<W;i++)base[i]&=c[i];memcpy(cond_stack[csp++],base,W*8);break;}
        case OP_TAG: case OP_NEG: case OP_NEGIF: break;
        case OP_Z: case OP_ZIF: q1++; break;
        case OP_X: case OP_XIF: {u64*t=QW(*q1++);for(int i=0;i<W;i++)t[i]^=cond[i];break;}
        case OP_R: case OP_RIF: {u64*t=QW(*q1++);for(int i=0;i<W;i++)t[i]&=~cond[i];break;}
        case OP_HMR: case OP_HMRIF: {u64*t=QW(*q1++);u64*b=BW(*b1++);for(int i=0;i<W;i++){t[i]&=~cond[i];b[i]=(b[i]&~cond[i])|(rnd()&cond[i]);}break;}
        case OP_CZ: case OP_CZIF: q2a++;q2b++;break;
        case OP_CX: case OP_CXIF: {const u64*a=QW(*q2a++);u64*t=QW(*q2b++);for(int i=0;i<W;i++)t[i]^=a[i]&cond[i];break;}
        case OP_SWAP: case OP_SWAPIF: {u64*a=QW(*q2a++),*b=QW(*q2b++);for(int i=0;i<W;i++){u64 x=(a[i]^b[i])&cond[i];a[i]^=x;b[i]^=x;}break;}
        case OP_BS0: case OP_BS0IF: {u64*b=BW(*b1++);for(int i=0;i<W;i++)b[i]&=~cond[i];break;}
        case OP_BS1: case OP_BS1IF: {u64*b=BW(*b1++);for(int i=0;i<W;i++)b[i]|=cond[i];break;}
        case OP_BINV: case OP_BINVIF: {u64*b=BW(*b1++);for(int i=0;i<W;i++)b[i]^=cond[i];break;}
        case OP_CCX: {const u64*A=QW(*q3a++),*Bv=QW(*q3b++);u64*C=QW(*q3c++);for(int i=0;i<W;i++)C[i]^=A[i]&Bv[i]&base[i];break;}
        case OP_CCZ: q3a++;q3b++;q3c++;break;
        case OP_CSWAP: {const u64*A=QW(*q3a++);u64*Bm=QW(*q3b++),*C=QW(*q3c++);for(int i=0;i<W;i++){u64 x=A[i]&base[i]&(Bm[i]^C[i]);Bm[i]^=x;C[i]^=x;}break;}
        default: return 3;
        }
    }
    fprintf(stderr,"evaluated=%ld dirty_target_zero_before=%ld clean_wire_available=%ld d_in_span=%ld\n",pi,dzero,clean_avail,span_dep);
    return 0;
}
int cmp_pair(const void*x,const void*y){ uint64_t a=((const Pair*)x)->op1,b=((const Pair*)y)->op1; return a<b?-1:a>b; }
