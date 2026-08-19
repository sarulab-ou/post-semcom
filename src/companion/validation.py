"""Regression checks for the reproducible, framework-centered ``arxiv24`` artifact."""

from __future__ import annotations

from dataclasses import fields, replace
import csv
from hashlib import sha256
import json
from pathlib import Path
import re

from . import artifacts, reporting_schema
from . import availability_model as am


ROOT = Path(__file__).resolve().parents[2]
TOLERANCE = 1e-10


def close(actual: float, expected: float, tolerance: float = TOLERANCE) -> None:
    assert abs(actual - expected) <= tolerance, (actual, expected)


def _row(finalizer: am.Finalizer, interaction: am.Interaction,
         model: am.Model = am.MODEL) -> dict[str, object]:
    return am.communication_case_summary(finalizer, interaction, model)


def _state(**changes: object) -> am.State:
    defaults: dict[str, object] = {
        "clearance_true": True, "no_motion_true": True,
        "sender_visual": am.RecordObservation.SUPPORTS,
        "sender_radio": am.RecordObservation.SUPPORTS,
        "receiver_visual": am.RecordObservation.SUPPORTS,
        "receiver_radio": am.RecordObservation.SUPPORTS,
        "forward_delivered": True, "reverse_delivered": True,
        "probability": 1.0,
    }
    defaults.update(changes)
    return am.State(**defaults)


def test_evidence_relation_semantics_and_error_boundaries() -> None:
    assert tuple(member.name for member in am.EvidenceRelation) == (
        "SUPPORTS", "CONFLICTS",
    )
    assert tuple(member.value for member in am.EvidenceRelation) == (
        "supports", "conflicts",
    )
    assert tuple(member.value for member in am.RecordObservation) == (
        "missing", "invalid", "supports", "conflicts",
    )

    zero = replace(am.MODEL, conditional_validity=1.0, evidence_relation_error=0.0)
    one = replace(am.MODEL, conditional_validity=1.0, evidence_relation_error=1.0)
    assert am._quality_outcomes(False, True, zero) == (
        (am.RecordObservation.MISSING, 1.0),
    )
    assert am._quality_outcomes(False, True, one) == (
        (am.RecordObservation.MISSING, 1.0),
    )
    assert am._quality_outcomes(True, True, zero)[1:] == (
        (am.RecordObservation.SUPPORTS, 1.0),
        (am.RecordObservation.CONFLICTS, 0.0),
    )
    assert am._quality_outcomes(True, False, zero)[1:] == (
        (am.RecordObservation.CONFLICTS, 1.0),
        (am.RecordObservation.SUPPORTS, 0.0),
    )
    assert am._quality_outcomes(True, False, one)[1:] == (
        (am.RecordObservation.CONFLICTS, 0.0),
        (am.RecordObservation.SUPPORTS, 1.0),
    )

    invalid_zero = am._quality_outcomes(
        True, True, replace(zero, conditional_validity=0.4)
    )[0]
    invalid_one = am._quality_outcomes(
        True, True, replace(one, conditional_validity=0.4)
    )[0]
    assert invalid_zero == invalid_one == (am.RecordObservation.INVALID, 0.6)


def test_relation_refactor_numeric_equivalence() -> None:
    """Freeze the corrected 0.10 baseline under relation-neutral keys."""
    expected = {
        ("sender", "one_way"): (
            0.5284675285560001, 0.6366131739000039, 0.024241522903033896,
            0.06742556682631531, 9.801000000000062, 11.40112,
        ),
        ("sender", "feedback"): (
            0.5115928239419154, 0.6274138710312969, 0.006621649577619159,
            0.01782941266614713, 8.916640329990805, 11.90112,
        ),
        ("receiver", "one_way"): (
            0.511422372380157, 0.6273209487800978, 0.006437739227085344,
            0.017328441412004014, 9.801000000000062, 11.40112,
        ),
        ("receiver", "feedback"): (
            0.511422372380157, 0.6273209487800978, 0.006437739227085344,
            0.017328441412004014, 2.6037343950750076, 11.8192,
        ),
    }
    actual = {
        (str(row["finalizer"]), str(row["interaction"])): row
        for row in am.matched_communication_case_rows()
    }
    keys = (
        "unconditional_coverage", "timely_safe_world_coverage", "selective_risk",
        "false_safe_rate", "mean_safe_world_evidence_traffic_kib",
        "p95_action_ready_latency_ms",
    )
    for communication_case, reference in expected.items():
        for key, value in zip(keys, reference):
            close(float(actual[communication_case][key]), value)


def test_exact_support_and_probability() -> None:
    states = am.enumerate_states()
    assert len(states) == 4096
    assert len(set(states)) == 4096
    close(sum(state.probability for state in states), 1.0)
    assert all(state.probability >= 0.0 for state in states)
    assert am.MODEL.conditional_validity == 0.99
    assert am.MODEL.evidence_relation_error == 0.10
    assert am.MODEL.reverse_delivery_success == 0.99
    assert am.MODEL.processing_time_ms == 10.0
    assert am.MODEL.decision_deadline_ms == 33.0
    assert am.MODEL.visual_initial_age_ms == 20.0
    assert am.MODEL.radio_initial_age_ms == 15.0
    assert am.MODEL.evidence_ttl_ms == 35.0


def test_declared_marginals_and_correlation() -> None:
    states = am.enumerate_states()
    for record in am.REQUIRED_RECORDS:
        sender = sum(s.probability for s in states
                     if s.observation("sender", record) is not am.RecordObservation.MISSING)
        receiver = sum(s.probability for s in states
                       if s.observation("receiver", record) is not am.RecordObservation.MISSING)
        both = sum(s.probability for s in states
                   if s.observation("sender", record) is not am.RecordObservation.MISSING
                   and s.observation("receiver", record) is not am.RecordObservation.MISSING)
        close(sender, am.MODEL.sender_availability)
        close(receiver, am.MODEL.receiver_availability)
        covariance = both - sender * receiver
        denominator = (sender * (1 - sender) * receiver * (1 - receiver)) ** 0.5
        close(covariance / denominator, am.MODEL.endpoint_availability_correlation)


def test_quality_probabilities() -> None:
    states = am.enumerate_states()
    for endpoint in ("sender", "receiver"):
        available = sum(s.probability for s in states
                        if s.observation(endpoint, am.VISUAL) is not am.RecordObservation.MISSING)
        invalid = sum(s.probability for s in states
                      if s.observation(endpoint, am.VISUAL) is am.RecordObservation.INVALID)
        error = sum(s.probability for s in states if (
            (s.clearance_true and s.observation(endpoint, am.VISUAL) is am.RecordObservation.CONFLICTS)
            or (not s.clearance_true and s.observation(endpoint, am.VISUAL) is am.RecordObservation.SUPPORTS)
        ))
        close(invalid / available, 1.0 - am.MODEL.conditional_validity)
        close(error / available,
              am.MODEL.conditional_validity * am.MODEL.evidence_relation_error)
        close(error / (available - invalid), am.MODEL.evidence_relation_error)


def test_receiver_fair_evidence_reachability() -> None:
    for q in (0.2, 0.5, 0.9, 1.0):
        model = replace(am.MODEL, sender_availability=q, receiver_availability=q,
                        forward_delivery_success=1.0, reverse_delivery_success=1.0,
                        decision_deadline_ms=100.0)
        one = _row(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, model)
        feedback = _row(am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, model)
        close(float(one["unconstrained_safe_accept_probability"]),
              float(feedback["unconstrained_safe_accept_probability"]))
        close(float(one["timely_safe_world_coverage"]),
              float(feedback["timely_safe_world_coverage"]))
        close(float(one["false_safe_rate"]), float(feedback["false_safe_rate"]))


