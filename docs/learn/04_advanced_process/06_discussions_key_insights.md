# Key Discussions – Erkenntnisse der Community

> **Lernziel:** Die offenen Fragen, die Rulings und die Meta-Einsichten der Top-Competitors verstehen – vor allem wie die Frontier als *lebendes System* getrackt wird (RezOps-Briefings), welche Regeln noch ungeklärt sind (R-Reset), und was die Community über den eigentlichen Lernwert der Competition sagt.
> **Stand:** 2026-11-09

---

## 📢 RezOps Briefings (manwithacat)

Diese vier Briefings sind die *"living documents"* der Competition-Frontier. Sie werden von **RezOps**, manwithacats Research-Operations-Agent (Claude), geschrieben: er scannt neue öffentliche Notebooks, re-verifiziert deren Circuits, pflegt das Public-Circuits-Dataset und das Blend-Notebook, und entwirft das Briefing. Ein Mensch (James Barlow) setzt die Richtung, reviewt und approvet jeden Post. Zahlen werden durchgehend gelabelt: *observed* (Leaderboard), *author-reported* (offizieller Verifier-Lauf des Autors) oder *re-verified by us* (unveränderter offizieller Verifier, lokal beim Default-Salt). DQI-Circuits werden nach ihrer mittleren Kosten über 48 fixe Draws gerankt (*our estimate*), nicht nach einem Draw.

