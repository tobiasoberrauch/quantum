
Independent research report · 3 November 2026 · Targets: Top 170 and Rank 1

Executive assessment

The immediate objective is not to develop a completely new quantum compilation architecture. It is to find a verified 0.68% reduction in one benchmark's cost, preserve the other two circuits, and cross the 24.00057 leaderboard threshold.

The longer-term objective is fundamentally different: reaching approximately 28.0 requires a major circuit-family improvement, a combination of independent advances, or a complementary team merger.

My preliminary recommendation is to operate three tracks in parallel:

Target A — public-frontier exploitation: search for a small, reproducible improvement in DQI, chemistry, or inverse square root. Require an official-verifier pass before adopting anything.

Target B — independent research: prioritize structural arithmetic improvements and alternative DQI schedules over further work on the already-disproved constant-seed implementations.

Merger strategy: establish technical complementarity and licensing provenance now, rather than waiting until the January merger window.

One important qualification: the accessible Kaggle pages contain inconsistently refreshed leaderboard snapshots. I can independently verify competition activity and published research, but I cannot treat every search-indexed leaderboard figure as the authoritative live state.

1. Current-state verification

The competition is real and active. Its official Kaggle page identifies Google Quantum AI as the organizer and confirms the $150,000 prize pool. The research paper, Leveraging verifiable structure in quantum circuits to find more efficient compilations with agentic AI, is available as arXiv:2610.23832, with a revised version dated 21 October 2026. 
Kaggle
+1

The paper confirms the three application families and the importance of classically verifiable structure: reversible classical logic, phasing, and measurement-based uncomputation. It does not, by itself, establish that the current leaderboard frontier is near a theoretical optimum.

A publicly accessible Kaggle leaderboard snapshot reports Breaking1800 at 27.15971, Jack at 27.14274, and Schrödinger’s cat lived at 27.06470. This conflicts with the 27.99617 leading score in your newer local download. The two observations should not be silently combined. 
Kaggle

For this report, I will use your 2 November component measurements as the working experimental baseline, not as independently verified live results.

1.1 Verified arithmetic: the baseline is internally consistent

Using the three reference costs and submission costs supplied in your brief:

Benchmark

	

Recomputed ratio

	

Your reported ratio




I — invsqrt

	

20.650345

	

20.6503




II — DQI

	

64.762089

	

~64.76




III — Chemistry

	

10.268052

	

10.268




Geometric mean

	

23.946685

	

23.94667

𝐺
𝑀
=
(
20.650345
×
64.762089
×
10.268052
)
1
/
3
=
23.946685
GM=(20.650345×64.762089×10.268052)
1/3
=23.946685

The discrepancy is only 0.000015 GM. This is consistent with rounded cost inputs, although it does not independently prove the verifier's complete scoring implementation.

Target A

+0.6766%
Required improvement in one benchmark's ratio

Target B

+59.79%
Required improvement in one benchmark's ratio

These are multiplicative ratio improvements, not percentage-point improvements in GM.

The precise one-benchmark requirements are:

Benchmark

	

Current

	

Target A

	

Target B




I — invsqrt

	

20.6503

	

20.7901

	

32.9980




II — DQI

	

64.7621

	

65.2003

	

103.4857




III — Chemistry

	

10.2681

	

10.3375

	

16.4077

The more actionable interpretation is cost reduction:

𝐶
new
𝐶
old
=
1
1.006765811
≈
0.993280
C
old
	​

C
new
	​

	​

=
1.006765811
1
	​

≈0.993280

You need to reduce one benchmark's total cost by approximately 0.672%.

For invsqrt, that is approximately 676 cost units out of 100,568.50. At fixed 62-qubit width, it corresponds to roughly 10.9 units of the weighted operation count.

That is a much smaller engineering target than inventing a new inverse-square-root algorithm.

1.2 What the public record establishes

Leaderboard state

Partially verified

The official leaderboard is accessible, but its search-indexed snapshot is inconsistent with your more recent data. Your exact current rank of 355 cannot be independently reconfirmed from the available page.

Public portfolio above 24.0

Unresolved

I found evidence of publicly shared circuit assemblies, but not a complete current inventory with reproducible verifier receipts establishing whether any public portfolio reaches 24.0.

Outreach replies

Unverified

Your discussion thread 755075 could not be retrieved. No conclusion about replies from somejoint or mrmeows is justified.

Public circuit aggregation

Verified existence

