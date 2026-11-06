// Minimal .kmb v2 reader (mmap), flat iteration, shared by analysis tools.
#pragma once
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
typedef struct {
    const uint8_t *map; size_t size;
    uint32_t nq, nb, nr; uint64_t nops, n3, n2, n1, nb1, nc, na, nt, ntc;
    const uint8_t *types; const uint32_t *q3a, *q3b, *q3c, *q2a, *q2b, *q1, *b1, *bc;
    size_t off_types; size_t reg_end;
} Kmb;
static inline void kmb_open(Kmb *k, const char *path) {
    int fd = open(path, O_RDONLY); if (fd < 0) { perror(path); exit(2); }
    struct stat st; fstat(fd, &st); k->size = st.st_size;
    k->map = (const uint8_t *)mmap(0, k->size, PROT_READ, MAP_SHARED, fd, 0);
    if (k->map == MAP_FAILED) { perror("mmap"); exit(2); }
    close(fd);
    const uint8_t *m = k->map;
    memcpy(&k->nq, m + 20, 4); memcpy(&k->nb, m + 24, 4); memcpy(&k->nr, m + 28, 4);
    uint64_t h[9]; memcpy(h, m + 32, 72);
    k->nops = h[0]; k->n3 = h[1]; k->n2 = h[2]; k->n1 = h[3]; k->nb1 = h[4]; k->nc = h[5]; k->na = h[6]; k->nt = h[7]; k->ntc = h[8];
    size_t off = 104;
    for (uint32_t i = 0; i < k->nr; i++) { uint64_t t, l; memcpy(&t, m + off, 8); memcpy(&l, m + off + 8, 8); if (t != 0) { fprintf(stderr, "bad reg pkt\n"); exit(2);} off += 16 + l; }
    k->reg_end = off; k->off_types = off;
    const void **slots[] = {(const void **)&k->types, (const void **)&k->q3a, (const void **)&k->q3b, (const void **)&k->q3c, (const void **)&k->q2a, (const void **)&k->q2b, (const void **)&k->q1, (const void **)&k->b1, (const void **)&k->bc};
    for (int i = 0; i < 9; i++) { uint64_t t, l; memcpy(&t, m + off, 8); memcpy(&l, m + off + 8, 8); if ((int)t != i + 1) { fprintf(stderr, "bad pkt order %d %llu\n", i, (unsigned long long)t); exit(2);} *slots[i] = m + off + 16; off += 16 + l; }
}
enum { OP_POP=0x01, OP_TAG=0x06, OP_Z=0x10, OP_ZIF=0x90, OP_X=0x11, OP_XIF=0x91, OP_R=0x12, OP_RIF=0x92, OP_HMR=0x50, OP_HMRIF=0xd0,
       OP_CZ=0x20, OP_CZIF=0xa0, OP_CX=0x21, OP_CXIF=0xa1, OP_SWAP=0x22, OP_SWAPIF=0xa2, OP_CCZ=0x30, OP_CCZIF=0xb0, OP_CCX=0x31, OP_CCXIF=0xb1,
       OP_CSWAP=0x32, OP_CSWAPIF=0xb2, OP_BS0=0x40, OP_BS0IF=0xc0, OP_BS1=0x41, OP_BS1IF=0xc1, OP_BINV=0x42, OP_BINVIF=0xc2, OP_NEG=0x00, OP_NEGIF=0x80, OP_PUSH=0x81 };
