# VQCC Top-10 Campaign — Autonomous R&D Plan

Stand: 2026-11-11 · Ziel: Kaggle **Top-100 (sofort)** → **Top-10 (bis Deadline 2027-01-13)**

## ⚡ UPDATE 2026-11-11 (autonom, ultracode-Mandat)
### Banked: Score **25.29522** bestätigt (ref 58232773) → **Rang 493/2830** (war 573 @ 25.22235)
- Picks: invsqrt `a15b0d73` **22.1109** (war im Pool, NIE verifiziert → jetzt offiziell PASS) · dqi `e9f54be3` 65.2264 (Bytes unverändert, kein Salt-Risiko) · chem `b0cc7e3c` **11.2224** (frisch aus manwithacat-Pool, Apache-2.0)
- Vorhersage 25.29523 → LB 25.29522 ✓ (11/11 exakte Trefferquote)
- **Feld bewegt sich:** Top-100-Cutoff stieg in 24h von 25.35072 auf **25.40112**. Neuer Bedarf bei fixem inv+chem: **dqi ≥ 66.05** (+1.26 % ≈ ~5.000 mean Toffolis gespart).
- Guard-Sweep (Builder-Knob): TOT (889–905, Optimum=Original). Public-Frontier dqi = 65.2267 ≈ unser 65.2264 → **Top 100 nur via NOVEL dqi oder Merge**.

### Aktiv: kmx_agent.py (jetzt lokal unter work/archive/, nicht im Git; usergelieferter Verifier-Optimierer) auf unserem DQI
- Selftest 6/6 OK · RAM 128 GB ausreichend
- **invsqrt-Run: NEGATIV** — Toffolis 1381→1381, Q=62 voll (22 In + 40 Scratch-Peak). Circuit ist tight; deterministische Pässe finden nichts.
- **DQI-Run läuft** (bg): Domäne = 840 Input-Qubits (S0..S69 × 12 Bit) + 52 Scratch (q840..q891) + 49140 Output-Bits (E0..E4094). Sample-Domäne 65.536 Lanes; Soundness-Nachweis via offiziellem Multi-Salt-Verifier vor Submit (Safety-Net).
- **Census e9f54be3:** CCX 382.190 / CCZ 1.384 / CSWAP 12.012 (395.586 gezählt) · HMR 78.990 · R 56.223 · 301.621 exakte Triple-Repeats (76 %), davon **111.308 innerhalb 10k Ops** = MBU-Kandidaten (Uncompute-Ketten → HMR + klassisch bedingte Phasenkorrektur, 0 gezählte Toffolis).
- Zielrechnung: ≥ ~5.000 Toffolis sparen (≈4,5 % der 111k Kandidaten) → dqi ≥ 66.05 → GM ≥ 25.40.
- Verifikation vorbereitet: `work/frontier_1110/opt/verify_dqi_opt.py` (Haupt-Salt 'notebook-verification' + 3 Extra-Salts).

### Outreach — ausgeführt 2026-11-11 ~12:30 UTC
- **ENTDECKT:** Discussion #755075 „Seeking collaboration / merger" ist UNSER Topic (9 Tage alt, alte Zahlen). crackercoder hat merger-offen geantwortet; somejoint hat ihn angesehen.
- **#3 GESANDT** (Reply-Kommentar via ego-browser) · **Topic AKTUALISIERT & PUBLIZIERT** (Rang ~493 @ 25.295, 11/11 exakt, Verifier-Optimierer, explizit nach stärkerer DQI-Line).
- **#1 NICHT GESANDT** (User-Entscheidung): Contact = E-Mail mit sichtbarer Adresse; Rang-9-Team hat wenig Merge-Anreiz → Topic + Thread reichen.
- **LB-Dynamik:** Top-10-Cutoff 27.32 · SomeJoint Rang 9 @ 27.34 (+0.34/Tag) · Top-100 25.40112 (steigt täglich) · manwithacat-Pool-Adoption-Welle hebt hunderte Teams +0.05..+0.4.