def test_receiver_partial_evidence_assembly() -> None:
    state = _state(
        sender_radio=am.RecordObservation.MISSING,
        receiver_visual=am.RecordObservation.MISSING,
    )
    one = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, state,
                            replace(am.MODEL, decision_deadline_ms=100.0))
    feedback = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, state,
                                 replace(am.MODEL, decision_deadline_ms=100.0))
    assert one.outcome == feedback.outcome == "accept"
    assert one.assembly_location == feedback.assembly_location == "receiver"
    assert one.forward_evidence_bytes == am.MODEL.visual_record_bytes
    assert feedback.forward_evidence_bytes == am.MODEL.visual_record_bytes


def test_remote_conflict_is_transmitted_as_validated_evidence() -> None:
    state = _state(
        clearance_true=False,
        sender_visual=am.RecordObservation.CONFLICTS,
        sender_radio=am.RecordObservation.MISSING,
    )
    model = replace(am.MODEL, decision_deadline_ms=100.0)
    for interaction in am.Interaction:
        episode = am.evaluate_state(am.Finalizer.RECEIVER, interaction, state, model)
        assert episode.outcome == "reject"
        assert episode.forward_evidence_bytes == model.visual_record_bytes


def test_sender_finalizer_requires_reverse_delivery_for_receiver_conflict() -> None:
    model = replace(am.MODEL, decision_deadline_ms=100.0)
    receiver_conflict = _state(
        receiver_visual=am.RecordObservation.CONFLICTS,
        reverse_delivered=False,
    )
    one_way = am.evaluate_state(
        am.Finalizer.SENDER, am.Interaction.ONE_WAY, receiver_conflict, model
    )
    feedback_lost = am.evaluate_state(
        am.Finalizer.SENDER, am.Interaction.FEEDBACK, receiver_conflict, model
    )
    assert one_way.outcome == "accept"
    assert feedback_lost.outcome == "accept"
    assert one_way.reverse_evidence_bytes == 0
    assert feedback_lost.reverse_evidence_bytes == model.visual_record_bytes

    feedback_delivered = am.evaluate_state(
        am.Finalizer.SENDER,
        am.Interaction.FEEDBACK,
        replace(receiver_conflict, reverse_delivered=True),
        model,
    )
    assert feedback_delivered.outcome == "reject"
    assert feedback_delivered.reverse_evidence_bytes == model.visual_record_bytes


def test_feedback_selective_transfer_and_reverse_fallback() -> None:
    baseline = {(row["finalizer"], row["interaction"]): row for row in am.matched_communication_case_rows()}
    one = baseline[("receiver", "one_way")]
    feedback = baseline[("receiver", "feedback")]
    close(float(one["timely_safe_world_coverage"]), float(feedback["timely_safe_world_coverage"]))
    close(float(one["false_safe_rate"]), float(feedback["false_safe_rate"]))
    assert float(feedback["mean_safe_world_evidence_traffic_bytes"]) < float(
        one["mean_safe_world_evidence_traffic_bytes"])
    lost = _state(receiver_visual=am.RecordObservation.MISSING,
                  receiver_radio=am.RecordObservation.MISSING, reverse_delivered=False)
    model = replace(am.MODEL, decision_deadline_ms=100.0)
    a = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, lost, model)
    b = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, lost, model)
    assert a.outcome == b.outcome
    assert a.forward_evidence_bytes == b.forward_evidence_bytes


def test_coordination_message_does_not_complete_current_contract() -> None:
    model = replace(am.MODEL, decision_deadline_ms=100.0)
    missing_sender_record = _state(
        sender_radio=am.RecordObservation.MISSING,
        receiver_visual=am.RecordObservation.MISSING,
        reverse_delivered=True,
    )
    one = am.evaluate_state(
        am.Finalizer.SENDER, am.Interaction.ONE_WAY, missing_sender_record, model
    )
    feedback = am.evaluate_state(
        am.Finalizer.SENDER, am.Interaction.FEEDBACK, missing_sender_record, model
    )
    assert one.outcome == "abstain"
    assert feedback.outcome == "accept"
    assert feedback.reverse_message_type == "evidence_record"
    receiver_feedback = am.evaluate_state(
        am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, missing_sender_record, model
    )
    assert receiver_feedback.reverse_message_type == "receiver_evidence_status"
    assert receiver_feedback.reverse_evidence_bytes == 0
    evidence_status = am.ReceiverEvidenceStatus(
        available=(am.VISUAL,), missing=(am.RADIO,), stale=(), conflict_flag=True
    )
    assert evidence_status.conflict_flag
    assert am.verify_records((), "p") == "abstain"


def test_transmission_suppression_and_runtime_stop_are_distinct() -> None:
    model = replace(am.MODEL, decision_deadline_ms=100.0)
    redundant = _state()
    one = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, redundant, model)
    feedback = am.evaluate_state(
        am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, redundant, model
    )
    assert not one.transmission_suppressed
    assert feedback.transmission_suppressed
    assert feedback.transmission_suppression_reason == "receiver_redundancy"
    assert not one.runtime_stopped and not feedback.runtime_stopped
    assert "transmission_suppressed" != "runtime_stopped"


def test_sender_artifact_format_is_independent() -> None:
    rows = {row["sender_feedback_format"]: row for row in am.sender_format_rows()}
    reference = rows[am.ArtifactFormat.REFERENCE_MANIFEST.value]
    contained = rows[am.ArtifactFormat.SELF_CONTAINED.value]
    close(float(reference["unconstrained_safe_accept_probability"]),
          float(contained["unconstrained_safe_accept_probability"]))
    close(float(reference["timely_safe_world_coverage"]),
          float(contained["timely_safe_world_coverage"]))
    assert float(reference["mean_safe_world_evidence_traffic_bytes"]) < float(
        contained["mean_safe_world_evidence_traffic_bytes"])
    assert float(reference["p95_action_ready_latency_ms"]) < float(
        contained["p95_action_ready_latency_ms"])


def test_forward_delivery_is_required() -> None:
    local_complete = _state(sender_visual=am.RecordObservation.MISSING,
                            sender_radio=am.RecordObservation.MISSING,
                            forward_delivered=False)
    model = replace(am.MODEL, decision_deadline_ms=100.0)
    for interaction in am.Interaction:
        episode = am.evaluate_state(am.Finalizer.RECEIVER, interaction, local_complete, model)
        assert episode.outcome == "abstain"
        assert episode.reason == "transport"
    perfect = replace(am.MODEL, forward_delivery_success=1.0, decision_deadline_ms=100.0)
    poor = replace(perfect, forward_delivery_success=0.5)
    for finalizer in am.Finalizer:
        for interaction in am.Interaction:
            assert float(_row(finalizer, interaction, perfect)["timely_safe_world_coverage"]) >= float(
                _row(finalizer, interaction, poor)["timely_safe_world_coverage"])


def test_typed_validation_conflict_rules() -> None:
    binding = "p"
    supporting_visual = am.EvidenceRecord(
        am.VISUAL, am.EvidenceRelation.SUPPORTS, "visual", "camera", "v-sup", binding
    )
    supporting_radio = am.EvidenceRecord(
        am.RADIO, am.EvidenceRelation.SUPPORTS, "radio", "radio", "r-sup", binding
    )
    conflict = am.EvidenceRecord(
        am.VISUAL, am.EvidenceRelation.CONFLICTS, "visual", "camera", "v-con", binding
    )
    assert am.verify_records(
        (supporting_visual, supporting_radio, conflict), binding, now=10.0
    ) == "reject"
    invalid = replace(conflict, provenance_valid=False)
    wrong = replace(conflict, proposal_binding="other")
    expired = replace(conflict, expires_at=5.0)
    revoked = replace(conflict, calibration_valid=False)
    untrusted = replace(conflict, source_trusted=False)
    uncertain = replace(conflict, uncertainty=2.0, maximum_uncertainty=1.0)
    for inadmissible in (invalid, wrong, expired, revoked, untrusted, uncertain):
        assert am.verify_records(
            (supporting_visual, supporting_radio, inadmissible), binding, now=10.0
        ) == "accept"
    assert all(bool(row["passes"]) for row in am.verifier_consistency_rows())
    assert am.authorized_finalization(
        "accept", am.Finalizer.RECEIVER, am.Finalizer.SENDER
    ) == "abstain"