manwithacat's public RezOps briefing documents 105 credited, reverified circuits, a chemistry parts inventory, and an automatically assembled best-public portfolio as of its 29 October report. 
Kaggle

The last finding matters because a maintained, independently verified parts inventory is a better discovery mechanism than searching notebook titles individually.

The same briefing reports a public blend of 22.87 and an unpublished local portfolio of 22.96 at that earlier point. Those scores are below your 23.94667 baseline and are not evidence of a newer improvement.

2. Research findings

The following findings distinguish observed public evidence from engineering hypotheses. Impact estimates are conditional until a candidate passes the unchanged official verifier.

F1 — Search for a 0.672% invsqrt cost reduction without changing the arithmetic family
PUBLIC

Benchmark I · Target A · High priority

Claim. The existing 62-qubit inverse-square-root circuit may offer a cheaper path to 24.0 through operation scheduling, phasing simplification, or liveness optimization than through a complete arithmetic replacement.

Evidence. The competition paper explicitly supports reversible logic and phasing optimizations within verifiable structures. The 62Q/1,497-CCX incumbent and its saturated numerical margin come from your local measurements, not independently retrieved source files. 
borowiecki.dev

Numerical impact. With Q fixed at 62:

𝐶
target
=
100568.50
1.006765811
≈
99892.5
C
target
	​

=
1.006765811
100568.50
	​

≈99892.5

Required savings: approximately 676 total cost units, or 10.9 weighted operations per qubit.

A reduction of 11 average Toffoli-equivalent operations would approximately reach Target A, assuming no changes in precision cost, width, or correctness.

Effort: 1–3 days for a targeted optimizer search.

First local validation: Extract the incumbent's reversible operation DAG. Identify commuting gates and independent controls, then perform constrained rescheduling and cancellation while preserving the input/output mapping and maximum live-qubit count. Compare exact operation statistics before running the official verifier.

Confidence: Medium that small improvements are worth searching; low that 11 operations can actually be eliminated.

Failure mode: The incumbent may already be highly optimized, or changes may increase peak width.

F2 — DQI approximation-budget exploitation
PUBLIC

Benchmark II · Target A and B

Claim. DQI is an attractive candidate for a controlled approximation search because your reported 
𝑅
(
𝜖
+
)
=
1.19126
R(ϵ
+
	​

)=1.19126 does not, on its own, demonstrate that the full allowed approximation budget is being used.

However, R is not the same quantity as 
𝜖
+
ϵ
+
	​

. Without inspecting the verifier's exact definition and the error decomposition, it would be incorrect to translate R directly into remaining error budget.

At fixed Q, achieving Target A requires:

398138.69
(
1
−
1
/
1.006765811
)
≈
2675
398138.69(1−1/1.006765811)≈2675

That is approximately 2,675 fewer mean Toffolis per execution, provided the other DQI cost terms remain unchanged.

Effort: 2–5 days.

First local validation: Instrument the DQI builder to record approximation choices, mean Toffoli cost, verifier acceptance, and error metrics for each configuration. Search the approximation frontier, starting with one parameter family at a time.

Confidence: Medium as an experiment, low on achievable savings.

Failure mode: The apparently unused budget may be constrained by another error condition, or the circuit may have discrete parameter thresholds with no cheap intermediate improvement.

Source status: The public discussion index identifies a recent DQI baseline thread by hengck23, but the full technical discussion and the specified somejoint source package were not retrieved. 
Kaggle

F3 — DQI's 892-qubit floor is conditional, not universal
PUBLIC

Benchmark II · Target B

Claim. Your interval-graph clique argument can prove a minimum register count for a particular operation graph and allocation model. It cannot establish a lower bound across all equivalent decoder algorithms.

A different reversible implementation may recompute intermediates, alter scheduling, or use a different representation.

There is also an arithmetic distinction worth correcting. Under the stated cost formula,

Cost
=
𝑄
×
𝐶
Cost=Q×C

the direct width benefit is linear, not quadratic, unless 
𝐶
C itself scales with Q.

For example, a hypothetical 892Q to 880Q reduction at unchanged C gives:

892
880
=
1.013636
880
892
	​

=1.013636

That would improve DQI's ratio by 1.364%, and the portfolio GM by approximately 0.453%.

The resulting GM would be about 24.055, crossing Target A. But the width reduction is not established as feasible.

The approximate allowable increase in mean Toffoli-equivalent cost would be:

398138.69
(
892
880
−
1
)
≈
5429
398138.69(
880
892
	​

−1)≈5429

