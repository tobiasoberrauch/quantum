#!/usr/bin/env python3
# Patch census.c into rank sampler
import re
src=open('tools/census.c').read()
# replace per-gate analysis by rank sampling
start=src.index('if (gate_idx % nparts == part) {')
end=src.index('if (ty == OP_CCX || ty == OP_CCXIF) { for (int i = 0; i < W; i++) C[i] ^= A[i]')
new='''if (gate_idx % nparts == part) {
                build_basis(-1,-1,-1);
                int nzw=0; for (uint32_t i=0;i<nq;i++) if(!is_zero(QW(i))) nzw++;
                // rank without const: nbasis includes all-ones vector
                fprintf(out,"%llu\\t%ld\\t%d\\t%d\\n",(unsigned long long)op,gate_idx,nzw,nbasis-1);
            }
            '''
src=src[:start]+new+src[end:]
open('tools/rankscan.c','w').write(src)