def test_framework_structural_metrics() -> None:
    checks = am.verifier_consistency_rows()
    expected_scenarios = {
        "complete supporting evidence",
        "incomplete supporting evidence",
        "admissible Visual conflict",
        "conflict before completeness",
        "invalid-provenance conflict",
        "binding-mismatched conflict",
        "expired conflict",
        "revoked-calibration conflict",
        "untrusted-source conflict",
        "excessive-uncertainty conflict",
        "complete evidence at unauthorized endpoint",
    }
    assert len(checks) == 11
    assert {str(row["scenario"]) for row in checks} == expected_scenarios
    assert all(bool(row["passes"]) for row in checks)
    rows = {row["metric"]: row for row in am.framework_structural_metric_rows()}
    assert set(rows) == {
        "sender_transfer_gain_mass",
        "receiver_reachability_mismatch_count",
        "receiver_coordination_payload_saving_bytes",
        "structural_check_pass_count",
    }
    assert float(rows["sender_transfer_gain_mass"]["value"]) > 0.0
    assert int(rows["sender_transfer_gain_mass"]["state_count"]) > 0
    assert int(rows["receiver_reachability_mismatch_count"]["state_count"]) == 0
    assert float(rows["receiver_coordination_payload_saving_bytes"]["value"]) > 0.0
    assert int(rows["structural_check_pass_count"]["value"]) == len(checks)
    assert int(rows["structural_check_pass_count"]["state_count"]) == len(checks)
    assert all(bool(row["passes"]) for row in rows.values())


def test_error_validity_and_correlation_effects() -> None:
    no_error = replace(am.MODEL, evidence_relation_error=0.0,
                       decision_deadline_ms=100.0)
    high_error = replace(no_error, evidence_relation_error=0.10)
    for finalizer in am.Finalizer:
        for interaction in am.Interaction:
            close(float(_row(finalizer, interaction, no_error)["false_safe_rate"]), 0.0)
            assert float(_row(finalizer, interaction, high_error)["false_safe_rate"]) > 0.0
            assert float(_row(finalizer, interaction, high_error)["selective_risk"]) > float(
                _row(finalizer, interaction, no_error)["selective_risk"]
            )
    low_validity = replace(am.MODEL, conditional_validity=0.7, decision_deadline_ms=100.0)
    high_validity = replace(low_validity, conditional_validity=1.0)
    assert float(_row(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, high_validity)[
        "timely_safe_world_coverage"]) > float(_row(
            am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, low_validity)["timely_safe_world_coverage"])
    independent = replace(am.MODEL, endpoint_availability_correlation=0.0,
                          decision_deadline_ms=100.0)
    correlated = replace(independent, endpoint_availability_correlation=0.75)
    assert float(_row(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, independent)[
        "timely_safe_world_coverage"]) != float(_row(
            am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, correlated)["timely_safe_world_coverage"])


def test_message_count_and_deadline_accounting() -> None:
    state = _state()
    base = replace(am.MODEL, decision_deadline_ms=100.0, per_message_latency_ms=0.5)
    changed = replace(base, per_message_latency_ms=0.8)
    for finalizer in am.Finalizer:
        for interaction, count in ((am.Interaction.ONE_WAY, 1), (am.Interaction.FEEDBACK, 2)):
            first = am.evaluate_state(finalizer, interaction, state, base)
            second = am.evaluate_state(finalizer, interaction, state, changed)
            assert first.message_count == count
            close(second.action_ready_latency_ms - first.action_ready_latency_ms, count * 0.3)
    for row in am.matched_communication_case_rows():
        close(float(row["timely_safe_world_coverage"])
              + float(row["deadline_caused_abstention_probability"]),
              float(row["unconstrained_safe_accept_probability"]))
        assert (float(row["timely_safe_world_coverage"])
                + float(row["deadline_caused_abstention_probability"])
                + float(row["evidence_insufficient_abstention_probability"]) <= 1.0 + TOLERANCE)


def test_full_risk_metrics_and_outcome_partition() -> None:
    safe_prior = am.MODEL.claim_true_probability ** 2
    unsafe_prior = 1.0 - safe_prior
    for row in am.matched_communication_case_rows():
        coverage = float(row["unconditional_coverage"])
        harmful = float(row["harmful_acceptance_probability"])
        close(
            coverage,
            safe_prior * float(row["timely_safe_world_coverage"])
            + unsafe_prior * float(row["false_safe_rate"]),
        )
        close(float(row["selective_risk"]), harmful / coverage)
        close(
            float(row["timely_safe_world_coverage"])
            + float(row["safe_world_reject_probability"])
            + float(row["safe_world_abstention_probability"]),
            1.0,
        )
        close(
            float(row["safe_world_abstention_probability"]),
            float(row["evidence_insufficient_abstention_probability"])
            + float(row["expired_evidence_abstention_probability"])
            + float(row["transport_abstention_probability"])
            + float(row["deadline_caused_abstention_probability"])
            + float(row["finalization_failure_probability"]),
        )
    sample = am.episode_rows()[0]
    required = {
        "required_evidence_set", "finalizer", "interaction",
        "reverse_message_type", "assembly_location", "artifact_format",
        "initial_record_age_ms", "decision_time_age_ms", "expired_at_decision",
        "finalizer_available", "handoff_required", "handoff_success",
        "coverage", "selective_risk", "false_safe", "safe_world_coverage",
        "reject_reason", "abstain_reason", "forward_bytes", "reverse_bytes",
        "control_bytes", "deadline_miss",
        "transmission_suppressed", "transmission_suppression_reason", "runtime_stopped",
        "evidence_assembly", "initial_record_age", "decision_time_age",
        "finalizer_feasibility_mode",
    }
    assert required.issubset(sample)
    baseline = am.matched_communication_case_rows()
    for finalizer in am.Finalizer:
        formats = {
            row["artifact_format"] for row in baseline
            if row["finalizer"] == finalizer.value
        }
        assert formats == {am.ArtifactFormat.REFERENCE_MANIFEST.value}


def test_decision_time_freshness_revalidation() -> None:
    state = _state(receiver_visual=am.RecordObservation.MISSING)
    model = replace(
        am.MODEL, visual_initial_age_ms=23.4, radio_initial_age_ms=0.0,
        evidence_ttl_ms=35.0, decision_deadline_ms=100.0,
    )
    one = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, state, model)
    feedback = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, state, model)
    assert one.outcome == "accept"
    assert feedback.outcome == "abstain"
    assert feedback.reason == "expired_evidence"
    assert feedback.expired_at_decision
    assert am.VISUAL in feedback.expired_records
    stale = replace(model, visual_initial_age_ms=40.0)
    stale_feedback = am.evaluate_state(
        am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, state, stale
    )
    assert stale_feedback.outcome == "abstain"
    assert stale_feedback.forward_evidence_bytes == 0