### Lern-Artefakte (fertig)
- `work/frontier_1110/hello_world_circuit.py` — 2-Bit-Addierer, selbstprüfend, 16/16 OK, 2 Toffolis
- `work/frontier_1110/lernen_stufe0-2.md` — Stufe 0→2 mit kickmix-Templates + Ressourcen

## Confirmed State (harte Zahlen)
- Zuletzt eingereicht (bestätigt): **24.94** (`work/frontier_scan/qvc010_build/PUBLIC_SCORE.json`, ref 58048913, 2026-11-06)
- Fertiges, verifiziertes Portfolio: **25.15** → `work/frontier_1109/build/submission.zip`
  - 18 Zip-Member, alle SHA-256 matchen `build_manifest.json` ✓
  - invsqrt **21.78** / dqi **65.23** / chem **11.20** → GM **25.1509** ✓
  - dqi 5-Salt-Check: 3× sauber, 2× mit 1 Fehler (Ratio 64.93) — Status bleibt **PASS**
- Top-10 Cutoff (Report 2026-11-09): **~27.03** · Public-Median ~21 · nur ~29 Teams ≥23
- **Gap zu Top-10: ~2 Punkte (~7.5 % overall)**

### UPDATE 2026-11-10 (autonomer invsqrt-Sweep)
- **Neues invsqrt-Best:** Circuit `26ebf39d` (aus heliosli `qcc-circuits-live`) offiziell verifiziert:
  PASS, 200,540,928 Shots, 62 Qubits, Cost 94537.60, **Ratio 21.9677** (war 21.7816). Deterministisch → sicher.
- Neues Portfolio-GM mit 21.9677/65.2264/11.1982 ≈ **25.22** (+0.07 über 25.15).
- Fortsetzungs-Sweep prüft die restlichen 5 unseen invsqrt gegen Bar 21.9677 (bg job). Danach EIN Rebuild:
  `build_zip.py 26ebf39d e9f54be3 0b88319e <outdir>` (oder besserer invsqrt-Präfix).
