"""Verify locked inputs, hashes, and deterministic artifact regeneration."""

from __future__ import annotations

import argparse
from hashlib import sha256
from importlib.metadata import version as distribution_version
import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, Sequence

from companion import artifacts, availability_model, figures, reporting_schema, validation


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = REPOSITORY_ROOT / "artifacts" / "generated"
DEFAULT_MANUSCRIPT = REPOSITORY_ROOT / "main" / "arxiv24.tex"
MANUSCRIPT_INPUTS = (
    r"\input{artifacts/generated/release_metadata}",
    r"\TableInput{artifacts/generated/concept_baseline_parameter_rows.tex}",
)
MANUSCRIPT_FIGURES = (
    r"\includegraphics[width=0.98\textwidth]{fig/fig1_test-crop.pdf}",
    r"\includegraphics[width=0.98\textwidth]{fig/fig2_test-crop.pdf}",
    r"\includegraphics[width=0.98\textwidth]{fig/fig_requirement_regime_map.pdf}",
)
OBSOLETE_ARTIFACTS = {
    "freshness_regime_map.csv", "freshness_regime_map.json",
    "record_resource_regime_map.csv", "record_resource_regime_map.json",
    "split_cell_winner_map.csv", "split_cell_winner_map.json",
    "matched_policy_bundles.csv", "matched_policy_bundles.json",
    "main_decomposition.csv", "main_decomposition.json",
    "public_sensor_replay.csv", "public_sensor_replay.json",
    "public_sensor_replay_rows.tex",
    "bundle_sensitivity_curves.csv", "bundle_sensitivity_curves.json",
    "policy_rank_reversal.csv", "policy_rank_reversal.json",
    "evidence_path_audit.csv", "evidence_path_audit.json",
    "evidence_path_audit_rows.tex",
    "conflict_audit.csv", "conflict_audit.json", "conflict_audit_rows.tex",
    "freshness_audit.csv", "freshness_audit.json", "freshness_audit_rows.tex",
    "realized_episode_trace.csv",
}


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="ascii").splitlines():
        checksum, separator, name = line.partition("  ")
        if not separator or len(checksum) != 64 or not name:
            raise AssertionError(f"invalid SHA256SUMS line: {line!r}")
        result[name] = checksum
    return result


def verify_locked_environment() -> None:
    expected_python = (REPOSITORY_ROOT / ".python-version").read_text("utf-8").strip()
    assert platform.python_version() == expected_python, (platform.python_version(), expected_python)
    for line in (REPOSITORY_ROOT / "requirements.lock").read_text("utf-8").splitlines():
        requirement = line.strip()
        if not requirement or requirement.startswith("#"):
            continue
        name, separator, expected = requirement.partition("==")
        if not separator:
            raise AssertionError(f"unlocked requirement: {requirement}")
        assert distribution_version(name) == expected, name