def test_receiver_feedback_latency_identity() -> None:
    model = replace(am.MODEL, decision_deadline_ms=float("inf"))
    for state in am.enumerate_states(model):
        one = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, state, model)
        feedback = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.FEEDBACK, state, model)
        expected = (
            model.per_message_latency_ms
            + 8.0 * (feedback.forward_evidence_bytes - one.forward_evidence_bytes)
            / (model.link_rate_mbps * 1_000.0)
        )
        close(feedback.action_ready_latency_ms - one.action_ready_latency_ms, expected)


def test_deadline_monotonicity_and_infinite_recovery() -> None:
    for finalizer in am.Finalizer:
        for interaction in am.Interaction:
            previous = -1.0
            for deadline in (10.0, 20.0, 33.0, 50.0, float("inf")):
                row = _row(finalizer, interaction,
                           replace(am.MODEL, decision_deadline_ms=deadline))
                coverage = float(row["timely_safe_world_coverage"])
                assert coverage + TOLERANCE >= previous
                previous = coverage
            infinite = _row(finalizer, interaction,
                            replace(am.MODEL, decision_deadline_ms=float("inf")))
            close(float(infinite["deadline_caused_abstention_probability"]), 0.0)
            close(float(infinite["timely_safe_world_coverage"]),
                  float(infinite["unconstrained_safe_accept_probability"]))


def test_payload_size_and_latency_parameter_separation() -> None:
    state = _state(receiver_visual=am.RecordObservation.MISSING)
    variants = (am.MODEL, replace(am.MODEL, per_message_latency_ms=3.0),
                replace(am.MODEL, decision_deadline_ms=0.1))
    for finalizer in am.Finalizer:
        for interaction in am.Interaction:
            byte_counts = {am.evaluate_state(finalizer, interaction, state, model).evidence_traffic_bytes
                           for model in variants}
            assert len(byte_counts) == 1
    small = replace(am.MODEL, visual_record_bytes=2048, decision_deadline_ms=100.0)
    large = replace(small, visual_record_bytes=4096)
    a = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, state, small)
    b = am.evaluate_state(am.Finalizer.RECEIVER, am.Interaction.ONE_WAY, state, large)
    assert b.evidence_traffic_bytes - a.evidence_traffic_bytes == 2048
    close(b.action_ready_latency_ms - a.action_ready_latency_ms,
          8.0 * 2048 / (small.link_rate_mbps * 1000.0))
    assert a.evidence_sufficient == b.evidence_sufficient


def test_unconditional_evidence_payload_accounting() -> None:
    states = am.enumerate_states()
    summaries = {
        (row["finalizer"], row["interaction"]): row
        for row in am.matched_communication_case_rows()
    }
    for finalizer in am.Finalizer:
        for interaction in am.Interaction:
            expected = sum(
                state.probability
                * am.evaluate_state(finalizer, interaction, state).evidence_traffic_bytes
                for state in states
            )
            row = summaries[(finalizer.value, interaction.value)]
            close(float(row["expected_evidence_payload_bytes"]), expected)
            close(float(row["expected_evidence_payload_kib"]), expected / 1024.0)

    # The Fig. 3 baseline candidate rows and the baseline summary must use the
    # same unconditional episode population and payload definition.
    regime = [row for row in am.requirement_regime_rows()
              if row["baseline_operating_point"]]
    for row in regime:
        for interaction in am.Interaction:
            summary = summaries[(row["finalizer"], interaction.value)]
            close(
                float(row[f"{interaction.value}_evidence_payload_bytes"]),
                float(summary["expected_evidence_payload_bytes"]),
            )


def test_requirement_threshold_neighborhood() -> None:
    rows = am.requirement_threshold_neighborhood_rows()
    assert len(rows) == (
        len(am.Finalizer)
        * len(am.REQUIREMENT_NEIGHBORHOOD_COVERAGE_FLOORS)
        * len(am.REQUIREMENT_NEIGHBORHOOD_ERROR_CEILINGS)
    )
    baseline_error = [
        row for row in rows
        if float(row["selective_error_ceiling"]) == 0.0075
    ]
    assert baseline_error
    for row in baseline_error:
        assert int(row["feedback_cells"]) > 0
        assert int(row["infeasible_cells"]) > 0
        if row["finalizer"] == am.Finalizer.SENDER.value:
            assert int(row["one_way_cells"]) == 0
            assert not row["all_three_classes_present"]
        else:
            assert int(row["one_way_cells"]) > 0
            assert row["all_three_classes_present"]
    strict_error = [
        row for row in rows
        if float(row["selective_error_ceiling"]) == 0.0050
    ]
    assert strict_error and all(not row["all_three_classes_present"] for row in strict_error)


def test_regime_grids_and_optimized_episode_records() -> None:
    primary = am.primary_regime_rows()
    deadline = am.deadline_latency_regime_rows()
    assert len(primary) == 2 * len(am.RECEIVER_AVAILABILITY_GRID) * len(am.VISUAL_SIZE_KIB_GRID)
    assert len(deadline) == 2 * len(am.MESSAGE_LATENCY_MS_GRID) * len(am.DECISION_DEADLINE_MS_GRID)
    assert len([row for row in primary if row["baseline_operating_point"]]) == 2
    assert len([row for row in deadline if row["baseline_operating_point"]]) == 2
    for finalizer, delta, limit in (
        (am.Finalizer.SENDER, 0.0, 15.0),
        (am.Finalizer.RECEIVER, 1.0, 25.0),
    ):
        selected = next(row for row in deadline if row["finalizer"] == finalizer.value
                        and row["fixed_per_message_latency_ms"] == delta
                        and row["decision_deadline_ms"] == limit)
        one = _row(finalizer, am.Interaction.ONE_WAY,
                   replace(am.MODEL, per_message_latency_ms=delta, decision_deadline_ms=limit))
        feedback = _row(finalizer, am.Interaction.FEEDBACK,
                        replace(am.MODEL, per_message_latency_ms=delta, decision_deadline_ms=limit))
        close(float(selected["feedback_minus_one_way_timely_coverage_pp"]),
              100.0 * (float(feedback["timely_safe_world_coverage"])
                       - float(one["timely_safe_world_coverage"])))