- **Ehrliche Lücke:** Curation bringt uns auf ~25.2–25.3 (Top-100/Top-20 gesichert). Top-10 (27.0) braucht
  ~+7 % overall = Novel-Work auf ≥1 Benchmark. Größter unbekannter Hebel: **R-Reset-Frage (#755302)** —
  wenn Reset statt Uncomputation erlaubt, fallen DQI-Kosten massiv. Noch ungeklärt.

### BANKED 2026-11-10 — neues submittierbares Portfolio **~25.22**
- `work/frontier_1109/build_2522/submission.zip` (28 MB, 18 Member, 0 SHA-Fehler) ✓
- Picks: invsqrt `26ebf39d` (21.9677, offiziell verifiziert) · dqi `e9f54be3` (65.2264 clean / 64.9282 err) · chem `0b88319e` (11.1982)
- Erwartetes GM: **25.2224** (clean dqi-Salze) … **25.1839** (dqi-Fehler-Draw) → **+0.24…+0.28** über eingereichtes 24.94
- Rebuild-Kommando (reproduzierbar): `.venv-qvc/bin/python work/frontier_1109/scripts/build_zip.py 26ebf39d e9f54be3 0b88319e work/frontier_1109/build_2522`
- Fortsetzungs-Sweep (bg) läuft noch; bei besserem invsqrt → 1× Rebuild nachziehen.

## Strategy (dominant Pattern der Top-Teams, Report §10)
Best-of-Public-Curation + inkrementelle Novel-Tweaks. Die Frontier ist eine dokumentierte Treppe
(`frontier_steps.csv`). `Overall = (R_inv·R_dqi·R_chem)^⅓` → x % auf EINE Benchmark = x % overall.
Fokus schlägt Breite.

## Levers (priorisiert)
1. **[GRATIS]** 25.15 einreichen (+0.21 über 24.94) → sichert Top-100/Top-20. **BEREIT.**
2. **[AUTONOM, läuft]** invsqrt-Sweep: 6 lokale unseen + `--download` für neue Public.
   invsqrt ist deterministisch (jede Eingabe lokal getestet, LB-Kosten = lokale Kosten, kein Salt-Risiko).
3. **[CODE]** Oracle auf dqi+chem erweitern → 9 dqi + 1 chem unseen sweepen (best-of-public auf allen Tasks).
4. **[NOVEL]** invsqrt „3-product lookup finish“ (−40 Toffolis → Ratio ×1.025 → Score ×1.0084).
   Dead-Ends-Note: „braucht eine strukturierte Konstruktion, keinen generischen Solver“.
5. **[REGELN, unklar]** R-Reset-Frage (Discussion #755302): wenn Reset statt Uncomputation erlaubt →
   massive DQI-Einsparung. Noch ungeklärt — nicht darauf bauen, aber beobachten.

## Risken
- **dqi salzabhängig:** 2/5 Salze ziehen 1 Fehler (64.93 statt 65.23). Kein Total-Fail (PASS), aber
  erwartetes GM liegt zwischen **25.11 und 25.15** je nach LB-Salt-Draw.
- **Private LB** nutzt andere 50 % Testdaten + andere Salts → Rang kann sich verschieben.
- **Deadline:** Report sagt Merger-Deadline **2027-01-13**; User schrieb „20.11“ → klären.

## Blockiert auf User (harte Grenzen)
- **Kaggle-Credentials zum Submit.** `~/.kaggle/access_token` (Downloads) vorhanden, aber ich greife
  Zugangsdaten nicht ohne explizite Freigabe an und mache keine Deployment-Aktion (Submit) ungefragt.
- **Deadline-Bestätigung** (2027-01-13 vs „20.11“).

## Status 2026-11-10 (live)
### Erledigt
- [x] **SUBMIT qvc-011** (build_2522, ~25.22) → Kaggle **ref 58195670**, 2026-11-10 ~09:40 UTC, Status PENDING→Score. (Limits: 4 frei heute.)
- [x] invsqrt-Sweep #1: `26ebf39d` (21.9677) offiziell verifiziert + adoptiert (heliosli live).
- [x] **chem-Win:** unseen `e5df79ad` offiziell PASS **11.2042** (Bar war 11.1982) → +0.05 % chem ≈ +0.004 GM. Im nächsten Rebuild adoptieren.
- [x] Track-C-Bug gefixt: `verify_one.py` löst relative Locator-Pfade jetzt gegen ROOT auf (run_verify.py nutzt cwd=/tmp). Stale EXC-Results gelöscht.
- [x] **R-Reset aufgelöst** (Subagent): MBUC/del_and ist LEGAL (Regeltext+Verifier+Google-Referenz). `del_and`=0 Toffolis. ABER großer DQI-Hebel (Inverse-Overhead −12.3 %) ist **architektonisch + blockiert durch fehlenden privaten Builder-Source** (Report A; atakan-Kernel = nur Readout-Edit-Layer).

### Job-Status (2026-11-10)
| Track | Ergebnis |
|---|---|
| Submit qvc-011 (ref 58195670) | ✅ **COMPLETE, public 25.22235** (clean dqi-Draw) |
| invsqrt-Sweep #1 | ✅ `26ebf39d` 21.9677 adoptiert (in qvc-011) |
| invsqrt-cont (5 unseen) | ✅ **Pool vollständig durchgeprüft (16/16, kept=0)** → 21.9677 ist Pool-Best |
| chem unseen | ✅ `e5df79ad` 11.2042 (Bar 11.1982) → +0.004 GM, **HELD** bis del_and-Audit |
| dqi-curation (9 unseen) | ✅ **kein Adoption**: bestes `368d2d1c` 65.2265 vs `e9f54be3` 65.2264 = +0.0002 (~1 mean Toffoli, Single-Salt); Byte-Wechsel würde sauberen LB-Draw neu würfeln → dqi bleibt `e9f54be3` |
| chem del_and | ✅ **NEGATIV (hohe Konfidenz):** ΔT=0, Circuit nutzt jede legale del_and schon; optimistischer Prototyp gebaut→offizieller Precheck FAIL. Echter Hebel liegt bei DQI. |
| Merger/Source | ✅ Subagent fertig — Befunde unten |
| chem Winkel-Compiler | ✅ **NEGATIV (hohe Konfidenz):** keine lokale Alternative schlägt helioslis 3006 CCX (emit_j5 +12 %, rank_parity +30 %, borrowed +29 %). Compiler-Lever erschöpft. |

## 🎯 ZIEL-KORREKTUR (2026-11-10, User-Entscheidung)
- **Echter LB-Platz: 573 / 2783** (Score 25.22235, Team "Tobias Oberrauch"/tobeetaylor, 10 Subs). NICHT ~90 (frühere Schätzung falsch).
- **Neues Ziel bis 20.11.: TOP 100** (nicht Top 10). Top 100 = Score **25.35072** (Rank 100, Qompaqt). Gap = **+0.128 GM**.
- **Feld extrem dicht:** 1004 Teams ≥25.0; Ranks 400–600 spannen nur 0.02 GM. Top-10-Cutoff 27.11782 (nur 12 Teams ≥27.0). Cutoff kann steigen (andere verbessern sich) → **Puffer anpeilen ~25.40**.
- **Was Top 100 braucht:** GM=(inv·dqi·chem)^⅓. Bei inv=21.9677, chem=11.2042 (held): dqi muss **66.15** (für 25.35) bzw. **~66.6** (für 25.40 Puffer) erreichen = **+1.5…+2.1 %** über unser dqi 65.23. Äquivalent: JEDE einzelne Aufgabe +1.5 % schließt die Lücke.
- **Pfad:** dqi ist der konkreteste Hebel, weil wir jetzt einen modifizierbaren Builder haben. Builder-Baseline 63.14 → muss ~66.2+ erreichen (+4.9 %, via Guard/Knobs + ggf. del_and/Pebbling). Guard-Sweep läuft (transform.py `guard`, NICHT cap900 — transform ändert 900→guard, Kandidat heißt "hybrid6-guard893").
- **Free Win (keine dqi-Bytes, kein Salt-Redraw):** held chem e5df79ad 11.2042 statt eingereichtes 11.1982 → +0.0045 GM (allein nicht genug, aber im Rebuild miteinbauen).

## SOLO-PHASE ABGESCHLOSSEN (2026-11-10)
Alle machbaren Solo-Hebel geprüft & banked/verworfen:
- Curation (invsqrt/dqi/chem): **Public-Frontier erreicht**, keine weiteren Gewinne.
- chem `del_and`: **ΔT=0** (Circuit schon optimal).
- chem Winkel-Compiler: **Alternativen alle schlechter** (heliosli ≈ ANF-Rang-Untergrenze).
- DQI Architektur/`del_and` (~74k Toffolis, der große Hebel): **blockiert ohne Builder-Source**.

**Solo-Obergrenze ≈ 25.22–25.23.** Eingereicht: **25.22235**. Gehaltener chem-Win `e5df79ad` (+0.0045 → 25.2269) bleibt gebündelt für den nächsten Rebuild (deterministisch, kein dqi-Redraw-Risiko).
**Top-10 (~27.0) erfordert den DQI-Builder.** Restliche Solo-Optionen (Factorization-Wechsel T↔λ_eff, Q brot 8→7) sind kleiner + unsicher und reichen allein nicht.

## DQI-GENERATOR-DURCHBRUCH (2026-11-10)
- **Open-Source-DQI-Generator gefunden + lokal lauffähig:** ahoirg „QCC Reproducible Circuit Assets v2" (`work/frontier_1104/downloads/intel_ahoirg_assets/qcc-reproducible-circuit-assets-v2/`) bündelt die SomeJoint-Carry-Decoder-Source (218 Dateien, SHA-gepinnt, Apache-Linie) + self-contained `build_dqi.py`.
- **Build reproduziert bitgenau** (SHA `fb2da4f2…` = expected) in ~90 s Source-Import. macOS-psutil-Bug in `build_dqi.py` Zeile 113 gefixt (`cpu_affinity` guard).
- **Baseline offiziell verifiziert: PASS, Ratio 63.14** (Q=893, mean T=407,444, max T=482,802, 0 Fehler, 63 s). → **unter** unserem compiled-Best `e9f54be3` (65.23, Q=892, mean T=395,303).
- **⚠️ KORRIGIERTE STRATEGIE (Explorer-Source-Mapping, 2026-11-10):**
  - **Die SomeJoint-Retained-Core-/Inverse-Overhead-Optimierungen sind in diesem Build SCHON installiert.** Alle 6 Prototypen (`retained_core_safe27`, `decode_inverse_retained`, `cache_support`, `forward_return`, `root_forward_return_v3`, `replay_erase`) sind live im 63.14-Circuit — keine ungenutzten Reserven. Der „+12 % Inverse-Overhead" stammt aus der Analyse der ANDEREN Linie (`e9f54be3`/ozertuu), NICHT aus dieser SomeJoint-norm5log7-Linie.
  - **Score-Modell DQI ≈ 1.1913 × Q² × T_mean** (aus 2 Datenpunkten gefit). ⇒ Q-Zuwachs wird **doppelt** bestraft; die exposed Knobs (ceiling 889→900 [schon erhöht], `norm_cache.FORCE`, `keep`, `forward_cache_shift`) handeln fast nur Q↔T am Pareto-Knie.
  - **Unser Bestes dqi (65.23) hat KEINE Source** (atakan-Edit-Layer auf ozertuu-V70). Die Source, die wir haben (63.14), ist schwächer. Um den Builder einzusetzen, müssen wir 63.14 per NOVELLER Arbeit über 65.23 drücken — Research-Aufwand, ungewisser Ertrag, 10 Tage.
  - **Bottom line:** Builder = echte Plattform für neuartige Optimierung (del_and-Patterns, neues Pebbling, Factorization), aber **kein sofortiger Win** und **Top-10 (dqi≈80) damit solo realistisch nicht erreichbar**. Merger bleibt der stärkere Pfad (jemand mit stärkerer Base: SomeJoint privat 25.717, oder ozertuu-Source hinter 65.23).
- **Bottom graph:** `playbook/kit/decoder/final_decoder/decode.py` `decode(b,S,E)` :262-273 (Forward+Backhalf, alle Region-Marks). Backhalf-Converter: `prior/decode_backhalf_q7.py`. Exposed Knobs: `decode_owner_cap900.py` (ceiling), `norm_cache.FORCE`, `decode_inverse_retained.install(keep=)`, `forward_cache_shift.install(levels=)`.
- **Pro-Region-Messung:** Subklasse-Instrumentierung **korrupt den Scheduler** (Builder macht exakte Type-Checks → Q 893→900, T 482k→2.48M). `flame_chart_svg` auf dem offiziellen kmb gibt die Mark-Hierarchie (extract/synthesis/convert/scan/unconvert/unsynthesis/unextract + companion_* + inverse*/reverse* Unter-Marks) aber KEINE pro-Mark-Kosten. Saubere pro-Mark-Toffolis nur per Source-Edit (Counter in den Funktionen) — für später, falls wir diesen Builder optimieren. **Für die Strategie-Entscheidung ausreichend:** Inverse-Overhead sitzt im Reverse-Pass (unextract/unconvert/unsynthesis/companion_return) und ist dort bereits via Retained-Core optimiert.

**Curation-Fazit:** Alle 3 Tasks am Public-Frontier; Erträge abnehmend (chem +0.004, dqi/invsqrt ≈0). Reale Top-10-Gewinne kommen über (a) chem-del_and und/oder (b) DQI-Builder-Source via Merger.

## Merger/Source-Recherche (2026-11-10, Subagent)
- **Kein lokaler, lauffähiger DQI-Generator.** SomeJoint `b7ca9bce` (der 892Q-Buildern) ist jetzt **privat (404)**; syed `fc3ba816` binary-only; unser Bestes `e9f54be3` = Edit-Layer (braucht private Base). → **Merger ist der primäre Weg zum großen DQI-Hebel**, kein Solo-Rebuild.
- **Einzel-Hebel reicht NICHT für 27.0:** Inverse-Overhead (−12.3 % T) allein → dqi ×1.14 → overall **~26.35** (unter 27.0). Top-10 braucht **gestapelte Hebel** (inverse + de-pebbling [267k CCX] + caching + del_and) ODER eine stärkere geerbte Base via Merger. (dqi ≈ 79.97× nötig für 27.0.)
- **Top-Merger-Kandidaten (gerankt):**
  1. **SomeJoint (Agniv Banerjee)** — hält DEN 892Q-Builder + privaten Delta (LB 25.717 vs public 24.65). Höchste Ceiling, aber privat + unklare Bereitschaft.
  2. **ahoirg (Ali Haydar Özdağ)** — tiefstes SomeJoint-Source-Wissen außer Agniv; beste Brücke zum Builder.
  3. **crackercoder** — explizit **merger-offen** (hat auf #755075 geantwortet); bringt C-Bitparallelen-DQI-Sim + ANF/Toffoli-Uncompute-Tracer + code-only-chem-Generator; sucht selbst DQI-Konstruktion. **Höchste Bereitschaft + infra-komplementär.**
  4. syed3000 (891Q auf SomeJoint-Kit, hält ggf. Generator). 5. yoyobar (Frontier-DQI-Bytes + Product-Cache).
- **Empfehlung:** crackercoder ERST (schnellst, willigst, Infrastruktur beschleunigt unseren Hebel), SomeJoint + ahoirg parallel (höhere Ceiling). Outreach-Entwürfe (korrigiert auf 25.22) → siehe Report an User; Vollversion in Memory-Note.
- **Blocker:** Topics-CLI cappt bei 20 (nicht alle Discussions gescannt); crackercoders DQI-Source-Holding unbestätigt (als Infra-Partner behandeln, bis bestätigt).

### Ehrliche Top-10-Einschätzung
- Wir stehen auf der **Public-Frontier** (alle 3 Tasks ≈ Referenz). Curation bringt nur noch **+0.004…+0.07** pro Fund (abnehmend).
- Gap zu Top-10 (~27.0) = ~1.8 Pkt (~7 %). Die großen Hebel sind **architektonisch** und brauchen Builder-Source, die wir (v. a. für dqi) nicht haben.
- **Machbarste Novel-Hebel:** (1) chem `del_and`/Loader-Tweaks — wir haben lokalen chem-Generator (`chem_emit_borrowed.py`, `chem_gluzdov_planner.py`), Verifikation schnell+deterministisch. (2) Surgery-Tweaks <5 %. (3) R-Reset-Superpositions-Ruling (#755302) beobachten.

### Next Actions
- [ ] dqi-curation + invsqrt-cont abwarten → bei Gewinn Portfolio neu bauen (invsqrt+chem+dqi best-of) + 1× Rebuild+Submit
- [ ] Submission-Score abrufen, wenn COMPLETE → `submission_log.jsonl`/PUBLIC_SCORE aktualisieren
- [ ] chem-`del_and`-Headroom auditieren (lokaler Generator) → machbarster Novel-Hebel
- [ ] vor JEDEM dqi-Byte-Change: ≥5 Salze re-auditieren (Process-Lesson)
