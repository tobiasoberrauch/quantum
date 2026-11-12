import sys, random
exec(open(str(__import__("pathlib").Path(__file__).resolve().parent / "fuzz_exact.py")).read().replace('if __name__ == "__main__":','if False:').replace("NQ, NB = 3, 2","NQ, NB = 5, 1"))
Q=5
def g(r):
    k=r.choice(["X","CX","CCX","SWAP","CSWAP","Z","CZ","CCZ","ZP","NEG"])
    qs=r.sample(range(Q),3)
    return {"X":f"X q{qs[0]}","CX":f"CX q{qs[0]} q{qs[1]}","CCX":f"CCX q{qs[0]} q{qs[1]} q{qs[2]}","SWAP":f"SWAP q{qs[0]} q{qs[1]}",
     "CSWAP":f"CSWAP q{qs[0]} q{qs[1]} q{qs[2]}","Z":f"Z q{qs[0]}","CZ":f"CZ q{qs[0]} q{qs[1]}","CCZ":f"CCZ q{qs[0]} q{qs[1]} q{qs[2]}",
     "ZP":f"Z_POW q{qs[0]} {r.choice(['0.5','-0.5','0.25','1.5','0.125'])}","NEG":"NEG"}[k]
r=random.Random(int(sys.argv[1])); pr=nt=0
for it in range(int(sys.argv[2])):
    a=[g(r) for _ in range(r.randrange(0,9))]
    c=list(a)
    for _ in range(r.randrange(0,3)):
        k=r.randrange(4)
        if k==0 and c: del c[r.randrange(len(c))]
        elif k==1: c.insert(r.randrange(len(c)+1), g(r))
        elif k==2 and len(c)>1:
            i=r.randrange(len(c)-1); c[i],c[i+1]=c[i+1],c[i]
        else:
            i=r.randrange(len(c)+1); s=g(r); c[i:i]=[s,s]
    oa,oc=m.parse_lines(a),m.parse_lines(c)
    st,_=m.check_exact(oa,oc,0,set())
    if st=="proved":
        pr+=1
        if not equiv(oa,oc,set(),0): print("UNSOUND",a,c)
print("proved",pr)