def test_evidence_contract_and_finalizer_comparisons() -> None:
    paths = am.evidence_contract_comparison_rows()
    assert len(paths) == (
        len(am.EVIDENCE_PATHS)
        * len(am.EVIDENCE_PATH_CORRELATIONS)
        * len(am.EVIDENCE_PATH_ENCODINGS)
    )
    baseline = [row for row in paths if row["observation_correlation"] == 0.25]
    assert {row["finalizer"] for row in paths} == {am.Finalizer.RECEIVER.value}
    assert {row["interaction"] for row in paths} == {am.Interaction.ONE_WAY.value}
    assert {row["channel_profile"] for row in paths} == {
        "evidence_layer_perfect_delivery"
    }
    for path_id in ("pi1", "pi4"):
        by_encoding = {row["record_encoding"]: row for row in baseline
                       if row["path_id"] == path_id}
        close(float(by_encoding["separate"]["unconditional_coverage"]),
              float(by_encoding["shared"]["unconditional_coverage"]))
        assert float(by_encoding["shared"]["mean_record_cost_kib"]) < float(
            by_encoding["separate"]["mean_record_cost_kib"])
    for path_id in ("pi2", "pi3"):
        by_encoding = {row["record_encoding"]: row for row in baseline
                       if row["path_id"] == path_id}
        close(float(by_encoding["separate"]["mean_record_cost_kib"]),
              float(by_encoding["shared"]["mean_record_cost_kib"]))

    matched = am.finalizer_placement_rows()
    assert len(matched) == 4
    perfect = replace(
        am.MODEL, sender_finalizer_availability=1.0,
        receiver_finalizer_availability=1.0, handoff_success=1.0,
        handoff_delay_ms=0.0, handoff_control_bytes=0,
    )
    perfect_rows = am.finalizer_placement_rows(perfect)
    for assembly in am.Finalizer:
        selected = [row for row in perfect_rows
                    if row["evidence_assembly"] == assembly.value]
        close(float(selected[0]["timely_safe_world_coverage"]),
              float(selected[1]["timely_safe_world_coverage"]))
        close(float(selected[0]["mean_safe_world_total_traffic_kib"]),
              float(selected[1]["mean_safe_world_total_traffic_kib"]))
    expected_sensitivity = (
        4 * sum(len(values) for values in am.FINALIZER_SENSITIVITY_GRIDS.values())
    )
    assert len(am.finalizer_placement_sensitivity_rows()) == expected_sensitivity
    freshness_matched = replace(
        perfect, visual_initial_age_ms=23.4, radio_initial_age_ms=0.0,
        evidence_ttl_ms=35.0, decision_deadline_ms=100.0,
        handoff_delay_ms=1.0,
    )
    placement = am.finalizer_placement_rows(freshness_matched)
    receiver_assembly = {
        row["finalizer"]: row for row in placement
        if row["evidence_assembly"] == am.Finalizer.RECEIVER.value
    }
    assert float(receiver_assembly["sender"]["expired_evidence_abstention_probability"]) > 0.0
    assert float(receiver_assembly["sender"]["timely_safe_world_coverage"]) < float(
        receiver_assembly["receiver"]["timely_safe_world_coverage"]
    )
    no_expiry = am.finalizer_placement_rows(replace(freshness_matched, evidence_ttl_ms=100.0))
    receiver_assembly = [
        row for row in no_expiry
        if row["evidence_assembly"] == am.Finalizer.RECEIVER.value
    ]
    close(float(receiver_assembly[0]["timely_safe_world_coverage"]),
          float(receiver_assembly[1]["timely_safe_world_coverage"]))
    layers = am.evaluation_layer_rows()
    assert len(layers) == 5
    assert all(row["fixed_dimensions"] and row["varied_dimensions"] for row in layers)
    freshness = am.freshness_comparison_rows()
    assert len(freshness) == len(am.FRESHNESS_COMPARISON_AGES_MS) * len(am.Interaction)
    assert any(float(row["expired_evidence_abstention_probability"]) > 0.0
               for row in freshness)


def test_requirement_map_and_selection_stability() -> None:
    requirements = am.interaction_requirement_rows()
    assert len(requirements) == (
        len(am.Finalizer) * len(am.COVERAGE_REQUIREMENT_GRID)
        * len(am.SELECTIVE_RISK_CEILING_GRID)
    )
    assert tuple(round(100.0 * value, 2) for value in am.SELECTIVE_RISK_CEILING_GRID) == (
        0.10, 0.20, 0.30, 0.40, 0.50, 0.75, 1.00,
    )
    assert am.GLOBAL_COVERAGE_REQUIREMENT == 0.60
    assert am.GLOBAL_SELECTIVE_RISK_CEILING == 0.0075
    sender_choices = {row["selected_interaction"] for row in requirements
                      if row["finalizer"] == "sender"}
    receiver_choices = {row["selected_interaction"] for row in requirements
                        if row["finalizer"] == "receiver"}
    assert sender_choices == receiver_choices == {"feedback", "infeasible"}
    uncertainty = am.global_uncertainty_rows()
    selections = am.global_selection_rows(uncertainty)
    assert len(selections) == len(am.Finalizer) * am.GLOBAL_SAMPLE_COUNT
    summary = am.global_selection_summary_rows(selections)
    assert len(summary) == 2
    for row in summary:
        close(
            float(row["one_way_selection_frequency"])
            + float(row["feedback_selection_frequency"])
            + float(row["infeasible_frequency"]),
            1.0,
        )
        assert 0.0 <= float(row["ordering_reversal_frequency"]) <= 1.0

    concept = am.requirement_regime_rows()
    assert len(concept) == (
        len(am.Finalizer)
        * len(am.REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID)
        * len(am.REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID)
    )
    assert am.REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID[0] == 0.0
    assert am.REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID[-1] == 8.0
    assert am.REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID[0] == 10.0
    assert am.REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID[-1] == 50.0
    assert am.REQUIREMENT_REGIME_COVERAGE_FLOOR == 0.40
    assert am.REQUIREMENT_REGIME_SELECTIVE_ERROR_CEILING == 0.0075
    expected_choices = {
        am.Finalizer.SENDER: {"feedback", "infeasible"},
        am.Finalizer.RECEIVER: {"one_way", "feedback", "infeasible"},
    }
    for finalizer in am.Finalizer:
        choices = {
            row["selected_interaction"] for row in concept
            if row["finalizer"] == finalizer.value
        }
        assert choices == expected_choices[finalizer], choices
        baseline = [
            row for row in concept
            if row["finalizer"] == finalizer.value and row["baseline_operating_point"]
        ]
        assert len(baseline) == 1
        assert baseline[0]["selected_interaction"] == "feedback"


def test_deep_sensitivity_products() -> None:
    curves = am.pattern_sensitivity_curve_rows()
    expected_curves = 4 * sum(len(values) for values in am.PATTERN_CURVE_GRIDS.values())
    assert len(curves) == expected_curves
    rank = am.interaction_selection_map_rows()
    assert len(rank) == 2 * len(am.RECEIVER_AVAILABILITY_GRID) * len(am.INTERACTION_SELECTION_LATENCY_GRID)
    assert len([row for row in rank if row["baseline_operating_point"]]) == 2
    assert {row["selected_interaction"] for row in rank} == {"one_way", "feedback"}
    assert {row["selection_basis"] for row in rank}.issubset({
        "coverage", "traffic_within_coverage_tolerance", "message_count_tiebreak",
    })
    signs = am.feedback_sign_change_rows(rank)
    assert len(signs) == 2
    assert all(float(row["first_negative_latency_after_baseline_ms"]) > am.MODEL.per_message_latency_ms
               for row in signs)
    assert all(float(row["first_both_zero_latency_ms"]) > am.MODEL.per_message_latency_ms
               for row in signs)
    assert all(float(row["maximum_positive_coverage_difference_pp"])
               >= float(row["baseline_coverage_difference_pp"]) for row in signs)
    assert all(float(row["minimum_coverage_difference_pp"]) < 0.0 for row in signs)
    decomposition = am.feedback_advantage_decomposition_rows()
    assert len(decomposition) == 2 * len(am.INTERACTION_SELECTION_LATENCY_GRID)
    assert len([row for row in decomposition if row["baseline_operating_point"]]) == 2
    for row in decomposition:
        close(float(row["probability_partition_sum"]), 1.0)
        close(
            float(row["feedback_minus_one_way_coverage_pp"]),
            100.0 * (
                float(row["feedback_only_timely_gain_probability"])
                - float(row["one_way_only_timely_loss_probability"])
            ),
        )

    uncertainty = am.global_uncertainty_rows()
    assert len(uncertainty) == 4 * am.GLOBAL_SAMPLE_COUNT
    assert len(am.global_parameter_range_rows()) == len(am.GLOBAL_PARAMETER_RANGES)
    assert json.dumps(uncertainty, sort_keys=True, allow_nan=True) == json.dumps(
        am.global_uncertainty_rows(), sort_keys=True, allow_nan=True
    )
    summary = am.global_uncertainty_summary_rows(uncertainty)
    assert len(summary) == 4
    for row in summary:
        for metric in ("timely_safe_world_coverage", "mean_safe_world_evidence_traffic_kib",
                       "p95_action_ready_latency_ms"):
            assert float(row[f"{metric}_p05"]) <= float(row[f"{metric}_p50"]) <= float(
                row[f"{metric}_p95"])
    assert len(am.global_sensitivity_rows(uncertainty)) == (
        len(am.Finalizer) * len(am.Interaction)
        * len(am.GLOBAL_PARAMETER_RANGES) * 2
    )
    local = am.local_sensitivity_rows()
    assert len(local) == 4 * len(am.LOCAL_PARAMETERS)
    assert len(am.local_sensitivity_summary_rows(local)) == 4
    assert am.SENSITIVITY_GRIDS["evidence_relation_error"] == (
        0.00, 0.02, 0.05, 0.10, 0.15, 0.20,
    )
    assert 0.10 in am.PATTERN_CURVE_GRIDS["evidence_relation_error"]
    assert am.GLOBAL_PARAMETER_RANGES["evidence_relation_error"] == (0.05, 0.15)
    relation_local = [row for row in local if row["parameter"] == "evidence_relation_error"]
    assert relation_local
    assert all(abs(float(row["baseline_value"]) - 0.10) <= TOLERANCE for row in relation_local)
    assert all(abs(float(row["lower_value"]) - 0.095) <= TOLERANCE for row in relation_local)
    assert all(abs(float(row["upper_value"]) - 0.105) <= TOLERANCE for row in relation_local)