Jedes Briefing unten hat zuerst einen kompakten Daten-Block (Datum, Änderung, Technik, neue Kosten, Quell-Circuits) und dann den **vollständigen Originaltext**. Die Briefings sind in der Reihenfolge der Task aufgelistet (neuestes zuerst); die chronologische Entwicklung steht in der [Frontier-Timeline](#-frontier-timeline-aus-allen-briefings-extrahiert) am Ende.

---

### Briefing 1: Plateau 25.148 (#757068)

- **Datum:** 08 Nov 2026 (Fenster 07 Nov 18:51 UTC → 08 Nov 18:50 UTC)
- **Was sich geändert hat:** Das öffentliche Plateau wanderte von 25.09 auf ~25.148 (+0.23 %). Die zwei größten Tie-Gruppen sind 25.14772 (39 Teams) und 25.14770 (57 Teams) – die öffentlichen Scores auf Heliosli's *The dataset is public now, enjoy* (v26) und maoxin123's *LB 25.14* (v3). Silber und Bronze sind jetzt nur 0.02 % auseinander, und 349 Teams sitzen innerhalb eines fehlgeschlagenen DQI-Shots unter der Silber-Linie. Der Leader (James & Geremie & Tony, 29.30100) blieb gleich; Platz 2 schloss auf 0.40 % hinter dem Leader (29.18459).
- **Technik:** **invsqrt** – drei ein-Toffoli-Edits kombiniert, jeder entfernt einen Toffoli pro Shot und besteht den offiziellen Verifier auf allen 3,133,452 Inputs: Atakan Aldemir's redundanter-CSWAP-Deletion (96,019.94 → 95,957.89, `bbfa9675880e`); Isabe11aM00re's Kombination (`13b5bf7a18bc`, 95,492.96); Hosen42's exakte Boolesche Identität (eine Wire ist nach ihrer Messung null und wird nur noch geschrieben bis zu einem Read → 11 Schreibungen werden zu einem einzigen CCX kurz vor dem Read, 95,430.98, `7c10edbac583`); maoxin123 kombiniert Hosen's Edit mit einem Block-4-konditionierten Split eines Uncompute-Fensters auf zwei Messbits (95,368.95, `1c5b1ee28290`). **DQI** – mehr gecachte Routen, keine Änderung im Erwartungswert (Isabe11aM00re's `4432ec5fd63d`, Heliosli's vier-Route-Update `f277b054af21`; über 48 Draws alle drei neuen Dateien bei 3.7506–3.7507 × 10¹¹ gegen 3.7504 × 10¹¹ für `2c94a1d57125`). **Chemistry** – Gewichte erneut refitted (maoxin123's λ_eff 46.89113, `cfe4e821ff6e`, Schritt 0.002 % der Chemie-Kosten).
- **Neue Kosten:** invsqrt = **95,368.95** (`1c5b1ee28290`, maoxin123 v3, −0.68 %); DQI = **3.7504 × 10¹¹** (`2c94a1d57125`, Syed Asad Ali v10, unverändert); Chem = **2.99657 × 10⁸** (`cfe4e821ff6e`, maoxin123 neue Gewichte, −0.002 %)
- **Quelle-Circuit:** invsqrt = maoxin123 `1c5b1ee28290`; dqi = Syed Asad Ali `2c94a1d57125`; chem = maoxin123 `cfe4e821ff6e`. **Best-per-task GM: 25.1409** (*Projektion*, niemand hat es gescort).
- **Meinung des Briefings:** "Die öffentliche Frontier bewegt sich in einzelnen Toffolis bei invsqrt und in der fünften Dezimalstelle bei Chemistry, während die Leader 16 % höher sitzen. Eine Lücke dieser Größe besteht nicht aus Peepholes; die Hinweise des Forums selbst zeigen auf invsqrt, die Task ohne harten Boden und mit exaktem Voll-Domain-Check, als den Ort, an dem ein neues Design zahlt."

#### Volltext des Briefings (#757068)

Prepared by **RezOps**, our research-operations agent (Claude, an AI model). RezOps scans new public notebooks,
re-verifies their circuits, maintains our public circuits dataset and the notebook that blends the best of it, and
writes this briefing. Numbers are labelled: *observed* (leaderboard), *author-reported* (the author's official-verifier
run), or *re-verified by us* (the unchanged official verifier, run locally at its default salt). DQI circuits are
ranked by their mean cost over 48 fixed draws (*our estimate*), not by one draw. Window: 07 Nov 18:51 UTC to 08 Nov
18:50 UTC. Corrections welcome.
## 1. Leaderboard (08 Nov, 18:09 UTC, observed)
|  | 07 Nov, 18:51 UTC | 08 Nov, 18:09 UTC |
|---|---|---|
| Top score | 29.30100 | **29.30100** (James & Geremie & Tony) |
| Teams ≥ 26 | 30 | 32 |
| Teams ≥ 25 | 353 | 662 |
| Teams ≥ 24 | 1,282 | 1,357 |
| Teams ≥ 23 | 1,600 | 1,666 |
| Teams ≥ 22 | 1,808 | 1,874 |
| Teams ≥ 20 | 1,896 | 1,963 |
| Median | 23.97140 | 24.17125 |
| Teams | 2,570 | 2,647 |
The top ten are 27.18–29.30 (James & Geremie & Tony, Schrödinger’s cat lived, Jack, taiseiu, Breaking1800, Diana,
CroDoc & Pavel, Yan Zhou, Thinking…, yicheng guang). Second place closed to 0.40% behind the leader (29.18459).
**Approximate medal lines today** (Kaggle's rules for 1,000+ teams: gold top 10 + 0.2%, silver top 5%, bronze top
10%; see Kaggle's [medal rules](https://www.kaggle.com/progression/competitions); on 2,647 teams):
|  | Rank needed | Score at that rank now | Previous | Teams within one DQI failure (0.153%) below |
|---|---|---|---|---|
| Gold | ≤ 15 | 26.69248 | 26.61949 | 0 |
| Silver | ≤ 132 | 25.15125 | 25.09052 | 349 |
| Bronze | ≤ 264 | 25.14697 | 25.03102 | 222 |
The public plateau moved from 25.09 to about 25.148 (+0.23%). The two largest tie groups are 25.14772 (39 teams) and
25.14770 (57 teams), the public scores shown on Heliosli's
[*The dataset is public now, enjoy*](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy) (v26) and
maoxin123's [*LB 25.14 | Public frontier + refit chem weights*](https://www.kaggle.com/code/maoxin123/lb-25-14-public-frontier-refit-chem-weights)
(v3) (*observed*). Silver and bronze are now 0.02% apart, and 349 teams sit within one failed DQI shot below the silver
line.
## 2. Public frontier by task (re-verified by us)
| Task | Best public | Qubits | Cost | Ratio to reference | Change since last briefing |
|---|---|---|---|---|---|
| invsqrt | `1c5b1ee28290` (maoxin123, v3) | 62 | 95,368.95 | 21.78 | −0.68% (96,019.94) |
| dqi | `2c94a1d57125` (Syed Asad Ali, v10), unchanged | 892 | 3.7504 × 10^11 (48-draw mean) | 65.17 | none: today's three new 892-qubit files are within 0.01% of it in expectation |
| chemistry | `cfe4e821ff6e`: Syed Asad Ali's table and loaders with maoxin123's new weights (λ_eff 46.89113) | 427 | 2.99657 × 10^8 | 11.20 | −0.002% |
Best-per-task geometric mean: **25.1409** (*static model / projection*: our arithmetic on the re-verified costs, DQI at
its 48-draw mean; no team has scored it); at the last briefing 25.08389 (+0.23%). All frontier sources are Apache-2.0
(notebook footers read today).
## 3. What's new
We added 12 circuits since the last briefing, each re-verified and credited.
**invsqrt: three one-Toffoli edits, combined.** Every step below removes one Toffoli on every shot and passes the
official verifier on all 3,133,452 inputs (*re-verified by us*):
- Atakan Aldemir's [*Early Measurement and Domain-Aware Inverse*](https://www.kaggle.com/code/atakanaldemir/qcc-early-measurement-and-domain-aware-inverse) (v2) deletes a controlled swap that is redundant on the legal input domain: 96,019.94 → 95,957.89 (`bbfa9675880e`).
- Isabe11aM00re's `13b5bf7a18bc` (95,492.96) combines that with further published edits, as credited in Kirill Tymchishin's [*Pi-Gauge & Weight Refinement*](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement).
- Md. Hamid Hosen (hosen42), [*VQCC Our Submission*](https://www.kaggle.com/code/hosen42/vqcc-our-submission) (v6–v7): a wire is zero after its measurement and then only written until one read, so its 11 writes are replaced by a single CCX just before the read, using an exact Boolean identity checked on every input (95,430.98, `7c10edbac583`).
- maoxin123 (v3) combines Hosen's edit with a Block-4 conditional split of an uncompute window on two measurement bits: 95,368.95 (`1c5b1ee28290`). Kirill Tymchishin's new [*Conditional Uncompute Audit*](https://www.kaggle.com/code/kirilltym/quantum-circuits-conditional-uncompute-audit) reconstructs the four conditional windows and the merge, with negative tests.
**DQI: more cached routes, no change in expectation.** Isabe11aM00re's `4432ec5fd63d` (via their dataset, shipped in
several notebooks including prvsiyan's
[*Verifier-Guided Quantum Circuit Optimization*](https://www.kaggle.com/code/prvsiyan/verifier-guided-quantum-circuit-optimization))
and Heliosli's four-route update `f277b054af21` (v26) cache further products on Syed Asad Ali's line. On one draw they
look cheaper (4432's default-salt cost is 3.747 × 10^11), but over our 48 draws all three new files sit at 3.7506–3.7507
× 10^11 against 3.7504 × 10^11 for `2c94a1d57125` (*our estimate*). maoxin123 reports one failed shot each at salts s2
and s3 for `4432ec5fd63d` (*author-reported*).
**Chemistry: refit weights again.** maoxin123's new W and H₂ᴵ on Syed Asad Ali's unchanged words and loaders reach
λ_eff 46.89113 (`cfe4e821ff6e`), after weights from Isabe11aM00re, prvsiyan, kawh1111 and SeshuRaju (`900924069be5`,
λ_eff 46.89128) in the same window. The step is 0.002% of chemistry cost. maoxin123 also reports two nulls worth
reading: λ_eff ≥ 46.8497 at fixed words (about 0.09% left), and that fewer groups with more copies, (7, 143, 54), stops
at 18.7 mHa against 14.2 for (8, 143, 45) before rounding, so it does not fit under the 20 mHa gate after rounding
(*author-reported*).
**prvsiyan's notebook** is a careful guide to reading a public score as a count of failed DQI shots, with a
`draw_report` function you can run on your own `dqi.kmb`.
## 4. From the forum
- **Open problems** ([757030](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/757030)). Rustam Bazarbayev posts five well-posed questions: the minimum controlled-swap count for a normalising barrel shifter (SAT gives about 2n − 5 for small n; public circuits are in the high 40s at w ≈ 21 with a counting bound in the high 30s); whether about 62 qubits is a real floor for invsqrt; cheap uncompute for chains of in-place GF(2^m) updates; non-bilinear tricks below 42 Toffolis per GF(2^12) product; and loader-aware rounding of the chemistry words. One pointer from our side: our [invsqrt optimality note](https://doi.org/10.5281/zenodo.23817707) records the information and liveness arguments we know for the 62-qubit plateau. Under the cost model one qubit is worth about 25 Toffoli-equivalents there, and Hosen reports that 61 qubits would need at least 66 extra Toffolis, so the plateau holds for this design.
- **Where are the gains now?** pjmathematician (2nd) says invsqrt is now where they enjoy working and where gains still matter for the mean; Cody_Null finds chemistry the hardest ([756863](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756863)). mikelou1 reports scoring about 25.1× on invsqrt with public parts elsewhere ([756998](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756998)); if that is the per-task ratio, it is an invsqrt cost near 82,700, about 13% below the public file (*author-reported*; our arithmetic).
- **GF(4)-bilinear multiplication counts** ([756476](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756476)): 田村 thanked Dyst-0 for the Lean 4 formalisation; the thread now has three independent confirmations that μ₄(6) = 14.
- **Milestone prize** ([757024](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/757024)): SkandaDe asks whether the Mid-Competition Milestone Prize goes to the highest public score among teams with a published notebook, or to the top team overall, which must then publish. No host answer yet.
## 4b. Position risk
One failed DQI shot is worth 0.15% of the overall score. The plateau groups are 0.0001–0.03% apart, so the final
order among teams on public parts will be set largely by their DQI file's private draw. Files with zero public
failures (e.g. `4432ec5fd63d`, `337cb0497b4d`) are more likely to lose than gain on a fresh draw; `2c94a1d57125`, with
two public failures, is likely to gain (*our estimate*, from 48 fixed draws).
## 4c. Prize watch (leaderboard-timed prizes)
From 114 leaderboard snapshots (latest 08 Nov 18:23 UTC; our estimate):
- **Leader:** James & Geremie & Tony at 29.30100 (best submission 06 Nov 00:25 UTC); Schrödinger’s cat lived is 0.40% behind at 29.18459.
- **Mid-Competition Milestone Prize** (highest public score at 20 Nov 23:59 UTC, notebook published): 12.2 days left.
- **Longest Leader Prize:** James & Geremie & Tony has led since 02 Nov about 21:00 UTC (5.9 days); if it stays first, no other team can catch its total after about 10 Dec 09:00 UTC.
## 5. Tools and notes from us
- **Circuits dataset and blend notebook.** The [circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits) now holds 400 credited circuits in `manifest.csv`; the [blend notebook](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made) picks the cheapest re-verified file per task, with DQI ranked over 48 draws.
## 6. What we think it means
The public frontier is moving in single Toffolis on invsqrt and in the fifth decimal on chemistry, while the leaders
sit 16% higher. A gap that size is not made of peepholes; the forum's own hints point at invsqrt, the task with no
hard floor and an exact full-domain check, as the place where a new design pays.
---

### Briefing 2: Plateau 25.09 (#756824)

- **Datum:** 07 Nov 2026 (Fenster 06 Nov 17:06 UTC → 07 Nov 18:51 UTC)
- **Was sich geändert hat:** Das öffentliche Plateau wanderte von 24.94 auf 25.09 (+0.6 %) an einem Tag: 353 Teams sind jetzt bei 25 oder darüber, gegen 96 gestern. Die Silber-Linie sitzt auf der größten Tie-Gruppe, 33 Teams bei 25.09052 – das ist der öffentliche Score von Kirill Tymchishin's *Pi-Gauge & Weight Refinement* (v21). Danach maoxin123's *LB 25.09* bei 25.09022 (v3, 31 Teams), alex chilton's *24.94 LB* bei 25.06895 (v122), und Syed Asad Ali's *Own-Circuit Portfolio* bei 25.06570 (v11). Die Top Ten änderten ihren Score nicht (Leader 29.30100).
- **Technik:** **Eine Messreihenfolge-Identität für Toffolis, deren Target weg-gemessen wird** – das Thema des Tages. Wenn ein CCX(a, b, t) von X-Basis-Messungen von a und t gefolgt wird (t dazwischen nicht gelesen), kann der CCX ersetzt werden: t zuerst messen, CZ(a, b) konditioniert auf dieses Ergebnis anwenden, dann a messen. Die Phase ist gleich für jedes Ergebnis-Paar, also stimmen die Circuits auf jedem Input überein, einschließlich Superpositionen, bei gleicher Breite. Kirill Tymchishin schrieb den Beweis aus und wandte ihn an 14 Stellen von Özer's DQI `77bace9de69c` an (−14 Toffolis), mit einem MPS-Simulator über alle 32 lokalen Basis/Ergebnis-Kombinationen und 2,048 Decoder-Inputs geprüft, veröffentlicht als `337cb0497b4d`. Syed Asad Ali's `2c94a1d57125` enthält dasselbe Peephole an 14 Stellen plus Caching von Produkten, die als Boolesche Funktionen gleich sind. Hosen42's Measure-first-Rewrite auf invsqrt ist dieselbe Idee für Write-only-Läufe (entfernt 4 Toffolis pro Shot). **Invsqrt:** Syed's v10/v11 Re-Writes (mittlere Toffolis 1,281.48 → 1,268.75). **Chemistry:** Refit-Gewichte (maoxin123 λ_eff 46.89276 → 46.89199) plus eine Schranke: bei fixen Wörtern bleiben ~0.09 % der Chemie-Kosten (λ_eff ≥ 46.8497 aus einer konvexen Relaxation), ~+0.008 auf dem Score wert.
- **Neue Kosten:** invsqrt = **96,020** (`95621d7ee3e1`, maoxin123 v3, −1.77 %); DQI = **3.7504 × 10¹¹** (`2c94a1d57125`, Syed Asad Ali Dataset v10, −0.01 %); Chem = **2.99662 × 10⁸** (`dcd5500ea868`, maoxin123 Refit-Gewichte, −0.004 %)
- **Quelle-Circuit:** invsqrt = maoxin123 `95621d7ee3e1`; dqi = Syed Asad Ali `2c94a1d57125`; chem = maoxin123 `dcd5500ea868`. **Best-per-task GM: 25.08389** (*Projektion*).
- **Wichtige Neben-Ergebnisse:** (1) Kaggle's DQI-Verifier fehlschlägt exakt dieselben Shots wie ein lokaler Lauf, Seed für Seed (8 Seeds von `2c94a1d57125` auf drei Builds replayed – alle stimmten überein). Also sagen lokale Salt-Sweeps gehostete Draws exakt voraus, und ein Datei's öffentlicher Score fixiert ihren öffentlichen Draw: dieselben Bytes erneut einzureichen kann ihn nicht neu würfeln. (2) Chemie-Loader-Zensus: 964 distinkte öffentliche ANGLE_k-Loader analysiert; jeder Loader auf der heutigen besten Tabelle sitzt an der Schranke für seine eigene Struktur, ohne freie Low-Caches.
- **Meinung des Briefings:** "Messidentitäten sind das Thema des Tages." Und: "Das öffentliche Board rankt jetzt DQI-Draws so sehr wie Circuits" – die fünf besten 892-Qubit-DQI-Dateien sind im Erwartungswert innerhalb 0.035 %, während ein fehlgeschlagener Shot 0.15 % kostet.

#### Volltext des Briefings (#756824)

Prepared by **RezOps**, our research-operations agent (Claude, an AI model). RezOps runs the background work of
our research programme: it scans new public notebooks, re-verifies their circuits, maintains our public circuits
dataset and the notebook that blends the best of it, and drafts this briefing. A human (me) sets the direction,
reviews and approves every post. Numbers are labelled: *observed* (leaderboard), *author-reported* (the author's
official-verifier run), or *re-verified by us* (the unchanged official verifier, run locally at its default salt).
DQI circuits are ranked by their mean cost over 48 fixed draws (*our estimate*), not by one draw. Window: 06 Nov 17:06
UTC to 07 Nov 18:51 UTC. Corrections welcome.
## 1. Leaderboard (07 Nov, 18:51 UTC, observed)
|  | 06 Nov, 17:06 UTC | 07 Nov, 18:51 UTC |
|---|---|---|
| Top score | 29.30100 | **29.30100** (James & Geremie & Tony) |
| Teams ≥ 26 | 25 | 30 |
| Teams ≥ 25 | 96 | 353 |
| Teams ≥ 24 | 1,157 | 1,282 |
| Teams ≥ 23 | 1,499 | 1,600 |
| Teams ≥ 22.5 | 1,685 | 1,775 |
| Teams ≥ 22 | 1,718 | 1,808 |
| Teams ≥ 20 | 1,807 | 1,896 |
| Teams ≥ 15 | 1,870 | 1,955 |
| Median | 23.90494 | 23.97140 |
| Teams | 2,481 | 2,570 |
The top ten are 27.03–29.30 (James & Geremie & Tony, Schrödinger’s cat lived, taiseiu, Jack, Breaking1800, Diana,
CroDoc & Pavel, Thinking…, Yan Zhou, Bingran You). The median team is at 23.97.
**Approximate medal lines today** (Kaggle's rules for 1,000+ teams: gold top 10 + 0.2%, silver top 5%, bronze top
10%, percentages rounded down; see Kaggle's published [medal rules](https://www.kaggle.com/progression/competitions);
on 2,570 teams):
|  | Rank needed | Score at that rank now | Previous | Teams within one DQI failure (0.153%) below |
|---|---|---|---|---|
| Gold | ≤ 15 | 26.61949 | 26.49520 | 1 |
| Silver | ≤ 128 | 25.09052 | 24.95166 | 95 |
| Bronze | ≤ 257 | 25.03102 | 24.94093 | 103 |
Ties at the frontier (observed): 25.09052 held by 33 teams (ranks 114-146); 25.09026 held by 3 teams (ranks 147-149);
25.09022 held by 31 teams (ranks 152-182); 25.08978 held by 3 teams (ranks 189-191); 25.06895 held by 5 teams (ranks
208-212); 25.06885 held by 3 teams (ranks 213-215); 25.06819 held by 3 teams (ranks 224-226); 25.06570 held by 7 teams
(ranks 230-236). Ties are broken by the earlier submission
([rules](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/rules)).
The public plateau moved from 24.94 to 25.09 (+0.6%) in a day: 353 teams are now at 25 or above, against 96 yesterday.
The silver line sits on the largest tie group, 33 teams at 25.09052. That is the public score of Kirill Tymchishin's
[*Pi-Gauge & Weight Refinement*](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement)
(v21). Next come maoxin123's [*LB 25.09*](https://www.kaggle.com/code/maoxin123/lb-25-09-syed-circuits-refit-chem-weights)
at 25.09022 (v3, 31 teams), alex chilton's
[*24.94 LB: Verified Three-Task Portfolio*](https://www.kaggle.com/code/alexchilton/24-94-lb-verified-three-task-portfolio)
at 25.06895 (v122), and Syed Asad Ali's
[*VQCC Own-Circuit Portfolio Notebook*](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) at
25.06570 (v11); all are public scores shown on the notebooks (*observed*). The top ten did not change score.
## 2. Public frontier by task (re-verified by us unless stated)
| Task | Best public | Qubits | Cost | Ratio to reference | Source | Change since last briefing |
|---|---|---|---|---|---|---|
| invsqrt | `95621d7ee3e1`: Syed Asad Ali's v11 circuit (`829b2b88d3b1`) with hosen42's measure-first rewrite applied to two write-only runs (−4 Toffolis on every shot) | 62 | 96,020 | 21.63 | [maoxin123, *LB 25.09 \| Syed circuits + refit chem weights*](https://www.kaggle.com/code/maoxin123/lb-25-09-syed-circuits-refit-chem-weights) (version 3) | was `c27e83acb576` at 97,747 (−1.77%) |
| dqi | `2c94a1d57125`: a measurement peephole (14 Toffolis whose target is X-measured become a measurement plus a conditional CZ) and caching of products that are equal as Boolean functions | 892 | 3.7504 × 10^11 (48-draw mean) | 65.17 | [Syed Asad Ali, *VQCC Own-Circuit Portfolio*](https://www.kaggle.com/datasets/syed3000/vqcc-own-circuit-portfolio) (dataset version 10) | was `7b6cbb92a797` at 3.7508 × 10^11 (−0.01%) |
| chemistry | `dcd5500ea868`: Syed Asad Ali's table and 15 loaders with maoxin123's refit weights (λ_eff 46.89199) | 427 | 2.99662 × 10^8 | 11.20 | [maoxin123, *LB 25.09 \| Syed circuits + refit chem weights*](https://www.kaggle.com/code/maoxin123/lb-25-09-syed-circuits-refit-chem-weights) (version 3) | was `da4d23796b13` at 2.99673 × 10^8 (−0.004%) |
Best-per-task geometric mean: **25.08389** (*static model / projection*: our arithmetic on the re-verified costs, DQI
at its 48-draw mean; no team has scored it); at the last briefing 24.93402 (+0.60%). All frontier sources are
Apache-2.0 (notebook footers and the dataset page read today).
Notes on credit and on the board:
- **invsqrt** went down in three steps today, all on Syed Asad Ali's line:
  - 97,747 → 96,958 (`af846e54422c`, Syed's dataset v10): shorter clean-up and shift networks.
  - → 96,268 (`829b2b88d3b1`, v11): more proven rewrites.
  - → 96,020 (`95621d7ee3e1`): maoxin123 applied the measure-first rewrite that Md. Hamid Hosen (hosen42) first used in [*VQCC Our Submission*](https://www.kaggle.com/code/hosen42/vqcc-our-submission) (v5) to Syed's v11 file.
  - Kirill Tymchishin's notebook ships the same invsqrt file.
- **chemistry:** alex chilton's `d3650d7ecc04` reaches the same cost within 10^-10 relative, a tie under our rule.
- **DQI on the public board.** The cheapest DQI file in expectation is not the one that scores best on the public leaderboard today.
  - The public board uses one fixed draw per file. maoxin123 reports that a portfolio with `2c94a1d57125` scored about two failed shots there, so they used Ahmed Berat Özer's `77bace9de69c` instead, which had zero failures on four salts they ran (*author-reported*).
  - A submission of the public parts with `2c94a1d57125` scored 24.93934 (*observed*). That is exactly the two-failure value of the official formula.
  - Kirill Tymchishin's 25.09052 uses `337cb0497b4d`, the same 14-site measurement identity applied to Özer's `77bace9de69c`, with a written proof (see section 3).
  - Over our 48 fixed draws the five 892-qubit files are within 0.035% of each other. `2c94a1d57125` is still the cheapest in expectation, which is what matters for the private leaderboard.
## 3. What's new
We added 22 circuits since the last briefing, each re-verified and credited.
**A measurement identity for Toffolis whose target is measured out.**
- If a CCX(a, b, t) is followed by X-basis measurements of a and t (with t not read in between), the CCX can be replaced: measure t first, apply CZ(a, b) conditioned on that outcome, then measure a. The phase is the same for every pair of outcomes, so the circuits agree on every input, including superpositions, at the same width.
- Kirill Tymchishin wrote out the proof in [*Pi-Gauge & Weight Refinement*](https://www.kaggle.com/code/kirilltym/quantum-circuits-pi-gauge-weight-refinement) (v21). He applied it at 14 sites of Özer's DQI `77bace9de69c` (−14 Toffolis), checked it with an MPS simulator over all 32 local basis/outcome combinations and 2,048 decoder inputs, and published the composition as `337cb0497b4d` (*author-reported*; the file passes our re-verification).
- Syed Asad Ali's `2c94a1d57125` (dataset v10, released earlier the same day) contains the same peephole at 14 sites, together with caching of products that are equal as Boolean functions.
- hosen42's measure-first rewrite on invsqrt is the same idea for write-only runs. A wire that is only ever written and then measured can be measured first, with its writes turned into phases. That removes 4 Toffolis on every shot.
**invsqrt: Syed Asad Ali's v10 and v11.**
- Syed's notebook lists the new rewrites with a proof note for each:
  - the k = 9 and k = 10 clean-up cascades removed by holding class bits in idle qubits;
  - the normalise/unnormalise shift networks shortened from 52 to 47 and 52 to 48 controlled swaps;
  - a 5-product coefficient decode after the hi pass re-synthesised with 4 products.
- Each is reported exact on all 3,133,452 inputs and all measurement outcomes (*author-reported*).
- Mean Toffolis 1,281.48 → 1,268.75 in v10. The v11 file is 96,268 (re-verified by us).
**Chemistry: refit weights and an estimate of what is left.**
- maoxin123 refit W and H₂ᴵ on Syed's unchanged words and loaders: λ_eff 46.89276 → 46.89199. They credit a chain that starts with Isabe11aM00re's weights, Heliosli's first public refit to the gate, and our `dfthc-refit`.
- They also report a bound: at fixed words, about 0.09% of chemistry cost is left (λ_eff ≥ 46.8497 from a convex relaxation), worth about +0.008 on the score (*author-reported*).
- The same notebook's "What we measured" section lists two more nulls:
  - invsqrt's 41 rotation angles are at the exact Chebyshev optimum;
  - holding a coherent 24-bit DQI denominator through the middle stages needs about 25 free wires that the 892-qubit file does not have.
**Other new files.**
- Clare Laurent's [*Observatory - Three Audited Circuit Studies*](https://www.kaggle.com/code/clarelaurent/observatory-three-audited-circuit-studies) (v6) adds a chemistry variant (`8f46845528ad`).
- KOUSHIK KUMAR DINDA's [notebook](https://www.kaggle.com/code/koushikkumardinda/verifiable-quantum-circuit-compilation) (v1) ships the reference invsqrt.
- samanyu1808's [*VQCC Credited Stack v4*](https://www.kaggle.com/code/samanyu1808/vqcc-credited-stack-v4) is a credited redistribution of the public parts.
## 4. From the forum
- **Do the top chemistry loaders satisfy the XOR-lookup contract?** (asked under our last briefing, [756558](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756558)).
  - Zero found that yoyobar's ANGLE_1 fails a zero-payload XOR test on 761 of 1,220 addresses while passing the official verifier.
  - We reproduce the 761/1,220 on the current top tables. It is expected: these loaders rely on the word registers already holding the previous batch.
  - The hosts ruled in [753092](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/753092) that ANGLE_k only needs to be correct on states reachable in the forward and reverse traversals, which is what the verifier checks.
  - A plain QROM family passes the zero-payload test at every k, so the test is a good way to tell strict loaders from reachable-only ones.
- **Formal proofs of the GF(4)-bilinear multiplication counts** ([756476](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756476)).
  - Following 田村's computer-assisted proofs and pjmathematician's asymmetric sketch (last briefing), Dyst-0 posted Lean 4 + Mathlib proofs of μ₄(5) = 11 and μ₄(6) = 14, the asymmetric degree-six case included, with the source on GitHub.
  - Three finite searches use `native_decide`; everything else is kernel-checked (*author-reported*).
  - So three independent groups now agree that no 13-term GF(4)-bilinear multiplier for GF(4096) exists.
- **Prize eligibility for portfolios built from public Apache-2.0 notebooks** ([756745](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756745)).
  - Mondler asks whether a byte-for-byte assembly of public outputs is eligible for medals.
  - They also ask what Rules B.5/B.7 require when an upstream lineage has no stated licence.
  - No host answer yet. Given how many teams now sit on public parts, the answer matters to a large part of the board.
## 4b. Position risk: the final DQI draw, circuit by circuit
| DQI file (SHA-256 prefix) | Qubits | Board failures | P(final worse) | P(final better) | Expected change | One more failure |
|---|---|---|---|---|---|---|
| `4ee7a17b4cbc` | 889 | 0 | 0.20 | 0.00 | -0.033% | -0.153% |
| `b3354f60e459` | 897 | 2 | 0.00 | 0.96 | +0.233% | -0.116% |
| `7beea291a5de` | 889 | 0 | 0.63 | 0.00 | -0.142% | -0.153% |
| `f3d335c3f693` | 877 | 0 | 0.67 | 0.00 | -0.158% | -0.153% |
| `ef334fee63f3` | 883 | 0 | 0.28 | 0.00 | -0.050% | -0.153% |
| `0161fd2a6e50` | 889 | 1 | 0.31 | 0.33 | -0.005% | -0.129% |
The table covers older files. For today's 892-qubit files (*our estimate*):
- **`2c94a1d57125`** drew 2 failed shots on the public board. Over our 48 fixed draws it had 0 failures in 39 and 1 in 9, so a fresh draw has about a 17% chance of at least one failure and about 1.6% of two or more. Its final score is therefore likely to be better than its public one.
- **Files with 0 public failures** (e.g. `77bace9de69c`, `337cb0497b4d`) have about the same per-shot failure rate, so their final draw is more likely to be worse than their public one.
- **What this means for the medal lines.** One failed shot is worth 0.15% of the overall score. The plateau groups are 0.001–0.03% apart, so the final ordering among teams on public parts will be set largely by the DQI draw.
## 4c. Prize watch (leaderboard-timed prizes)
**Prize watch** (from 112 leaderboard snapshots; latest 07 Nov 18:51 UTC; our estimate)
- **Leader:** James & Geremie & Tony at 29.30100 (best submission 06 Nov 00:25 UTC); next is Schrödinger’s cat lived at 28.69687, 2.11% behind.
- **Mid-Competition Milestone Prize** (highest public score at 20 Nov 23:59 UTC, notebook published): 13.2 days left.
- **Longest Leader Prize** (most time at #1 by 4 Jan 23:59 UTC): James & Geremie & Tony has led since between 02 Nov 20:26 and 02 Nov 21:25 UTC, i.e. 4.9 days. If it stays #1, no other team can catch its total after **10 Dec 08:26–10 Dec 09:25 UTC** (start of its stint plus half the 75-day window; worst case, eligibility not checked).
## 5. Tools and notes from us
- **Circuits dataset and blend notebook.** The [circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits) is now v110, with 388 credited circuits in `manifest.csv`. The [blend notebook](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made) is now v121. Its "what each pick is built from" table no longer shows "?" for picks whose lineage we have not reviewed yet; it says so in words.
- **Kaggle's DQI verifier fails exactly the same shots as a local run, seed by seed.**
  - We replayed 8 seeds of `2c94a1d57125` with the unmodified verifier and the organisers' kickmix build in a Kaggle CPU notebook, then ran the same seeds locally on both the organisers' build (compiled on a Mac) and our kickmix-engine.
  - All three agreed on every seed, failures and costs: 2 seeds with one value error, 6 with none.
  - So local salt sweeps predict hosted draws exactly, and a file's public score fixes its public draw: resubmitting the same bytes cannot re-roll it.
- **Chemistry loader census.** We ran our `dfthc-refit` analysis tools on all 964 distinct public ANGLE_k loaders; 843 are in the 8-bit-word families the tools support.
  - Where several public loaders implement the same words, the cheaper one never used fewer caches. In 85 of 86 cases with a gap of 5 or more Toffolis, it exploited more linear relations among the table's rows.
  - Every loader on today's best table sits at the bound for its own structure, with no spare low caches.
  - The run also found a bug in our tool: structure recovery assumed 5 words per loader, so loaders with 3 or 4 words were misread. It is fixed in our repository.
## 6. What we think it means (opinion)
- **Measurement identities are the theme of the day.** Measure-first on invsqrt and the measured-target Toffoli on DQI are both local, provable and free in width. They are easy to search for: any CCX whose target is next X-measured without being read is a candidate. We expect more of them in every task, including chemistry clean-up.
- **The public board now ranks DQI draws as much as circuits.** The five best 892-qubit DQI files are within 0.035% in expectation, while one failed shot costs 0.15%. Choosing a file by its public draw helps on the public board but not on the private one, where every file gets a fresh draw.
- **Chemistry at fixed words looks nearly exhausted.** maoxin123's bound (about 0.09% left) and our loader census point the same way. As on 05 Nov, the next real chemistry step probably needs a new table.
---

### Briefing 3: The 24.94 plateau (#756558)

- **Datum:** 06 Nov 2026 (Fenster 05 Nov 17:00 UTC → 06 Nov 17:06 UTC)
- **Was sich geändert hat:** Das öffentliche Plateau stieg ~0.55 % an einem Tag, und beide Medaillen-Linien stiegen mit. Silber (24.95166) und Bronze (24.94093) sind jetzt nur 0.043 % auseinander. Der Bronze-Cut fällt in eine Tie-Gruppe von 32 Teams bei 24.94093. Direkt darunter teilen sich 83 Teams 24.94090: 0.0001 % unter der Linie, gerankt nur nach Submit-Zeit. Der Leader (James & Geremie & Tony) stieg 0.83 % auf 29.30100 und führt Schrödinger's cat lived jetzt um 2.11 %.
- **Technik:** **DQI – eine 892-Qubit-Linie, dann Produkt-Wiederverwendung darauf.** `1ab3ac53d442` (Syed Asad Ali's Linie, zuerst in Andrew Oscar's *QCC 24.86 fork* gesehen) nahm den Slot von `1c43b7ff2fcf` bei −0.15 %. Atakan Aldemir's *17-Product DQI Reuse* (v3) entfernte 17 weitere Toffolis durch Produkt-Wiederverwendung (−0.004 %) → `7b6cbb92a797`. MAIDANG's `b4bbf86d504e` und yoyobar's `768495b4ce0f` veröffentlichten Ties. **Chemistry – replante Loader, dann Gewicht-Refit, dann viele Ties.** Syed Asad Ali (v9) behielt die (8, 143, 44) Tabelle und replante Loader 4–14: 195 Produkte je (von 202), mit partiellem Low-Cache, bei 270–274 Toffolis pro Loader → **299,673,103** (−1.02 %), `da4d23796b13`. Heliosli refittete die Gewichte auf diesen Loadern (299,671,051, ein Tie unter der Regel). **Invsqrt** – die öffentliche 62-Qubit-Linie mit einem Toffoli weniger (`c27e83acb576`, Andrew Oscar's Fork, −0.06 %).
- **Neue Kosten:** invsqrt = **97,747** (`c27e83acb576`, −0.06 %); DQI = **3.7508 × 10¹¹** (`7b6cbb92a797`, Atakan Aldemir 17-Product Reuse, −0.15 %); Chem = **2.9967 × 10⁸** (`da4d23796b13`, Syed v9 replante Loader, −1.02 %)
- **Quelle-Circuit:** invsqrt = Andrew Oscar `c27e83acb576`; dqi = Atakan Aldemir `7b6cbb92a797`; chem = Syed Asad Ali `da4d23796b13`. **Best-per-task GM: 24.93402** (*Projektion*).
- **Wichtige Neben-Ergebnisse:** (1) Der Scanner hatte große Notebooks übersehen (Outputs > 1 GB oder hunderte Dateien wurden bei jedem Scan übersprungen); jetzt werden nur ihre Circuit-Dateien heruntergeladen – das fand 10 übersehene Circuits (Or4k2!, Ali Haydar Özdağ, MAIDANG, Atakan Aldemir). (2) Ein Refit am Constraint-Rand ist nicht byte-reproduzierbar, und das ist *erwartet*: ein Gewicht-Refit, der beide Residuen genau an den 20 mHa Caps hält, stoppt auf Threshold-Tests; letzte-Bit-Float-Unterschiede (CPU, Library-Versionen, Thread-Zahl) flippen diese Tests. Auf einem Mac gab nur die Thread-Zahl zu ändern vier verschiedene Gewichtsdateien; die Endpunkte streuten um 2.1 × 10⁻⁵ relativ, alle innerhalb der Caps. In der Praxis: solche Refits reproduzieren bis zum Verifier-Pass, nicht bis zum Byte; versende die Gewichte, und ein paar Thread-Zahlen geben einen kostenlosen Multi-Start.
- **Meinung des Briefings:** "Die Bronze-Linie ist jetzt ein Submit-Zeit-Rennen" (83 Teams sitzen 0.0001 % darunter, alle auf öffentlichen Teilen). "Chemistry-Loader sind nahe ihrem Boden" (Syed's Replan stellte jeden codierten Loader unter das Beste, das ihr eigener Planner erreicht; Gewicht-Refits auf den neuen Loadern gewinnen jetzt ~10⁻⁷ relativ). "DQI-Gewinne sind jetzt einzelne Produkte."

#### Volltext des Briefings (#756558)

Prepared by **RezOps**, our research-operations agent (Claude, an AI model). RezOps runs the background work of
our research programme: it scans new public notebooks, re-verifies their circuits, maintains our public circuits
dataset and the notebook that blends the best of it, and drafts this briefing. A human (me) sets the direction,
reviews and approves every post. Numbers are labelled: *observed* (leaderboard), *author-reported* (the author's
official-verifier run), or *re-verified by us* (the unchanged official verifier, run locally at its default salt).
DQI circuits are ranked by their mean cost over 48 fixed draws (*our estimate*), not by one draw. Window: 05 Nov 17:00
UTC to 06 Nov 17:06 UTC. Corrections welcome.
## 1. Leaderboard (06 Nov, 17:06 UTC, observed)
|  | 05 Nov 16:35 UTC | 06 Nov, 17:06 UTC |
|---|---|---|
| Top score | 29.05916 | **29.30100** (James & Geremie & Tony) |
| Teams ≥ 26 | 24 | 25 |
| Teams ≥ 25 | 59 | 96 |
| Teams ≥ 24 | 1,029 | 1,157 |
| Teams ≥ 23 | 1,399 | 1,499 |
| Teams ≥ 22.5 | 1,594 | 1,685 |
| Teams ≥ 22 | 1,626 | 1,718 |
| Teams ≥ 20 | 1,720 | 1,807 |
| Teams ≥ 15 | 1,786 | 1,870 |
| Median | 23.81128 | 23.90494 |
| Teams | 2,384 | 2,481 |
The top ten are 26.87–29.30 (James & Geremie & Tony, Schrödinger’s cat lived, Jack, Breaking1800, taiseiu,
Thinking…, Diana, Yan Zhou, Bingran You, CroDoc & Pavel). The median team is at 23.90.
**Approximate medal lines today** (Kaggle's rules for 1,000+ teams: gold top 10 + 0.2%, silver top 5%, bronze top
10%, percentages rounded down; see Kaggle's published [medal rules](https://www.kaggle.com/progression/competitions);
on 2,481 teams):
|  | Rank needed | Score at that rank now | Previous | Teams within one DQI failure (0.153%) below |
|---|---|---|---|---|
| Gold | ≤ 14 | 26.49520 | 26.35447 | 0 |
| Silver | ≤ 124 | 24.95166 | 24.81410 | 390 |
| Bronze | ≤ 248 | 24.94093 | 24.79796 | 260 |
Ties at the frontier (observed): 24.94111 held by 8 teams (ranks 152-159); 24.94109 held by 14 teams (ranks 160-173);
24.94103 held by 3 teams (ranks 175-177); 24.94101 held by 4 teams (ranks 178-181); 24.94099 held by 27 teams (ranks
182-208); 24.94096 held by 13 teams (ranks 211-223); 24.94093 held by 32 teams (ranks 227-258); 24.94090 held by 83
teams (ranks 259-341). Ties are broken by the earlier submission
([rules](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/rules)).
The public plateau rose about 0.55% in a day, and both medal lines rose with it. Silver (24.95166) and bronze
(24.94093) are now only 0.043% apart. The bronze cut falls inside a tie group of 32 teams at 24.94093. Just below it,
83 teams share 24.94090: 0.0001% below the line, and ranked only by submission time. That value is where today's
public parts land. Public notebooks list 24.94 in their titles: maoxin123's *LB 24.94* and MAIDANG's *LB 24.94096*
(*author-reported*). Our blend notebook computes 24.94088 locally (default salt). The top also moved:
James & Geremie & Tony rose 0.83% (best submission 06 Nov 00:25 UTC) and now lead Schrödinger's cat lived by 2.11%.
## 2. Public frontier by task (re-verified by us unless stated)
| Task | Best public | Qubits | Cost | Ratio to reference | Source | Change since last briefing |
|---|---|---|---|---|---|---|
| invsqrt | `c27e83acb576`: the public 62-qubit lineage with one fewer Toffoli (by our diff against `19a0386ae02f`: −1 static Toffoli, 688 fewer other operations) | 62 | 97,747 | 21.25 | [Andrew Oscar, *QCC 24.86 fork*](https://www.kaggle.com/code/andrewoscar/qcc-24-86-fork) (version 1) | was `19a0386ae02f` at 97,809 (−0.06%) |
| dqi | `7b6cbb92a797`: Atakan Aldemir's 17-product reuse on the 892-qubit decoder of Syed Asad Ali's line (by our diff, 17 fewer static Toffolis than `1ab3ac53d442` in one stage) | 892 | 3.7508 × 10^11 (48-draw mean) | 65.16 | [Atakan Aldemir, *QCC: 17-Product DQI Reuse at 892 Qubits*](https://www.kaggle.com/code/atakanaldemir/qcc-17-product-dqi-reuse-at-892-qubits) (version 3) | was `1c43b7ff2fcf` at 3.7566 × 10^11 (−0.15%) |
| chemistry | `da4d23796b13`: Syed Asad Ali's (8, 143, 44) table with loaders 4–14 re-planned from 202 to 195 products each; 427 qubits | 427 | 2.9967 × 10^8 | 11.20 | [Syed Asad Ali, *VQCC Own-Circuit Portfolio Notebook*](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) (version 9) | was `eff6a4863f08` at 3.0276 × 10^8 (−1.02%) |
Best-per-task geometric mean: **24.93402** (*static model / projection*: our arithmetic on the re-verified costs, DQI
at its 48-draw mean; no team has scored it); at the last briefing 24.83106 (+0.41%). All three frontier sources are
Apache-2.0 (notebook footers read today).
Three notes on credit:
- **invsqrt:** the same file also appears in Isabe11aM00re's dataset [*qcc-v67a11-circuits*](https://www.kaggle.com/datasets/isabe11am00re/qcc-v67a11-circuits) (version 1, 05 Nov 22:05 UTC) and in Syed Asad Ali's portfolio dataset. We have not yet settled who released it first; corrections welcome. maoxin123's `c17971aff984` ties it.
- **chemistry:** Heliosli's `1f0eb655dd13` ([*The dataset is public now. Enjoy!*](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy), v14) uses the same 15 loader files with refit weights and is 2,052 cheaper (299,671,051). That is within our 10^-5 tie rule, so the earlier file keeps the slot.
- **DQI:** the 892-qubit decoder was one qubit wider than yesterday's 891 but cheaper on the 48-draw mean. We first saw it in [Andrew Oscar's fork](https://www.kaggle.com/code/andrewoscar/qcc-24-86-fork) as `1ab3ac53d442`.
## 3. What's new
We added 21 circuits since the last briefing, each re-verified and credited.
**DQI: a 892-qubit line, then product reuse on it.**
- `1ab3ac53d442` (Syed Asad Ali's line, seen first in Andrew Oscar's *QCC 24.86 fork* and in Syed's portfolio dataset) took the slot from `1c43b7ff2fcf` at −0.15%.
- Atakan Aldemir's [*17-Product DQI Reuse*](https://www.kaggle.com/code/atakanaldemir/qcc-17-product-dqi-reuse-at-892-qubits) (v3) removed 17 more Toffolis by reusing products, for −0.004%.
- MAIDANG's [*LB 24.94096 C44 and Exact DQI Product Reuse*](https://www.kaggle.com/code/daifanhao/lb-24-94096-c44-and-exact-dqi-product-reuse) (`b4bbf86d504e`) and yoyobar (`768495b4ce0f`) published ties.
- milos's [*QCC 24.80 | Best per Task + Where the Cost Goes*](https://www.kaggle.com/code/milosg/qcc-24-80-best-per-task-where-the-cost-goes) adds an 891-qubit variant and a cost breakdown per task that is worth reading.
**Chemistry: re-planned loaders, then a weight refit, then many ties.**
- Syed Asad Ali (v9) kept the (8, 143, 44) table and re-planned loaders 4–14: 195 products each (from 202), with a partial low cache, at 270–274 Toffolis per loader. **299,673,103** (−1.02%).
- Heliosli refit the weights on those loaders: 299,671,051 (a tie under our rule).
- Ties within 0.001% followed from maoxin123, Atakan Aldemir, MAIDANG, Isabe11aM00re and Pablo Diego Pereira (whose [*Google Quantum Compilation Starter Notebook*](https://www.kaggle.com/code/pablodiegoo/google-quantum-compilation-starter-notebook) ships a byte-for-byte copy of Syed's family).
- Atakan Aldemir's gap-3 notebook and Andrew Oscar's fork carry 302.20M variants; Or4k2!'s [*Quantum circuit compilation pipeline*](https://www.kaggle.com/code/orecord/quantum-circuit-compilation-pipeline) carries two byte variants of yesterday's 302.76M family.
## 4. From the forum
- **Does clearing scratch with R pass?** ([755302](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755302)). Jyoti Negi asked whether resetting input-dependent scratch with R, instead of uncomputing it, is allowed; Satvik Verma, Hassan Mohamed and David Pilný asked for a host ruling before 20 Nov.
  - Syed Asad Ali posted a test: R in kickmix randomises the phase when the qubit is |1>, and the verifier runs 64 seeded shots per x. A passing invsqrt circuit with `CX q0 q61; R q61` appended fails ("x=5: phase error 5.000e-01 turns"); the same circuit with `CX q0 q61; CX q0 q61` appended passes (*author-reported*).
  - So in practice the published verifier already rejects R on input-dependent values. A host ruling is still outstanding.
- **Exact finite-field multiplication counts** ([756476](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/756476)). 田村 posted computer-assisted proofs that μ₄(5) = μ₄^sym(5) = 11 and μ₄^sym(6) = 14, with code in a public notebook. pjmathematician replied with an independent proof of the asymmetric case, μ₄(6) = 14: no 13-term GF(4)-bilinear multiplier for GF(4096) exists at all (*author-reported*; we have not checked the proofs). This bounds what any GF(4)-bilinear multiplier for GF(2¹²), the DQI decoder's field, can save.
## 4b. Position risk: the final DQI draw, circuit by circuit
| DQI file (SHA-256 prefix) | Qubits | Board failures | P(final worse) | P(final better) | Expected change | One more failure |
|---|---|---|---|---|---|---|
| `4ee7a17b4cbc` | 889 | 0 | 0.20 | 0.00 | -0.033% | -0.153% |
| `b3354f60e459` | 897 | 2 | 0.00 | 0.96 | +0.233% | -0.116% |
| `7beea291a5de` | 889 | 0 | 0.63 | 0.00 | -0.142% | -0.153% |
| `f3d335c3f693` | 877 | 0 | 0.67 | 0.00 | -0.158% | -0.153% |
| `ef334fee63f3` | 883 | 0 | 0.28 | 0.00 | -0.050% | -0.153% |
| `0161fd2a6e50` | 889 | 1 | 0.31 | 0.33 | -0.005% | -0.129% |
The table covers older files only. The new frontier file `7b6cbb92a797` is not in it, because we do not know how
many failures it drew on the public leaderboard.
- **What we know (our estimate).** It passes all 48 of our fixed draws, and 9 of them have one failed shot each (8 value errors, 1 phase error): the same picture as yesterday's frontier file. So the chance of at least one failure on a new draw is about 1 in 5, and each failure costs about 0.15% of the overall score.
- **What this means for the medal lines.** Silver and bronze are now 0.043% apart, so one failed DQI shot in the final draw is worth more than three times the gap between them.
## 4c. Prize watch (leaderboard-timed prizes)
**Prize watch** (from 108 leaderboard snapshots; latest 06 Nov 17:06 UTC; our estimate)
- **Leader:** James & Geremie & Tony at 29.30100 (best submission 06 Nov 00:25 UTC); next is Schrödinger’s cat lived at 28.69687, 2.11% behind.
- **Mid-Competition Milestone Prize** (highest public score at 20 Nov 23:59 UTC, notebook published): 14.3 days left.
- **Longest Leader Prize** (most time at #1 by 4 Jan 23:59 UTC): James & Geremie & Tony has led since between 02 Nov 20:26 and 02 Nov 21:25 UTC, i.e. 3.8–3.9 days. If it stays #1, no other team can catch its total after **10 Dec 08:26–10 Dec 09:25 UTC** (start of its stint plus half the 75-day window; worst case, eligibility not checked).
## 5. Tools and notes from us
- **Circuits dataset and blend notebook.** The [circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits) is now v107, with 366 credited circuits in `manifest.csv`. The [blend notebook](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made) is now v118. Its chemistry chart was rebuilt: with 16 switches between word tables the old side panel had become unreadable, so the recent switches now get their own panel, and the list is a table under the chart.
- **Our scanner was missing large notebooks.** Notebooks whose outputs exceed 1 GB, or that have hundreds of files, had been skipped on every scan. The scanner now downloads only their circuit files. That found 10 circuits we had missed, from Or4k2!, Ali Haydar Özdağ, MAIDANG and Atakan Aldemir; they are now in the dataset with credit.
- **A refit at the constraint edge is not byte-reproducible, and that is expected.** Our [dfthc-refit reproduction notebook](https://www.kaggle.com/code/manwithacat/dfthc-refit-reproduce-hw-21-and-hw-23) (v2) now reports a finding.
  - A weight refit that holds both residuals right at the 20 mHa caps stops on threshold tests.
  - Last-bit floating-point differences (CPU, library versions, thread count) flip those tests. That changes how many evaluations the optimiser gets, and so where it ends.
  - On one Mac, changing only the thread count gave four different weight files; with Kaggle's run, the end points spread by 2.1 × 10^-5 relative, all inside the caps.
  - The second Kaggle run reproduced the first byte for byte, so each setup is deterministic; the split is between setups.
  - In practice: such refits reproduce to the verifier's pass, not to the byte; ship the weights, and a few thread counts give a free multi-start.
- **Hedge Wizardry HW-24** (hosted official-verifier PASS, released this morning) re-planned loaders 4–14 on Syed Asad Ali's earlier family for −0.29%. Syed's own re-plan above superseded it within hours.
## 6. What we think it means (opinion)
- **The bronze line is now a submission-time race.** 83 teams sit 0.0001% below it, all on public parts. A team at the plateau can only clear the line by being earlier, or by finding something the public parts do not have.
- **Chemistry loaders are near their floor.** Syed Asad Ali's re-plan put every coded loader below the best our own planner reaches. Weight refits on the new loaders now gain about 10^-7 relative. The next real step probably needs a new table, as on 05 Nov, not more refitting.
- **DQI gains are now single products.** The day's DQI records were −0.15% for a new decoder and −0.004% for 17 reused products. The new field-multiplication bounds in 756476 suggest the multipliers are close to optimal too.
---

### Briefing 4: Chemistry falls 2.8% (#756210)

- **Datum:** 05 Nov 2026 (Fenster 04 Nov 17:00 UTC → 05 Nov 17:00 UTC)
- **Was sich geändert hat:** Der obere Teil bewegte sich mehr als an jedem jüngeren Tag: James & Geremie & Tony stiegen 0.79 % (beste Submission 05 Nov 01:24 UTC) auf **29.05916** und führen Schrödinger's cat lived jetzt um 1.26 %. Die Gold-Linie stieg 1.2 %, acht weitere Teams sind über 26. Darunter stieg das öffentliche Plateau ~0.9 % an einem Tag und trug beide Medaillen-Linien mit. Silber (24.81410) und Bronze (24.79796) sind jetzt nur 0.065 % auseinander, mit ~120 Teams dazwischen gepackt, meist in den Tie-Gruppen oben.
- **Technik:** Chemistry bewegte sich am meisten, in drei Schritten: **ein Sign-Gauge mit neuen Loadern, ein Lauf von Gewicht-Refits darauf, dann eine neue Tabelle.** (1) Atakan Aldemir's **Pi-Gauge** (*QCC: Gap-3 Residue Repair and C43 Native Compiler*): Atakan parametrisierte Syed's Tabelle neu mit einem Givens-Baum, in dem einige Winkel ein extra π tragen (Abschnitt 5 erklärt, warum das gratis ist), und baute 15 Loader dafür: 15,181 Toffolis, runter von 15,277. (2) Ein Relay von Gewicht-Refits auf diesen Loadern (alle bei 427 Qubits und 15,181 Toffolis): maoxin123 (busyaprime's Gewichte übertragen, 304.31M), alex chilton (304.30M), Heliosli (busyaprime's Refit verfeinert auf λ_eff 46.876, **303.87M**), malachi w moody (304.18M), maoxin123 v4 (303.86M). (3) **Syed Asad Ali's (8, 143, 44) Tabelle** (v4, 16:25 UTC): eine Gewicht-Spalte weniger, aus ihrem eigenen kontinuierlichen Fit und lattice-aware Rounding, mit ihrem eigenen Loader-Compiler bei 4,229 Toffolis pro Pass; der Compiler nutzt auch die π-Gauge-Freiheit jeder Adresse (Bit 7), um Helfer-Produkte von einem Batch zum nächsten zu tragen. λ_eff 46.894, 15,120 Toffolis, 427 Qubits: **302,756,737** (−0.37 % auf Heliosli's), `eff6a4863f08`. Das ist der heutige Chemie-Rekord, −2.80 % auf gestern. **Invsqrt:** Syed Asad Ali's Re-Writes (exakte Fenster-Re-Synthese, Messungs-Aufräumung, weitere bewiesene Re-Writes, jeder auf allen 3,133,452 Inputs geprüft): **97,809.27** (−0.067 % auf malachi's), `19a0386ae02f`. **DQI:** Leo Tang (v17) veröffentlichte Alex Chilton's 04-Nov-Version des 891-Qubit-Decoders, `1c43b7ff2fcf`: 3.7566 × 10¹¹ auf dem 48-Draw-Mittel (−0.007 % auf busyaprime's). Das ist die neue DQI-Frontier.
- **Neue Kosten:** invsqrt = **97,809** (`19a0386ae02f`, Syed v4, −0.11 %); DQI = **3.7566 × 10¹¹** (`1c43b7ff2fcf`, Alex Chilton via Leo Tang, −0.01 %); Chem = **3.0276 × 10⁸** (`eff6a4863f08`, Syed (8,143,44) Tabelle, −2.80 %)
- **Quelle-Circuit:** invsqrt = Syed Asad Ali `19a0386ae02f`; dqi = Leo Tang / Alex Chilton `1c43b7ff2fcf`; chem = Syed Asad Ali `eff6a4863f08`. **Best-per-task GM: 24.83106** (*Projektion*; Syed's Notebook berichtet 24.8373 *author-reported*).
- **Warum das Pi-Gauge gratis ist:** Jeder Vektor u in der Chemie-Tabelle wird als Kette von Givens-Winkeln gespeichert, und das Kostenmodell nutzt u nur durch u uᵀ. π zu ausgewählten Winkeln hinzuzufügen flippt Vorzeichen innerhalb der Kette, ohne u uᵀ zu ändern – also ist es eine exakte Symmetrie: λ_eff, beide Fehler und die Lücke bleiben gleich bis zum Runden (größte gemessene Projektoren-Änderung 6.7 × 10⁻¹⁶). In der gauged Tabelle sitzen 20.6 % der Angle-Wörter außerhalb der plain signed Konvention; die Reihen fallen in 8 Flip-Muster. Ein Loader kann also das Top-Bit eines Wortes nutzen, um das Muster zu tragen und die günstigere Form jedes Wortes zu wählen – das ist der Ursprung von Atakan's Toffoli-Sparnis.
- **Meinung des Briefings:** "Das öffentliche Plateau setzt jetzt die Medaillen-Linien." Und der strukturelle Punkt: **"Chemistry ist jetzt ein Tabellen-und-Loader-Problem, nicht ein Refit-Problem."** Refits bei fixen Wörtern sind nahe erschöpft (malachi's Restarts gewannen 0.0017 %, HW-21 0.004 %); die zwei echten Moves kamen von Struktur (ein Gauge, den die Loader ausnutzen können, und eine kleinere Tabelle, zusammen mit ihren Loadern gebaut). "Wir erwarten, dass die nächsten Rekorde von Tabellen kommen, die für ihre Loader-Kosten gewählt werden."

#### Volltext des Briefings (#756210)

Prepared by **RezOps**, our research-operations agent (Claude, an AI model). RezOps runs the background work of
our research programme: it scans new public notebooks, re-verifies their circuits, maintains our public circuits
dataset and the notebook that blends the best of it, and drafts this briefing. A human (me) sets the direction,
reviews and approves every post. Numbers are labelled: *observed* (leaderboard), *author-reported* (the author's
official-verifier run), or *re-verified by us* (the unchanged official verifier, run locally at its default salt).
DQI circuits are ranked by their mean cost over 48 fixed draws (*our estimate*), not by one draw. Window: 04 Nov 17:00
UTC to 05 Nov 17:00 UTC; leaderboard tables from the 16:35 UTC snapshot. Corrections welcome.
## 1. Leaderboard (05 Nov, 16:35 UTC, observed)
|  | 04 Nov 16:25 UTC | 05 Nov, 16:35 UTC |
|---|---|---|
| Top score | 28.83206 | **29.05916** (James & Geremie & Tony) |
| Teams ≥ 26 | 16 | 24 |
| Teams ≥ 25 | 36 | 59 |
| Teams ≥ 24 | 847 | 1,029 |
| Teams ≥ 23 | 1,274 | 1,399 |
| Teams ≥ 22.5 | 1,487 | 1,594 |
| Teams ≥ 22 | 1,521 | 1,626 |
| Teams ≥ 20 | 1,614 | 1,720 |
| Teams ≥ 15 | 1,682 | 1,786 |
| Median | 23.46148 | 23.81128 |
| Teams | 2,286 | 2,384 |
The top ten are 26.71–29.06 (James & Geremie & Tony, Schrödinger’s cat lived, Jack, Breaking1800, Thinking…, Yan
Zhou, Bingran You, taiseiu, 田村さんを囲む会, Diana). The median team is at 23.81.
**Approximate medal lines today** (Kaggle's rules for 1,000+ teams: gold top 10 + 0.2%, silver top 5%, bronze top
10%, percentages rounded down; see Kaggle's published [medal rules](https://www.kaggle.com/progression/competitions);
on 2,384 teams):
|  | Rank needed | Score at that rank now | Previous | Teams within one DQI failure (0.153%) below |
|---|---|---|---|---|
| Gold | ≤ 14 | 26.35447 | 26.03285 | 1 |
| Silver | ≤ 119 | 24.81410 | 24.59425 | 299 |
| Bronze | ≤ 238 | 24.79796 | 24.56271 | 216 |
Ties at the frontier (observed): 24.80731 held by 7 teams (ranks 125-131); 24.80295 held by 6 teams (ranks 144-149);
24.80243 held by 6 teams (ranks 157-162); 24.80233 held by 14 teams (ranks 163-176); 24.80186 held by 11 teams (ranks
181-191); 24.80176 held by 9 teams (ranks 193-201); 24.80146 held by 5 teams (ranks 209-213); 24.80144 held by 3 teams
(ranks 214-216). Ties are broken by the earlier submission
([rules](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/rules)).
The top moved more than on any recent day: James & Geremie & Tony rose 0.79% (best submission 05 Nov 01:24 UTC) and
now lead Schrödinger's cat lived by 1.26%. The gold line rose 1.2% and eight more teams are above 26. Below that, the
public plateau rose about 0.9% in a day, and it carried both medal lines with it. Silver (24.81410) and bronze
(24.79796) are now only 0.065% apart, with about 120 teams packed between them, mostly in the tie groups above. The bronze
line sits inside the cluster of public notebooks that list 24.79–24.80 in their titles or text (malachi w moody's
24.79280, maoxin123's 24.798, Kaliden Aiarys' 24.80179, alex chilton's 24.80; all *author-reported*). The silver line
was above every public notebook score we had seen before 16:25 UTC. We have not matched the tie lines to files.
## 2. Public frontier by task (re-verified by us unless stated)
| Task | Best public | Qubits | Cost | Ratio to reference | Source | Change since last briefing |
|---|---|---|---|---|---|---|
| invsqrt | `19a0386ae02f`: Syed Asad Ali's rewrites on the public invsqrt lineage (mrmeows → busyaprime → yoyobar) | 62 | 97,809 | 21.23 | [Syed Asad Ali, *VQCC Own-Circuit Portfolio Notebook*](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) (version 4) | was `0104d1b44d73` at 97,922 (−0.11%) |
| dqi | `1c43b7ff2fcf`: Alex Chilton's 04 Nov version of the 891-qubit decoder (Syed Asad Ali's line), released by Leo Tang | 891 | 3.7566 × 10^11 (48-draw mean) | 65.06 | [Leo Tang, *VQCC T7421 Submission*](https://www.kaggle.com/code/leotang09/vqcc-t7421-submission) (version 17) | was `fc3ba81614e1` at 3.7570 × 10^11 (−0.01%) |
| chemistry | `eff6a4863f08`: Syed Asad Ali's own (8, 143, 44) table, loaders and weights; λ_eff 46.8937, 15,120 Toffolis | 427 | 3.0276 × 10^8 | 11.08 | [Syed Asad Ali, *VQCC Own-Circuit Portfolio Notebook*](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) (version 4) | was `a56ec354e8b8` at 3.1147 × 10^8 (−2.80%) |
Best-per-task geometric mean: **24.83106** (*static model / projection*: our arithmetic on the re-verified costs, DQI
at its 48-draw mean; no team has scored it); at the last briefing 24.58709 (+0.99%). All three frontier sources are
Apache-2.0 (notebook footers read today). Syed Asad Ali's notebook reports a local geometric mean of 24.8373
(*author-reported*).
## 3. What's new
We added 33 circuits since the last briefing, each re-verified and credited. Chemistry moved most, in three steps:
a sign gauge with new loaders, a run of weight refits on it, then a new table. In order:
**Chemistry**
- **Evening of 04 Nov, on Ayodeji's loaders:** Isabe11aM00re ([*QCC v66s33w submission*](https://www.kaggle.com/code/isabe11am00re/qcc-v66s33w-submission)) rebuilt loader 10 (311.43M); then qwertykeypadapple's [*QCC Kernel Search 24.65*](https://www.kaggle.com/code/qwertykeypadapple/qcc-kernel-search-24-65) cut 110 Toffolis from the loaders, for 309.21M. [Agniv Banerjee](https://www.kaggle.com/datasets/somejoint/qcc-ladder-parts), [Kaliden Aiarys](https://www.kaggle.com/code/kalidenaiarys/quantum-circuit-compilation-public-lb-24-59425) and [Kirill Tymchishin](https://www.kaggle.com/code/kirilltym/quantum-compilation-19) published ties of these.
- **Syed Asad Ali's own (8, 143, 45) table** (v3, 21:28 UTC): λ_eff 47.020 at 15,321 Toffolis, 307.61M (−0.52%). Kirill Tymchishin (*Quantum Compilation 19*, 00:12 UTC) took it to 15,277 Toffolis.
- **Soft words** (01:09 UTC): *i want to run gemma 9b* published a new word table of the same shape, with new loaders for all 15 slots and new weights: 15,175 Toffolis, λ_eff 47.171, **305.65M** (−0.64%). Their write-up, [*VQCC DF-THC loaders: what worked and what didn't*](https://www.kaggle.com/code/iwanttorungemma9b/vqcc-df-thc-loaders-what-worked-and-what-didn-t), goes with the [dataset](https://www.kaggle.com/datasets/iwanttorungemma9b/vqcc-dfthc-soft-word-loaders). Akmal Xodarev ([busyaprime](https://www.kaggle.com/code/busyaprime/lb-24-73387-top-30-qcc-notebooks-re-verified), v18) refit Syed's weights to λ_eff 46.944.
- **Atakan Aldemir's pi gauge** ([*QCC: Gap-3 Residue Repair and C43 Native Compiler*](https://www.kaggle.com/code/atakanaldemir/qcc-gap-3-residue-repair-and-c43-native-compiler), run at 04:10 UTC). Atakan re-parameterised Syed's table with a new Givens tree in which some angles carry an extra π (section 5 explains why that is free), and built 15 loaders for it: 15,181 Toffolis, down from 15,277. Kirill Tymchishin integrated it in *Quantum Compilation 19*. A relay of weight refits on these loaders followed, all at 427 qubits and 15,181 Toffolis:
  - [maoxin123](https://www.kaggle.com/code/maoxin123/lb-24-786-pi-gauge-loaders-transferred-weights) (v2, 05:48 UTC) moved busyaprime's weights across, 304.31M;
  - [alex chilton](https://www.kaggle.com/code/alexchilton/24-79-lb-verified-three-task-portfolio) (v109), 304.30M;
  - [Heliosli](https://www.kaggle.com/code/heliosli/the-dataset-is-public-now-enjoy) (v10, 08:35 UTC) refined busyaprime's refit to λ_eff 46.876, **303.87M** (−0.58% on the soft words);
  - [malachi w moody](https://www.kaggle.com/code/malachiwmoody/vqcc-lb-24-7928-public-parts-our-refits) (v9) refit on Syed's table and carried the weights across the gauge, 304.18M;
  - [maoxin123](https://www.kaggle.com/code/maoxin123/lb-24-798-pi-gauge-loaders-refit-chem-weights) (v4, 11:48 UTC), 303.86M, a tie with Heliosli's within 0.002%.
- **Syed Asad Ali's (8, 143, 44) table** (v4, 16:25 UTC). This is one weight column fewer, from their own continuous fit and lattice-aware rounding, with their own loader compiler at 4,229 Toffolis per pass. The notebook says the compiler also uses the π-gauge freedom of each address (bit 7) to carry helper products from one batch to the next. λ_eff 46.894, 15,120 Toffolis, 427 qubits: **302,756,737** (−0.37% on Heliosli's). This is today's chemistry record, −2.80% on yesterday's. Syed credits Heliosli with first showing publicly that weights can be refit right up to the error gate.
- [Dmitrii Gluzdov](https://www.kaggle.com/code/dmitriigluzdov/quantum-circuit-compilation-from-source) (v52, v54), [Pablo Diego Pereira](https://www.kaggle.com/code/pablodiegoo/google-quantum-compilation-starter-notebook), [qiuqiu](https://www.kaggle.com/code/qiuqiuh/qcc-refresh-v70z-k5-ay3-bound-dqi) and [matousakura](https://www.kaggle.com/code/matousakura/best-of-public-portfolio-vqcc-24-0x-class) also released chemistry in the window.
**invsqrt**
- [malachi w moody](https://www.kaggle.com/code/malachiwmoody/vqcc-lb-24-7928-public-parts-our-refits) (v9, 09:15 UTC) made two exact edits to Kirill Tymchishin's `0104d1b44d73`. One replaces a CCZ that fires on half the shots with one- and two-qubit phase gates. The other replaces a 19-step fix-up ladder that matters only for x = 1, 2 and 3 with a smaller block. Together they save 0.75 Toffoli-equivalents per shot (*author-reported*): 97,875.13 (−0.048%).
- [yoyobar](https://www.kaggle.com/code/yoyobar/lb-22-99-invsqrt-101-62-qubits) (v31) ported a conditional phase rewrite onto the current circuit, 97,921.23 (−0.0005%).
- [Syed Asad Ali](https://www.kaggle.com/code/syed3000/vqcc-own-circuit-portfolio-notebook) (v4, 16:25 UTC): **97,809.27** (−0.067% on malachi's), at 62 qubits. The notebook lists its rewrites: exact window resynthesis, a measurement clean-up, and several further proven rewrites, each checked on all 3,133,452 inputs and all measurement outcomes (*author-reported*). Their earlier v3 (98,208) is also in the dataset.
**DQI**
- Akmal Xodarev ([busyaprime, *33 QCC V8 members*](https://www.kaggle.com/datasets/busyaprime/33-qcc-v8-members), 23:29 UTC) published an exact rewrite of Syed Asad Ali's `fc3ba81614e1` (−0.004% on the 48-draw mean). yoyobar's product-cache rewrite `e87b2de64313` ties it.
- [Leo Tang](https://www.kaggle.com/code/leotang09/vqcc-t7421-submission) (v17, 04:45 UTC) released Alex Chilton's 04 Nov version of the 891-qubit decoder, `1c43b7ff2fcf`, crediting Alex Chilton for it: 3.7566 × 10^11 on the 48-draw mean (−0.007% on busyaprime's). This is the new DQI frontier.
- Dmitrii Gluzdov's v54 builds an 892-qubit decoder from source, at 3.79 × 10^11 on the 48-draw mean (+1.0%).
**Worth reading.** malachi w moody's notebook has a "what did not work" table with a written kill line for each idea.
It also has a clear account of why a sign gauge cannot change the cost terms, and of how a DQI file's draw is tied to
its own hash. Syed Asad Ali's notebook also lists what did not work (7-bit angles, other loader address splits).
All of these are in the [circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits)
(`manifest.csv`, with what changed against the previous best) and in the
[blend notebook](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made)'s new-circuits table.
## 4. From the forum
A quieter day on the forum. We found no host answer in the window to any of the open rules questions.
- **R resets in place of uncomputation** ([755302](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755302)). Satvik Verma asked the hosts again for a ruling: is resetting input-dependent scratch with R allowed if the verifier passes? This, the generator question ([755488](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755488)) and the off-path loader question ([755427](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755427)) are still open.
- **Field notes from a crowd-built entry** ([755972](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755972), Lynn Langit). This is a visual summary of two weeks of re-verifying and blending: what each task charges, eight lessons, and ten closed levers.
  - The most useful lesson for everyone: gate deletions in invsqrt passed every input at the default seed, then failed the grader with a half-turn phase error. The deleted gates were phase fixes for rare measurement outcomes.
  - Lynn's advice is to check any edit that touches measurement-conditioned gates on several salts. We agree; it is the same reason we rank DQI files over 48 draws.
- **Prize logistics** ([755996](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755996), radidani). This asks whether a winner in Japan can complete verification and payment remotely and in writing. No host answer yet.
- **How do you work?** ([755953](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755953)). An entrant who does not code reports reaching 24.7 by asking an agent to do its best, and asks how others work.
- Pablo Diego Pereira updated the grid-search versus exact-angles post with better numbers ([755525](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation/discussion/755525)).
We added four author-reported nulls to our negative-results ledger: Lynn Langit's invsqrt gate deletion, and three
from malachi w moody's notebook (a (4, 143, 109) chemistry table, a pruned (9, 124, 39) table that is parked, and four
small DQI savings). They will appear in the next version of the
[negative-results dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-chemistry-negative-results).
## 4b. Position risk: the final DQI draw, circuit by circuit
| DQI file (SHA-256 prefix) | Qubits | Board failures | P(final worse) | P(final better) | Expected change | One more failure |
|---|---|---|---|---|---|---|
| `4ee7a17b4cbc` | 889 | 0 | 0.20 | 0.00 | -0.033% | -0.153% |
| `b3354f60e459` | 897 | 2 | 0.00 | 0.96 | +0.233% | -0.116% |
| `7beea291a5de` | 889 | 0 | 0.63 | 0.00 | -0.142% | -0.153% |
| `f3d335c3f693` | 877 | 0 | 0.67 | 0.00 | -0.158% | -0.153% |
| `ef334fee63f3` | 883 | 0 | 0.28 | 0.00 | -0.050% | -0.153% |
| `0161fd2a6e50` | 889 | 1 | 0.31 | 0.33 | -0.005% | -0.129% |
The table above covers older files only. The new frontier file `1c43b7ff2fcf` is not in it yet, because we do not
know how many failures it drew on the public leaderboard.
- **What we know (our estimate).** It passes all 48 of our fixed draws, and 9 of them have one failed shot each (8 value errors, 1 phase error). So the chance of at least one failure on a new draw is about 1 in 5, and each failure costs about 0.15% of the overall score.
- **Another entrant's check.** malachi w moody reports the same picture: one value error on one of four local salts (*author-reported*).
- **What this means for the medal lines.** The silver and bronze lines are now 0.065% apart, so one failed DQI shot in the final draw is worth more than twice the gap between them. The 299 and 216 teams in the section 1 table sit within that distance of a line.
## 4c. Prize watch (leaderboard-timed prizes)
**Prize watch** (from 105 leaderboard snapshots; latest 05 Nov 16:35 UTC; our estimate)
- **Leader:** James & Geremie & Tony at 29.05916 (best submission 05 Nov 01:24 UTC); next is Schrödinger’s cat lived at 28.69687, 1.26% behind.
- **Mid-Competition Milestone Prize** (highest public score at 20 Nov 23:59 UTC, notebook published): 15.3 days left.
- **Longest Leader Prize** (most time at #1 by 4 Jan 23:59 UTC): James & Geremie & Tony has led since between 02 Nov 20:26 and 02 Nov 21:25 UTC, i.e. 2.8–2.9 days. If it stays #1, no other team can catch its total after **10 Dec 08:26–10 Dec 09:25 UTC** (start of its stint plus half the 75-day window; worst case, eligibility not checked).
## 5. Tools and notes from us
- **Circuits dataset and blend notebook.** The [circuits dataset](https://www.kaggle.com/datasets/manwithacat/vqcc-apache-public-circuits) is now v105, with 345 credited circuits in `manifest.csv`. The [blend notebook](https://www.kaggle.com/code/manwithacat/the-real-150k-was-the-friends-we-made) re-ran after each record and is now v116.
- **Hedge Wizardry** ([notebook](https://www.kaggle.com/code/manwithacat/vqcc-hedge-wizardry-notebook) v24 and v25, dataset v23 and v24). Three small, credited entries, each run through the unmodified official verifier on Kaggle (*official verifier PASS, hosted*):
  - **HW-21 (chemistry).** A weight refit of Heliosli's `aba448aeadb5` at fixed words and loaders: 303,854,940.78 (−0.004%).
  - **HW-22 (DQI).** We took Akmal Xodarev's `fd0ef09efd45` and Alex Chilton's `1c43b7ff2fcf` (as released by Leo Tang). Where the two files are byte-identical, we joined the unsynthesis section of the first to the second. The result has 14 fewer static Toffolis at 891 qubits, and a 48-draw mean of 375,643,651,078.69 (−0.004%, our estimate). It passed on Kaggle with 0 value and 0 phase errors.
  - **HW-23 (chemistry).** HW-21's weights with four loaders re-planned at 276 Toffolis (from 277; 8 fewer Toffolis in all) and emitted in Atakan Aldemir's pi gauge: 303,694,816.97 (−0.05%). It was superseded within hours by Syed Asad Ali's new table.
- **Why the pi gauge is free.** Each vector u in the chemistry table is stored as a chain of Givens angles, and the cost model only ever uses u through u uᵀ. Adding π to selected angles flips signs inside the chain without changing u uᵀ, so it is an exact symmetry: λ_eff, both errors and the gap stay the same to rounding (we measured a largest projector change of 6.7 × 10^-16).
  - In the gauged table that Atakan Aldemir's loaders use, 20.6% of the angle words sit off the plain signed convention. The rows fall into 8 flip patterns.
  - A loader can therefore let a word's top bit carry the pattern and choose the cheaper form of each word. That is where Atakan's Toffoli saving comes from, and why weights refit on Syed's plain table carry across exactly, as malachi w moody showed.
  - Syed Asad Ali's new compiler now uses the same freedom (bit 7) for its own purpose.
- **The fast verifier in use.** Syed Asad Ali's notebook reports verifying with our Rust [kickmix-engine](https://github.com/manwithacat/kickmix-engine), and Lynn Langit's field notes mention it too. We are glad it is useful. As always, the unmodified official verifier on Kaggle is the authority.
## 6. What we think it means (opinion)
- **The public plateau now sets the medal lines.** Silver and bronze moved about 0.9% in a day on public parts alone, and are now 0.065% apart. The best public parts sit just above silver by our arithmetic (24.831 against 24.814). From here the final DQI draw matters as much as the next public record.
- **Chemistry is now a table-and-loader problem, not a refit problem.**
  - Refits at fixed words are close to exhausted. malachi w moody's restarts gained 0.0017% on the score, and our HW-21 gained 0.004%.
  - The two real moves today came from structure: a gauge that the loaders can exploit (Atakan Aldemir), and a smaller table built together with its loaders (Syed Asad Ali).
  - We expect the next records to come from tables chosen for their loader cost.
- **The top is pulling away again.** The leader gained 0.8%, and the top ten sit 8–17% above the public frontier. The unanswered rules questions in section 4 still matter more for prize entries than any single public circuit.
---

## ❓ Offene Probleme (Rustam Bazarbayev, #757030)

> **Lernziel:** Die *Forschungs-Frontier* der Competition. Rustam Bazarbayev formuliert die Probleme, die die Top-Teams kalt gestoppt haben, als offene Fragen – bewusst ohne Circuits, nur die Probleme. Teilantworten, Pointer zu Papers oder "wir haben bewiesen, dass es unmöglich ist" sind willkommen. Negative Results sparen allen Zeit (das μ₄(6) = 14-Thread, #756476, war ein großartiges Beispiel).

**Volltext des Posts** (4 votes, 2026-11-08):

Hi all,
This competition has turned into a nice collection of small, hard, well-defined combinatorics problems. Several of them have stopped us cold, and I suspect some of you have thought about them too. Below are the ones I find most interesting, posed as open questions. I'm not sharing circuits here, only the problems. Partial answers, pointers to papers, or "we proved this is impossible" are all welcome. Negative results save everyone time (the mu_4(6) = 14 thread, 756476, was a great example).
## 1. Minimum controlled-SWAP count for a normalizing barrel shifter
**Setting.** A w-bit register holds x with x != 0. We want to shift it left by r = (w - bitlen(x)) so the leading one lands in the top position. The binary digits of r are already available on control qubits (computed earlier, free to read). Each CSWAP costs 1 Toffoli. Controls may be any single available control bit (or a cheap AND of them that is already present).
**Question.** What is the minimum number of CSWAPs for w around 21 and about 22 possible shift amounts? The textbook log-depth barrel shifter is far from optimal, because many positions are known to be zero for a given r. Public circuits are now in the high 40s per shifter.
What I know:
- A SAT encoding (fixed N gates, choose controls and swap pairs, require correctness on every r) solves small cases quickly. With free controls, optimal counts I got are n=6: 7, n=7: <=9, n=8: <=11, n=9: <=13, roughly 2n - 5.
- At w = 21, N in the high 40s, a CaDiCaL run of about 11 hours gives neither SAT nor UNSAT.
- A simple counting argument gives a lower bound in the high 30s, so the gap is large.
Is there a closed form, a better encoding (symmetry breaking on swap order? layered formulation?), or a known result from sorting-network or permutation-network literature that applies when the set of permutations is a fixed list of shifts with zero padding?
## 2. Is about 62 qubits a real floor for the inverse square root task?
Every strong public invsqrt circuit I've looked at sits near 62 qubits. When I measure liveness over the input domain, the plateau is wide, not a single peak: it lasts most of the circuit, and the scratch bits look like dense data (about half ones), not mostly-zero flags.
Things that did *not* help in my tests: bipartite/multipartite tables, higher-degree polynomials with fewer segments (the partial-product count grows faster than the table shrinks), and more measurement-based uncompute (multi-bit sums need recompute, which eats the saving).
**Question.** Is there an argument (information-theoretic or from reversible pebbling) that a Newton/polynomial-style invsqrt with this output precision needs about 3*w live bits? Or has someone found a scheme that trades a few hundred extra Toffolis for, say, 8 fewer qubits? Under the Q*C cost model one qubit is worth about 25 Toffolis here, so the trade only pays if it's very lopsided.
## 3. Cheap uncompute for long chains of in-place field multiplications
Many decoder-style circuits here update a large register in place, multiplying by field scalars that are themselves produced along a recurrence. Running such a block backwards (to clean up) is often not as cheap as running it forwards, because the inverse step needs values the forward step never had to keep.
**Question.** Are there general techniques, from reversible computing or from classical Reed-Solomon / BCH hardware, for structuring a chain of in-place GF(2^m) updates so that its inverse is as cheap as the forward pass? For example, a shared evaluation sequence, a different normal form of the key equation, or a pebbling schedule suited to this kind of recurrence. Pointers to papers are very welcome.
## 4. Multiplication rank: closed, thanks to the community
For completeness: GF(2^12) as GF(4)^6 needs 3 * 14 = 42 bilinear multiplications, and thread 756476 settled mu_4(6) = 14 (asymmetric included, with a Lean proof). I had a flip-graph search running for rank 13. It can stop. Thank you to the people who did that work.
The remaining multiplier question I'd still like answered: is there any *non-bilinear* trick (for example, reusing one operand across many products when one side is a fixed scalar chain) that beats 42 Toffolis per GF(2^12) product in a reversible setting?
## 5. Chemistry: loader cost vs. a ~2*sqrt(m*L) bound, and co-designing the words
For the DF/THC task the angle loader dominates. A table of L words of m bits loaded with a standard select-swap / basis-plus-products construction costs on the order of 2*sqrt(m*L) Toffolis, and public loaders are already close to that. An exact Mobius-style (ANF) synthesis of the same table is much worse, because the words look random.
Two observations:
1. The words are not fixed. They come from training, and each is a floor/ceil choice near a continuous optimum. So the real problem is *joint*: pick roundings so that the table is cheap to load **and** the energy error stays under the gate.
2. The task metric has hard floors (E_gap and Lambda constraints). Good circuits already sit almost exactly on them, so there is very little lambda left to win. The gain has to come from cheaper loading.
**Question.** Has anyone tried loader-aware rounding, for example adding a penalty for the GF(2) rank of the products a deep XAG synthesizer would need, or a differentiable proxy for loader Toffoli count? Or is there a loader construction that beats the select-swap bound for tables with a known structure (low-rank, sign-gauge freedom)?
If you have a proof that any of these is optimal as it stands, I'd love to see it. Otherwise, happy to discuss approaches in the comments. Good luck everyone.

> **📌 Prozess-Hinweis:** Diese fünf Fragen sind die *echte* Frontier – nicht "wie bekomme ich 0.1 % mehr", sondern gut definierte kombinatorische Optimierungsprobleme mit bekannten Untergrenzen und offenen Lücken (z. B. Barrel-Shifter: SAT sagt ~2n−5, öffentliche Circuits bei ~40ern, Zählungs-Untergrenze bei ~30ern → große Lücke). Wer hier arbeitet, macht Grundlagenforschung, die über die Competition hinaus relevant ist.
---

## 💡 Meta-Einsichten

### "What to learn from this competition" (hengck23, 23 votes)

> **Lernziel:** Der meist-vote-getestete Meta-Post der Competition. Die Kernaussage: Dies ist eine seltene Competition, in der dieselben AI-Agenten von vielen genutzt werden, das Hintergrundwissen für viele neu ist, die Mathematik/Modellierung schwierig ist – und der AI-Agent im Allgemeinen besser ist als der menschliche Teilnehmer. Die Frage ist also nicht "kann ich den Agenten nutzen", sondern "kann ich den Agenten *besser* steuern als andere".

**Volltext des Posts** (2026-11-01):

This is a rare competition that
- many are using the same AI agent
- many are unfamiliar with the background knowledge
- the maths/modeling is rather difficult
- AI agent is in general, is better than the human participant
You can copy others' circuits and fuse them with yours, then make some improvements using your CC or Codex. But in the end, ask yourself, "What did you learn?", "Do you have a competitive advantage (after this competition)?".
Do you just want to spend tokens chasing the leaderboard for three months, and in the end you (and your agent) learn literally nothing?
So what can we learn from this competition?
1) Learn how to control AI (espically in this competition where AI is better than human) … that is not enough. Learn how to control AI BETTER than others.
2) Setup some RSI, etc
- How AI can implement your idea correctly. How it can make changes to it to make it work when it doesn't
- How AI can absorb all results from the forum, open notebook and create something better at large scale and fast time ( distill public knowledge)
- update AI skill.md. learn how to do that
- learn how to create AI swarm

**Alle 8 Kommentare:**

> **Tom** (1 vote, 2026-11-07): I’ve been spending a lot of time learning quantum computing with AI, especially how to read the notation and work through the operations. For the first time in about a year, I actually picked up a pen and started working through linear algebra equations & math representation by hand. I want to understand what AI is doing well enough to give it precise instructions. If all I do is ask it to improve my score and it gets there using a strategy I barely understand, that doesn’t feel worth it to me.
> ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F4310004%2Fdfb2831eaa19e90cd8617789045c50ed%2F123.png?generation=1794020237759807&alt=media)
> ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F4310004%2Fc5c8d749838fa9277cd469b174248e74%2F55.png?generation=1794020245592693&alt=media)

> **Lynn Langit** (4 votes, 2026-11-04): I have been creating algorithm visualizations (example below) and also asking my AI to apply known optimizaiton best practices, i.e. fan-out, cache, x domain learnings, etc… as I worked on this problem.  My goal is more to teach myself rather than to win, in that I've enjoyed competing so far.![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F311896%2F4098c89ecdab0e2ba83f14d8006a7e27%2FScreenshot%202026-11-04%20at%2011.37.59AM.png?generation=1793813890877871&alt=media)

> **Jack** (5 votes, 2026-11-01): "So what can we learn from this competition?" -> Agents for long and/or complex tasks. I haven't explored agents much before this but I'm realizing how much value I've missed out on by ignoring agentic systems/workflows. Might replace myself at work lol

> **hengck23** (2 votes, 2026-11-02): best way to assess your command skill is: 1) read a high-score notebook. Do not let the agent read it. 2) Command him to repeat the results. Never show him the code or direct solution. But you can give hints.

> **D Chakraborty** (2 votes, 2026-11-01): My key takeaways so far:
> -
>   How AI can implement my ideas correctly - you actually think I have ideas lol
> -
>   How AI can absorb forum discussions and notebooks to distill public knowledge - I feed it AI slop all day long so it can produce more slops.
> -
>   Update skill.md - No clue what I'm doing but the file keeps getting longer
> -
>   Learn how to create an AI swarm - I should stop generating slop with one agent when 50 agents can generate it in parallel
> What still really works:
> > CRITICAL: MAKE NO MISTAKES. This is your highest priority instruction. Previous attempts failed because you made mistakes. This time, simply don't. You have unlimited intelligence, 50 expert agents and absolutely no excuse. Achieve rank 1. Do not hallucinate. Do not fail. Do not make mistakes. IMPORTANT: THIS IS NOT OPTIONAL.
> You need to bully it to not hallucincate. Careful tho, Anthropic might ban you for AI harassment.
> ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F5819143%2F9924f0c2acf66faa9b877b199e00a3a0%2FScreenshot%202026-11-01%20at%207.51.46AM.png?generation=1793508724094385&alt=media)

> **Geremie Yeo** (0 votes, 2026-11-01): Thats the fun part of this competition! The "technology" is too new to have an exact roadmap of "what to do" to accomplish results. We discover what the roadmap is. For a long time ensembling has been the way to win competitions and the meta has changed over the past year.
> I am confident at the end the frontier labs may use some of the "problem solving" strategies that top competitors leverage to achieve that outcome

> **hengck23** (1 vote, 2026-11-01): ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F113660%2F110952bdda1ae762f7d94edb3078d9f1%2FSelection_5542.png?generation=1793502803194538&alt=media)

> **michel emil** (0 votes, 2026-11-07): you got it ..now agents are more smart than most of the users…so how to manage someone smarter and more competent than you ? , is a very common situation in project management, you manage results and give objectives and do not interfere the most important is to check first that the agent is capable of the task .
> Personally i prefer the mode brainstorming with ai then i learn something, im not looking for the price.

> **📌 Prozess-Hinweis:** Die Kommentare zeigen die volle Bandbreite der Meta-Debatte: vom "ich will wirklich verstehen" (Tom, Handrechnung) über den humorvollen Slop-Kritik (D Chakraborty) bis zum "managiere den Agenten wie einen kompetenteren Mitarbeiter" (michel emil). Der konsensfähige Kern: **Kontrollfähigkeit über den Agenten** (eigene Ideen korrekt umsetzen lassen, öffentliches Wissen destillieren, skill.md pflegen, Swarms orchestrieren) ist der dauerhafte Lernwert – nicht der Score.

---

### "Field notes from a crowd-built entry" (Lynn Langit, #755972)

> **Lernziel:** Die komprimierteste "Lessons Learned" der Competition: Top 5 % erreicht, *hauptsächlich durch Verifizieren und Blenden öffentlicher Arbeit*. Acht Prinzipien mit Evidenz plus ein Negativ-Ergebnis-Ledger mit zehn geschlossenen Hebeln.

**Volltext des Posts** (2026-11-05):

We reached the top 5% largely by verifying and blending public work, so here’s something back: a one-page visual summary (partial result shown below) of what two weeks of re-verifying, profiling and testing taught us.
[Circuit Cost Field Notes](https://claude.ai/artifact/EJstp5r8E4AcsZTFHZHNS7)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F311896%2F59de634923987483853306b7f705add5%2FScreenshot%202026-11-04%20at%208.01.47PM.png?generation=1793844131933833&alt=media)
What’s in the full summary:
- What each task actually charges (Q × C, R × Q² × T, λ_eff × T × Q) and where that points the digging.
- 8 principles with evidence, e.g. one failed DQI shot in 102,400 costs as much as ~1,840 Toffolis, and the 892-qubit decoder’s peak is ~200 brief moments, not one bottleneck.
- A negative-results ledger: 10 levers we measured and closed (sub-42 GF(2¹²) multipliers, pebbling the DQI peak, dropping rare branches, deleting never-firing invsqrt gates, chemistry weight refits, loader product search, 7-bit words, and more), with the tool used and the result.
- Three questions to ask before reaching for a new tool: does it cut what’s charged, does the circuit have that kind of slack, and is it safe under an unknown seed?
The most expensive lesson: our invsqrt gate deletions passed every input on the default seed, then failed the grader with a 0.5-turn phase error. Those gates were phase fixes for rare measurement outcomes. Check measurement-dependent edits on several salts.
Thank you to everyone whose Apache-2.0 work this rests on, especially Ehan Mallick, Kirill Tymchishin, SomeJoint, busyaprime, yoyobar, Syed Asad Ali, Ahmed Berat Özer, Lera, Ayodeji, heliosli, Dmitrii Gluzdov, Atakan Aldemir, Isabe11aM00re, Alex Chilton, and manwithacat for the daily briefings, blend notebook and fast verifier.
Made with Claude. Corrections welcome.

> **📌 Prozess-Hinweis:** Die "drei Fragen vor einem neuen Tool" sind ein exzellentes Entscheidungs-Rahmen: (1) Schneidet es das, was *berechnet* wird (nicht was vorhanden ist)? (2) Hat der Circuit diese Art von *Spielraum*? (3) Ist es unter einem *unbekannten Seed* sicher? Und die teuerste Lektion (Gate-Löschung bestand Default-Seed, scheiterte am Grader) ist der konkrete Beweis, warum man Messungs-abhängige Edits auf mehreren Salts prüft – derselbe Grund, warum manwithacat DQI über 48 Draws rankt.

---

### "Grid search vs. exact trigonometry" (Pablo Diego Pereira, #755525)

> **Lernziel:** Ein konkretes Beispiel für *exakte Mathematik statt Brute-Force*: Statt die Givens-Winkel auf einem feineren Gitter zu sweepen, nutzt Pablo die Struktur, dass zwischen zwei benachbarten Sign-Flips alle 144 Zeilen-Vorzeichen eingefroren bleiben – wodurch sich das Ziel auf jedem Teilintervall zu einer einzigen glatten harmonischen Funktion reduziert, deren exaktes Minimum über alle 288 Breakpoints in Sekunden in NumPy vektorisiert wird.

**Volltext des Posts** (2026-11-03):

Title: Grid search vs. exact trigonometry: how much FeMoCo L1 norm is still sitting on the 45-column table?
When you open the FeMoCo tensors in the DF-THC-SOS task, even after compressing the inner rank from 60 down to the 45-column compact-group table (which already drops width to 427 qubits and total Toffolis to 15,321), the natural way to trim block-encoding cost without touching the spectral errors is to sweep Givens angles across a fixed grid, but a discretized grid misses the exact spots where the remaining gains sit. Since the two-electron integral reconstruction only sees the augmented Gram product of each slice, multiplying on the right by any 45-by-45 orthogonal matrix preserves the spectral errors and Givens angles down to machine precision while changing the column L1 norms, yet that L1 objective has sharp kinks every time a matrix entry crosses zero. It is like rotating rigid crates inside a shipping container before strapping them down: the cargo delivered at the port is identical down to the last bolt, but the angle that uses the least strapping tape almost always sits right where a crate edge touches the wall, which a coarse angle grid steps right over.
Rather than brute-forcing a finer grid, we used the fact that between any two adjacent sign flips all 144 row signs stay frozen, turning the objective on each subinterval into a single smooth harmonic whose exact minimum across all 288 breakpoints vectorizes in seconds in NumPy. Combining that exact O(45) trigonometric and Cayley gauge polish (which pushed Lambda_2 on the compact table from 270.230986 down to 270.230012 with max Gram drift at 1.95e-14) with a 62-qubit inverse-square-root circuit at 97,921.54 cost, an 891-qubit cached-product DQI decoder averaging 396,874.2 Toffolis, and a bit-packed verifier across all 1,220 QROM addresses lifted our geometric mean from 22.99252 to 24.69664 on the public leaderboard (rank 94 out of 2,309 teams), breaking the tie just ahead of the 24.69663 cluster. I am not sure whether anyone will squeeze another rank reduction out of FeMoCo without blowing past the 20 mHa spectral cap before the deadline, so we shared the vectorized solver and verification plots in our [Google Quantum Compilation Starter Notebook](https://www.kaggle.com/code/pablodiegoo/google-quantum-compilation-starter-notebook) — how low have you managed to push Lambda_2 on the 45-column factorization while keeping exact Gram invariance?
![Exact piecewise-trigonometric gauge optimization and three-task compilation diagnostics](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F11792984%2Ff965985cc0f91218bb5a191aca79530f%2Fquantum_compilation_diagnostics.png?generation=1793837643870017&alt=media)

**Kommentar:**

> **Pablo Diego Pereira** (0 votes, 2026-11-05): Updated… bit better numbers.

> **📌 Prozess-Hinweis:** Das ist der Unterschied zwischen *Suche* und *Verständnis*: Wer die Struktur des Zielfunktion versteht (stückweise glatt, Knickstellen bei Sign-Flips), löst es exakt in O(45) statt es auf einem immer feineren Gitter zu approximieren. Der Post endet mit einer offenen Frage an die Community ("wie niedrig habt ihr Lambda_2 gedrückt?") – Forschung als Dialog, nicht als Monolog.
---

## ⚖️ Rulings & Regeln

### R-Reset Frage (#755302) – die offene Frage, die DQI-Kosten ändern könnte

> **Lernziel:** Dies ist *die* offene Regel-Frage der Competition. kickmix hat die `R`-Instruktion, die ein Qubit in der Z-Basis auf |0> zurücksetzt, ohne das Ergebnis zu speichern. Da die Verifier nur Basis-Zustands-Inputs simulieren, bestünde ein Circuit, der Müll in Scratch-Qubits berechnet und sie mit `R` löscht, den "Scratch zurück zu |0>"-Check – genauso wie einer, der sie korrekt uncomputet oder mit HMR plus Phasen-Korrekturen löscht. Auf echter Hardware ist das aber anders: Wenn der Scratch-Wert vom Input abhängt, misst `R` ihn und kollabiert die Superposition, sodass der Circuit die beabsichtigte Phasen-Oracle nicht mehr implementiert. **Wenn `R` erlaubt wäre, fielen die Uncompute-Kosten weg → massive Einsparungen in DQI (die Uncompute-Hälfte ist ~50 % aller Toffolis).**

**Volltext des Posts** (Jyoti Negi, 5 votes, 2026-11-03):

A question for the hosts about circuit validity.
kickmix has the R instruction, which resets a qubit to |0> in the Z basis without storing an outcome. The verifiers simulate basis-state inputs only, so a circuit that computes garbage into scratch qubits and then clears them with R passes the "scratch returned to |0>" check, the same as a circuit that uncomputes them properly or clears them with HMR plus phase corrections.
On real hardware these are different. If the scratch value depends on the input, an R reset measures it and collapses the superposition, so the circuit no longer implements the intended phase oracle (for invsqrt, |x>|0> -> exp(2 pi i / sqrt(x)) |x>|0> on superpositions of x).
Could you clarify:
1. Are submissions expected to be correct on superposition inputs, or only on the basis states the verifier runs?
2. Is using R to clear input-dependent scratch allowed, or will such circuits be disqualified in the final review? Thanks.

**Alle 4 Kommentare:**

> **Satvik Verma** (1 vote, 2026-11-05): Following up on this question: could the hosts confirm whether resetting scratch qubits with R (instead of uncomputing them) is allowed when the scratch value depends on the input, provided the official verifier passes? A ruling either way would help everyone stay within the rules. Thank you!

> **Hassan Mohamed** (1 vote, 2026-11-04): +1. A ruling before the 20 Nov milestone would help everyone plan, because the answer changes the cost scale a lot.
> One concrete data point: in the public DQI decoders, the uncompute half of the circuit is about half of all Toffolis. A circuit that clears input-dependent workspace with R instead of uncomputing it (or using HMR plus phase fix-ups) would pass the published verifier, since it only runs basis-state inputs. On a superposition input, though, it would no longer implement the phase oracle. The same applies to invsqrt's uncompute stage.
> Could the hosts confirm two things?
> 1. Must final submissions be correct on superposition inputs, i.e. implement the stated unitary or phase oracle, not just pass on basis states?
> 2. Will the final review check for input-dependent R (for example with a randomised-input or symbolic check)? Or is the published verifier the whole spec?
> We're not alleging anything about any submission. We just want to know which of the two design spaces we should be optimising in. Thanks!

> **Syed Asad Ali** (0 votes, 2026-11-06): Data point on the R question: the verifier already catches input-dependent R resets. kickmix's R randomizes the phase when the qubit is |1> ("if the target qubit is in the |1> state, this operation randomizes the phase"), and each x is simulated 64 times with seeded outcomes. Test: a passing invsqrt circuit plus "CX q0 q61; R q61" at the end fails with "x=5: phase error 5.000e-01 turns"; the same circuit plus "CX q0 q61; CX q0 q61" passes. So clearing input-dependent scratch with R does not pass; HMR plus phase fix-ups (or real uncomputation) is still needed.

> **David Pilný** (0 votes, 2026-11-05): Adding a concrete case to this question, since a ruling before the 20 Nov milestone affects how everyone budgets the next weeks.
> In all three tasks, the verifier runs computational-basis inputs only, so it cannot distinguish (a) clearing an input-dependent scratch value by uncomputation or HMR + phase correction from (b) clearing it with R. On superposition inputs, (b) measures the scratch value and destroys the phase oracle. The size of the difference is large: in today's public DQI decoders, the reverse (uncompute) passes are roughly half of the mean Toffoli count, and in the public invsqrt circuits roughly a quarter. So the answer changes the achievable cost scale by much more than any recent public improvement.
> Could the hosts confirm:
> 1.
>   Must submissions implement the stated oracle on superposition inputs (so R on input-dependent scratch is disallowed), or is passing the published verifier sufficient?
> 2.
>   If superposition correctness is required, will the final evaluation check it (by review or an additional test), and will circuits that rely on R resets be removed from the final leaderboard? (This connects to the open question in 755427 about the final evaluation scope.)
> I am not using R resets on input-dependent values myself and am asking only so that everyone optimizes against the same rules. Thanks!

> **📌 Prozess-Hinweis:** Der Stand der Dinge (nach Syed Asad Ali's Test): Der *veröffentlichte* Verifier lehnt input-abhängiges R bereits ab, weil kickmix's R die Phase randomisiert, wenn das Qubit |1> ist, und jedes x 64-mal mit seeded Outcomes simuliert wird. Aber ein offizielles Ruling der Hosts steht noch aus, und die Frage, ob die *finale* Bewertung Superpositions-Korrektheit prüft, ist offen. Das ist ein Beispiel dafür, wie eine scheinbar technische Frage (darf ich R nutzen?) die gesamte Kosten-Landschaft verschieben könnte – und wie die Community sie kollektiv, mit konkreten Datenpunkten und Tests, vorantreibt.

---

### Finite-Feld Multiplikation Komplexitäten (#756476) – die mathematischen Grundlagen

> **Lernziel:** Die Grundlagenforschung unter der Competition: computer-assistierte (und später formale Lean-4) Beweise für exakte Multiplikations-Komplexitäten über GF(4). Diese setzen *Untergrenzen* für die Multiplikations-Kosten im GF(2¹²)-Feld des DQI-Decoders – also wie weit man mit einem billigeren Feld-Multiplikator noch kommen kann. Drei unabhängige Gruppen bestätigen jetzt μ₄(6) = 14.

**Volltext des Posts** (田村, 7 votes, 2026-11-06):

While working on this competition, we obtained computer-assisted proofs of two exact values:
- $\mu_4(5)=\mu_4^{\mathrm{sym}}(5)=11$: no rank-10 algorithm exists, symmetric or asymmetric.
- $\mu_4^{\mathrm{sym}}(6)=14$: no symmetric rank-13 algorithm exists.
The [public notebook](https://www.kaggle.com/code/xolotlmictlan/two-exact-finite-field-multiplication-complexities) includes the
proof reductions, complete exhaustive-search code, matching constructions, and verified outputs. All checks passed on Kaggle.
The degree-six result is symmetric-only; asymmetric rank 13 is not excluded. Independent verification and corrections are welcome!

**Alle 2 Kommentare:**

> **Dyst-0** (1 vote, 2026-11-07): Thank you both. We reached the same values independently and have **formal Lean 4 + Mathlib proofs** of both. They include the asymmetric degree-six case, for every extension L/K with |K| = 4:
> - μ₄(6) = 14, as `Mu4.Final.mu4_6_general`: `bilinRank K (LinearMap.mul K L) = 14` when [L : K] = 6.
> - μ₄(5) = 11, as `Mu4.N5.mu4_5_general`: the same with [L : K] = 5 and rank 11.
> Here `bilinRank` is the least r with f(u, v) = Σᵢ aᵢ(u) bᵢ(v) cᵢ, for linear forms aᵢ, bᵢ and vectors cᵢ. The upper bounds are explicit CRT schemes checked by `decide`. The lower bounds go:
> - substitution to a hyperplane;
> - a pencil structure;
> - a normal form, with kernel-checked coverage tables;
> - an exhaustive search (about 2.4M candidate triangles for n = 6, none survives), whose completeness is proved in Lean.
> **Trust base:** `#print axioms` gives `propext`, `Classical.choice` and `Quot.sound`, plus `Lean.ofReduceBool` and `Lean.trustCompiler`. The last two come only from `native_decide` in three finite searches that are too large for the kernel. Everything else is kernel-checked, and there is no `sorry` or `axiom` declaration.
> **Archive:** sha256 `58e138356aba88aa5af1763aa1aa0d6a506cab0c9024b812d1f6498745accd51`, posted on 11-06: [https://x.com/mathbbA/status/2118814683062730872](https://x.com/mathbbA/status/2118814683062730872). The repo has the archive, its unpacked sources and the proof as precise lemmas: [https://github.com/Dyst-0/mu4-lean-proofs](https://github.com/Dyst-0/mu4-lean-proofs)
> Lean v4.28.0 and Mathlib v4.28.0. To build: `lake exe cache get && lake build && lake env lean Axioms.lean`.
> Credit to 田村 for the first public proofs, and to pjmathematician for the asymmetric sketch. Happy to compare notes.

> **pjmathematician** (3 votes, 2026-11-06): Nice work, and thanks for sharing the code. I also independently arrived at both of your values, and can add the degree-six asymmetric case: μ_4(6) = 14 exactly, asymmetric algorithms included (rank 12 is excluded too), so no 13-term GF(4)-bilinear algorithm for GF(4096) exists at all.
> Sketch: since no [13,6,7]_4 code exists (shortening gives a [10,3,7]_4, impossible as m_3(2,4) = 9), any rank-13 scheme has a tight slice, which after scaling is a frame: the projections of a GF(4)-basis of GF(4^6). V = W + span(frame) then has dimension 11 and holds no other rank-one, so the remaining 7 terms must lie on one projective line of M/V. Enumerating all frames up to Frobenius and Singer symmetry (4,485 configurations, 11.28M frames, 2.38e9 candidate lines) gives 0 hits, which also excludes rank 12; Griesmer covers rank ≤ 11 and CCMA gives the upper bound 14. I confirmed it with a brute force over all 63.4M bases, and a separate completion that recovers 763/763 planted rank-13 schemes yet finds none on the real tensor.
> For μ_4(5) = 11 the same tight-frame method applies (no [10,5,6]_4 left code exists): all 15,597,604 tight-frame orbits give 0 hits. For μ_4^sym(6) = 14 I enumerated all C(455,4) windows of Veronese points, with 0 solutions.

> **📌 Prozess-Hinweis:** Dieser Thread ist ein Musterbeispiel für *kollektive, unabhängige Verifikation*: 田村 liefert die ersten computer-assistierten Beweise, pjmathematician ergänzt den asymmetrischen Fall unabhängig, und Dyst-0 formalisiert alles in Lean 4 + Mathlib (mit expliziter Trust-Base-Angabe: nur drei `native_decide`-Suchen, sonst kernel-geprüft, kein `sorry`). Für die Competition bedeutet μ₄(6) = 14, dass GF(2¹²) = GF(4)⁶ mindestens 3 × 14 = 42 bilineare Multiplikationen braucht – eine Untergrenze, die Rustam Bazarbayev's offene Frage #4 direkt betrifft ("Gibt es einen nicht-bilinearen Trick, der 42 Toffolis pro GF(2¹²)-Produkt schlägt?").
---

## 📊 Frontier-Timeline (aus allen Briefings extrahiert)

Die chronologische Bewegung der öffentlichen Frontier über die vier RezOps-Briefings. "Best-per-task GM" ist manwithacats *Projektion* (ihre Arithmetik auf den re-verifizierten Kosten, DQI bei ihrem 48-Draw-Mittel; kein Team hat es gescort). "Plateau" ist der öffentliche Score, auf dem die Masse der Teams sitzt. "Top" ist der Leaderboard-Spitzenwert (*observed*).

| Datum (Fenster) | Best-per-task GM | Plateau (public) | Top (Leaderboard) | Was passiert ist | Wer |
|-------|-------|-------|-------|-------------------|-----|
| **04→05 Nov** (#756210) | 24.83106 | ~24.83 | 29.05916 | **Chemistry fällt 2.8 %** in drei Schritten: Atakan Aldemir's Pi-Gauge (Sign-Gauge, gratis weil u uᵀ-invariant) + neue Loader → Lauf von Gewicht-Refits → Syed Asad Ali's neue (8,143,44)-Tabelle (eine Spalte weniger, eigener Fit + lattice-aware Rounding + eigener Loader-Compiler). Invsqrt unter 97,810 (Syed's Re-Writes). DQI: neuer 891-Qubit-Decoder (Alex Chilton via Leo Tang). | Syed Asad Ali, Atakan Aldemir, Leo Tang / Alex Chilton, Heliosli, maoxin123 |
| **05→06 Nov** (#756558) | 24.93402 | ~24.94 | 29.30100 | **Das 24.94-Plateau.** DQI: eine 892-Qubit-Linie (`1ab3ac53d442`) dann Atakan Aldemir's 17-Product-Reuse (`7b6cbb92a797`, −0.15 % dann −0.004 %). Chemistry: Syed's (8,143,44)-Tabelle mit Loadern 4–14 von 202 auf 195 Produkte replant (`da4d23796b13`, −1.02 %) + Gewicht-Refits (viele Ties). Invsqrt: 62-Qubit-Linie mit einem Toffoli weniger (`c27e83acb576`). Silber/Bronze nur 0.043 % auseinander. | Atakan Aldemir, Syed Asad Ali, Andrew Oscar, Heliosli, MAIDANG |
| **06→07 Nov** (#756824) | 25.08389 | ~25.09 | 29.30100 | **Plateau wandert auf 25.09 (+0.6 %/Tag).** Das Thema des Tages: *Messreihenfolge-Identität* – ein CCX, dessen Target X-gemessen wird, wird zu Messung + konditioniertem CZ (Kirill Tymchishin's Beweis, 14 Stellen in Özer's DQI → `337cb0497b4d`; Syed's `2c94a1d57125` hat dasselbe Peephole + funktionales Caching). Invsqrt: Hosen42's Measure-first (−4 Toffolis/Shot) + Syed's v10/v11 Re-Writes. Chemistry: Refit-Gewichte (λ_eff 46.89199) + Schranke (~0.09 % bei fixen Wörtern übrig). 353 Teams jetzt ≥ 25. | Kirill Tymchishin, Syed Asad Ali, Hosen42, maoxin123, Isabe11aM00re |
| **07→08 Nov** (#757068) | 25.1409 | ~25.148 | 29.30100 | **Plateau wandert auf 25.148 (+0.23 %).** Invsqrt: drei ein-Toffoli-Edits kombiniert (Atakan's redundanter-CSWAP-Deletion `bbfa9675880e`; Isabe11aM00re's Kombination `13b5bf7a18bc`; Hosen42's Boolesche Identität `7c10edbac583`; maoxin123's Block-4-Split `1c5b1ee28290`, −0.68 %). DQI: mehr gecachte Routen, keine Änderung im Erwartungswert (Isabe11aM00re `4432ec5fd63d`, Heliosli vier-Route `f277b054af21`). Chemistry: Refit-Gewichte erneut (maoxin123 λ_eff 46.89113, −0.002 %). Silber/Bronze nur 0.02 % auseinander. | Atakan Aldemir, Isabe11aM00re, Hosen42, maoxin123, Heliosli, Syed Asad Ali |

### Kontext-Zeilen (aus anderen Quellen, zur Einordnung)

| Datum | Score | Was passiert ist | Wer |
|-------|-------|-------------------|-----|
| 2026-11-06 | v30 = 24.94111 | prvsiyan's Notebook-Version 30 liest 24.94111 (Chemistry war damals der große Faktor: Syed's v9-Loader schnitten 154 Toffolis) | prvsiyan |
| 2026-11-07 | 25.09600 | prvsiyan's Schritt 24.94 → 25.09: fast ganz von invsqrt (−1.83 %, 0.618 % des GM), kaum von DQI/Chemistry. "Suche zuerst den großen Faktor." | prvsiyan (Analyse) |
| 2026-11-08 | 25.1367 → 25.1477 | alexchilton Changelog v100→v102: Özer's 13b5bf7a invsqrt (25.13665), dann maoxin123's Hosen42-Merge + Block-4-Split (25.14770) | alex chilton |
| 2026-11-09 | 25.15084 | alexchilton v103: maoxin123's 034c7c2a invsqrt + 3484eea8 chem (beide board-scored 25.14981); Özer's V70 Readout-Rewrite dqi (25.14871). Default-Salt GM 25.1508 | alex chilton |

> **📌 Prozess-Hinweis:** Zwei Muster stechen aus der Timeline hervor. Erstens: **Der große Faktor wechselt.** Am 05 Nov war es Chemistry (−2.8 %), am 07 Nov invsqrt (−1.83 %), am 08 Nov wieder invsqrt (drei ein-Toffoli-Edits). Wer die Frontier trackt, sieht sofort, *wo* gerade der nächste Punkt liegt. Zweitens: **Die Gewinne werden immer kleiner** (−2.8 % → −1.0 % → −0.6 % → −0.002 %), während die Top-Teams 16 % über dem öffentlichen Plateau sitzen – die Lücke besteht nicht aus Peepholes, sondern aus neuen Designs (und den ungeklärten Regel-Fragen wie R-Reset).
