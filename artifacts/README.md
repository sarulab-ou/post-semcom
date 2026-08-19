# Generated reproducible-evaluation artifact

`generated/` is a closed, machine-generated snapshot for `main/arxiv24.tex`.
Do not edit files in it by hand.

The evaluator exactly enumerates 4,096 weighted states: two claim-truth bits,
four endpoint-record observations (missing, invalid, supports, or conflicts),
and forward/reverse delivery outcomes. The four communication cases use the same state
support. Receiver/One-way sends all validated sender-held records and
combines them with Receiver-local evidence; Receiver/Feedback has the same
initial evidence reachability and uses an evidence-coordination message for
selective transfer. Its availability, missingness, and freshness content does
not map to a required record under the current contract; another application
may admit such content only by mapping and validating it accordingly. Every
record is revalidated against its age and TTL at the case-specific
decision time.

The snapshot uses conditional evidence-relation error 0.10, defined only after record
availability and record validation. It is a deliberately non-ideal synthetic
design probe rather than a detector-accuracy measurement. Each per-episode evaluation record
keeps `transmission_suppressed` and `runtime_stopped` separate; runtime stopping
is outside the core pre-action evaluator and is therefore false in this record.

Headline outputs are:

- `baseline_declaration.{csv,json}` and `baseline_metrics.{csv,json}`;
- `sender_artifact_format.{csv,json}` for reference versus self-contained
  Sender/Feedback forwarding;
- `decision_deadline_message_latency_regime.{csv,json}` for the central map;
- `requirement_regime_map.{csv,json}` for the Concept Paper's discrete
  One-way/Feedback/Infeasible design illustration;
- `requirement_threshold_neighborhood.{csv,json}` for the internal
  38--42% coverage and 0.50--1.00% selective-error threshold check;
- `evidence_availability_record_size_regime.{csv,json}` for appendix sensitivity;
- `verifier_consistency_checks.{csv,json}` for shared supporting/conflicting validation checks;
- `framework_structural_metrics.{csv,json}` for transfer gain, coordination
  reachability, payload saving, and framework-check counts;
- `evidence_relation_error_sweep.{csv,json}` for the dedicated relation-error sweep;
- `sensitivity*.{csv,json}` for one-factor sweeps;
- `pattern_sensitivity_curves.*`, `interaction_selection_map.*`, and
  `feedback_sign_changes.*` for case-level sensitivity and sign-change analysis;
- `feedback_advantage_decomposition.*` for gain/loss probability accounting;
- `interaction_requirement_map.*` for coverage--risk constrained selection;
- `evidence_contract_comparison.*` for four admissible evidence requirements and two encodings;
- `finalizer_placement*.*` for assembly-fixed authority and handoff comparisons;
- `evaluation_layer_declaration.*` for machine-readable fixed/varied dimensions;
- `freshness_comparison.*` for explicit decision-time expiry;
- `global_uncertainty*.*`, `global_rank_sensitivity.*`, and
  `global_selection*.*` for metric propagation and selection stability;
- `local_sensitivity*.*` for baseline-neighborhood sensitivity;
- `episode_evaluation_records.csv` for 4,096 states by four communication cases, including
  portable age/assembly aliases and the Evaluation-A finalizer mode;
- generated LaTeX rows/macros, `artifact_manifest.json`, and `SHA256SUMS`.

The portable cross-study schema is maintained separately at
`schemas/post_semantic_episode.schema.json`; its valid synthetic example is
deterministically mapped from `episode_evaluation_records.csv`.

The primary communication cost is expected transmitted evidence-record bytes
over all weighted proposal episodes, including episodes that later reject or
abstain. Retained safe-world traffic fields are auxiliary diagnostics only. A logical
message takes `delta + 8P/R`; common processing time is then added before the
TTL revalidation and deadline test. P95 latency is descriptive and is not a
verifier threshold.
The evaluated boundary ends at authorized finalization. Runtime-gate
performance and physical execution are not evaluated. All results are
synthetic design evidence, not deployment measurements.

Regenerate from the repository root:

```powershell
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/generate_figures.py
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/generate_artifacts.py
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/verify_artifacts.py --manuscript main/arxiv24.tex --regenerate --run-validation
```