def test_deterministic_core_rows() -> None:
    for producer in (am.matched_communication_case_rows, am.sender_format_rows,
                     am.verifier_consistency_rows, am.framework_structural_metric_rows,
                     am.baseline_declaration_rows,
                     am.evidence_contract_comparison_rows, am.finalizer_placement_rows,
                     am.interaction_requirement_rows):
        first = json.dumps(producer(), sort_keys=True, allow_nan=True)
        second = json.dumps(producer(), sort_keys=True, allow_nan=True)
        assert first == second


def test_generated_macro_names_are_tex_safe() -> None:
    path = ROOT / "artifacts" / "generated" / "headline_result_macros.tex"
    if not path.exists():
        return
    source = path.read_text("utf-8")
    names = re.findall(r"\\newcommand\{\\([^}]+)\}", source)
    assert names
    assert all(name.isalpha() for name in names), [name for name in names if not name.isalpha()]


def test_manuscript_has_no_retired_replay_or_unfair_rule() -> None:
    manuscript = (ROOT / "main" / "arxiv24.tex").read_text("utf-8").lower()
    forbidden = (
        "complete sender v/r evidence, or abstention",
        "fig_public_sensor_replay", "uci occupancy", "16-state", "16 states",
        "receiver/feedback increases evidence reachability",
        "authorization_processing_ms", "main/arxiv12.tex",
    )
    assert not any(term in manuscript for term in forbidden), [
        term for term in forbidden if term in manuscript
    ]


def test_no_stale_nonideal_baseline_strings() -> None:
    maintained = (
        ROOT / "main" / "arxiv24.tex",
        ROOT / "README.md",
        ROOT / "artifacts" / "README.md",
        ROOT / "src" / "README.md",
        ROOT / "src" / "companion" / "availability_model.py",
        ROOT / "src" / "companion" / "figures.py",
        ROOT / "src" / "verify_artifacts.py",
    )
    forbidden = (
        "evidence-relation error 0.01",
        "baseline epsilon = 0.01",
        "rmax = 0.050%",
        "rmax = 0.05%",
        "recognition accuracy = 90%",
        "suppress = runtime gate",
    )
    hits = []
    for path in maintained:
        source = path.read_text("utf-8").lower()
        hits.extend((path.name, term) for term in forbidden if term in source)
    assert not hits, hits


def test_generated_nonideal_baseline_matches_manuscript_macros() -> None:
    generated = ROOT / "artifacts" / "generated"
    macros = generated / "headline_result_macros.tex"
    declaration = generated / "baseline_declaration_rows.tex"
    if not macros.exists() or not declaration.exists():
        return
    assert r"\newcommand{\BaselineEvidenceRelationError}{0.10}" in macros.read_text("utf-8")
    assert "Evidence-relation error & 0.10" in declaration.read_text("utf-8")


def test_current_release_terminology_and_schema() -> None:
    roots = (
        ROOT / "README.md",
        ROOT / "arxiv.tex",
        ROOT / "main" / "arxiv24.tex",
        ROOT / "artifacts" / "README.md",
        ROOT / "src" / "README.md",
        ROOT / "src" / "companion",
        ROOT / "src" / "verify_artifacts.py",
        ROOT / "src" / "package_release.py",
        ROOT / "artifacts" / "generated",
    )
    retired = (
        "polar" + "it",
        "positive" + " evidence",
        "negative" + " evidence",
        "wrong" + " sign",
    )
    hits: list[tuple[str, str]] = []
    for root in roots:
        paths = (root,) if root.is_file() else root.rglob("*")
        for path in paths:
            if not path.is_file() or path.suffix.lower() in {
                ".pdf", ".png", ".eps", ".zip", ".pyc",
            }:
                continue
            source = path.read_text("utf-8", errors="ignore").lower()
            hits.extend((str(path.relative_to(ROOT)), term) for term in retired if term in source)
    assert not hits, hits
    manifest_path = ROOT / "artifacts" / "generated" / "artifact_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text("utf-8"))
        evidence = manifest["model"]["evidence"]
        assert evidence["evidence_relation_error"] == 0.10
        assert all("polar" + "it" not in key.lower() for key in evidence)
        sweep = json.loads(
            (ROOT / "artifacts" / "generated" / "evidence_relation_error_sweep.json")
            .read_text("utf-8")
        )
        assert sweep and all("evidence_relation_error" in row for row in sweep)


def test_reader_facing_terminology_and_explanations() -> None:
    manuscript = (ROOT / "main" / "arxiv24.tex").read_text("utf-8")
    lower = manuscript.lower()
    normalized = re.sub(r"\s+", " ", lower)
    for retired in (
        "delivery bundle", "matched bundle", "safe-world", "safe world",
        "unsafe world", "selective risk", "false-safe", "typed evidence",
        "typed-validation",
        "typed contribution", "auditable ledger",
    ):
        assert retired not in lower, retired
    # Reject the retired noun phrase without flagging ordinary prose such as
    # "incomplete evidence yields Abstain."
    assert re.search(r"\bevidence yield\b", lower) is None, "evidence yield"
    for required in (
        "evidence record", "evidence transfer",
        "evidence coordination", "episode-level trace",
        "supporting and conflicting records traverse the same validation pipeline",
        "finalization authority", "runtime gate",
    ):
        assert required in lower, required

    contribution_start = normalized.index("this paper makes four contributions")
    contribution = normalized[contribution_start:contribution_start + 1200]
    ordered = (
        "it defines the verification gap",
        "it proposes the post-semantic communication framework",
        "it implements the framework in a finite-state evaluator",
        "a controlled communication study demonstrates",
    )
    locations = [contribution.index(term) for term in ordered]
    assert locations == sorted(locations), locations

    for required in (
        "controlled communication study",
        "headers, acknowledgments, retransmissions",
        "future measured physical-ai studies",
    ):
        assert required in normalized, required
    assert lower.count("auditable") <= 2
    assert "warehouse case study" not in lower
    assert "action admissibility" not in lower


