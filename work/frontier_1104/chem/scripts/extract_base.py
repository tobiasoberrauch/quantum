"""Extract the best public dfthcsos members (heliosli live) into the lane's base dir."""
import sys, zipfile, os
src, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(src) as z:
    for n in z.namelist():
        if n.startswith('dfthcsos__'):
            with open(os.path.join(out, n.split('__', 1)[1]), 'wb') as f:
                f.write(z.read(n))