Thus a genuinely different algorithm reducing width by 12 qubits could tolerate approximately 5,429 additional weighted operations while breaking even, under the simplified fixed-other-cost assumption.

Effort: 1–3 weeks for an alternative decoder architecture.

First local validation: Construct a smaller-width reversible decoder at the algorithm level, rather than merely renumbering the current graph.

Confidence: High that the distinction between graph-specific and algorithmic lower bounds matters; low that an improved decoder can be implemented quickly.

Failure mode: Recomputation cost dominates the width savings.

F4 — Chemistry component recombination is the best externally evidenced public search mechanism
PUBLIC

Benchmark III · Target A

Claim. A verified chemistry parts inventory creates an actionable opportunity to find improvements without designing a new factorization.

Evidence. manwithacat documents a public Apache-2.0 circuit collection, including chemistry loaders, weights, word tables, family compatibility checks, and a best-assembly manifest. This is concrete evidence of a modular public optimization workflow. 
Kaggle

At unchanged Q, the required improvement is:

16233
1.006765811
≈
16124
1.006765811
16233
	​

≈16124

This is a reduction of approximately 109 mean Toffolis, assuming the 16,233 figure fully represents the relevant variable cost.

A compatible public component that saves 110 operations would be worth testing immediately.

Effort: 4–12 hours for inventory comparison; longer for a new implementation.

First local validation: Compare the local chemistry manifest against the latest public parts manifest by slot, word-family hash, verifier cost, and provenance. Rebuild only combinations with proven compatibility.

Confidence: High that this comparison is cheap and useful; low that an unadopted saving currently exists.

Failure mode: The best public components may already be in your submission, or independently optimized parts may be incompatible.

F5 — The chemistry λ floor is not a global mathematical lower bound
PRIVATE / NEW RESEARCH

Benchmark III · Target B

Your reported 
𝜆
e
f
f
λ
eff
	​

 floor of 46.79 is best treated as a bound within the tested factorization family and its constraints.

To call it fundamental would require a proof covering the admissible Hamiltonian representations, approximation tolerances, and optimization variables.

Numerical opportunity: Even a 1% improvement in chemistry's full cost would produce:

23.946685
×
1.01
1
/
3
≈
24.026
23.946685×1.01
1/3
≈24.026

But a 1% improvement in λ does not necessarily imply a 1% improvement in the scored circuit cost.

Effort: 2–8 weeks for new factorization research.

First local validation: Separate the chemistry objective into λ, approximation error, register requirements, and compilation cost. Generate a Pareto frontier over the existing admissible factorization family before attempting a new one.

Confidence: High that the stated floor is not proven universal; low that a materially better factorization is available within the remaining competition period.

Failure mode: Lower λ may require more expensive data loading or violate the energy-gap check.

F6 — The published constant-seed projection is not a proof of impossibility
PRIVATE / NEW RESEARCH

Benchmark I · Target B

Your full-domain failures are strong evidence against the two tested implementations. The extrapolation to approximately 12.7×, however, assumes that optimization factors from one circuit family transfer multiplicatively and independently to another.

That is an engineering projection, not a lower bound.

The sensible decision remains to park the existing implementations. Reopen them only with evidence of a cheaper one-Newton seed, a genuinely different arithmetic layout, or a compiled cost below the current incumbent.

Effort: No new implementation now; 2–4 hours to evaluate any concrete new public artifact.

First local validation: Require an actual kickmix circuit and official-verifier receipt, not a numerical seed approximation alone.

Confidence: High in the decision to park; low in any claim that all constant-seed architectures are intrinsically inferior.

Failure mode: A new numerical approximation again increases reversible arithmetic width.

F7 — Public infrastructure may improve research throughput, not circuit score directly
PUBLIC

Meta · Both targets

The public RezOps briefing describes kickmix-engine, reporting approximately 10× faster local DQI verification and 4.9× faster chemistry verification than its comparison baseline. These are author-reported figures, not benchmarks reproduced here. 
Kaggle

The Kaggle discussion index also lists a recent announcement that kickmix is available on PyPI for Windows, Linux, and macOS. 
Kaggle

Impact: Potentially more candidate evaluations per hour, with no guaranteed score improvement.

Effort: 2–6 hours to benchmark compatibility and performance.

First local validation: Run the same circuit and seeds through both implementations, compare acceptance and cost results, and measure wall-clock time and peak memory.

Confidence: Medium.

