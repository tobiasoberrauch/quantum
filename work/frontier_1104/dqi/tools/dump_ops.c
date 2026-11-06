// dump_ops base.kmb lo hi : print ops in [lo,hi) as text
#include "kmb.h"
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]); uint64_t lo = strtoull(argv[2], 0, 10), hi = strtoull(argv[3], 0, 10);
    const uint32_t *q3a = k.q3a, *q3b = k.q3b, *q3c = k.q3c, *q2a = k.q2a, *q2b = k.q2b, *q1 = k.q1, *b1 = k.b1, *bc = k.bc;
    for (uint64_t op = 0; op < hi && op < k.nops; op++) {
        uint8_t ty = k.types[op]; int p = op >= lo; uint32_t c = 0; int hc = 0;
        if (ty & 0x80) { c = *bc++; hc = 1; }
        uint32_t a=0,b=0,d=0,e=0;
        switch (ty & 0x70) { case 0x30: a=*q3a++; b=*q3b++; d=*q3c++; break; case 0x20: a=*q2a++; b=*q2b++; break; case 0x10: a=*q1++; break; case 0x50: a=*q1++; e=*b1++; break; case 0x40: e=*b1++; break; }
        if (!p) continue;
        const char *n = "?";
        switch (ty) { case OP_POP: n="POP"; break; case OP_TAG: n="TAG"; break; case OP_Z: case OP_ZIF: n="Z"; break; case OP_X: case OP_XIF: n="X"; break; case OP_R: n="R"; break; case OP_HMR: n="HMR"; break; case OP_CZ: case OP_CZIF: n="CZ"; break; case OP_CX: case OP_CXIF: n="CX"; break; case OP_SWAP: case OP_SWAPIF: n="SWAP"; break; case OP_CCZ: n="CCZ"; break; case OP_CCX: n="CCX"; break; case OP_CSWAP: n="CSWAP"; break; case OP_BS0: n="BS0"; break; case OP_BS1: n="BS1"; break; case OP_BINV: case OP_BINVIF: n="BINV"; break; case OP_NEG: case OP_NEGIF: n="NEG"; break; case OP_PUSH: n="PUSH"; break; }
        printf("%llu %s", (unsigned long long)op, n);
        switch (ty & 0x70) { case 0x30: printf(" q%u q%u q%u", a,b,d); break; case 0x20: printf(" q%u q%u", a,b); break; case 0x10: printf(" q%u", a); break; case 0x50: printf(" q%u b%u", a,e); break; case 0x40: printf(" b%u", e); break; }
        if (hc) printf(" if b%u", c);
        printf("\n");
    }
}
