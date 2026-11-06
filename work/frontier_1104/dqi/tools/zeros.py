#!/usr/bin/env python3
src=open('tools/census.c').read()
start=src.index('if (gate_idx % nparts == part) {')
end=src.index('if (ty == OP_CCX || ty == OP_CCXIF) { for (int i = 0; i < W; i++) C[i] ^= A[i]')
new='''{
                int nzw=0; for (uint32_t i=0;i<nq;i++) if(is_zero(QW(i))) nzw++;
                int tz=is_zero(QW(c));
                fprintf(out,"%llu\\t%ld\\t%x\\t%u\\t%u\\t%u\\t%d\\t%d\\n",(unsigned long long)op,gate_idx,ty,a,b,c,nzw,tz);
            }
            '''
src=src[:start]+new+src[end:]
open('tools/zeros.c','w').write(src)