Failure mode: A faster third-party simulator may not match the official verifier on boundary cases. The official verifier must remain the final authority.

3. Ranked action list — top 10

These are research priorities, not measured probabilities of success. The ranking favors experiments that can be invalidated quickly and that do not disturb the existing verified portfolio.

Rank

	

Action

	

Target

	

Effort

	

Priority




1

	

Diff the latest public chemistry parts against your local manifest

	

A

	

4–12 h

	

Very high




2

	

Search for 11 weighted-operation savings in 62Q invsqrt

	

A

	

1–3 d

	

Very high




3

	

Sweep DQI approximation parameters against official acceptance

	

A

	

2–5 d

	

High




4

	

Rebuild the complete public component frontier with verifier receipts

	

A

	

1–2 d

	

High




5

	

Investigate the 4,874 vs 4,168 chemistry re-pairing discrepancy

	

A/B

	

2–5 d

	

High




6

	

Benchmark faster local verification engines

	

A/B

	

2–6 h

	

High




7

	

Analyze DQI schedule and arithmetic representation changes

	

B

	

1–3 wk

	

Medium




8

	

Search for genuinely different invsqrt arithmetic families

	

B

	

1–3 wk

	

Medium




9

	

Establish technical exchange with complementary teams

	

B

	

Ongoing

	

Medium




10

	

Explore alternative chemistry factorizations

	

B

	

2–8 wk

	

Lower near-term

The key rule is to stop an experiment once its measured upper bound cannot cross the required cost threshold. This prevents another extended investigation of an attractive but economically inferior circuit family.

Target A: the three concrete cost budgets

Required one-benchmark savings at fixed width

Invsqrt

10.9 weighted operations

DQI

2,675 mean Toffolis

Chemistry

109 Toffolis

These are separate alternative targets, not additive savings. Calculations assume the other cost components remain unchanged.
4. Merger intelligence

The accessible evidence does not establish which leading teams possess superior private invsqrt, DQI, or chemistry circuits. Leaderboard position alone cannot identify the source of a team's advantage.

I would therefore distinguish technical-contact candidates from confirmed complementary merger candidates.

Candidate

	

Public signal

	

Potential value

	

Main uncertainty




somejoint

	

Named public 892Q DQI source package in your inventory

	

Access to decoder research and possible independent improvements

	

Private exp/ capabilities and merger interest unverified




mrmeows

	

Public circuit-sharing activity and active discussion thread

	

Invsqrt optimization methodology, possible arithmetic-family knowledge

	

No verified compiled ≥25× constant-seed result




manwithacat

	

Public, credited circuit aggregation and automated chemistry assembly

	

Provenance, public-frontier monitoring, component compatibility

	

No demonstrated private improvement over your current portfolio

The public evidence for mrmeows's discussion activity and manwithacat's assembly workflow is available in Kaggle's discussion index and RezOps briefing. 
Kaggle
+1

I would not currently rank any of these teams as likely to merge. Reachability, complementarity, and willingness are different variables, and the available evidence is insufficient to estimate them reliably.

Suggested outreach message
Writing

Hi,

I'm working on the Google Quantum AI Verifiable Circuit Compilation competition. My current verified portfolio scores approximately 23.9467, with invsqrt at 20.65×, DQI at 64.76×, and chemistry at 10.27×.

I've built a local verification and optimization workflow and am interested in exchanging reproducible results, particularly where our approaches are complementary.

I'm also open to discussing a potential team merger when the competition rules permit it. I'd be happy to share our benchmark-level results, methods, and attribution requirements before discussing any private source code.

Would you be interested in comparing approaches?

For the merger window, use the dates in your brief as planning assumptions until checked against the authoritative competition rules. The rules page was reachable but did not expose readable text in this session. 
Kaggle

A sensible sequence is technical contact now, benchmark-level comparison before January, and merger negotiations only after establishing genuine complementarity and a compatible licensing/credit arrangement.

5. Could not verify / open questions

The following requirements remain unresolved. They should not be presented as established research findings.

Research question

	

Status

	

Evidence needed




Exact live rank and score

	

Unverified

	

Fresh authenticated leaderboard export




All public portfolios ≥24.0

	

Unverified

	

Current circuit manifests, artifacts, verifier receipts




Public invsqrt SOTA

	

Unverified

	

Complete current source inventory and cost comparisons




Public DQI SOTA and R floor

	

Unverified

	

Builder code, approximation definitions, verifier instrumentation




Private somejoint exp/ core

	

Unavailable

	

