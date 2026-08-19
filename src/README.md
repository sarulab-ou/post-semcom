# Executable Technical Companion

The maintained `arxiv24` path is:

- `companion/availability_model.py`: exact controlled-comparison evaluator for
  4,096 weighted states and four finalization/interaction communication cases;
- `companion/figures.py`: exact generation of the requirement-based
  communication-regime map used as Fig. 3;
- `companion/reporting_schema.py`: portable schema examples and machine-readable
  minimum reporting checklist generation;
- `companion/artifacts.py`: CSV, JSON, LaTeX fragments, source-bound manifest,
  and checksums;
- `companion/validation.py`: fairness, validation, delivery, timing, and
  deterministic-generation regressions;
- `verify_artifacts.py`: locked-environment, hash, manuscript-input, and
  byte-identical-regeneration checks;
- `package_release.py`: commit-bound deterministic release archive.

`fig/fig1_test-crop.pdf` and `fig/fig2_test-crop.pdf` are supplied publication
PDF assets. They are hashed and included in the package but are not claimed as
Python-generated; Fig. 3 is regenerated as PDF byte for byte. The public
`fig/` directory intentionally contains no PNG or EPS copies.

The baseline evidence contract requires Visual clearance and Radio no-motion.
Each claim has an independent synthetic truth prior of 0.90. Both endpoints
have per-item evidence availability 0.90; conditional validity is 0.99, conditional
evidence-relation error is 0.10, endpoint availability correlation is 0.25, and forward/reverse
logical-message success is 0.99/0.99. Evidence payloads are 10/1 KiB, the link
rate is 100 Mbit/s, fixed latency is 0.5 ms per logical message, common
pre-action processing is 10 ms, and the design deadline is 33 ms (one 30-Hz period).
Visual/Radio records begin at 20/15 ms of age and share a 35-ms TTL; both are
revalidated after the full communication and processing sequence. The matched
finalizer comparison separately declares Sender/Receiver availability, handoff
success, delay, and control bytes while holding evidence assembly fixed.
Handoff delay is included before both TTL revalidation and the deadline test.

The primary payload metric is the unconditional expected number of transmitted
evidence-record bytes per proposal episode. It includes traffic incurred by
episodes that subsequently reject or abstain. Conditional safe-world traffic
fields remain available only as auxiliary diagnostics.

Conditional evidence-relation error means
`P(observed relation differs from truth-implied relation | record available and passes record validation)`. The 0.10
baseline is a deliberately non-ideal synthetic probe, not recognition accuracy
or a measured detector error. One-factor sweeps use 0.00/0.02/0.05/0.10/0.15/0.20;
global design uncertainty uses 0.05--0.15 around the 0.10 baseline, and local
finite differences use 0.095/0.105.

The Receiver One-way and Feedback communication cases deliberately share
initial evidence reachability. Evidence-coordination feedback can save bytes by
reporting Receiver availability before the forward transfer; different
message-sequence times can still cause different
decision-time expiry. Under the current contract, coordination content does not
map to a required record and therefore does not expand the verifier's evidence
set. Sender/Feedback uses a reference manifest by default and
reports a self-contained-object sensitivity separately. Alternative evidence
requirements and finalizer placement are evaluated as separate matched layers.
Their fixed and varied dimensions are exported in
`artifacts/generated/evaluation_layer_declaration.csv/json`.

Run from the repository root:

```powershell
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/run_validation.py
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/validate_reporting_schema.py
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/generate_figures.py
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/generate_artifacts.py
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/verify_artifacts.py --manuscript main/arxiv24.tex --regenerate --run-validation
```

Historical modules that are not imported by this path are intentionally absent
from this public snapshot and its published history.
