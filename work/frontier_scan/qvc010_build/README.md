# QCC 24.94096: C44 and exact DQI product reuse

Companion to the public competition notebook. Actual submission58048913 scored **24.94096**; local default-salt score **24.94096013417**. These agree at displayed precision for this submission; no guarantee is made for other inputs or hidden-score draws.

The notebook rebuilds all18 submitted artifacts from the pinned Helios input, reruns the exact DQI chain scanner/emitter, and runs the three unmodified full official verifiers. The full matching C44 family is kept together. The extra rewrite saves4staticToffolis at Q892; most of this portfolio comes from the credited public components.

`public_release.bundle` and `scored_submission.bundle` are ZIP archives with a .bundle extension to preserve their exact bytes when uploaded as dataset files. `scored_submission.bundle` may be copied to `submission.zip` to obtain the exact scored archive. The notebook writes that exact archive only after checking all rebuilt payload hashes and official verification.

`reproduce.py` and both Atakan source files are readable source. CPython3.13 wheels permit offline execution with the pinned Kaggle image. Official runtime, verifier and reference Hamiltonian are loaded from the attached competition, not copied here. `reported_official_*.json` are the original local reports; a fresh notebook run creates its own official reports.

See CREDITS.md for current attribution, LICENSE.md for scope and original upstream notices for full contributor history.