Author disclosure or collaboration




Replies to thread 755075

	

Unverified

	

Authenticated Kaggle discussion access




Replies to mrmeows/somejoint comments

	

Unverified

	

Exact comment URLs or authenticated thread export




Chemistry 4,874/4,168 discrepancy

	

Unverified

	

Planner and incumbent circuit traces




Theoretical invsqrt Q·C minimum

	

Unknown

	

Formal lower-bound argument for the allowed gate model and finite domain




Public compiled constant-seed ≥25×

	

Not established

	

Verifiable artifact with matching constraints




Top-170 benchmark attribution

	

Unknown

	

Component costs or voluntary disclosure from teams

There is an important distinction between not finding a public circuit and proving that no such circuit is public. The latter requires a sufficiently complete inventory. The available search results do not provide that completeness.

Likewise, no universal lower bound for invsqrt or chemistry has been established in this report. General arithmetic-circuit complexity arguments cannot automatically be converted into tight lower bounds on the competition's exact peak-qubit-times-weighted-operation objective.

6. Challenge — three assumptions I would question
Assumption 1: The gap above 24.0 is primarily an invsqrt breakthrough

Why I question it: The geometric mean is symmetric in multiplicative improvements. A 0.6766% gain in any one benchmark reaches Target A. A strong private DQI schedule or chemistry component could explain the same leaderboard gap.

Single decisive evidence: A verified benchmark-level cost breakdown from one team scoring above 24.0, showing whether the advantage is concentrated in invsqrt or elsewhere.

Consequence: Do not allocate most engineering time to invsqrt until that attribution exists.

Assumption 2: 892Q is the fundamental DQI width floor

Why I question it: A clique in the live ranges of a fixed computation graph proves a register-allocation constraint for that graph. It does not exclude different decoder computations or reversible recomputation strategies.

Single decisive evidence: A kickmix-compatible, official-verifier-passing DQI circuit below 892 peak qubits with a competitive total Q·C cost.

Consequence: Keep the current width-renumbering work closed, but do not rule out alternative decoder architectures.

Assumption 3: The public frontier will advance enough to carry the portfolio over 24.0

Why I question it: Public sharing does not guarantee monotonic improvement, nor does a large number of published circuits imply that their components are compatible or better than the current best assembly.

The existing public parts workflow is valuable, but the documented 29 October blend was still well below your current score. 
Kaggle

Single decisive evidence: A newly published circuit or compatible assembly that passes your unchanged official verifier and reduces the current portfolio's cost enough to exceed 24.00057.

Consequence: Continue same-day adoption monitoring, but maintain an independent optimization program.

7. Recommended next experiment

I would run a tightly bounded, three-branch investigation before returning to multiweek architecture research.

48-hour Target A sprint

0 of 4 completed

48-hour plan

Chemistry public-parts diff

0–8 h

Compare hashes, word families, per-slot costs and attribution.

Invsqrt operation DAG search

8–24 h

Target ≥11 weighted operations saved at fixed 62Q.

DQI approximation sweep

24–40 h

Target ≥2,675 mean Toffolis saved at fixed 892Q.

Official verification and submission decision

40–48 h

Verify the best candidate and retain the current portfolio as rollback.

Copy sprint checklist

The submission gate should be strict: a candidate must pass the full official verifier, preserve the correct output artifacts, improve the measured portfolio cost, and maintain a complete provenance chain. Do not spend one of the five daily submissions merely to confirm a local arithmetic estimate.

Final conclusion

Target A looks like an optimization problem; Target B looks like a research and collaboration problem.

The strongest immediately actionable direction is not another constant-seed reconstruction. It is a bounded search for a very small cost reduction in the current circuit families, supported by the public parts inventory and exact local verification.

The most consequential correction to your existing analysis is that 892Q is a proven constraint only for the examined DQI computation graph, not for every possible decoder. That distinction preserves a legitimate long-term research path without reopening the already-exhausted renumbering experiments.

I have verified the baseline arithmetic and identified relevant public research and community infrastructure. I have not verified a new public portfolio above 24.0, a compiled invsqrt circuit above 25×, the private contents of any team's builder, or the current outreach replies. Consequently, this is a prioritized, evidence-qualified research assessment—not a complete census of the current public and private frontier.

The next highest-value evidence is a fresh public-artifact inventory with official-verifier receipts. It would settle whether Target A can be reached by adoption alone and identify exactly which of the three 0.672% cost-reduction experiments deserves the next engineering cycle.