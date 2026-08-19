"""Generate the reproducible concept-illustration artifact."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Iterable, Mapping, Optional, Sequence

from . import availability_model


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = REPOSITORY_ROOT / "artifacts" / "generated"
MANIFEST_INPUTS = (
    ".python-version", "requirements.lock", "RELEASE_VERSION", "Dockerfile",
    "README.md", "CITATION.cff", "LICENSES/README.md", "paper.pdf",
    "arxiv.tex", "main/arxiv24.tex", "reference.bib", "artifacts/README.md",
    "schemas/post_semantic_episode.schema.json",
    "examples/post_semantic_episode.example.json",
    "examples/post_semantic_episode.invalid.json",
    "docs/reporting_checklist.md",
    "generated/reporting_checklist.csv", "generated/reporting_checklist.json",
    ".github/workflows/reproducibility.yml", ".github/workflows/release-artifact.yml",
    "src/generate_artifacts.py", "src/generate_figures.py", "src/run_validation.py",
    "src/package_release.py", "src/verify_artifacts.py", "src/README.md",
    "src/companion/__init__.py", "src/companion/availability_model.py",
    "src/companion/artifacts.py", "src/companion/figures.py",
    "src/companion/reporting_schema.py",
    "src/companion/validation.py", "src/validate_reporting_schema.py",
)
GENERATED_FIGURE_STEMS = (
    "fig_requirement_regime_map",
)
FIGURE_SUFFIXES = ("pdf",)
CANONICAL_FIGURE_STEMS = ("fig1_test-crop", "fig2_test-crop")
CANONICAL_FIGURE_FILES = (
    "fig1_test-crop.pdf", "fig2_test-crop.pdf",
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _finite(value: object) -> object:
    return None if isinstance(value, float) and not isfinite(value) else value


def normalized_rows(rows: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    return [{key: _finite(value) for key, value in row.items()} for row in rows]


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def _write_pair(output_dir: Path, stem: str, rows: Sequence[Mapping[str, object]], payloads: list[Path]) -> None:
    clean = normalized_rows(rows)
    csv_path, json_path = output_dir / f"{stem}.csv", output_dir / f"{stem}.json"
    write_csv(csv_path, clean); write_json(json_path, clean)
    payloads.extend((csv_path, json_path))


def _record(path: Path, displayed: Optional[str] = None) -> dict[str, object]:
    return {"path": displayed or path.name, "bytes": path.stat().st_size, "sha256": digest(path)}


def _pct(value: object, digits: int = 2) -> str:
    return f"{100.0 * float(value):.{digits}f}"


def baseline_declaration_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{row['parameter']} & {row['baseline']} & {row['interpretation']} \\\\\n" for row in rows
    )


def baseline_metrics_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()} & "
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{_pct(row['unconditional_coverage'])} & "
        f"{_pct(row['timely_safe_world_coverage'])} & "
        f"{_pct(row['selective_risk'], 3)} & {_pct(row['false_safe_rate'], 3)} & "
        f"{float(row['expected_evidence_payload_kib']):.3f} & "
        f"{float(row['p95_action_ready_latency_ms']):.3f} \\\\\n" for row in rows
    )


def concept_baseline_parameter_latex(rows: Sequence[Mapping[str, object]]) -> str:
    """Render the compact baseline declaration retained in Appendix D."""
    return "% Generated; do not edit.\n" + "".join(
        f"{row['parameter']} & {row['baseline']} \\\\\n" for row in rows
    )


def concept_baseline_result_latex(rows: Sequence[Mapping[str, object]]) -> str:
    """Render the compact four-case exact-enumeration result table."""
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()} & "
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{_pct(row['unconditional_coverage'], 1)} & "
        f"{_pct(row['selective_risk'], 2)} & "
        f"{float(row['expected_evidence_payload_kib']):.1f} \\\\\n" for row in rows
    )


def compact_feedback_comparison_latex(rows: Sequence[Mapping[str, object]]) -> str:
    """Render reader-facing labels with metrics computed by the baseline evaluator."""
    feedback_function = {
        ("sender", "one_way"): "No Receiver feedback",
        ("sender", "feedback"): "Evidence transfer",
        ("receiver", "one_way"): "No Receiver feedback",
        ("receiver", "feedback"): "Evidence coordination",
    }
    timing = {
        "one_way": "One logical message",
        "feedback": "Additional reverse message",
    }
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()} & "
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{feedback_function[(str(row['finalizer']), str(row['interaction']))]} & "
        f"{_pct(row['timely_safe_world_coverage'])} & "
        f"{_pct(row['selective_risk'], 3)} & "
        f"{float(row['expected_evidence_payload_kib']):.3f} & "
        f"{timing[str(row['interaction'])]} \\\\\n" for row in rows
    )


def outcome_partition_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()}/"
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{_pct(row['timely_safe_world_coverage'])} & "
        f"{_pct(row['safe_world_reject_probability'])} & "
        f"{_pct(row['evidence_insufficient_abstention_probability'])} & "
        f"{_pct(row['expired_evidence_abstention_probability'])} & "
        f"{_pct(row['transport_abstention_probability'])} & "
        f"{_pct(row['deadline_caused_abstention_probability'])} & "
        f"{_pct(row['finalization_failure_probability'])} \\\\\n"
        for row in rows
    )


def evidence_contract_latex(rows: Sequence[Mapping[str, object]]) -> str:
    selected = [row for row in rows if float(row["observation_correlation"]) == 0.25]
    labels = {"separate": "Separate", "shared": "Shared"}
    return "% Generated; do not edit.\n" + "".join(
        f"$\\pi_{{{str(row['path_id']).removeprefix('pi')}}}$ & "
        f"{labels[str(row['record_encoding'])]} & "
        f"{_pct(row['unconditional_coverage'])} & "
        f"{_pct(row['selective_risk'], 3)} & "
        f"{float(row['mean_record_cost_kib']):.3f} \\\\\n"
        for row in selected
    )


def finalizer_placement_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['evidence_assembly']).capitalize()} & "
        f"{str(row['finalizer']).capitalize()} & "
        f"{'Yes' if row['handoff_required'] else 'No'} & "
        f"{_pct(row['timely_safe_world_coverage'])} & "
        f"{_pct(row['finalization_failure_probability'])} & "
        f"{_pct(row['expired_evidence_abstention_probability'])} & "
        f"{float(row['mean_safe_world_total_traffic_kib']):.3f} & "
        f"{float(row['p95_action_ready_latency_ms']):.3f} \\\\\n"
        for row in rows
    )


def global_selection_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()} & "
        f"{_pct(row['one_way_selection_frequency'])} & "
        f"{_pct(row['feedback_selection_frequency'])} & "
        f"{_pct(row['infeasible_frequency'])} & "
        f"{_pct(row['ordering_reversal_frequency'])} \\\\\n"
        for row in rows
    )


def freshness_comparison_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{float(row['visual_initial_age_ms']):.1f} & "
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{_pct(row['timely_safe_world_coverage'])} & "
        f"{_pct(row['expired_evidence_abstention_probability'])} & "
        f"{float(row['mean_safe_world_evidence_traffic_kib']):.3f} & "
        f"{float(row['p95_action_ready_latency_ms']):.3f} \\\\\n"
        for row in rows
    )


def sender_format_latex(rows: Sequence[Mapping[str, object]]) -> str:
    labels = {"reference_manifest": "Reference manifest", "self_contained": "Self-contained"}
    return "% Generated; do not edit.\n" + "".join(
        f"{labels[str(row['sender_feedback_format'])]} & "
        f"{_pct(row['timely_safe_world_coverage'])} & {_pct(row['false_safe_rate'], 3)} & "
        f"{float(row['mean_safe_world_evidence_traffic_kib']):.3f} & "
        f"{float(row['p95_action_ready_latency_ms']):.3f} & "
        f"{_pct(row['deadline_caused_abstention_probability'])} \\\\\n" for row in rows
    )


def sensitivity_summary_latex(rows: Sequence[Mapping[str, object]]) -> str:
    labels = {
        "evidence_availability": "Evidence availability $q$", "conditional_validity": "Conditional validity",
        "evidence_relation_error": "Evidence-relation error", "endpoint_correlation": "Endpoint correlation $\\rho$",
        "forward_delivery_success": "Forward success", "reverse_delivery_success": "Reverse success",
        "visual_record_kib": "Visual size (KiB)", "radio_record_kib": "Radio size (KiB)",
        "link_rate_mbps": "Link rate (Mbit/s)", "fixed_per_message_latency_ms": "$\\delta$ (ms)",
        "processing_time_ms": "Processing time $T_p$ (ms)", "decision_deadline_ms": "$D$ (ms)",
        "visual_initial_age_ms": "Visual initial age (ms)",
        "radio_initial_age_ms": "Radio initial age (ms)",
        "record_ttl_ms": "Evidence TTL (ms)",
    }
    return "% Generated; do not edit.\n" + "".join(
        f"{labels[str(row['parameter'])]} & {row['grid']} & "
        f"{100*float(row['minimum_timely_coverage']):.1f}--{100*float(row['maximum_timely_coverage']):.1f} & "
        f"{100*float(row['maximum_false_safe_rate']):.2f} & "
        f"{float(row['minimum_evidence_traffic_kib']):.2f}--{float(row['maximum_evidence_traffic_kib']):.2f} & "
        f"{100*float(row['maximum_deadline_miss']):.1f} \\\\\n" for row in rows
    )


def verifier_consistency_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{row['scenario']} & {str(row['verification_outcome']).capitalize()} & "
        f"{'Pass' if row['passes'] else 'Fail'} \\\\\n" for row in rows
    )


def dimensionless_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{row['quantity']} & {float(row['value']):.4g} & {row['interpretation']} \\\\\n"
        for row in rows
    )


def feedback_sign_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()} & "
        f"{float(row['baseline_coverage_difference_pp']):+.2f} & "
        f"{float(row['first_negative_latency_after_baseline_ms']):.1f} & "
        f"{float(row['first_both_zero_latency_ms']):.1f} & "
        f"{float(row['maximum_positive_coverage_difference_pp']):+.2f} & "
        f"{float(row['minimum_coverage_difference_pp']):+.2f} & "
        f"{float(row['baseline_traffic_saving_percent']):.1f} \\\\\n"
        for row in rows
    )


def feedback_decomposition_latex(rows: Sequence[Mapping[str, object]]) -> str:
    baseline = [row for row in rows if row["baseline_operating_point"]]
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()} & "
        f"{100*float(row['feedback_only_timely_gain_probability']):.2f} & "
        f"{100*float(row['one_way_only_timely_loss_probability']):.2f} & "
        f"{float(row['feedback_minus_one_way_coverage_pp']):+.2f} & "
        f"{100*float(row['common_timely_accept_probability']):.2f} \\\\\n"
        for row in baseline
    )


def uncertainty_summary_latex(rows: Sequence[Mapping[str, object]]) -> str:
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()}/"
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{100*float(row['timely_safe_world_coverage_p05']):.1f}--"
        f"{100*float(row['timely_safe_world_coverage_p95']):.1f} & "
        f"{float(row['mean_safe_world_evidence_traffic_kib_p05']):.2f}--"
        f"{float(row['mean_safe_world_evidence_traffic_kib_p95']):.2f} & "
        f"{float(row['p95_action_ready_latency_ms_p05']):.2f}--"
        f"{float(row['p95_action_ready_latency_ms_p95']):.2f} \\\\\n"
        for row in rows
    )


def local_sensitivity_latex(rows: Sequence[Mapping[str, object]]) -> str:
    labels = {
        "evidence_availability": "Evidence availability", "conditional_validity": "Validity",
        "evidence_relation_error": "Evidence-relation error",
        "endpoint_correlation": "Endpoint correlation",
        "forward_delivery_success": "Forward success",
        "reverse_delivery_success": "Reverse success",
        "visual_record_kib": "Visual size", "radio_record_kib": "Radio size",
        "link_rate_mbps": "Link rate", "fixed_per_message_latency_ms": "Message latency",
        "processing_time_ms": "Processing time",
        "decision_deadline_ms": "Deadline",
        "visual_initial_age_ms": "Visual initial age",
        "radio_initial_age_ms": "Radio initial age",
        "record_ttl_ms": "Evidence TTL",
    }
    return "% Generated; do not edit.\n" + "".join(
        f"{str(row['finalizer']).capitalize()}/"
        f"{'One-way' if row['interaction'] == 'one_way' else 'Feedback'} & "
        f"{labels.get(str(row['largest_coverage_driver']), str(row['largest_coverage_driver']))} & "
        f"{float(row['coverage_change_pp_per_plus_10_percent']):+.2f} & "
        f"{labels.get(str(row['largest_traffic_driver']), str(row['largest_traffic_driver']))} & "
        f"{float(row['traffic_change_percent_per_plus_10_percent']):+.2f} \\\\\n"
        for row in rows
    )


def global_driver_latex(rows: Sequence[Mapping[str, object]]) -> str:
    labels = {
        "evidence_availability": "Evidence availability", "conditional_validity": "Validity",
        "evidence_relation_error": "Evidence-relation error",
        "endpoint_correlation": "Endpoint correlation",
        "forward_delivery_success": "Forward success",
        "reverse_delivery_success": "Reverse success",
        "visual_record_kib": "Visual size", "radio_record_kib": "Radio size",
        "link_rate_mbps": "Link rate", "fixed_per_message_latency_ms": "Message latency",
        "processing_time_ms": "Processing time", "decision_deadline_ms": "Deadline",
        "visual_initial_age_ms": "Visual initial age",
        "radio_initial_age_ms": "Radio initial age",
        "record_ttl_ms": "Evidence TTL",
    }
    result = ["% Generated; do not edit.\n"]
    for finalizer in availability_model.Finalizer:
        for interaction in availability_model.Interaction:
            for metric, label in (
                ("timely_safe_world_coverage", "Coverage"),
                ("mean_safe_world_evidence_traffic_kib", "Evidence traffic"),
            ):
                selected = [row for row in rows if row["finalizer"] == finalizer.value
                            and row["interaction"] == interaction.value
                            and row["metric"] == metric]
                strongest = max(selected, key=lambda row: float(row["absolute_rank_correlation"]))
                result.append(
                    f"{finalizer.value.capitalize()}/"
                    f"{'One-way' if interaction is availability_model.Interaction.ONE_WAY else 'Feedback'} & "
                    f"{label} & {labels[str(strongest['parameter'])]} & "
                    f"{float(strongest['spearman_rank_correlation']):+.2f} \\\\\n"
                )
    return "".join(result)


def global_ranges_latex(rows: Sequence[Mapping[str, object]]) -> str:
    labels = {
        "evidence_availability": "Evidence availability", "conditional_validity": "Validity",
        "evidence_relation_error": "Evidence-relation error",
        "endpoint_correlation": "Endpoint correlation",
        "forward_delivery_success": "Forward success",
        "reverse_delivery_success": "Reverse success",
        "visual_record_kib": "Visual size (KiB)", "radio_record_kib": "Radio size (KiB)",
        "link_rate_mbps": "Link rate (Mbit/s)",
        "fixed_per_message_latency_ms": "Message latency (ms)",
        "processing_time_ms": "Processing time (ms)", "decision_deadline_ms": "Deadline (ms)",
        "visual_initial_age_ms": "Visual initial age (ms)",
        "radio_initial_age_ms": "Radio initial age (ms)",
        "record_ttl_ms": "Evidence TTL (ms)",
    }
    return "% Generated; do not edit.\n" + "".join(
        f"{labels[str(row['parameter'])]} & {float(row['baseline']):g} & "
        f"{float(row['lower']):g} & {float(row['upper']):g} \\\\\n" for row in rows
    )


def _saving(one: Mapping[str, object], feedback: Mapping[str, object]) -> float:
    return 100.0 * (
        float(one["expected_evidence_payload_bytes"])
        - float(feedback["expected_evidence_payload_bytes"])
    ) / float(one["expected_evidence_payload_bytes"])


def _range(values: Sequence[float], suffix: str) -> str:
    return f"{min(values):.1f} to {max(values):.1f}{suffix}"


def headline_macros_latex(
    baseline: Sequence[Mapping[str, object]], primary: Sequence[Mapping[str, object]],
    deadline_rows: Sequence[Mapping[str, object]], formats: Sequence[Mapping[str, object]],
    sign_rows: Sequence[Mapping[str, object]], dimensionless: Sequence[Mapping[str, object]],
) -> str:
    by_case = {(row["finalizer"], row["interaction"]): row for row in baseline}
    lines = ["% Generated; do not edit.\n"]
    names = {
        ("sender", "one_way"): "BaselineSenderOne", ("sender", "feedback"): "BaselineSenderFeedback",
        ("receiver", "one_way"): "BaselineReceiverOne", ("receiver", "feedback"): "BaselineReceiverFeedback",
    }
    for key, name in names.items():
        row = by_case[key]
        lines.extend((
            f"\\newcommand{{\\{name}Unconditional}}{{{_pct(row['unconditional_coverage'])}\\%}}\n",
            f"\\newcommand{{\\{name}Coverage}}{{{_pct(row['timely_safe_world_coverage'])}\\%}}\n",
            f"\\newcommand{{\\{name}SelectiveRisk}}{{{_pct(row['selective_risk'], 3)}\\%}}\n",
            f"\\newcommand{{\\{name}FalseSafe}}{{{_pct(row['false_safe_rate'], 3)}\\%}}\n",
            f"\\newcommand{{\\{name}Traffic}}{{{float(row['expected_evidence_payload_kib']):.3f}}}\n",
            f"\\newcommand{{\\{name}Pctl}}{{{float(row['p95_action_ready_latency_ms']):.3f}}}\n",
            f"\\newcommand{{\\{name}Reuse}}{{{_pct(row['local_reuse_probability'])}\\%}}\n",
            f"\\newcommand{{\\{name}DeadlineMiss}}{{{_pct(row['deadline_caused_abstention_probability'])}\\%}}\n",
            f"\\newcommand{{\\{name}ExpiryAbstain}}{{{_pct(row['expired_evidence_abstention_probability'])}\\%}}\n",
        ))
    for finalizer, label in (("sender", "Sender"), ("receiver", "Receiver")):
        pvalues = [float(row["feedback_evidence_traffic_saving_percent"]) for row in primary
                   if row["finalizer"] == finalizer]
        dvalues = [float(row["feedback_minus_one_way_timely_coverage_pp"]) for row in deadline_rows
                   if row["finalizer"] == finalizer]
        lines.extend((
            f"\\newcommand{{\\Primary{label}SavingRange}}{{{_range(pvalues, r'\%')}}}\n",
            f"\\newcommand{{\\Deadline{label}DifferenceRange}}{{{_range(dvalues, ' percentage points')}}}\n",
            f"\\newcommand{{\\Deadline{label}ZeroCrossing}}{{{'yes' if min(dvalues) <= 0 <= max(dvalues) else 'no'}}}\n",
            f"\\newcommand{{\\Baseline{label}TrafficSaving}}{{{_saving(by_case[(finalizer,'one_way')], by_case[(finalizer,'feedback')]):.1f}\\%}}\n",
        ))
    format_map = {row["sender_feedback_format"]: row for row in formats}
    lines.extend((
        f"\\newcommand{{\\ReferenceFormatTraffic}}{{{float(format_map['reference_manifest']['mean_safe_world_evidence_traffic_kib']):.3f}}}\n",
        f"\\newcommand{{\\SelfContainedTraffic}}{{{float(format_map['self_contained']['mean_safe_world_evidence_traffic_kib']):.3f}}}\n",
        f"\\newcommand{{\\SelfContainedDeadlineMiss}}{{{_pct(format_map['self_contained']['deadline_caused_abstention_probability'])}\\%}}\n",
        f"\\newcommand{{\\DeadlineMaximumMiss}}{{{100*max(float(row['feedback_deadline_caused_abstention_probability']) for row in deadline_rows):.1f}\\%}}\n",
        f"\\newcommand{{\\ExactStateSpaceSize}}{{{len(availability_model.enumerate_states())}}}\n",
        f"\\newcommand{{\\BaselineDeadline}}{{{availability_model.MODEL.decision_deadline_ms:g}}}\n",
        f"\\newcommand{{\\BaselineProcessing}}{{{availability_model.MODEL.processing_time_ms:g}}}\n",
        f"\\newcommand{{\\SelectionCoverageTolerance}}{{{availability_model.SELECTION_COVERAGE_TOLERANCE_PP:g}}}\n",
        f"\\newcommand{{\\DimensionlessDeadlineLatency}}{{{float(dimensionless[0]['value']):.1f}}}\n",
        f"\\newcommand{{\\GlobalSampleCount}}{{{availability_model.GLOBAL_SAMPLE_COUNT}}}\n",
        f"\\newcommand{{\\BaselineEvidenceRelationError}}{{{availability_model.MODEL.evidence_relation_error:.2f}}}\n",
        f"\\newcommand{{\\GlobalCoverageRequirement}}{{{100*availability_model.GLOBAL_COVERAGE_REQUIREMENT:.2f}}}\n",
        f"\\newcommand{{\\GlobalRiskRequirement}}{{{100*availability_model.GLOBAL_SELECTIVE_RISK_CEILING:.2f}}}\n",
    ))
    for row in sign_rows:
        label = str(row["finalizer"]).capitalize()
        lines.extend((
            f"\\newcommand{{\\{label}FirstNegativeLatency}}{{{float(row['first_negative_latency_after_baseline_ms']):.1f}}}\n",
            f"\\newcommand{{\\{label}FirstBothZeroLatency}}{{{float(row['first_both_zero_latency_ms']):.1f}}}\n",
        ))
    return "".join(lines)


def generate(output_dir: Path = DEFAULT_OUTPUT_DIR) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in output_dir.iterdir():
        if path.is_file(): path.unlink()

    declaration = availability_model.baseline_declaration_rows()
    # The reader-facing baseline table excludes implementation-only finalizer,
    # handoff, and artifact-format sensitivities while retaining distinct truth
    # and evidence-availability declarations.
    concept_declaration = declaration[:15]
    baseline = availability_model.matched_communication_case_rows()
    formats = availability_model.sender_format_rows()
    primary = availability_model.primary_regime_rows()
    deadline = availability_model.deadline_latency_regime_rows()
    requirement_regime = availability_model.requirement_regime_rows()
    threshold_neighborhood = availability_model.requirement_threshold_neighborhood_rows(
        requirement_regime
    )
    verifier_checks = availability_model.verifier_consistency_rows()
    structural_metrics = availability_model.framework_structural_metric_rows()
    sensitivity = availability_model.sensitivity_rows()
    sensitivity_summary = availability_model.sensitivity_summary_rows(sensitivity)
    pattern_curves = availability_model.pattern_sensitivity_curve_rows()
    relation_sweep = [
        {
            "evidence_relation_error": row["value"],
            **{key: value for key, value in row.items() if key not in {"parameter", "value"}},
        }
        for row in pattern_curves
        if row["parameter"] == "evidence_relation_error"
    ]
    interaction_selection = availability_model.interaction_selection_map_rows()
    sign_changes = availability_model.feedback_sign_change_rows(interaction_selection)
    feedback_decomposition = availability_model.feedback_advantage_decomposition_rows()
    requirements = availability_model.interaction_requirement_rows()
    evidence_contracts = availability_model.evidence_contract_comparison_rows()
    finalizer_placement = availability_model.finalizer_placement_rows()
    finalizer_sensitivity = availability_model.finalizer_placement_sensitivity_rows()
    evaluation_layers = availability_model.evaluation_layer_rows()
    freshness = availability_model.freshness_comparison_rows()
    global_uncertainty = availability_model.global_uncertainty_rows()
    global_ranges = availability_model.global_parameter_range_rows()
    uncertainty_summary = availability_model.global_uncertainty_summary_rows(global_uncertainty)
    global_sensitivity = availability_model.global_sensitivity_rows(global_uncertainty)
    global_selection = availability_model.global_selection_rows(global_uncertainty)
    global_selection_summary = availability_model.global_selection_summary_rows(global_selection)
    local_sensitivity = availability_model.local_sensitivity_rows()
    local_summary = availability_model.local_sensitivity_summary_rows(local_sensitivity)
    dimensionless = availability_model.dimensionless_baseline_rows()
    episodes = availability_model.episode_rows()
    payloads: list[Path] = []
    for stem, rows in (
        ("baseline_declaration", declaration), ("baseline_metrics", baseline),
        ("sender_artifact_format", formats), ("evidence_availability_record_size_regime", primary),
        ("decision_deadline_message_latency_regime", deadline),
        ("requirement_regime_map", requirement_regime),
        ("requirement_threshold_neighborhood", threshold_neighborhood),
        ("verifier_consistency_checks", verifier_checks),
        ("framework_structural_metrics", structural_metrics),
        ("sensitivity", sensitivity), ("sensitivity_summary", sensitivity_summary),
        ("pattern_sensitivity_curves", pattern_curves),
        ("evidence_relation_error_sweep", relation_sweep),
        ("interaction_selection_map", interaction_selection),
        ("feedback_sign_changes", sign_changes),
        ("feedback_advantage_decomposition", feedback_decomposition),
        ("interaction_requirement_map", requirements),
        ("evidence_contract_comparison", evidence_contracts),
        ("finalizer_placement", finalizer_placement),
        ("finalizer_placement_sensitivity", finalizer_sensitivity),
        ("evaluation_layer_declaration", evaluation_layers),
        ("freshness_comparison", freshness),
        ("global_uncertainty_propagation", global_uncertainty),
        ("global_parameter_ranges", global_ranges),
        ("global_uncertainty_summary", uncertainty_summary),
        ("global_rank_sensitivity", global_sensitivity),
        ("global_selection_stability", global_selection),
        ("global_selection_summary", global_selection_summary),
        ("local_sensitivity", local_sensitivity),
        ("local_sensitivity_summary", local_summary),
        ("dimensionless_baseline", dimensionless),
    ):
        _write_pair(output_dir, stem, rows, payloads)
    episode_records_path = output_dir / "episode_evaluation_records.csv"
    write_csv(episode_records_path, normalized_rows(episodes)); payloads.append(episode_records_path)

    for name, content in (
        ("baseline_declaration_rows.tex", baseline_declaration_latex(declaration)),
        ("baseline_metrics_rows.tex", baseline_metrics_latex(baseline)),
        ("concept_baseline_parameter_rows.tex", concept_baseline_parameter_latex(concept_declaration)),
        ("compact_feedback_comparison_rows.tex", compact_feedback_comparison_latex(baseline)),
        ("outcome_partition_rows.tex", outcome_partition_latex(baseline)),
        ("evidence_contract_comparison_rows.tex", evidence_contract_latex(evidence_contracts)),
        ("finalizer_placement_rows.tex", finalizer_placement_latex(finalizer_placement)),
        ("global_selection_summary_rows.tex", global_selection_latex(global_selection_summary)),
        ("freshness_comparison_rows.tex", freshness_comparison_latex(freshness)),
        ("sender_artifact_format_rows.tex", sender_format_latex(formats)),
        ("verifier_consistency_rows.tex", verifier_consistency_latex(verifier_checks)),
        ("sensitivity_summary_rows.tex", sensitivity_summary_latex(sensitivity_summary)),
        ("dimensionless_baseline_rows.tex", dimensionless_latex(dimensionless)),
        ("feedback_sign_change_rows.tex", feedback_sign_latex(sign_changes)),
        ("feedback_advantage_decomposition_rows.tex", feedback_decomposition_latex(
            feedback_decomposition)),
        ("global_uncertainty_summary_rows.tex", uncertainty_summary_latex(uncertainty_summary)),
        ("global_parameter_range_rows.tex", global_ranges_latex(global_ranges)),
        ("global_sensitivity_driver_rows.tex", global_driver_latex(global_sensitivity)),
        ("local_sensitivity_summary_rows.tex", local_sensitivity_latex(local_summary)),
        ("headline_result_macros.tex", headline_macros_latex(
            baseline, primary, deadline, formats, sign_changes, dimensionless)),
    ):
        path = output_dir / name; path.write_text(content, encoding="utf-8", newline="\n"); payloads.append(path)

    release_id = (REPOSITORY_ROOT / "RELEASE_VERSION").read_text("utf-8").strip()
    release_metadata = output_dir / "release_metadata.tex"
    baseline_by_case = {
        (str(row["finalizer"]), str(row["interaction"])): row for row in baseline
    }
    structural_by_name = {
        str(row["metric"]): row for row in structural_metrics
    }
    release_metadata.write_text(
        "% Generated; do not edit.\n"
        f"\\newcommand{{\\ArtifactReleaseID}}{{{release_id}}}\n"
        f"\\newcommand{{\\ExactStateSpaceSize}}{{{len(availability_model.enumerate_states())}}}\n"
        f"\\newcommand{{\\ConceptSenderOnePayload}}{{{float(baseline_by_case[('sender', 'one_way')]['expected_evidence_payload_kib']):.2f}}}\n"
        f"\\newcommand{{\\ConceptSenderFeedbackPayload}}{{{float(baseline_by_case[('sender', 'feedback')]['expected_evidence_payload_kib']):.2f}}}\n"
        f"\\newcommand{{\\ConceptReceiverOnePayload}}{{{float(baseline_by_case[('receiver', 'one_way')]['expected_evidence_payload_kib']):.2f}}}\n"
        f"\\newcommand{{\\ConceptReceiverFeedbackPayload}}{{{float(baseline_by_case[('receiver', 'feedback')]['expected_evidence_payload_kib']):.2f}}}\n"
        f"\\newcommand{{\\SenderTransferGainMassPercent}}{{{100.0 * float(structural_by_name['sender_transfer_gain_mass']['value']):.1f}}}\n"
        f"\\newcommand{{\\SenderTransferGainStateCount}}{{{int(structural_by_name['sender_transfer_gain_mass']['state_count'])}}}\n"
        f"\\newcommand{{\\ReceiverReachabilityMismatchCount}}{{{int(structural_by_name['receiver_reachability_mismatch_count']['state_count'])}}}\n"
        f"\\newcommand{{\\ReceiverCoordinationSavingKiB}}{{{float(structural_by_name['receiver_coordination_payload_saving_bytes']['value']) / 1024.0:.2f}}}\n"
        f"\\newcommand{{\\FrameworkStructuralPassCount}}{{{int(structural_by_name['structural_check_pass_count']['value'])}}}\n"
        f"\\newcommand{{\\FrameworkStructuralCheckCount}}{{{int(structural_by_name['structural_check_pass_count']['state_count'])}}}\n",
        encoding="utf-8", newline="\n",
    )
    payloads.append(release_metadata)
    model = availability_model.MODEL
    manifest_path = output_dir / "artifact_manifest.json"
    manifest = {
        "schema": "post-semcom.reproducible-evaluation-artifact.v24", "release_id": release_id,
        "model": {
            "required_evidence": [availability_model.VISUAL, availability_model.RADIO],
            "truth": {
                "per_claim_true_probability": model.claim_true_probability,
                "claims_independent": True,
                "truth_states": 4,
            },
            "evidence": {
                "sender_availability": model.sender_availability,
                "receiver_availability": model.receiver_availability,
                "conditional_validity": model.conditional_validity,
                "evidence_relation_error": model.evidence_relation_error,
                "endpoint_availability_correlation": model.endpoint_availability_correlation,
            },
            "delivery": {"forward_success": model.forward_delivery_success,
                         "reverse_success": model.reverse_delivery_success},
            "typed_validation_invariants": {
                "supporting_and_conflicting_share_pipeline": True,
                "proposal_binding_required": True,
                "provenance_required": True,
                "decision_time_within_record_lifetime": True,
                "calibration_must_be_valid": True,
                "source_must_be_trusted": True,
                "uncertainty_must_be_within_contract": True,
                "inadmissible_conflict_cannot_veto": True,
            },
            "timing": {"link_rate_mbps": model.link_rate_mbps,
                        "fixed_per_message_latency_ms": model.per_message_latency_ms,
                        "processing_time_ms": model.processing_time_ms,
                        "decision_deadline_ms": model.decision_deadline_ms},
            "freshness": {
                "visual_initial_age_ms": model.visual_initial_age_ms,
                "radio_initial_age_ms": model.radio_initial_age_ms,
                "evidence_ttl_ms": model.evidence_ttl_ms,
                "decision_time_revalidation": True,
            },
            "finalizer_matched_comparison": {
                "sender_availability": model.sender_finalizer_availability,
                "receiver_availability": model.receiver_finalizer_availability,
                "handoff_success": model.handoff_success,
                "handoff_delay_ms": model.handoff_delay_ms,
                "handoff_control_bytes": model.handoff_control_bytes,
                "assembly_held_fixed": True,
                "handoff_delay_precedes_ttl_revalidation": True,
            },
            "record_sizes_bytes": {"visual": model.visual_record_bytes, "radio": model.radio_record_bytes},
            "controlled_communication_invariants": {
                "receiver_one_way_sends_every_validated_sender_record": True,
                "receiver_one_way_uses_receiver_local_evidence": True,
                "receiver_feedback_falls_back_to_one_way_when_evidence_status_is_lost": True,
                "receiver_one_way_and_feedback_share_evidence_reachability": True,
                "sender_feedback_artifact_format_is_independent": True,
                "artifact_format_fixed_within_interaction_comparison": True,
                "default_sender_feedback_format": model.sender_feedback_format.value,
                "transmission_suppression_is_distinct_from_runtime_stop": True,
                "runtime_stop_is_outside_core_evaluator": True,
            },
            "selection_requirements": {
                "coverage_floor": availability_model.GLOBAL_COVERAGE_REQUIREMENT,
                "selective_risk_ceiling": availability_model.GLOBAL_SELECTIVE_RISK_CEILING,
                "requirement_map_risk_grid_probability": list(
                    availability_model.SELECTIVE_RISK_CEILING_GRID
                ),
                "display_unit": "percent",
            },
            "concept_regime_requirements": {
                "unconditional_coverage_floor": availability_model.REQUIREMENT_REGIME_COVERAGE_FLOOR,
                "selective_error_ceiling": availability_model.REQUIREMENT_REGIME_SELECTIVE_ERROR_CEILING,
                "message_latency_range_ms": [
                    min(availability_model.REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID),
                    max(availability_model.REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID),
                ],
                "decision_deadline_range_ms": [
                    min(availability_model.REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID),
                    max(availability_model.REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID),
                ],
                "selection_order": [
                    "feasibility", "expected_evidence_payload_bytes_per_proposal_episode",
                    "logical_message_count",
                    "one_way_exact_tie",
                ],
                "authority_compared_only_within_fixed_finalizer": True,
            },
            "evaluation_support": {"state_count": len(availability_model.enumerate_states()),
                                   "exact_not_monte_carlo": True,
                                   "probability_mass": sum(state.probability for state in availability_model.enumerate_states()),
                                   "evaluated_boundary": "evidence_requirements_to_authorized_finalization",
                                   "runtime_gate_performance_evaluated": False},
        },
        "metric_definitions": {
            "unconditional_coverage": "probability of timely accept over all truth states",
            "timely_safe_world_coverage": "legacy machine key: timely accept conditional on both claims true (supporting-world coverage)",
            "selective_risk": "legacy machine key: probability of a ground-truth-unsupported state conditional on timely accept (selective error)",
            "false_safe_rate": "legacy machine key: timely acceptance conditional on a ground-truth-unsupported state",
            "expected_evidence_payload_bytes": (
                "expected transmitted evidence-record bytes over all weighted proposal "
                "episodes, including episodes that later reject or abstain"
            ),
            "mean_safe_world_evidence_traffic": (
                "legacy auxiliary diagnostic conditional on both claims being true"
            ),
            "p95_action_ready_latency": "weighted P95 before deadline among safe unconstrained accepts",
        },
        "counts": {
            "baseline_parameters": len(declaration),
            "baseline_communication_cases": len(baseline),
            "sender_format_rows": len(formats), "exact_states": len(availability_model.enumerate_states()),
            "episode_rows": len(episodes), "primary_regime_rows": len(primary),
            "deadline_latency_regime_rows": len(deadline),
            "requirement_regime_rows": len(requirement_regime),
            "requirement_threshold_neighborhood_rows": len(threshold_neighborhood),
            "verifier_consistency_rows": len(verifier_checks),
            "framework_structural_metric_rows": len(structural_metrics),
            "sensitivity_rows": len(sensitivity),
            "pattern_sensitivity_curve_rows": len(pattern_curves),
            "evidence_relation_error_sweep_rows": len(relation_sweep),
            "interaction_selection_map_rows": len(interaction_selection),
            "feedback_sign_change_rows": len(sign_changes),
            "feedback_advantage_decomposition_rows": len(feedback_decomposition),
            "global_uncertainty_rows": len(global_uncertainty),
            "global_parameter_range_rows": len(global_ranges),
            "global_sensitivity_rows": len(global_sensitivity),
            "global_selection_rows": len(global_selection),
            "global_selection_summary_rows": len(global_selection_summary),
            "local_sensitivity_rows": len(local_sensitivity),
            "dimensionless_baseline_rows": len(dimensionless),
            "interaction_requirement_rows": len(requirements),
            "evidence_contract_comparison_rows": len(evidence_contracts),
            "finalizer_placement_rows": len(finalizer_placement),
            "finalizer_placement_sensitivity_rows": len(finalizer_sensitivity),
            "evaluation_layer_rows": len(evaluation_layers),
            "freshness_comparison_rows": len(freshness),
        },
        "boundary": (
            "Synthetic exact design comparison. Baseline quality, correlation, delivery, and timing "
            "values are declared rather than calibrated to a robot deployment."
        ),
        "figure_provenance": {
            "canonical_supplied_files": list(CANONICAL_FIGURE_FILES),
            "deterministically_generated_stems": list(GENERATED_FIGURE_STEMS),
        },
        "inputs": [_record(REPOSITORY_ROOT / relative, relative) for relative in MANIFEST_INPUTS],
        "figures": [
            *[_record(REPOSITORY_ROOT / "fig" / name, f"fig/{name}")
              for name in CANONICAL_FIGURE_FILES],
            *[_record(REPOSITORY_ROOT / "fig" / f"{stem}.{suffix}",
                      f"fig/{stem}.{suffix}")
              for stem in GENERATED_FIGURE_STEMS for suffix in FIGURE_SUFFIXES],
        ],
        "files": [_record(path) for path in sorted(payloads, key=lambda item: item.name)],
    }
    write_json(manifest_path, manifest)
    checksums = output_dir / "SHA256SUMS"
    targets = sorted(payloads + [manifest_path], key=lambda item: item.name)
    checksums.write_text("".join(f"{digest(path)}  {path.name}\n" for path in targets),
                         encoding="ascii", newline="\n")
    return sorted(payloads + [manifest_path, checksums], key=lambda item: item.name)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv); paths = generate(args.output_dir)
    print(f"generated {len(paths)} files in {args.output_dir}")


if __name__ == "__main__": main()