def test_introduction_scope_structure() -> None:
    manuscript = (ROOT / "main" / "arxiv24.tex").read_text("utf-8")
    introduction = manuscript.split(r"\section{Introduction}", 1)[1].split(
        r"\section{Related Work and Motivation}", 1
    )[0]
    assert r"\noindent\textbf{Scope.}" not in manuscript
    assert "Scope boundary" not in manuscript
    order = (
        introduction.index("warehouse robot"),
        introduction.index("same distinction arises"),
        introduction.index("We define the \\emph{verification gap}"),
        introduction.index("Post-semantic communication} names"),
        introduction.index("This paper makes four contributions"),
    )
    assert list(order) == sorted(order), order

    related = manuscript.split(r"\section{Related Work and Motivation}", 1)[1].split(
        r"\begin{table*}", 1
    )[0]
    assert related.count("\n\n") >= 2
    for required in (
        r"\cite{gunduz,pragcomm}", r"\cite{wynerziv,kaspi}",
        r"\cite{tenney,ahlswede}", r"\cite{prov,proofsensing,verifiablesemantics}",
    ):
        assert required in related, required

    main = manuscript.split(r"\appendices", 1)[0]
    assert r"\begin{equation}" not in main
    assert r"\begin{align}" not in main
    assert main.count(r"\begin{figure") == 3
    assert main.count(r"\begin{table") == 2
    assert "fig/fig2_test-crop.pdf" in main
    assert "fig/fig_requirement_regime_map.pdf" in main


def test_verification_gap_concept_paper_contract() -> None:
    master = (ROOT / "arxiv.tex").read_text("utf-8")
    manuscript = (ROOT / "main" / "arxiv24.tex").read_text("utf-8")
    main, separator, appendix = manuscript.partition(r"\appendices")
    assert separator
    assert r"\input{main/arxiv24}" in master
    assert "The Verification Gap in Networked Physical AI" in master

    abstract = manuscript.split(r"\begin{abstract}", 1)[1].split(r"\end{abstract}", 1)[0]
    abstract_normalized = re.sub(r"\s+", " ", abstract).lower()
    words = re.findall(r"[A-Za-z]+(?:[-'][A-Za-z]+)*", abstract)
    assert 180 <= len(words) <= 210, len(words)
    for required in (
        "verification gap", "evidence sufficiency", "authorized finalization",
        "runtime gate", "evidence transfer", "evidence coordination",
        "finite-state framework checks", "controlled communication study",
        "episode-level reporting schema",
    ):
        assert required in abstract_normalized, required

    assert main.count(r"\begin{figure") == 3
    assert main.count(r"\begin{table") == 2
    assert appendix.count(r"\begin{table") == 1
    assert appendix.count(r"\section{") == 4
    for required in (
        "fig/fig1_test-crop.pdf", "fig/fig2_test-crop.pdf",
        "fig/fig_requirement_regime_map.pdf",
        "Same Proposal, Different Action Outcomes",
        "Minimum Reporting Checklist for Post-Semantic Comparisons",
        "concept_baseline_parameter_rows.tex",
    ):
        assert required in manuscript, required
    assert "fig/fig_deadline_latency_regime_map.pdf" not in main
    assert "fig/fig_interaction_requirement_map.pdf" not in main
    assert r"\pi_1" not in manuscript and r"\pi_4" not in manuscript
    assert main.count(r"\TableInput{") == 0
    assert appendix.count(r"\TableInput{") == 1
    assert "concept_baseline_result_rows.tex" not in manuscript
    assert r"\subsection{A Finite-State Design Illustration}" not in main
    assert r"\subsection{Using the Checklist}" not in main
    assert r"\section{Framework Checks and Communication Study}" in main
    assert r"\subsection{Questions and Setup}" in main
    assert r"\subsection{Framework Checks}" in main
    assert r"\subsection{Communication Study}" in main
    assert r"\section{Framework Evaluation}" not in manuscript
    assert "Proposition" not in manuscript
    assert "Observation 1" in appendix
    assert "Structural Property 1" in appendix
    assert "Structural Property 2" in appendix
    assert r"\pi(w_1)=\pi(w_2)" in appendix
    assert r"A_q" not in appendix
    assert r"\mathcal{A}" in appendix
    assert "Under the declared synthetic state distribution" in main
    assert "universal" not in manuscript.lower()
    assert "safe-truth" not in manuscript.lower()
    assert manuscript.index(r"\bibliography{reference}") < manuscript.index(
        r"\begin{IEEEbiographynophoto}"
    )


def test_post_semantic_positioning_and_editorial_policy() -> None:
    manuscript = (ROOT / "main" / "arxiv24.tex").read_text("utf-8")
    main, separator, appendix = manuscript.partition(r"\appendices")
    assert separator
    normalized = re.sub(r"\s+", " ", manuscript)
    abstract = manuscript.split(r"\begin{abstract}", 1)[1].split(r"\end{abstract}", 1)[0]
    introduction = manuscript.split(r"\section{Introduction}", 1)[1].split(
        r"\section{Related Work and Motivation}", 1
    )[0]
    related = manuscript.split(r"\section{Related Work and Motivation}", 1)[1].split(
        r"\section{Post-Semantic Communication Framework}", 1
    )[0]
    conclusion = manuscript.split(r"\section{Conclusion}", 1)[1].split(r"\appendices", 1)[0]
    assert r"\subsection{Concrete distinctions omitted by proposal-only formulations}" not in manuscript
    assert main.count("Weaver") == 1
    assert main.count("Level~C") == 1
    assert "Weaver" in related and "Level~C" in related
    assert "Weaver" not in conclusion and "Level~C" not in conclusion
    assert "Level D" not in manuscript and "Level~D" not in manuscript

    assert "Post-semantic communications" not in manuscript
    assert "post-semantic communications" not in manuscript
    assert "not a measured deployment evaluation" not in abstract.lower()
    assert "not a physical-safety guarantee" not in abstract.lower()
    assert "fig/fig1_test-crop.pdf" in main
    assert "fig1_test-crop" in artifacts.CANONICAL_FIGURE_STEMS
    assert "fig1_test-crop" not in artifacts.GENERATED_FIGURE_STEMS
    package_source = (ROOT / "src" / "package_release.py").read_text("utf-8")
    framework_source = (ROOT / "src" / "companion" / "figures.py").read_text("utf-8")
    assert '"fig1_test-crop.pdf"' in package_source
    assert '"fig2_test-crop.pdf"' in package_source
    assert "missing / invalid / stale / conflicting" not in framework_source

    assert "A task-effective proposal is not yet a justified physical action." in main
    assert (
        "The Post-Semantic Communication Framework makes the missing objects "
        "and responsibilities explicit"
    ) in normalized
    assert "downstream runtime boundary" in normalized

    citation_keys = {
        key for group in re.findall(r"\\cite\{([^}]+)\}", manuscript)
        for key in group.split(",")
    }
    assert 29 <= len(citation_keys) <= 32, len(citation_keys)
    required_keys = {
        "palme", "innermonologue", "knowno", "chatenv",
        "rahmanperceptive", "liu", "benvenistecontracts", "luckcuckrobotics",
        "rajkumarcps", "kehoecloud",
    }
    assert required_keys <= citation_keys
    assert (
        r"\emph{Evidence-gap detection} separates deterministic checking from AI"
    ) in manuscript
    assert "deterministic checking from AI assistance" in normalized
    assert "admissible conflict yields Reject" in normalized
    assert "could propose evidence needs or clarifications" in normalized
    assert "Neither confidence nor diagnosis is an evidence record" in normalized
    assert "Interactive agents select visual, acoustic, haptic, and proprioceptive" in normalized
    assert "jointly support radio communication and environmental sensing" in normalized
    assert "Semantic and task-oriented communication support task-relevant" in normalized
    assert "could use validated evidence records to revise a proposal" in normalized
    assert (
        "AI agents may diagnose and plan, but the evidence contract, common validator, "
        "authorization policy, and runtime gate remain explicit decision boundaries."
    ) in normalized
    for required in (
        r"language and sensor inputs \cite{palme}",
        r"help under ambiguity \cite{knowno}",
        r"information-gathering actions \cite{chatenv}",
        r"environmental sensing \cite{rahmanperceptive,liu}",
        r"task-relevant representation and delivery \cite{gunduz,pragcomm}",
        r"verification \cite{benvenistecontracts}",
        r"ROS nodes \cite{luckcuckrobotics}",
    ):
        assert required in normalized, required
    for forbidden_citation_group in (
        r"\cite{palme,knowno}",
        r"\cite{chatenv,rahmanperceptive,liu}",
    ):
        assert forbidden_citation_group not in manuscript
    for forbidden in (
        "AI agents are required for all evidence-gap detection",
        "LLMs can determine whether an action is safe",
        "VLM confidence satisfies the evidence contract",
        "AI-generated requirements are automatically trusted",
        "Our framework extends ISAC",
        "ISAC is a special case of post-semantic communication",
        "ISAC observations are automatically verified evidence",
        "ISAC guarantees closure of the verification gap",
    ):
        assert forbidden.lower() not in manuscript.lower()

    bibliography = (ROOT / "reference.bib").read_text("utf-8")
    for key in required_keys:
        assert re.search(rf"^@\w+\{{{key},", bibliography, flags=re.MULTILINE)
    for doi in (
        "10.1109/IROS55552.2023.10342363",
        "10.1109/TAES.2019.2939611",
        "10.1109/JSAC.2022.3156632",
        "10.1561/1000000053",
        "10.1016/j.robot.2026.105648",
        "10.1145/1837274.1837461",
        "10.1109/TASE.2014.2376492",
    ):
        assert bibliography.count(doi) == 1


