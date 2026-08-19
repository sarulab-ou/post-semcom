# Minimum Reporting Checklist for Verifiable Physical-AI Decisions

The verification gap is the receiver-dependent mismatch between a correctly
communicated proposal and the valid, timely, and authorized evidentiary basis
required to justify physical action.

This checklist makes comparisons across post-semantic communication studies
attributable and reusable. A message counts as evidence only when its content is
mapped to an application evidence requirement and passes the verifier's
validity, binding, freshness, and provenance checks. Packet names alone do not
determine evidentiary status.

## Minimum layers

| Layer | Required fields | What can be evaluated |
|---|---|---|
| Evidence | Synchronized sender/receiver records; ground truth; contract item; support/conflict relation; source; measurement time; age at decision; calibration; provenance; proposal binding | Validity, evidence sufficiency, selective risk, and false-safe behavior |
| Delivery | Forward/reverse message; message role; bytes; loss; delay; retransmission and packetization when available | Feedback function, communication cost, and comparison fairness |
| Finalization | Finalizer; assembly location; credential state; handoff; finalization outcome | Authority feasibility and completion failure |
| Runtime | Plant state; runtime-gate outcome; fallback; actuation; physical result | Closed-loop safety beyond pre-action verification |

Without these fields, a reported improvement cannot be attributed reliably to
better evidence, a different information set, lower communication cost, a
looser application requirement, or an external runtime-safety mechanism.

## Portable schema

- Schema: `schemas/post_semantic_episode.schema.json`
- Valid synthetic example: `examples/post_semantic_episode.example.json`
- Deliberately invalid example: `examples/post_semantic_episode.invalid.json`
- Machine-readable checklist: `generated/reporting_checklist.csv` and
  `generated/reporting_checklist.json`

Validate both examples from the repository root:

```powershell
c:/Users/saru/miniconda3/Scripts/conda.exe run -n base python src/validate_reporting_schema.py
```

The valid example is deterministically mapped from state 3143 in
`artifacts/generated/episode_evaluation_records.csv`. The invalid example uses
an undeclared evidence relation and must fail validation.

## Field glossary

- `synthetic_or_measured`: declares whether the record is a model realization
  or an observed system episode.
- `ground_truth`: records the reference and task labels used to judge coverage,
  selective risk, and false-safe behavior.
- `contract_item`: identifies the application requirement that the record is
  intended to satisfy.
- `relation`: `SUPPORTS` or `CONFLICTS` with the proposal-bound claim.
- `proposal_binding`: prevents a record from being silently reused for another
  proposal or version.
- `role`: distinguishes proposal, evidence-coordination, evidence-transfer, and
  finalization messages.
- `calibration_reference`, `credential_state`, and `handoff_outcome`: expose
  validity and authority dependencies that a payload-only trace omits.
- `retransmission_count` and `packet_count`: may be `null` when unavailable but
  must be explicit rather than silently excluded from delivery accounting.
- `evidence_outcome`: verifier result (`ACCEPT`, `REJECT`, or `ABSTAIN`).
- `finalizer`: endpoint permitted to finalize a positive action; it need not be
  the evidence source or assembly location.
- `gate_outcome`: downstream runtime result. Use `NOT_RECORDED` when runtime
  execution lies outside the study boundary.

## Feedback semantics

Evidence-transfer feedback carries a validated evidence record and may expand
what a remote verifier can establish. Evidence-coordination feedback reports
availability, missingness, or freshness and can change what should be sent.
Both functions incur an interaction cost in reliability, latency, and evidence
freshness.