def verify_tracked_artifacts(
    artifact_dir: Path = DEFAULT_ARTIFACT_DIR,
    manuscript: Path = DEFAULT_MANUSCRIPT,
    expected_tag: Optional[str] = None,
) -> None:
    release_id = (REPOSITORY_ROOT / "RELEASE_VERSION").read_text("utf-8").strip()
    if expected_tag is not None:
        assert expected_tag == release_id, (expected_tag, release_id)
    manifest_path = artifact_dir / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "post-semcom.reproducible-evaluation-artifact.v24"
    assert manifest["release_id"] == release_id

    model = manifest["model"]
    assert model["required_evidence"] == [availability_model.VISUAL, availability_model.RADIO]
    assert model["truth"] == {
        "per_claim_true_probability": 0.9,
        "claims_independent": True,
        "truth_states": 4,
    }
    assert model["evidence"] == {
        "sender_availability": 0.9,
        "receiver_availability": 0.9,
        "conditional_validity": 0.99,
        "evidence_relation_error": 0.10,
        "endpoint_availability_correlation": 0.25,
    }
    assert model["delivery"] == {"forward_success": 0.99, "reverse_success": 0.99}
    assert model["typed_validation_invariants"] == {
        "supporting_and_conflicting_share_pipeline": True,
        "proposal_binding_required": True,
        "provenance_required": True,
        "decision_time_within_record_lifetime": True,
        "calibration_must_be_valid": True,
        "source_must_be_trusted": True,
        "uncertainty_must_be_within_contract": True,
        "inadmissible_conflict_cannot_veto": True,
    }
    assert model["record_sizes_bytes"] == {"radio": 1024, "visual": 10240}
    assert model["timing"]["link_rate_mbps"] == 100.0
    assert model["timing"]["fixed_per_message_latency_ms"] == 0.5
    assert model["timing"]["processing_time_ms"] == 10.0
    assert model["timing"]["decision_deadline_ms"] == 33.0
    assert model["freshness"] == {
        "visual_initial_age_ms": 20.0,
        "radio_initial_age_ms": 15.0,
        "evidence_ttl_ms": 35.0,
        "decision_time_revalidation": True,
    }
    assert model["finalizer_matched_comparison"] == {
        "sender_availability": 0.995,
        "receiver_availability": 0.985,
        "handoff_success": 0.98,
        "handoff_delay_ms": 1.0,
        "handoff_control_bytes": 64,
        "assembly_held_fixed": True,
        "handoff_delay_precedes_ttl_revalidation": True,
    }
    assert model["controlled_communication_invariants"] == {
        "receiver_one_way_sends_every_validated_sender_record": True,
        "receiver_one_way_uses_receiver_local_evidence": True,
        "receiver_feedback_falls_back_to_one_way_when_evidence_status_is_lost": True,
        "receiver_one_way_and_feedback_share_evidence_reachability": True,
        "sender_feedback_artifact_format_is_independent": True,
        "artifact_format_fixed_within_interaction_comparison": True,
        "default_sender_feedback_format": "reference_manifest",
        "transmission_suppression_is_distinct_from_runtime_stop": True,
        "runtime_stop_is_outside_core_evaluator": True,
    }
    assert model["selection_requirements"] == {
        "coverage_floor": 0.60,
        "selective_risk_ceiling": 0.0075,
        "requirement_map_risk_grid_probability": [
            0.001, 0.002, 0.003, 0.004, 0.005, 0.0075, 0.01,
        ],
        "display_unit": "percent",
    }
    assert model["concept_regime_requirements"] == {
        "unconditional_coverage_floor": 0.40,
        "selective_error_ceiling": 0.0075,
        "message_latency_range_ms": [0.0, 8.0],
        "decision_deadline_range_ms": [10.0, 50.0],
        "selection_order": [
            "feasibility", "expected_evidence_payload_bytes_per_proposal_episode",
            "logical_message_count",
            "one_way_exact_tie",
        ],
        "authority_compared_only_within_fixed_finalizer": True,
    }
    assert model["evaluation_support"]["exact_not_monte_carlo"] is True
    assert model["evaluation_support"]["state_count"] == 4096
    assert abs(float(model["evaluation_support"]["probability_mass"]) - 1.0) <= 1e-12
    assert model["evaluation_support"]["evaluated_boundary"] == (
        "evidence_requirements_to_authorized_finalization"
    )
    assert model["evaluation_support"]["runtime_gate_performance_evaluated"] is False
    assert manifest["counts"] == {
        "baseline_communication_cases": 4,
        "baseline_parameters": 18,
        "sender_format_rows": 2,
        "verifier_consistency_rows": 11,
        "framework_structural_metric_rows": 4,
        "deadline_latency_regime_rows": 1394,
        "requirement_regime_rows": 5346,
        "requirement_threshold_neighborhood_rows": 18,
        "episode_rows": 16384,
        "exact_states": 4096,
        "primary_regime_rows": 80,
        "sensitivity_rows": 236,
        "pattern_sensitivity_curve_rows": 240,
        "evidence_relation_error_sweep_rows": 24,
        "interaction_selection_map_rows": 272,
        "feedback_sign_change_rows": 2,
        "feedback_advantage_decomposition_rows": 34,
        "global_uncertainty_rows": 256,
        "global_parameter_range_rows": 15,
        "global_sensitivity_rows": 120,
        "global_selection_rows": 128,
        "global_selection_summary_rows": 2,
        "local_sensitivity_rows": 60,
        "dimensionless_baseline_rows": 3,
        "interaction_requirement_rows": 112,
        "evidence_contract_comparison_rows": 24,
        "finalizer_placement_rows": 4,
        "finalizer_placement_sensitivity_rows": 100,
        "evaluation_layer_rows": 5,
        "freshness_comparison_rows": 6,
    }

    baseline = {(row["finalizer"], row["interaction"]): row
                for row in availability_model.matched_communication_case_rows()}
    receiver_one = baseline[("receiver", "one_way")]
    receiver_feedback = baseline[("receiver", "feedback")]
    assert receiver_one["timely_safe_world_coverage"] == receiver_feedback[
        "timely_safe_world_coverage"]
    assert receiver_one["false_safe_rate"] == receiver_feedback["false_safe_rate"]
    assert receiver_feedback["expected_evidence_payload_bytes"] < receiver_one[
        "expected_evidence_payload_bytes"]

    regime_rows = availability_model.requirement_regime_rows()
    expected_regions = {
        availability_model.Finalizer.SENDER: {"feedback", "infeasible"},
        availability_model.Finalizer.RECEIVER: {
            "one_way", "feedback", "infeasible",
        },
    }
    for finalizer in availability_model.Finalizer:
        regions = {
            row["selected_interaction"] for row in regime_rows
            if row["finalizer"] == finalizer.value
        }
        assert regions == expected_regions[finalizer], (finalizer, regions)

    for record in manifest["inputs"]:
        path = REPOSITORY_ROOT / record["path"]
        assert path.stat().st_size == record["bytes"], record["path"]
        assert digest(path) == record["sha256"], record["path"]
    for record in manifest["figures"]:
        path = REPOSITORY_ROOT / record["path"]
        assert path.stat().st_size == record["bytes"], record["path"]
        assert digest(path) == record["sha256"], record["path"]

    payload_names: set[str] = set()
    for record in manifest["files"]:
        path = artifact_dir / record["path"]
        payload_names.add(record["path"])
        assert path.stat().st_size == record["bytes"], record["path"]
        assert digest(path) == record["sha256"], record["path"]
    tracked_names = {path.name for path in artifact_dir.iterdir() if path.is_file()}
    assert not tracked_names.intersection(OBSOLETE_ARTIFACTS), sorted(tracked_names.intersection(OBSOLETE_ARTIFACTS))
    assert tracked_names == payload_names | {"artifact_manifest.json", "SHA256SUMS"}

    checksums = _checksums(artifact_dir / "SHA256SUMS")
    assert set(checksums) == payload_names | {manifest_path.name}
    for name, checksum in checksums.items():
        assert digest(artifact_dir / name) == checksum, name

    source = manuscript.read_text(encoding="utf-8")
    for expected_input in MANUSCRIPT_INPUTS:
        assert expected_input in source, expected_input
    for expected_figure in MANUSCRIPT_FIGURES:
        assert expected_figure in source, expected_figure
    for forbidden in (
        "safe-world", "safe world", "unsafe world", "selective risk",
        "false-safe", "\\pi_1", "\\pi_2", "\\pi_3", "\\pi_4",
    ):
        assert forbidden not in source.lower(), forbidden
    assert source.count(r"\begin{figure") == 3
    assert source.count(r"\begin{table") == 3
    assert (REPOSITORY_ROOT / "paper.pdf").is_file()


