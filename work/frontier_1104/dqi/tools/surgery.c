// surgery base.kmb edits.txt out.kmb
// edits.txt lines sorted by op: "<op> <n> <ty a b c> ..." each replacement op is: "CX a b" / "X a" / "Z a" / "CZ a b" / "CCX a b c" / "DROP"
// Written as: op TAB items separated by ';' e.g. "123\tCX 5 7;X 7"
#include "kmb.h"
#include <assert.h>
typedef struct { uint8_t *d; size_t n, cap; } B8; typedef struct { uint32_t *d; size_t n, cap; } B32;
static void p8(B8 *b, uint8_t v) { if (b->n == b->cap) { b->cap = b->cap ? b->cap * 2 : 1 << 20; b->d = realloc(b->d, b->cap); } b->d[b->n++] = v; }
static void p32(B32 *b, uint32_t v) { if (b->n == b->cap) { b->cap = b->cap ? b->cap * 2 : 1 << 20; b->d = realloc(b->d, b->cap * 4); } b->d[b->n++] = v; }
static void wpkt(FILE *f, uint64_t ty, const void *d, uint64_t len) { fwrite(&ty, 8, 1, f); fwrite(&len, 8, 1, f); if (len) fwrite(d, 1, len, f); }
int main(int argc, char **argv) {
    Kmb k; kmb_open(&k, argv[1]);
    B8 types = {0}; B32 q3a = {0}, q3b = {0}, q3c = {0}, q2a = {0}, q2b = {0}, q1 = {0}, b1 = {0}, bc = {0};
    FILE *e = fopen(argv[2], "r"); char line[1 << 16]; uint64_t next = UINT64_MAX; char *items = 0;
    #define READ_NEXT() do { next = UINT64_MAX; while (fgets(line, sizeof line, e)) { char *tab = strchr(line, '\t'); if (!tab) continue; *tab = 0; next = strtoull(line, 0, 10); items = tab + 1; break; } } while (0)
    READ_NEXT();
    const uint32_t *a3 = k.q3a, *b3 = k.q3b, *c3 = k.q3c, *a2 = k.q2a, *b2 = k.q2b, *a1 = k.q1, *bb = k.b1, *cc = k.bc;
    long replaced = 0;
    for (uint64_t op = 0; op < k.nops; op++) {
        uint8_t ty = k.types[op];
        uint32_t c = 0, x = 0, y = 0, z = 0, bt = 0;
        if (ty & 0x80) c = *cc++;
        switch (ty & 0x70) { case 0x30: x = *a3++; y = *b3++; z = *c3++; break; case 0x20: x = *a2++; y = *b2++; break; case 0x10: x = *a1++; break; case 0x50: x = *a1++; bt = *bb++; break; case 0x40: bt = *bb++; break; }
        if (op == next) {
            replaced++;
            if (ty & 0x80) { fprintf(stderr, "edit on conditional op %llu\n", (unsigned long long)op); return 2; }
            char *s = strtok(items, ";\n");
            while (s) {
                char nm[16]; unsigned u = 0, v = 0, w = 0, b0 = 0; int n = sscanf(s, "%15s %u %u %u", nm, &u, &v, &w); (void)n;
                if (!strcmp(nm, "CX")) { p8(&types, OP_CX); p32(&q2a, u); p32(&q2b, v); }
                else if (!strcmp(nm, "CZ")) { p8(&types, OP_CZ); p32(&q2a, u); p32(&q2b, v); }
                else if (!strcmp(nm, "SWAP")) { p8(&types, OP_SWAP); p32(&q2a, u); p32(&q2b, v); }
                else if (!strcmp(nm, "X")) { p8(&types, OP_X); p32(&q1, u); }
                else if (!strcmp(nm, "Z")) { p8(&types, OP_Z); p32(&q1, u); }
                else if (!strcmp(nm, "CCX")) { p8(&types, OP_CCX); p32(&q3a, u); p32(&q3b, v); p32(&q3c, w); }
                else if (!strcmp(nm, "CZIF")) { sscanf(s, "%15s %u %u %u", nm, &u, &v, &b0); p8(&types, OP_CZIF); p32(&q2a, u); p32(&q2b, v); p32(&bc, b0); }
                else if (!strcmp(nm, "ZIF")) { sscanf(s, "%15s %u %u", nm, &u, &b0); p8(&types, OP_ZIF); p32(&q1, u); p32(&bc, b0); }
                else if (!strcmp(nm, "HMR")) { sscanf(s, "%15s %u %u", nm, &u, &b0); p8(&types, OP_HMR); p32(&q1, u); p32(&b1, b0); }
                else if (!strcmp(nm, "DROP")) { }
                else { fprintf(stderr, "bad item %s\n", s); return 2; }
                s = strtok(0, ";\n");
            }
            READ_NEXT();
            continue;
        }
        p8(&types, ty);
        if (ty & 0x80) p32(&bc, c);
        switch (ty & 0x70) { case 0x30: p32(&q3a, x); p32(&q3b, y); p32(&q3c, z); break; case 0x20: p32(&q2a, x); p32(&q2b, y); break; case 0x10: p32(&q1, x); break; case 0x50: p32(&q1, x); p32(&b1, bt); break; case 0x40: p32(&b1, bt); break; }
    }
    if (next != UINT64_MAX) { fprintf(stderr, "unconsumed edits at %llu\n", (unsigned long long)next); return 2; }
    FILE *o = fopen(argv[3], "wb");
    uint8_t hdr[104]; memcpy(hdr, k.map, 104);
    uint64_t h[9] = { types.n, q3a.n, q2a.n, q1.n, b1.n, bc.n, k.na, k.nt, k.ntc };
    memcpy(hdr + 32, h, 72);
    fwrite(hdr, 1, 104, o);
    fwrite(k.map + 104, 1, k.reg_end - 104, o);
    wpkt(o, 1, types.d, types.n); wpkt(o, 2, q3a.d, q3a.n * 4); wpkt(o, 3, q3b.d, q3b.n * 4); wpkt(o, 4, q3c.d, q3c.n * 4);
    wpkt(o, 5, q2a.d, q2a.n * 4); wpkt(o, 6, q2b.d, q2b.n * 4); wpkt(o, 7, q1.d, q1.n * 4); wpkt(o, 8, b1.d, b1.n * 4); wpkt(o, 9, bc.d, bc.n * 4);
    // remaining packets (angle, tags) verbatim: find by walking
    size_t off = k.reg_end; for (int i = 0; i < 9; i++) { uint64_t l; memcpy(&l, k.map + off + 8, 8); off += 16 + l; }
    fwrite(k.map + off, 1, k.size - off, o);
    fclose(o);
    fprintf(stderr, "replaced=%ld ops=%zu n3=%zu n2=%zu n1=%zu nb1=%zu nc=%zu\n", replaced, types.n, q3a.n, q2a.n, q1.n, b1.n, bc.n);
    return 0;
}