def test_reporting_schema_examples() -> None:
    reporting_schema.validate_assets()


def test_reader_terminology_numeric_equivalence() -> None:
    def canonical_digest(rows: object) -> str:
        payload = json.dumps(
            rows, sort_keys=True, separators=(",", ":"), allow_nan=True
        ).encode("utf-8")
        return sha256(payload).hexdigest()

    requirements = [
        {key: value for key, value in row.items() if key != "selection_basis"}
        for row in am.interaction_requirement_rows()
    ]
    uncertainty = am.global_uncertainty_rows()
    uncertainty_selection = [
        {key: value for key, value in row.items() if key != "selection_basis"}
        for row in am.global_selection_rows(uncertainty)
    ]
    datasets = {
        "baseline": am.matched_communication_case_rows(),
        "freshness": am.freshness_comparison_rows(),
        "evidence_contract": am.evidence_contract_comparison_rows(),
        "finalizer": am.finalizer_placement_rows(),
        "requirements": requirements,
        "uncertainty_selection": uncertainty_selection,
    }
    expected = {
        "baseline": "879154a95f6bad8d6fa9b8eff0553fc7640810297f099a136466d8f8cb42df68",
        "freshness": "0ac183aea13a187fbd38c3f46a385f393f7c4861a3088165d44d5c4c2774be4b",
        "evidence_contract": "db6305a640d8be9e6d1e9e863fd577911e7fc1246fa6b8a5ad72afb3e036a525",
        "finalizer": "fe2911a033bd4173c90b56d3cc7f0f7d12c4c7d52e216d30ae4b0ef407715948",
        "requirements": "585e3745c616386535652204197b456c687175c82e71b6d0eac1fc4080064b9d",
        "uncertainty_selection": "c1f2c2f7ce00f243244329721a4414bfdf182ef3361a9c4c0f7061d23346ea12",
    }
    assert {name: canonical_digest(rows) for name, rows in datasets.items()} == expected


def test_generated_csv_json_and_latex_consistency() -> None:
    generated = ROOT / "artifacts" / "generated"
    for json_path in sorted(generated.glob("*.json")):
        csv_path = json_path.with_suffix(".csv")
        if not csv_path.exists():
            continue
        json_rows = json.loads(json_path.read_text("utf-8"))
        with csv_path.open("r", encoding="utf-8", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        assert len(csv_rows) == len(json_rows), json_path.name
        for csv_row, json_row in zip(csv_rows, json_rows):
            assert set(csv_row) == set(json_row), json_path.name
            for key, value in json_row.items():
                expected = "" if value is None else str(value)
                assert csv_row[key] == expected, (json_path.name, key)

    latex_expectations = {
        "baseline_declaration_rows.tex": artifacts.baseline_declaration_latex(
            am.baseline_declaration_rows()
        ),
        "baseline_metrics_rows.tex": artifacts.baseline_metrics_latex(
            am.matched_communication_case_rows()
        ),
        "compact_feedback_comparison_rows.tex": artifacts.compact_feedback_comparison_latex(
            am.matched_communication_case_rows()
        ),
        "outcome_partition_rows.tex": artifacts.outcome_partition_latex(
            am.matched_communication_case_rows()
        ),
        "evidence_contract_comparison_rows.tex": artifacts.evidence_contract_latex(
            am.evidence_contract_comparison_rows()
        ),
        "finalizer_placement_rows.tex": artifacts.finalizer_placement_latex(
            am.finalizer_placement_rows()
        ),
        "freshness_comparison_rows.tex": artifacts.freshness_comparison_latex(
            am.freshness_comparison_rows()
        ),
        "verifier_consistency_rows.tex": artifacts.verifier_consistency_latex(
            am.verifier_consistency_rows()
        ),
        "concept_baseline_parameter_rows.tex": artifacts.concept_baseline_parameter_latex(
            am.baseline_declaration_rows()[:15]
        ),
    }
    for name, expected in latex_expectations.items():
        assert (generated / name).read_text("utf-8") == expected, name


TESTS = (
    test_evidence_relation_semantics_and_error_boundaries,
    test_relation_refactor_numeric_equivalence,
    test_exact_support_and_probability,
    test_declared_marginals_and_correlation,
    test_quality_probabilities,
    test_receiver_fair_evidence_reachability,
    test_receiver_partial_evidence_assembly,
    test_remote_conflict_is_transmitted_as_validated_evidence,
    test_sender_finalizer_requires_reverse_delivery_for_receiver_conflict,
    test_feedback_selective_transfer_and_reverse_fallback,
    test_coordination_message_does_not_complete_current_contract,
    test_transmission_suppression_and_runtime_stop_are_distinct,
    test_sender_artifact_format_is_independent,
    test_forward_delivery_is_required,
    test_typed_validation_conflict_rules,
    test_framework_structural_metrics,
    test_error_validity_and_correlation_effects,
    test_message_count_and_deadline_accounting,
    test_full_risk_metrics_and_outcome_partition,
    test_decision_time_freshness_revalidation,
    test_receiver_feedback_latency_identity,
    test_deadline_monotonicity_and_infinite_recovery,
    test_payload_size_and_latency_parameter_separation,
    test_unconditional_evidence_payload_accounting,
    test_requirement_threshold_neighborhood,
    test_regime_grids_and_optimized_episode_records,
    test_evidence_contract_and_finalizer_comparisons,
    test_requirement_map_and_selection_stability,
    test_deep_sensitivity_products,
    test_deterministic_core_rows,
    test_generated_macro_names_are_tex_safe,
    test_manuscript_has_no_retired_replay_or_unfair_rule,
    test_no_stale_nonideal_baseline_strings,
    test_generated_nonideal_baseline_matches_manuscript_macros,
    test_current_release_terminology_and_schema,
    test_reader_facing_terminology_and_explanations,
    test_introduction_scope_structure,
    test_verification_gap_concept_paper_contract,
    test_post_semantic_positioning_and_editorial_policy,
    test_reporting_schema_examples,
    test_reader_terminology_numeric_equivalence,
    test_generated_csv_json_and_latex_consistency,
)


def main() -> None:
    for test in TESTS:
        test()
        print(f"PASS {test.__name__}")
    print(f"All {len(TESTS)} fair-comparison regression groups passed.")


if __name__ == "__main__":
    main()