def verify_regeneration(artifact_dir: Path = DEFAULT_ARTIFACT_DIR) -> None:
    with TemporaryDirectory(prefix="post-semcom-regenerate-") as directory:
        generated = artifacts.generate(Path(directory))
        generated_names = {path.name for path in generated}
        tracked_names = {path.name for path in artifact_dir.iterdir() if path.is_file()}
        assert generated_names == tracked_names, (sorted(generated_names), sorted(tracked_names))
        for name in generated_names:
            assert (Path(directory) / name).read_bytes() == (artifact_dir / name).read_bytes(), name


def verify_figure_regeneration() -> None:
    with TemporaryDirectory(prefix="post-semcom-figures-") as directory:
        output_dir = Path(directory)
        figures.generate_all(output_dir)
        for stem in artifacts.GENERATED_FIGURE_STEMS:
            for suffix in artifacts.FIGURE_SUFFIXES:
                name = f"{stem}.{suffix}"
                assert (output_dir / name).read_bytes() == (
                    REPOSITORY_ROOT / "fig" / name
                ).read_bytes(), name


def verify_reporting_assets() -> None:
    valid = json.loads(reporting_schema.VALID_EXAMPLE_PATH.read_text(encoding="utf-8"))
    invalid = json.loads(reporting_schema.INVALID_EXAMPLE_PATH.read_text(encoding="utf-8"))
    checklist_json = json.loads(
        reporting_schema.CHECKLIST_JSON_PATH.read_text(encoding="utf-8")
    )
    assert valid == reporting_schema.valid_example()
    assert invalid == reporting_schema.invalid_example()
    assert checklist_json == list(reporting_schema.CHECKLIST)
    reporting_schema.validate_assets()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=DEFAULT_ARTIFACT_DIR)
    parser.add_argument("--manuscript", type=Path, default=DEFAULT_MANUSCRIPT)
    parser.add_argument("--expected-tag")
    parser.add_argument("--regenerate", action="store_true")
    parser.add_argument("--run-validation", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    verify_locked_environment()
    print("PASS Python and package versions match the lock files")
    verify_reporting_assets()
    print("PASS deterministic reporting schema assets")
    if args.run_validation:
        validation.main()
        reporting_schema.validate_assets()
        print("PASS portable reporting schema and examples")
    verify_tracked_artifacts(args.artifact_dir, args.manuscript, args.expected_tag)
    print("PASS tracked artifact hashes and manuscript inputs")
    if args.regenerate:
        verify_regeneration(args.artifact_dir)
        print("PASS deterministic regeneration matches tracked artifacts")
        verify_figure_regeneration()
        print("PASS deterministic figure regeneration matches tracked figures")


if __name__ == "__main__":
    main()
