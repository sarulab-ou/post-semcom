# The Verification Gap in Networked Physical AI

This repository is the public data and executable companion for the Concept
Paper **"The Verification Gap in Networked Physical AI: A Post-Semantic
Communication Framework."** It is bound to snapshot
`arxiv24-v25.1.0` and to the frozen nine-page paper in [`paper.pdf`](paper.pdf).

SHA-256 of the frozen paper:

```text
b4a220b6e5243968a19495653bafefab6d29d9dc56dfbd5aafc6e816172fc82b
```

The **verification gap** is the mismatch between a task-effective proposal and
the valid, timely, proposal-bound evidence and authorization required at the
permitted finalizer before physical action. **Post-semantic communication** is
the interface after proposal formation and before execution, where agents
coordinate evidence holdings, transfer validated evidence records, and assemble
the basis required for authorized finalization.

[Figure 1: verification gap and post-semantic interface (PDF)](fig/fig1_test-crop.pdf)

## What the artifact evaluates

The controlled synthetic study keeps the evidence requirements, verifier,
evidence-quality model, record sizes, link rate, processing time, and deadline
fixed while separating two design axes:

| Axis | Values |
|---|---|
| Authorized finalizer | Sender, Receiver |
| Interaction | One-way, Feedback |

The exact evaluator enumerates 4,096 weighted states. The baseline requires a
Visual-clearance record and a Radio-no-motion record. Per-item endpoint evidence
availability is 0.90, conditional validity is 0.99, conditional
evidence-relation error is 0.10, and forward/reverse logical-message success is
0.99/0.99. The common authorization processing time is 10 ms and the decision
deadline is 33 ms. These values are declared design probes, not measurements.

Receiver feedback has two distinct functions:

- **Evidence transfer** can move a missing admissible record to a Sender
  finalizer and expand evidence reachability.
- **Evidence coordination** can tell a Sender which records are already held at
  a Receiver finalizer and suppress redundant payload. Status alone is not
  evidence under the evaluated contract.

The artifact evaluates evidence sufficiency and authorized finalization. It
does not evaluate detector performance, wireless traces, runtime-gate
performance, physical execution, certification, or deployment safety.

## Claim-to-artifact map

| Paper item | Public data or check |
|---|---|
| RQ1: structural distinctions | `verifier_consistency_checks.*`, `framework_structural_metrics.*` |
| RQ2: transfer versus coordination | `baseline_metrics.*`, `framework_structural_metrics.*`, `episode_evaluation_records.csv` |
| RQ3 / Fig. 3: requirement-preserving interaction choice | `requirement_regime_map.*`, `requirement_threshold_neighborhood.*`, `fig/fig_requirement_regime_map.pdf` |
| Synthetic declarations / Table III | `baseline_declaration.*`, `concept_baseline_parameter_rows.tex` |
| Portable reporting schema / Table II | `schemas/`, `examples/`, `docs/reporting_checklist.md` |
| Snapshot and file hashes | `artifact_manifest.json`, `SHA256SUMS` |

All generated data are under [`artifacts/generated/`](artifacts/generated/).
The CSV files are the easiest entry point; JSON preserves the same records for
programmatic use, and LaTeX fragments supply the manuscript's declared values.

## Repository layout

| Path | Purpose |
|---|---|
| `paper.pdf` | Frozen PDF matched to this snapshot |
| `arxiv.tex`, `main/arxiv24.tex`, `reference.bib` | Exact manuscript source |
| `src/companion/availability_model.py` | Finite-state model and four-case evaluator |
| `src/companion/validation.py` | Structural, fairness, timing, and regression checks |
| `src/companion/artifacts.py` | CSV/JSON/LaTeX and manifest generation |
| `src/companion/figures.py` | Deterministic generation of the numerical Fig. 3 |
| `artifacts/generated/` | Fixed generated data, manifest, and checksums |
| `fig/` | The three hashed publication figures in PDF format |
| `schemas/`, `examples/` | Portable episode-level reporting schema |

Historical paper versions, duplicated figure trees, legacy result snapshots,
and archived implementations are intentionally excluded from this public
snapshot and its published history.

## Reproduce and verify

The reference environment is Python 3.14.6 with dependencies pinned in
`requirements.lock`.

```bash
python -m pip install --requirement requirements.lock
python src/verify_artifacts.py --manuscript main/arxiv24.tex --regenerate --run-validation
```

The full command verifies package versions, schema examples, all tracked input
hashes, exact finite-state checks, deterministic artifact regeneration, and
byte-identical regeneration of generated figures. It can take several minutes.

The same check can be run in the pinned container:

```bash
docker build -t post-semcom-artifact .
docker run --rm post-semcom-artifact
```

Build the manuscript with an IEEE-compatible TeX installation:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error arxiv.tex
```

Figures 1 and 2 are supplied publication PDFs and are hash-checked rather than
claimed as Python-generated. Figure 3 is regenerated as PDF by
`src/generate_figures.py`. No PNG, EPS, historical, or supporting figures are
kept in `fig/`.

## Version binding

`artifacts/generated/artifact_manifest.json` records the release ID, model
declarations, row counts, input hashes, figure provenance, and generated-file
hashes. `artifacts/generated/SHA256SUMS` covers the generated snapshot.

The frozen manuscript conservatively states that its source-bound version did
not itself assert a public repository or archival DOI. This repository is the
subsequent publication of that same source and data snapshot; it does not change
the paper's scientific claims or numerical results.

## Citation and license

Citation metadata are in [`CITATION.cff`](CITATION.cff). The repository URL is
<https://github.com/sarulab-ou/post-semcom>.

No repository-wide license grant is currently asserted. See
[`LICENSES/README.md`](LICENSES/README.md) before reuse or redistribution.
