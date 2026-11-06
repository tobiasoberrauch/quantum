"""Erzeugt learn/03_erklaerung.html (R(ε)-Kurve wird exakt berechnet)."""
import math
from pathlib import Path

R = lambda e: math.log(2) / -math.log(0.5 + 2 * math.sqrt(e))
X0, X1, Y0, Y1 = 70, 600, 250, 30          # Plotfläche
EMAX, RMIN, RMAX = 0.005, 1.0, 1.6
px = lambda e: X0 + (X1 - X0) * e / EMAX
py = lambda r: Y0 - (Y0 - Y1) * (r - RMIN) / (RMAX - RMIN)
pts = " ".join(f"{px(e):.1f},{py(R(e)):.1f}" for e in [i * EMAX / 400 for i in range(401)])
EF = 0.000866
assert abs(R(EF) - 1.19126) < 1e-3

xt = "".join(
    f'<line x1="{px(e):.1f}" y1="{Y0}" x2="{px(e):.1f}" y2="{Y0+5}" class="ax"/>'
    f'<text x="{px(e):.1f}" y="{Y0+20}" class="tk" text-anchor="middle">{e:g}</text>'
    for e in [0, 0.001, 0.002, 0.003, 0.004, 0.005])
yt = "".join(
    f'<line x1="{X0}" y1="{py(r):.1f}" x2="{X1}" y2="{py(r):.1f}" class="grid"/>'
    f'<text x="{X0-8}" y="{py(r)+4:.1f}" class="tk" text-anchor="end">{r:.1f}</text>'
    for r in [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6])
rcurve = f"""<svg viewBox="0 0 640 305" role="img" aria-label="R von epsilon plus">
{yt}{xt}
<line x1="{X0}" y1="{Y0}" x2="{X1}" y2="{Y0}" class="ax"/><line x1="{X0}" y1="{Y1}" x2="{X0}" y2="{Y0}" class="ax"/>
<polyline points="{pts}" fill="none" stroke="var(--ink)" stroke-width="2.2"/>
<line x1="{px(EF):.1f}" y1="{py(R(EF)):.1f}" x2="{px(EF):.1f}" y2="{Y0}" stroke="var(--acc)" stroke-dasharray="4 3"/>
<line x1="{X0}" y1="{py(R(EF)):.1f}" x2="{px(EF):.1f}" y2="{py(R(EF)):.1f}" stroke="var(--acc)" stroke-dasharray="4 3"/>
<circle cx="{px(EF):.1f}" cy="{py(R(EF)):.1f}" r="5" fill="var(--acc)"/>
<text x="{px(EF)+10:.1f}" y="{py(R(EF))-10:.1f}" class="lab acc">Floor: R ≈ 1,191 bei ε₊ ≈ 0,000866 (0 beobachtete Fehler)</text>
<text x="{px(0.002)-10:.1f}" y="{py(R(0.002))-10:.1f}" class="tk" text-anchor="end">ε₊ = 0,002 → R ≈ {f"{R(0.002):.3f}".replace(".", ",")}</text>
<circle cx="{px(0.002):.1f}" cy="{py(R(0.002)):.1f}" r="3.5" fill="var(--ink)"/>
<text x="{(X0+X1)/2}" y="{Y0+40}" class="lab" text-anchor="middle">ε₊ (obere Konfidenzgrenze der Decoder-Fehlerrate)</text>
<text x="18" y="{(Y0+Y1)/2}" class="lab" transform="rotate(-90 18 {(Y0+Y1)/2})" text-anchor="middle">Strafe R(ε₊)</text>
</svg>"""

html = Path(__file__).with_name("_03_template.html").read_text(encoding="utf-8")
html = html.replace("{{RCURVE}}", rcurve)
Path(__file__).with_name("03_erklaerung.html").write_text(html, encoding="utf-8")
print("ok", len(html))
