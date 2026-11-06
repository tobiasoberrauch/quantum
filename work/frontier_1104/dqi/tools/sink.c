// sink: backward pass. A wire is "sink" at time p if from p on it is only written (X, CX target, CCX target, CX control into sink wire)
// until an HMR/R clears it. Counts CCX gates whose target is sink at the gate.  Usage: sink base.kmb out.tsv
#include "kmb.h"
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]);
    uint8_t *sink = calloc(k.nq, 1); // 0 = not sink, 1 = sink
    const uint32_t *q3a = k.q3a + k.n3, *q3b = k.q3b + k.n3, *q3c = k.q3c + k.n3, *q2a = k.q2a + k.n2, *q2b = k.q2b + k.n2, *q1 = k.q1 + k.n1, *b1 = k.b1 + k.nb1;
    FILE *out = fopen(argv[2], "w");
    long n_sink_ccx = 0, n_sink_cswap = 0, n_ccx = 0, multi = 0;
    for (int64_t op = (int64_t)k.nops - 1; op >= 0; op--) {
        uint8_t ty = k.types[op];
        switch (ty) {
        case OP_R: case OP_RIF: { uint32_t t = *--q1; sink[t] = (ty == OP_R) ? 1 : 0; break; }
        case OP_HMR: case OP_HMRIF: { uint32_t t = *--q1; --b1; sink[t] = (ty == OP_HMR) ? 1 : 0; break; }
        case OP_Z: case OP_ZIF: { uint32_t t = *--q1; sink[t] = 0; break; }
        case OP_X: case OP_XIF: { --q1; break; }
        case OP_CZ: case OP_CZIF: { uint32_t a = *--q2a, b = *--q2b; sink[a] = sink[b] = 0; break; }
        case OP_CX: case OP_CXIF: { uint32_t a = *--q2a, t = *--q2b; /* a read */
            if (ty == OP_CX && sink[a] && sink[t]) { multi++; /* stays sink */ }
            else if (!sink[t]) sink[a] = 0; else sink[a] = 0; /* a not sink unless both */
            if (ty == OP_CX && sink[t]) { /* t stays */ }
            break; }
        case OP_SWAP: { uint32_t a = *--q2a, b = *--q2b; uint8_t x = sink[a]; sink[a] = sink[b]; sink[b] = x; break; }
        case OP_SWAPIF: { uint32_t a = *--q2a, b = *--q2b; sink[a] = sink[b] = 0; break; }
        case OP_CCX: { uint32_t a = *--q3a, b = *--q3b, c = *--q3c; n_ccx++; if (sink[c]) { n_sink_ccx++; fprintf(out, "%lld\t%u\t%u\t%u\n", (long long)op, a, b, c); } sink[a] = sink[b] = 0; break; }
        case OP_CCZ: { uint32_t a = *--q3a, b = *--q3b, c = *--q3c; sink[a] = sink[b] = sink[c] = 0; break; }
        case OP_CSWAP: { uint32_t a = *--q3a, b = *--q3b, c = *--q3c; sink[a] = sink[b] = sink[c] = 0; break; }
        default: break;
        }
    }
    fprintf(stderr, "ccx=%ld sink_ccx=%ld multi_cx=%ld\n", n_ccx, n_sink_ccx, multi);
    return 0;
}
