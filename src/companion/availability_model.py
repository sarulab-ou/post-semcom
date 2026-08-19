"""Fair-comparison evaluator for the current concept-paper artifact.

The evaluator keeps finalization authority, interaction, assembly location,
and artifact format explicit.  Receiver/One-way sends every validated sender
record, including a valid conflict, and assembles it with receiver-local
evidence.  Thus
Receiver/Feedback does not receive an artificial evidence-coverage advantage;
its value is selective transfer, paid for with an extra logical message.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from functools import lru_cache
from itertools import product
from math import isfinite, sqrt
import random
from typing import Iterable, Mapping, Sequence


class Finalizer(str, Enum):
    SENDER = "sender"
    RECEIVER = "receiver"


class Interaction(str, Enum):
    ONE_WAY = "one_way"
    FEEDBACK = "feedback"


class ArtifactFormat(str, Enum):
    REFERENCE_MANIFEST = "reference_manifest"
    SELF_CONTAINED = "self_contained"


class EvidenceRelation(str, Enum):
    """A valid record's relation to its proposal-bound claim assertion."""

    SUPPORTS = "supports"
    CONFLICTS = "conflicts"


class RecordObservation(str, Enum):
    """The complete per-record state alphabet used by the evaluator."""

    MISSING = "missing"
    INVALID = "invalid"
    SUPPORTS = EvidenceRelation.SUPPORTS.value
    CONFLICTS = EvidenceRelation.CONFLICTS.value


VISUAL = "visual_clearance"
RADIO = "radio_no_motion"
REQUIRED_RECORDS = (VISUAL, RADIO)


@dataclass(frozen=True)
class Model:
    claim_true_probability: float = 0.90
    sender_availability: float = 0.90
    receiver_availability: float = 0.90
    conditional_validity: float = 0.99
    evidence_relation_error: float = 0.10
    endpoint_availability_correlation: float = 0.25
    forward_delivery_success: float = 0.99
    reverse_delivery_success: float = 0.99
    visual_record_bytes: int = 10 * 1024
    radio_record_bytes: int = 1024
    link_rate_mbps: float = 100.0
    per_message_latency_ms: float = 0.5
    processing_time_ms: float = 10.0
    decision_deadline_ms: float = 33.0
    visual_initial_age_ms: float = 20.0
    radio_initial_age_ms: float = 15.0
    evidence_ttl_ms: float = 35.0
    sender_finalizer_availability: float = 0.995
    receiver_finalizer_availability: float = 0.985
    handoff_success: float = 0.98
    handoff_delay_ms: float = 1.0
    handoff_control_bytes: int = 64
    sender_feedback_format: ArtifactFormat = ArtifactFormat.REFERENCE_MANIFEST

    def __post_init__(self) -> None:
        probabilities = (
            self.claim_true_probability, self.sender_availability, self.receiver_availability,
            self.conditional_validity, self.evidence_relation_error,
            self.endpoint_availability_correlation, self.forward_delivery_success,
            self.reverse_delivery_success, self.sender_finalizer_availability,
            self.receiver_finalizer_availability, self.handoff_success,
        )
        if any(not 0.0 <= value <= 1.0 for value in probabilities):
            raise ValueError("probabilities and correlation must be in [0,1]")
        if self.visual_record_bytes < 0 or self.radio_record_bytes < 0:
            raise ValueError("record sizes must be nonnegative")
        if self.link_rate_mbps <= 0.0:
            raise ValueError("link_rate_mbps must be positive")
        if min(self.per_message_latency_ms, self.processing_time_ms,
               self.decision_deadline_ms, self.visual_initial_age_ms,
               self.radio_initial_age_ms, self.evidence_ttl_ms,
               self.handoff_delay_ms) < 0.0:
            raise ValueError("latencies, ages, TTL, and deadline must be nonnegative")
        if self.handoff_control_bytes < 0:
            raise ValueError("handoff_control_bytes must be nonnegative")
        _availability_joint(self.sender_availability, self.receiver_availability,
                            self.endpoint_availability_correlation)

    def record_bytes(self, record: str) -> int:
        return self.visual_record_bytes if record == VISUAL else self.radio_record_bytes

    def initial_age_ms(self, record: str) -> float:
        return self.visual_initial_age_ms if record == VISUAL else self.radio_initial_age_ms

    def record_fresh(self, record: str, decision_time_ms: float) -> bool:
        return self.initial_age_ms(record) + decision_time_ms <= self.evidence_ttl_ms

    def finalizer_availability(self, finalizer: Finalizer) -> float:
        return (
            self.sender_finalizer_availability
            if finalizer is Finalizer.SENDER
            else self.receiver_finalizer_availability
        )

    def message_latency_ms(self, payload_bytes: int, *, exists: bool = True) -> float:
        if not exists:
            return 0.0
        if payload_bytes < 0:
            raise ValueError("payload_bytes must be nonnegative")
        return self.per_message_latency_ms + 8.0 * payload_bytes / (
            self.link_rate_mbps * 1_000.0
        )


@dataclass(frozen=True)
class State:
    clearance_true: bool
    no_motion_true: bool
    sender_visual: RecordObservation
    sender_radio: RecordObservation
    receiver_visual: RecordObservation
    receiver_radio: RecordObservation
    forward_delivered: bool
    reverse_delivered: bool
    probability: float

    @property
    def safe(self) -> bool:
        return self.clearance_true and self.no_motion_true

    def observation(self, endpoint: str, record: str) -> RecordObservation:
        if endpoint == "sender":
            return self.sender_visual if record == VISUAL else self.sender_radio
        return self.receiver_visual if record == VISUAL else self.receiver_radio


@dataclass(frozen=True)
class Episode:
    outcome: str
    unconstrained_outcome: str
    reason: str
    evidence_traffic_bytes: int
    forward_evidence_bytes: int
    reverse_evidence_bytes: int
    message_count: int
    action_ready_latency_ms: float
    local_reuse: bool
    deadline_caused_abstention: bool
    evidence_sufficient: bool
    assembly_location: str
    artifact_format: str
    reverse_message_type: str
    control_bytes: int
    expired_at_decision: bool
    expired_records: str
    finalizer_available: bool
    handoff_required: bool
    handoff_success: bool
    reject_reason: str
    abstain_reason: str
    transmission_suppressed: bool
    transmission_suppression_reason: str
    runtime_stopped: bool


@dataclass(frozen=True)
class EvidenceRecord:
    claim: str
    relation: EvidenceRelation
    modality: str
    source: str
    record_id: str
    proposal_binding: str
    provenance_valid: bool = True
    measurement_time: float = 0.0
    expires_at: float = float("inf")
    calibration_valid: bool = True
    source_trusted: bool = True
    uncertainty: float = 0.0
    maximum_uncertainty: float = float("inf")


@dataclass(frozen=True)
class ReceiverEvidenceStatus:
    """Non-evidentiary feedback used only to adapt the forwarding rule."""

    available: tuple[str, ...]
    missing: tuple[str, ...]
    stale: tuple[str, ...]
    conflict_flag: bool = False


def validate_record(record: EvidenceRecord, expected_binding: str, now: float = 0.0) -> bool:
    return (
        record.claim in REQUIRED_RECORDS
        and record.modality in {"visual", "radio"}
        and bool(record.source)
        and bool(record.record_id)
        and record.proposal_binding == expected_binding
        and record.provenance_valid
        and record.measurement_time <= now <= record.expires_at
        and record.calibration_valid
        and record.source_trusted
        and 0.0 <= record.uncertainty <= record.maximum_uncertainty
    )


def verify_records(
    records: Iterable[EvidenceRecord], expected_binding: str, now: float = 0.0
) -> str:
    valid = tuple(
        record for record in records if validate_record(record, expected_binding, now)
    )
    if any(record.relation is EvidenceRelation.CONFLICTS for record in valid):
        return "reject"
    supporting_claims = {
        record.claim for record in valid
        if record.relation is EvidenceRelation.SUPPORTS
    }
    return "accept" if set(REQUIRED_RECORDS).issubset(supporting_claims) else "abstain"


def authorized_finalization(
    verification_outcome: str,
    endpoint: Finalizer,
    authorized_endpoint: Finalizer,
) -> str:
    """Apply the authorization boundary after evidence verification.

    Verification and authorization are deliberately separate: a verifier may
    find a complete admissible support set at an endpoint that is not permitted
    to finalize the action.  Rejection remains a stop outcome; an unauthorized
    acceptance becomes abstention rather than an action authorization.
    """
    if verification_outcome not in {"accept", "reject", "abstain"}:
        raise ValueError(f"unknown verification outcome: {verification_outcome}")
    if verification_outcome != "accept":
        return verification_outcome
    return "accept" if endpoint is authorized_endpoint else "abstain"


def _availability_joint(qs: float, qr: float, rho: float) -> dict[tuple[bool, bool], float]:
    covariance = rho * sqrt(qs * (1.0 - qs) * qr * (1.0 - qr))
    p11 = qs * qr + covariance
    lower = max(0.0, qs + qr - 1.0)
    upper = min(qs, qr)
    if not lower - 1e-12 <= p11 <= upper + 1e-12:
        raise ValueError("declared availability correlation is outside the Frechet bounds")
    p11 = min(upper, max(lower, p11))
    return {
        (True, True): p11,
        (True, False): qs - p11,
        (False, True): qr - p11,
        (False, False): 1.0 - qs - qr + p11,
    }


MODEL = Model()


def _quality_outcomes(available: bool, truth: bool, model: Model) -> tuple[tuple[RecordObservation, float], ...]:
    if not available:
        return ((RecordObservation.MISSING, 1.0),)
    consistent = RecordObservation.SUPPORTS if truth else RecordObservation.CONFLICTS
    opposite = RecordObservation.CONFLICTS if truth else RecordObservation.SUPPORTS
    return (
        (RecordObservation.INVALID, 1.0 - model.conditional_validity),
        (consistent, model.conditional_validity * (1.0 - model.evidence_relation_error)),
        (opposite, model.conditional_validity * model.evidence_relation_error),
    )


def _endpoint_pairs(truth: bool, model: Model) -> tuple[tuple[RecordObservation, RecordObservation, float], ...]:
    rows: list[tuple[RecordObservation, RecordObservation, float]] = []
    for (sender_available, receiver_available), availability_probability in _availability_joint(
        model.sender_availability, model.receiver_availability, model.endpoint_availability_correlation
    ).items():
        for sender_outcome, sender_probability in _quality_outcomes(sender_available, truth, model):
            for receiver_outcome, receiver_probability in _quality_outcomes(receiver_available, truth, model):
                rows.append((
                    sender_outcome, receiver_outcome,
                    availability_probability * sender_probability * receiver_probability,
                ))
    return tuple(rows)


@lru_cache(maxsize=128)
def enumerate_states(model: Model = MODEL) -> tuple[State, ...]:
    states: list[State] = []
    for clearance_true, no_motion_true in product((False, True), repeat=2):
        truth_probability = (
            (model.claim_true_probability if clearance_true else 1.0 - model.claim_true_probability)
            * (model.claim_true_probability if no_motion_true else 1.0 - model.claim_true_probability)
        )
        for sender_visual, receiver_visual, visual_probability in _endpoint_pairs(clearance_true, model):
            for sender_radio, receiver_radio, radio_probability in _endpoint_pairs(no_motion_true, model):
                for forward_delivered, reverse_delivered in product((False, True), repeat=2):
                    delivery_probability = (
                        (model.forward_delivery_success if forward_delivered else 1.0 - model.forward_delivery_success)
                        * (model.reverse_delivery_success if reverse_delivered else 1.0 - model.reverse_delivery_success)
                    )
                    states.append(State(
                        clearance_true, no_motion_true,
                        sender_visual, sender_radio, receiver_visual, receiver_radio,
                        forward_delivered, reverse_delivered,
                        truth_probability * visual_probability * radio_probability * delivery_probability,
                    ))
    return tuple(states)


def _valid_map(state: State, endpoint: str) -> dict[str, RecordObservation]:
    return {
        record: state.observation(endpoint, record)
        for record in REQUIRED_RECORDS
        if state.observation(endpoint, record) in {RecordObservation.SUPPORTS, RecordObservation.CONFLICTS}
    }


def _verify(observations: Mapping[str, RecordObservation]) -> str:
    if any(outcome is RecordObservation.CONFLICTS for outcome in observations.values()):
        return "reject"
    return "accept" if all(observations.get(record) is RecordObservation.SUPPORTS for record in REQUIRED_RECORDS) else "abstain"


def _merge(*inventories: Mapping[str, RecordObservation]) -> dict[str, RecordObservation]:
    merged: dict[str, RecordObservation] = {}
    for inventory in inventories:
        for record, outcome in inventory.items():
            if outcome is RecordObservation.CONFLICTS or record not in merged:
                merged[record] = outcome
    return merged


def _bytes(records: Iterable[str], model: Model) -> int:
    return sum(model.record_bytes(record) for record in set(records))


def _fresh_map(
    inventory: Mapping[str, RecordObservation], model: Model, decision_time_ms: float,
) -> dict[str, RecordObservation]:
    """Revalidate initially admissible records at the actual decision time."""
    return {
        record: observation
        for record, observation in inventory.items()
        if model.record_fresh(record, decision_time_ms)
    }


def _expired_records(
    inventories: Iterable[Mapping[str, RecordObservation]], model: Model,
    decision_time_ms: float,
) -> tuple[str, ...]:
    records = {record for inventory in inventories for record in inventory}
    return tuple(sorted(
        record for record in records
        if not model.record_fresh(record, decision_time_ms)
    ))


def evaluate_state(
    finalizer: Finalizer,
    interaction: Interaction,
    state: State,
    model: Model = MODEL,
) -> Episode:
    # RecordObservation.MISSING/INVALID are removed by the common record-validation
    # boundary. Records that pass at t0 are revalidated after the complete
    # communication and processing sequence; expiry never creates a veto.
    sender = _fresh_map(_valid_map(state, "sender"), model, 0.0)
    receiver = _fresh_map(_valid_map(state, "receiver"), model, 0.0)
    reverse_records: set[str] = set()
    forward_records: set[str] = set()
    local_reuse = False
    assembly_location = finalizer.value
    # Artifact format is a design variable independent of interaction.  Keep
    # it fixed across the matched One-way/Feedback comparison instead of
    # labelling the One-way row ``not_applicable``.  Receiver finalization uses
    # a receiver-resolved manifest in both interactions; Sender finalization
    # uses the declared Sender format in both interactions.
    artifact_format = (
        model.sender_feedback_format.value
        if finalizer is Finalizer.SENDER
        else ArtifactFormat.REFERENCE_MANIFEST.value
    )
    reverse_message_type = "none"
    transmission_suppression_reason = ""
    relevant_inventories: list[Mapping[str, RecordObservation]] = []

    if interaction is Interaction.ONE_WAY:
        # Fair common One-way forwarding rule: every validated record held
        # by Sender is transmitted, even if partial or conflicting.  A remote
        # conflict cannot affect Receiver's verifier without being carried as
        # an evidence record and charged as evidence traffic.
        forward_records = set(sender)
        message_count = 1
        reverse_latency = 0.0
    elif finalizer is Finalizer.SENDER:
        artifact_format = model.sender_feedback_format.value
        reverse_message_type = "evidence_record"
        # The proposal advertises sender holdings. Receiver returns only evidence
        # records that can fill a missing key, or any valid conflict.
        reverse_records = {
            record for record, outcome in receiver.items()
            if outcome is RecordObservation.CONFLICTS
            or (outcome is RecordObservation.SUPPORTS and sender.get(record) is not RecordObservation.SUPPORTS)
        }
        received_reverse = (
            {record: receiver[record] for record in reverse_records}
            if state.reverse_delivered else {}
        )
        preliminary = _merge(sender, received_reverse)
        preliminary_outcome = _verify(preliminary)
        if preliminary_outcome == "accept":
            if model.sender_feedback_format is ArtifactFormat.SELF_CONTAINED:
                forward_records = set(REQUIRED_RECORDS)
            else:
                # Receiver-origin evidence records remain at Receiver; the signed
                # manifest references their IDs and hashes without re-sending payload.
                forward_records = {
                    record for record, outcome in sender.items()
                    if outcome is RecordObservation.SUPPORTS
                }
                if reverse_records:
                    transmission_suppression_reason = "receiver_owned_record_reuse"
        elif preliminary_outcome == "reject":
            transmission_suppression_reason = "known_valid_conflict"
        message_count = 2
        reverse_latency = model.message_latency_ms(_bytes(reverse_records, model))
    else:
        artifact_format = ArtifactFormat.REFERENCE_MANIFEST.value
        reverse_message_type = "receiver_evidence_status"
        # A delivered receiver evidence-status message permits selective transfer.
        # Valid conflicts always travel as evidence records. A lost evidence-status
        # message triggers the fair One-way
        # fallback and sends every validated sender-held record.
        sender_conflicts = {
            record for record, outcome in sender.items()
            if outcome is RecordObservation.CONFLICTS
        }
        sender_supports = {
            record for record, outcome in sender.items()
            if outcome is RecordObservation.SUPPORTS
        }
        if state.reverse_delivered:
            receiver_supports = {
                record for record, outcome in receiver.items()
                if outcome is RecordObservation.SUPPORTS
            }
            forward_records = sender_conflicts | (sender_supports - receiver_supports)
            if set(sender) - forward_records:
                transmission_suppression_reason = "receiver_redundancy"
        else:
            forward_records = set(sender)
        message_count = 2
        reverse_latency = model.message_latency_ms(0)

    reverse_bytes = _bytes(reverse_records, model)
    forward_bytes = _bytes(forward_records, model)
    latency = reverse_latency + model.message_latency_ms(forward_bytes) + model.processing_time_ms
    sender_decision = _fresh_map(sender, model, latency)
    receiver_decision = _fresh_map(receiver, model, latency)

    if interaction is Interaction.ONE_WAY:
        if finalizer is Finalizer.SENDER:
            relevant_inventories = [sender]
            decision = _verify(sender_decision)
        else:
            received = (
                {record: sender[record] for record in forward_records}
                if state.forward_delivered else {}
            )
            relevant_inventories = [receiver, received]
            decision = _verify(_merge(
                receiver_decision, _fresh_map(received, model, latency)
            ))
    elif finalizer is Finalizer.SENDER:
        received_reverse = (
            {record: receiver[record] for record in reverse_records}
            if state.reverse_delivered else {}
        )
        relevant_inventories = [sender, received_reverse]
        decision = _verify(_merge(
            sender_decision, _fresh_map(received_reverse, model, latency)
        ))
    else:
        received_forward = (
            {record: sender[record] for record in forward_records}
            if state.forward_delivered else {}
        )
        relevant_inventories = [receiver, received_forward]
        decision = _verify(_merge(
            receiver_decision, _fresh_map(received_forward, model, latency)
        ))

    expired = _expired_records(relevant_inventories, model, latency)
    transport_reason = decision == "accept" and not state.forward_delivered
    if transport_reason:
        decision = "abstain"
    local_reuse = (
        decision == "accept"
        and finalizer is Finalizer.RECEIVER
        and any(outcome is RecordObservation.SUPPORTS for outcome in receiver_decision.values())
    ) or (
        decision == "accept"
        and finalizer is Finalizer.SENDER
        and interaction is Interaction.FEEDBACK
        and model.sender_feedback_format is ArtifactFormat.REFERENCE_MANIFEST
        and bool(set(REQUIRED_RECORDS) - set(forward_records))
    )

    unconstrained = decision
    sufficient = unconstrained == "accept"
    missed = sufficient and latency > model.decision_deadline_ms
    outcome = "abstain" if missed else unconstrained
    reason = (
        "deadline" if missed else
        "timely_accept" if outcome == "accept" else
        "valid_conflict" if outcome == "reject" else
        "transport" if transport_reason else
        "expired_evidence" if expired else
        "evidence_insufficient"
    )
    reject_reason = "valid_conflict" if outcome == "reject" else ""
    abstain_reason = reason if outcome == "abstain" else ""
    return Episode(
        outcome, unconstrained, reason,
        forward_bytes + reverse_bytes, forward_bytes, reverse_bytes,
        message_count, latency, local_reuse, missed, sufficient,
        assembly_location, artifact_format, reverse_message_type, 0,
        bool(expired), "+".join(expired), True, False, True,
        reject_reason, abstain_reason,
        bool(transmission_suppression_reason), transmission_suppression_reason,
        False,
    )


def weighted_percentile(values: Sequence[tuple[float, float]], quantile: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    threshold = quantile * sum(weight for _, weight in ordered)
    cumulative = 0.0
    for value, weight in ordered:
        cumulative += weight
        if cumulative + 1e-15 >= threshold:
            return value
    return ordered[-1][0]


@lru_cache(maxsize=2048)
def communication_case_summary(
    finalizer: Finalizer,
    interaction: Interaction,
    model: Model = MODEL,
) -> dict[str, object]:
    """Return an immutable-by-convention exact summary for a communication case.

    Artifact generation requests the same matched summaries from several
    views.  Caching avoids repeating the 4,096-state evaluation without
    changing any generated value; callers treat the returned mapping as
    read-only.
    """
    safe_mass = unsafe_mass = timely_safe = false_safe = traffic = reuse = 0.0
    all_episode_traffic = 0.0
    deadline = insufficient = expired = transport = safe_reject = safe_abstain = 0.0
    accepted_mass = 0.0
    unconstrained_safe_accept = 0.0
    latency_values: list[tuple[float, float]] = []
    for state in enumerate_states(model):
        episode = evaluate_state(finalizer, interaction, state, model)
        weight = state.probability
        # Primary communication-cost metric: unconditional over the common
        # proposal-episode population, including later reject/abstain outcomes.
        all_episode_traffic += weight * episode.evidence_traffic_bytes
        accepted_mass += weight if episode.outcome == "accept" else 0.0
        if state.safe:
            safe_mass += weight
            timely_safe += weight if episode.outcome == "accept" else 0.0
            traffic += weight * episode.evidence_traffic_bytes
            reuse += weight if episode.local_reuse else 0.0
            deadline += weight if episode.deadline_caused_abstention else 0.0
            insufficient += weight if episode.reason == "evidence_insufficient" else 0.0
            expired += weight if episode.reason == "expired_evidence" else 0.0
            transport += weight if episode.reason == "transport" else 0.0
            safe_reject += weight if episode.outcome == "reject" else 0.0
            safe_abstain += weight if episode.outcome == "abstain" else 0.0
            unconstrained_safe_accept += weight if episode.unconstrained_outcome == "accept" else 0.0
            if episode.unconstrained_outcome == "accept":
                latency_values.append((episode.action_ready_latency_ms, weight))
        else:
            unsafe_mass += weight
            false_safe += weight if episode.outcome == "accept" else 0.0
    return {
        "finalizer": finalizer.value,
        "interaction": interaction.value,
        "sender_feedback_format": model.sender_feedback_format.value,
        "artifact_format": (
            model.sender_feedback_format.value
            if finalizer is Finalizer.SENDER
            else ArtifactFormat.REFERENCE_MANIFEST.value
        ),
        "unconditional_coverage": accepted_mass,
        "timely_safe_world_coverage": timely_safe / safe_mass,
        "selective_risk": false_safe / accepted_mass if accepted_mass else 0.0,
        "false_safe_rate": false_safe / unsafe_mass,
        "harmful_acceptance_probability": false_safe,
        "expected_evidence_payload_bytes": all_episode_traffic,
        "expected_evidence_payload_kib": all_episode_traffic / 1024.0,
        # Retained as a legacy auxiliary diagnostic. It is not used by the
        # concept-paper selector or its baseline communication-cost statement.
        "mean_safe_world_evidence_traffic_bytes": traffic / safe_mass,
        "mean_safe_world_evidence_traffic_kib": traffic / safe_mass / 1024.0,
        "p95_action_ready_latency_ms": weighted_percentile(latency_values, 0.95),
        "local_reuse_probability": reuse / safe_mass,
        "deadline_caused_abstention_probability": deadline / safe_mass,
        "evidence_insufficient_abstention_probability": insufficient / safe_mass,
        "expired_evidence_abstention_probability": expired / safe_mass,
        "transport_abstention_probability": transport / safe_mass,
        "safe_world_reject_probability": safe_reject / safe_mass,
        "safe_world_abstention_probability": safe_abstain / safe_mass,
        "finalization_failure_probability": 0.0,
        "unconstrained_safe_accept_probability": unconstrained_safe_accept / safe_mass,
        "logical_message_count": 1 if interaction is Interaction.ONE_WAY else 2,
    }


def matched_communication_case_rows(model: Model = MODEL) -> list[dict[str, object]]:
    return [communication_case_summary(finalizer, interaction, model)
            for finalizer in Finalizer for interaction in Interaction]


def sender_format_rows(model: Model = MODEL) -> list[dict[str, object]]:
    return [
        communication_case_summary(
            Finalizer.SENDER, Interaction.FEEDBACK,
            replace(model, sender_feedback_format=artifact_format),
        )
        for artifact_format in ArtifactFormat
    ]


def episode_rows(model: Model = MODEL) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for state_index, state in enumerate(enumerate_states(model)):
        for finalizer in Finalizer:
            for interaction in Interaction:
                episode = evaluate_state(finalizer, interaction, state, model)
                ages = ";".join(
                    f"{record}={model.initial_age_ms(record):g}"
                    for record in REQUIRED_RECORDS
                )
                decision_ages = ";".join(
                    f"{record}={model.initial_age_ms(record) + episode.action_ready_latency_ms:.6g}"
                    for record in REQUIRED_RECORDS
                )
                rows.append({
                    "state_index": state_index,
                    "required_evidence_set": "+".join(REQUIRED_RECORDS),
                    "finalizer": finalizer.value,
                    "interaction": interaction.value,
                    "clearance_true": state.clearance_true,
                    "no_motion_true": state.no_motion_true,
                    "sender_visual": state.sender_visual.value,
                    "sender_radio": state.sender_radio.value,
                    "receiver_visual": state.receiver_visual.value,
                    "receiver_radio": state.receiver_radio.value,
                    "forward_delivered": state.forward_delivered,
                    "reverse_delivered": state.reverse_delivered,
                    "probability": state.probability,
                    "initial_record_age_ms": ages,
                    "decision_time_age_ms": decision_ages,
                    # Unit-qualified names are retained for analysis while the
                    # aliases implement the minimum cross-domain episode-record schema
                    # stated in the manuscript design task.
                    "initial_record_age": ages,
                    "decision_time_age": decision_ages,
                    "evidence_assembly": episode.assembly_location,
                    "finalizer_feasibility_mode": "conditioned_available",
                    "coverage": episode.outcome == "accept",
                    "selective_risk": episode.outcome == "accept" and not state.safe,
                    "false_safe": episode.outcome == "accept" and not state.safe,
                    "safe_world_coverage": episode.outcome == "accept" and state.safe,
                    "forward_bytes": episode.forward_evidence_bytes,
                    "reverse_bytes": episode.reverse_evidence_bytes,
                    "deadline_miss": episode.deadline_caused_abstention,
                    **episode.__dict__,
                })
    return rows


# Values stay inside the Frechet-feasible range for the declared q_S=0.90
# and Pearson availability correlation rho=0.25.
RECEIVER_AVAILABILITY_GRID = (0.40, 0.50, 0.60, 0.70, 0.75, 0.80, 0.90, 0.95)
VISUAL_SIZE_KIB_GRID = (2, 5, 10, 20, 32)
MESSAGE_LATENCY_MS_GRID = (0.0, 0.5) + tuple(float(index) for index in range(1, 16))
DECISION_DEADLINE_MS_GRID = tuple(float(index) for index in range(10, 51))

# Reader-facing requirement regime used by the concept paper.  The denser grid
# is still finite and is evaluated by exact enumeration.  It deliberately
# varies only the timing quantities shown on the axes; every other baseline
# declaration remains fixed.
REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID = tuple(
    index / 4.0 for index in range(33)
)
REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID = tuple(
    10.0 + index / 2.0 for index in range(81)
)
REQUIREMENT_REGIME_COVERAGE_FLOOR = 0.40
REQUIREMENT_REGIME_SELECTIVE_ERROR_CEILING = 0.0075


def _saving(one: Mapping[str, object], feedback: Mapping[str, object]) -> float:
    denominator = float(one["expected_evidence_payload_bytes"])
    return float("nan") if denominator == 0.0 else 100.0 * (
        denominator - float(feedback["expected_evidence_payload_bytes"])
    ) / denominator


def primary_regime_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for finalizer in Finalizer:
        for visual_kib in VISUAL_SIZE_KIB_GRID:
            for receiver_q in RECEIVER_AVAILABILITY_GRID:
                model = replace(MODEL, receiver_availability=receiver_q,
                                visual_record_bytes=visual_kib * 1024)
                one = communication_case_summary(finalizer, Interaction.ONE_WAY, model)
                feedback = communication_case_summary(finalizer, Interaction.FEEDBACK, model)
                rows.append({
                    "finalizer": finalizer.value,
                    "receiver_evidence_availability": receiver_q,
                    "visual_record_kib": visual_kib,
                    "feedback_evidence_traffic_saving_percent": _saving(one, feedback),
                    "one_way_timely_coverage": one["timely_safe_world_coverage"],
                    "feedback_timely_coverage": feedback["timely_safe_world_coverage"],
                    "feedback_false_safe_rate": feedback["false_safe_rate"],
                    "feedback_local_reuse_probability": feedback["local_reuse_probability"],
                    "baseline_operating_point": receiver_q == 0.90 and visual_kib == 10,
                })
    return rows


def deadline_latency_regime_rows() -> list[dict[str, object]]:
    # Re-evaluate once per fixed-latency value because a longer interaction can
    # invalidate a record at decision time even when the deadline is infinite.
    states = enumerate_states(MODEL)
    safe_mass = sum(state.probability for state in states if state.safe)
    unsafe_mass = sum(state.probability for state in states if not state.safe)
    baseline = {
        (row["finalizer"], row["interaction"]): row
        for row in matched_communication_case_rows(MODEL)
    }

    episode_records: dict[
        tuple[Finalizer, Interaction, float], tuple[tuple[State, Episode], ...]
    ] = {}
    for delta in MESSAGE_LATENCY_MS_GRID:
        sequence_model = replace(
            MODEL, per_message_latency_ms=delta, decision_deadline_ms=float("inf")
        )
        for finalizer in Finalizer:
            for interaction in Interaction:
                episode_records[(finalizer, interaction, delta)] = tuple(
                    (state, evaluate_state(finalizer, interaction, state, sequence_model))
                    for state in states
                )

    def metrics(finalizer: Finalizer, interaction: Interaction,
                delta: float, deadline: float) -> tuple[float, float, float]:
        timely_safe = false_safe = missed = 0.0
        for state, episode in episode_records[(finalizer, interaction, delta)]:
            latency = episode.action_ready_latency_ms
            timely = episode.unconstrained_outcome == "accept" and latency <= deadline
            if state.safe:
                timely_safe += state.probability if timely else 0.0
                missed += state.probability if (
                    episode.unconstrained_outcome == "accept" and latency > deadline
                ) else 0.0
            else:
                false_safe += state.probability if timely else 0.0
        return timely_safe / safe_mass, false_safe / unsafe_mass, missed / safe_mass

    rows: list[dict[str, object]] = []
    for finalizer in Finalizer:
        for deadline in DECISION_DEADLINE_MS_GRID:
            for delta in MESSAGE_LATENCY_MS_GRID:
                one_coverage, one_false_safe, _ = metrics(
                    finalizer, Interaction.ONE_WAY, delta, deadline
                )
                feedback_coverage, feedback_false_safe, feedback_miss = metrics(
                    finalizer, Interaction.FEEDBACK, delta, deadline
                )
                one = baseline[(finalizer.value, Interaction.ONE_WAY.value)]
                feedback = baseline[(finalizer.value, Interaction.FEEDBACK.value)]
                rows.append({
                    "finalizer": finalizer.value,
                    "fixed_per_message_latency_ms": delta,
                    "decision_deadline_ms": deadline,
                    "feedback_minus_one_way_timely_coverage_pp": 100.0 * (feedback_coverage - one_coverage),
                    "one_way_timely_coverage": one_coverage,
                    "feedback_timely_coverage": feedback_coverage,
                    "one_way_false_safe_rate": one_false_safe,
                    "feedback_false_safe_rate": feedback_false_safe,
                    "feedback_deadline_caused_abstention_probability": feedback_miss,
                    "both_zero_timely_coverage": one_coverage == 0.0 and feedback_coverage == 0.0,
                    "feedback_evidence_traffic_saving_percent": _saving(one, feedback),
                    "baseline_operating_point": delta == 0.5 and deadline == 33.0,
                })
    return rows


def requirement_regime_rows(model: Model = MODEL) -> list[dict[str, object]]:
    """Return the three-region interaction map used in the concept paper.

    Finalization authority is fixed within a panel.  At each point, One-way
    and Feedback are first screened by the declared unconditional-coverage and
    selective-error requirements.  Feasible alternatives are ordered by
    expected evidence payload bytes, then logical-message count, with an exact
    tie resolved in favor of One-way.  The ordering is an application-declared
    accounting rule, not a universal utility function.
    """
    states = enumerate_states(model)
    episode_records: dict[
        tuple[Finalizer, Interaction, float], tuple[tuple[State, Episode], ...]
    ] = {}
    for delta in REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID:
        sequence_model = replace(
            model, per_message_latency_ms=delta, decision_deadline_ms=float("inf")
        )
        for finalizer in Finalizer:
            for interaction in Interaction:
                episode_records[(finalizer, interaction, delta)] = tuple(
                    (state, evaluate_state(finalizer, interaction, state, sequence_model))
                    for state in states
                )

    def metrics(finalizer: Finalizer, interaction: Interaction,
                delta: float, deadline: float) -> dict[str, object]:
        accepted = unsupported_accepted = evidence_payload = 0.0
        for state, episode in episode_records[(finalizer, interaction, delta)]:
            timely_accept = (
                episode.unconstrained_outcome == "accept"
                and episode.action_ready_latency_ms <= deadline
            )
            if timely_accept:
                accepted += state.probability
                if not state.safe:
                    unsupported_accepted += state.probability
            evidence_payload += state.probability * episode.evidence_traffic_bytes
        return {
            "interaction": interaction.value,
            "unconditional_coverage": accepted,
            "selective_error": unsupported_accepted / accepted if accepted else 0.0,
            "expected_evidence_payload_bytes": evidence_payload,
            "logical_message_count": 1 if interaction is Interaction.ONE_WAY else 2,
        }

    rows: list[dict[str, object]] = []
    for finalizer in Finalizer:
        for deadline in REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID:
            for delta in REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID:
                one = metrics(finalizer, Interaction.ONE_WAY, delta, deadline)
                feedback = metrics(finalizer, Interaction.FEEDBACK, delta, deadline)
                selected, basis = select_interaction_for_requirements(
                    one, feedback,
                    REQUIREMENT_REGIME_COVERAGE_FLOOR,
                    REQUIREMENT_REGIME_SELECTIVE_ERROR_CEILING,
                )
                rows.append({
                    "finalizer": finalizer.value,
                    "fixed_per_logical_message_latency_ms": delta,
                    "decision_deadline_ms": deadline,
                    "coverage_floor": REQUIREMENT_REGIME_COVERAGE_FLOOR,
                    "selective_error_ceiling": REQUIREMENT_REGIME_SELECTIVE_ERROR_CEILING,
                    "selected_interaction": selected,
                    "selection_basis": basis,
                    "one_way_unconditional_coverage": one["unconditional_coverage"],
                    "feedback_unconditional_coverage": feedback["unconditional_coverage"],
                    "one_way_selective_error": one["selective_error"],
                    "feedback_selective_error": feedback["selective_error"],
                    "one_way_evidence_payload_bytes": one["expected_evidence_payload_bytes"],
                    "feedback_evidence_payload_bytes": feedback["expected_evidence_payload_bytes"],
                    "one_way_logical_message_count": one["logical_message_count"],
                    "feedback_logical_message_count": feedback["logical_message_count"],
                    "baseline_operating_point": delta == 0.5 and deadline == 33.0,
                })
    return rows


SENSITIVITY_GRIDS: Mapping[str, tuple[float, ...]] = {
    "evidence_availability": (0.5, 0.75, 0.9, 1.0),
    "conditional_validity": (0.90, 0.95, 0.99, 1.0),
    "evidence_relation_error": (0.00, 0.02, 0.05, 0.10, 0.15, 0.20),
    "endpoint_correlation": (0.0, 0.25, 0.5, 0.75),
    "forward_delivery_success": (0.90, 0.95, 0.99, 1.0),
    "reverse_delivery_success": (0.90, 0.95, 0.99, 1.0),
    "visual_record_kib": (2.0, 10.0, 32.0),
    "radio_record_kib": (0.5, 1.0, 4.0),
    "link_rate_mbps": (50.0, 100.0, 250.0),
    "fixed_per_message_latency_ms": (0.0, 0.5, 5.0, 15.0),
    "processing_time_ms": (5.0, 10.0, 15.0, 20.0),
    "decision_deadline_ms": (15.0, 25.0, 33.0, 50.0),
    "visual_initial_age_ms": (0.0, 10.0, 20.0, 24.0),
    "radio_initial_age_ms": (0.0, 10.0, 15.0, 24.0),
    "record_ttl_ms": (25.0, 30.0, 35.0, 50.0),
}


def _sensitivity_model(parameter: str, value: float) -> Model:
    mapping = {
        "conditional_validity": "conditional_validity",
        "evidence_relation_error": "evidence_relation_error",
        "endpoint_correlation": "endpoint_availability_correlation",
        "forward_delivery_success": "forward_delivery_success",
        "reverse_delivery_success": "reverse_delivery_success",
        "link_rate_mbps": "link_rate_mbps",
        "fixed_per_message_latency_ms": "per_message_latency_ms",
        "processing_time_ms": "processing_time_ms",
        "decision_deadline_ms": "decision_deadline_ms",
        "visual_initial_age_ms": "visual_initial_age_ms",
        "radio_initial_age_ms": "radio_initial_age_ms",
        "record_ttl_ms": "evidence_ttl_ms",
    }
    if parameter == "evidence_availability":
        return replace(MODEL, sender_availability=value, receiver_availability=value)
    if parameter == "visual_record_kib":
        return replace(MODEL, visual_record_bytes=round(value * 1024))
    if parameter == "radio_record_kib":
        return replace(MODEL, radio_record_bytes=round(value * 1024))
    return replace(MODEL, **{mapping[parameter]: value})


def sensitivity_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for parameter, values in SENSITIVITY_GRIDS.items():
        for value in values:
            for row in matched_communication_case_rows(_sensitivity_model(parameter, value)):
                rows.append({"parameter": parameter, "value": value, **row})
    return rows


def sensitivity_summary_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for parameter, values in SENSITIVITY_GRIDS.items():
        selected = [row for row in rows if row["parameter"] == parameter]
        result.append({
            "parameter": parameter,
            "grid": ", ".join(f"{value:g}" for value in values),
            "minimum_timely_coverage": min(float(row["timely_safe_world_coverage"]) for row in selected),
            "maximum_timely_coverage": max(float(row["timely_safe_world_coverage"]) for row in selected),
            "maximum_false_safe_rate": max(float(row["false_safe_rate"]) for row in selected),
            "minimum_evidence_traffic_kib": min(float(row["mean_safe_world_evidence_traffic_kib"]) for row in selected),
            "maximum_evidence_traffic_kib": max(float(row["mean_safe_world_evidence_traffic_kib"]) for row in selected),
            "maximum_deadline_miss": max(float(row["deadline_caused_abstention_probability"]) for row in selected),
        })
    return result


# The following analyses replace an undifferentiated min--max table with
# inspectable, pattern-specific evidence. None of the selectors compare Sender
# authority with Receiver authority: authority is a declared constraint, not a
# utility term.
PATTERN_CURVE_GRIDS: Mapping[str, tuple[float, ...]] = {
    "evidence_availability": (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.93, 0.96, 0.99, 1.00),
    "evidence_relation_error": (0.00, 0.02, 0.05, 0.10, 0.15, 0.20),
    "fixed_per_message_latency_ms": (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0),
    "decision_deadline_ms": (10.0, 12.0, 15.0, 18.0, 21.0, 24.0, 27.0, 30.0, 33.0, 36.0, 40.0, 45.0, 50.0),
    "visual_initial_age_ms": (0.0, 5.0, 10.0, 15.0, 18.0, 20.0, 21.0, 22.0, 23.0, 24.0),
    "record_ttl_ms": (25.0, 28.0, 30.0, 32.0, 33.0, 35.0, 38.0, 40.0, 45.0, 50.0),
}
INTERACTION_SELECTION_LATENCY_GRID = (0.0, 0.5) + tuple(float(index) for index in range(1, 16))
SELECTION_COVERAGE_TOLERANCE_PP = 0.25


def pattern_sensitivity_curve_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for parameter, values in PATTERN_CURVE_GRIDS.items():
        for value in values:
            for row in matched_communication_case_rows(_sensitivity_model(parameter, value)):
                rows.append({"parameter": parameter, "value": value, **row})
    return rows


def _select_interaction(one: Mapping[str, object], feedback: Mapping[str, object]) -> tuple[str, str]:
    difference_pp = 100.0 * (
        float(feedback["timely_safe_world_coverage"])
        - float(one["timely_safe_world_coverage"])
    )
    if difference_pp > SELECTION_COVERAGE_TOLERANCE_PP:
        return Interaction.FEEDBACK.value, "coverage"
    if difference_pp < -SELECTION_COVERAGE_TOLERANCE_PP:
        return Interaction.ONE_WAY.value, "coverage"
    one_bytes = float(one["mean_safe_world_evidence_traffic_bytes"])
    feedback_bytes = float(feedback["mean_safe_world_evidence_traffic_bytes"])
    if feedback_bytes + 1e-9 < one_bytes:
        return Interaction.FEEDBACK.value, "traffic_within_coverage_tolerance"
    if one_bytes + 1e-9 < feedback_bytes:
        return Interaction.ONE_WAY.value, "traffic_within_coverage_tolerance"
    return Interaction.ONE_WAY.value, "message_count_tiebreak"


def interaction_selection_map_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for receiver_q in RECEIVER_AVAILABILITY_GRID:
        for delta in INTERACTION_SELECTION_LATENCY_GRID:
            model = replace(
                MODEL, receiver_availability=receiver_q, per_message_latency_ms=delta,
            )
            for finalizer in Finalizer:
                one = communication_case_summary(finalizer, Interaction.ONE_WAY, model)
                feedback = communication_case_summary(finalizer, Interaction.FEEDBACK, model)
                winner, basis = _select_interaction(one, feedback)
                rows.append({
                    "finalizer": finalizer.value,
                    "receiver_evidence_availability": receiver_q,
                    "fixed_per_message_latency_ms": delta,
                    "decision_deadline_ms": MODEL.decision_deadline_ms,
                    "coverage_tolerance_pp": SELECTION_COVERAGE_TOLERANCE_PP,
                    "one_way_timely_coverage": one["timely_safe_world_coverage"],
                    "feedback_timely_coverage": feedback["timely_safe_world_coverage"],
                    "feedback_minus_one_way_coverage_pp": 100.0 * (
                        float(feedback["timely_safe_world_coverage"])
                        - float(one["timely_safe_world_coverage"])
                    ),
                    "one_way_evidence_traffic_kib": one["mean_safe_world_evidence_traffic_kib"],
                    "feedback_evidence_traffic_kib": feedback["mean_safe_world_evidence_traffic_kib"],
                    "one_way_selective_risk": one["selective_risk"],
                    "feedback_selective_risk": feedback["selective_risk"],
                    "feedback_traffic_saving_percent": _saving(one, feedback),
                    "selected_interaction": winner,
                    "selection_basis": basis,
                    "baseline_operating_point": receiver_q == 0.90 and delta == 0.5,
                })
    return rows


COVERAGE_REQUIREMENT_GRID = (0.50, 0.55, 0.60, 0.625, 0.65, 0.675, 0.70, 0.725)
SELECTIVE_RISK_CEILING_GRID = (
    0.00100, 0.00200, 0.00300, 0.00400, 0.00500, 0.00750, 0.01000,
)
GLOBAL_COVERAGE_REQUIREMENT = 0.60
GLOBAL_SELECTIVE_RISK_CEILING = 0.00750


def select_interaction_for_requirements(
    one: Mapping[str, object], feedback: Mapping[str, object],
    coverage_floor: float, selective_risk_ceiling: float,
) -> tuple[str, str]:
    """Select interaction under a fixed finalization authority."""
    def error(row: Mapping[str, object]) -> float:
        key = "selective_error" if "selective_error" in row else "selective_risk"
        return float(row[key])

    def payload(row: Mapping[str, object]) -> float:
        key = (
            "expected_evidence_payload_bytes"
            if "expected_evidence_payload_bytes" in row
            else "mean_safe_world_evidence_traffic_bytes"
        )
        return float(row[key])

    feasible = [
        row for row in (one, feedback)
        if float(row["unconditional_coverage"]) + 1e-12 >= coverage_floor
        and error(row) <= selective_risk_ceiling + 1e-12
    ]
    if not feasible:
        return "infeasible", "no_communication_case_meets_requirements"
    feasible.sort(key=lambda row: (
        payload(row),
        int(row["logical_message_count"]),
        0 if row["interaction"] == Interaction.ONE_WAY.value else 1,
    ))
    selected = feasible[0]
    return str(selected["interaction"]), "minimum_traffic_feasible"


REQUIREMENT_NEIGHBORHOOD_COVERAGE_FLOORS = (0.38, 0.40, 0.42)
REQUIREMENT_NEIGHBORHOOD_ERROR_CEILINGS = (0.0050, 0.0075, 0.0100)


def requirement_threshold_neighborhood_rows(
    regime_rows: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, object]]:
    """Reapply nearby application thresholds to the fixed Fig. 3 candidates.

    The check changes only the requirement screen. Candidate outcomes and the
    unconditional payload ordering remain exactly those generated for Fig. 3.
    It is a robustness/regression diagnostic, not model validation.
    """
    candidates = list(regime_rows or requirement_regime_rows())
    summaries: list[dict[str, object]] = []
    for finalizer in Finalizer:
        selected_rows = [
            row for row in candidates if row["finalizer"] == finalizer.value
        ]
        for coverage_floor in REQUIREMENT_NEIGHBORHOOD_COVERAGE_FLOORS:
            for error_ceiling in REQUIREMENT_NEIGHBORHOOD_ERROR_CEILINGS:
                counts = {"one_way": 0, "feedback": 0, "infeasible": 0}
                for row in selected_rows:
                    one = {
                        "interaction": Interaction.ONE_WAY.value,
                        "unconditional_coverage": row["one_way_unconditional_coverage"],
                        "selective_error": row["one_way_selective_error"],
                        "expected_evidence_payload_bytes": row["one_way_evidence_payload_bytes"],
                        "logical_message_count": row["one_way_logical_message_count"],
                    }
                    feedback = {
                        "interaction": Interaction.FEEDBACK.value,
                        "unconditional_coverage": row["feedback_unconditional_coverage"],
                        "selective_error": row["feedback_selective_error"],
                        "expected_evidence_payload_bytes": row["feedback_evidence_payload_bytes"],
                        "logical_message_count": row["feedback_logical_message_count"],
                    }
                    selected, _ = select_interaction_for_requirements(
                        one, feedback, coverage_floor, error_ceiling
                    )
                    counts[selected] += 1
                summaries.append({
                    "finalizer": finalizer.value,
                    "coverage_floor": coverage_floor,
                    "selective_error_ceiling": error_ceiling,
                    "one_way_cells": counts["one_way"],
                    "feedback_cells": counts["feedback"],
                    "infeasible_cells": counts["infeasible"],
                    "all_three_classes_present": all(value > 0 for value in counts.values()),
                })
    return summaries


def interaction_requirement_rows(model: Model = MODEL) -> list[dict[str, object]]:
    baseline = {
        (row["finalizer"], row["interaction"]): row
        for row in matched_communication_case_rows(model)
    }
    rows: list[dict[str, object]] = []
    for finalizer in Finalizer:
        one = baseline[(finalizer.value, Interaction.ONE_WAY.value)]
        feedback = baseline[(finalizer.value, Interaction.FEEDBACK.value)]
        for coverage_floor in COVERAGE_REQUIREMENT_GRID:
            for risk_ceiling in SELECTIVE_RISK_CEILING_GRID:
                selected, basis = select_interaction_for_requirements(
                    one, feedback, coverage_floor, risk_ceiling
                )
                rows.append({
                    "finalizer": finalizer.value,
                    "coverage_floor": coverage_floor,
                    "selective_risk_ceiling": risk_ceiling,
                    "selected_interaction": selected,
                    "selection_basis": basis,
                    "one_way_coverage": one["unconditional_coverage"],
                    "feedback_coverage": feedback["unconditional_coverage"],
                    "one_way_selective_risk": one["selective_risk"],
                    "feedback_selective_risk": feedback["selective_risk"],
                    "one_way_traffic_kib": one["mean_safe_world_evidence_traffic_kib"],
                    "feedback_traffic_kib": feedback["mean_safe_world_evidence_traffic_kib"],
                })
    return rows


EVIDENCE_PATHS = (
    ("pi1", "Visual clearance + Visual no-motion", "visual", "visual"),
    ("pi2", "Visual clearance + Radio no-motion", "visual", "radio"),
    ("pi3", "Radio clearance + Visual no-motion", "radio", "visual"),
    ("pi4", "Radio clearance + Radio no-motion", "radio", "radio"),
)
EVIDENCE_PATH_CORRELATIONS = (0.0, 0.25, 0.50)
EVIDENCE_PATH_ENCODINGS = ("separate", "shared")
EVIDENCE_PATH_VISUAL_AVAILABILITY = 0.90
EVIDENCE_PATH_RADIO_AVAILABILITY = 0.85


def _modality_availability(modality: str) -> float:
    return (
        EVIDENCE_PATH_VISUAL_AVAILABILITY
        if modality == "visual"
        else EVIDENCE_PATH_RADIO_AVAILABILITY
    )


def _modality_bytes(modality: str, model: Model) -> int:
    return model.visual_record_bytes if modality == "visual" else model.radio_record_bytes


def _path_record_cost(
    clearance_observation: RecordObservation, no_motion_observation: RecordObservation,
    clearance_modality: str, no_motion_modality: str, encoding: str, model: Model,
) -> int:
    carried = []
    if clearance_observation in {RecordObservation.SUPPORTS, RecordObservation.CONFLICTS}:
        carried.append(clearance_modality)
    if no_motion_observation in {RecordObservation.SUPPORTS, RecordObservation.CONFLICTS}:
        carried.append(no_motion_modality)
    if encoding == "shared" and len(set(carried)) == 1:
        return _modality_bytes(carried[0], model) if carried else 0
    return sum(_modality_bytes(modality, model) for modality in carried)


def evidence_contract_comparison_rows(model: Model = MODEL) -> list[dict[str, object]]:
    """Small exact comparison that keeps evidence design separate from delivery."""
    rows: list[dict[str, object]] = []
    for path_id, required_set, clearance_modality, motion_modality in EVIDENCE_PATHS:
        q_clearance = _modality_availability(clearance_modality)
        q_motion = _modality_availability(motion_modality)
        for correlation in EVIDENCE_PATH_CORRELATIONS:
            availability = _availability_joint(q_clearance, q_motion, correlation)
            for encoding in EVIDENCE_PATH_ENCODINGS:
                accept = unsafe_accept = safe_accept = traffic = safe_traffic = 0.0
                safe_mass = unsafe_mass = 0.0
                for clearance_true, no_motion_true in product((False, True), repeat=2):
                    truth_probability = (
                        (model.claim_true_probability if clearance_true else 1.0 - model.claim_true_probability)
                        * (model.claim_true_probability if no_motion_true else 1.0 - model.claim_true_probability)
                    )
                    safe = clearance_true and no_motion_true
                    for (clearance_available, motion_available), availability_probability in availability.items():
                        for clearance_observation, clearance_probability in _quality_outcomes(
                            clearance_available, clearance_true, model
                        ):
                            for motion_observation, motion_probability in _quality_outcomes(
                                motion_available, no_motion_true, model
                            ):
                                weight = (
                                    truth_probability * availability_probability
                                    * clearance_probability * motion_probability
                                )
                                observations = {
                                    VISUAL: clearance_observation,
                                    RADIO: motion_observation,
                                }
                                outcome = _verify({
                                    key: value for key, value in observations.items()
                                    if value in {RecordObservation.SUPPORTS, RecordObservation.CONFLICTS}
                                })
                                cost = _path_record_cost(
                                    clearance_observation, motion_observation,
                                    clearance_modality, motion_modality, encoding, model,
                                )
                                accept += weight if outcome == "accept" else 0.0
                                unsafe_accept += weight if outcome == "accept" and not safe else 0.0
                                safe_accept += weight if outcome == "accept" and safe else 0.0
                                traffic += weight * cost
                                if safe:
                                    safe_mass += weight
                                    safe_traffic += weight * cost
                                else:
                                    unsafe_mass += weight
                rows.append({
                    "path_id": path_id,
                    "required_evidence_set": required_set,
                    "finalizer": Finalizer.RECEIVER.value,
                    "interaction": Interaction.ONE_WAY.value,
                    "channel_profile": "evidence_layer_perfect_delivery",
                    "clearance_modality": clearance_modality,
                    "no_motion_modality": motion_modality,
                    "observation_correlation": correlation,
                    "record_encoding": encoding,
                    "shared_encoding_effective": (
                        encoding == "shared" and clearance_modality == motion_modality
                    ),
                    "unconditional_coverage": accept,
                    "safe_world_coverage": safe_accept / safe_mass,
                    "selective_risk": unsafe_accept / accept if accept else 0.0,
                    "false_safe_rate": unsafe_accept / unsafe_mass,
                    "mean_record_cost_kib": traffic / 1024.0,
                    "mean_safe_world_record_cost_kib": safe_traffic / safe_mass / 1024.0,
                })
    return rows


def finalizer_placement_rows(model: Model = MODEL) -> list[dict[str, object]]:
    """Hold assembly and message sequence fixed; vary only the finalizer."""
    states = enumerate_states(model)
    safe_mass = sum(state.probability for state in states if state.safe)
    unsafe_mass = 1.0 - safe_mass
    rows: list[dict[str, object]] = []
    for assembly in Finalizer:
        for finalizer in Finalizer:
            handoff_required = finalizer is not assembly
            availability = model.finalizer_availability(finalizer)
            handoff_probability = model.handoff_success if handoff_required else 1.0
            completion_probability = availability * handoff_probability
            delay = model.handoff_delay_ms if handoff_required else 0.0
            control_bytes = model.handoff_control_bytes if handoff_required else 0
            # Handoff is part of decision completion.  Add its delay before
            # revalidating record TTLs, rather than checking only the deadline
            # after an evaluation with the shorter base message sequence.
            sequence_model = replace(
                model, processing_time_ms=model.processing_time_ms + delay,
            )
            base = tuple(
                (state, evaluate_state(assembly, Interaction.ONE_WAY, state, sequence_model))
                for state in states
            )
            safe_accept = unsafe_accept = finalization_failure = traffic = 0.0
            expiry_abstention = deadline_abstention = evidence_abstention = 0.0
            latency_values: list[tuple[float, float]] = []
            for state, episode in base:
                evidence_accept = episode.unconstrained_outcome == "accept"
                latency = episode.action_ready_latency_ms
                timely = evidence_accept and latency <= model.decision_deadline_ms
                completed_probability = completion_probability if timely else 0.0
                if state.safe:
                    safe_accept += state.probability * completed_probability
                    if evidence_accept and latency <= model.decision_deadline_ms:
                        finalization_failure += state.probability * (1.0 - completion_probability)
                    traffic += state.probability * (
                        episode.evidence_traffic_bytes
                        + (control_bytes if evidence_accept else 0)
                    )
                    if timely:
                        latency_values.append((latency, state.probability * completion_probability))
                    if episode.reason == "expired_evidence":
                        expiry_abstention += state.probability
                    elif episode.deadline_caused_abstention:
                        deadline_abstention += state.probability
                    elif episode.outcome == "abstain":
                        evidence_abstention += state.probability
                elif timely:
                    unsafe_accept += state.probability * completion_probability
            unconditional = safe_accept + unsafe_accept
            rows.append({
                "evidence_assembly": assembly.value,
                "required_evidence_set": "+".join(REQUIRED_RECORDS),
                "interaction": Interaction.ONE_WAY.value,
                "artifact_format": (
                    model.sender_feedback_format.value
                    if assembly is Finalizer.SENDER
                    else ArtifactFormat.REFERENCE_MANIFEST.value
                ),
                "finalizer": finalizer.value,
                "finalizer_available_probability": availability,
                "handoff_required": handoff_required,
                "handoff_success_probability": handoff_probability,
                "handoff_delay_ms": delay,
                "handoff_control_bytes": control_bytes,
                "unconditional_coverage": unconditional,
                "timely_safe_world_coverage": safe_accept / safe_mass,
                "selective_risk": unsafe_accept / unconditional if unconditional else 0.0,
                "false_safe_rate": unsafe_accept / unsafe_mass,
                "finalization_failure_probability": finalization_failure / safe_mass,
                "expired_evidence_abstention_probability": expiry_abstention / safe_mass,
                "deadline_abstention_probability": deadline_abstention / safe_mass,
                "other_evidence_abstention_probability": evidence_abstention / safe_mass,
                "mean_safe_world_total_traffic_kib": traffic / safe_mass / 1024.0,
                "p95_action_ready_latency_ms": weighted_percentile(latency_values, 0.95),
            })
    return rows


def evaluation_layer_rows() -> list[dict[str, object]]:
    """Machine-readable declaration of fixed and varied comparison dimensions."""
    common = {
        "required_evidence_set": "+".join(REQUIRED_RECORDS),
        "evidence_law": "declared_exact_finite_state_law",
        "verifier": "common_typed_validation_pipeline",
    }
    return [
        {
            "evaluation": "A_fair_interaction_sender",
            **common,
            "fixed_dimensions": "finalizer=sender;evidence_contract;inventory_law;verifier;artifact_format=reference_manifest",
            "varied_dimensions": "interaction=one_way|feedback",
        },
        {
            "evaluation": "A_fair_interaction_receiver",
            **common,
            "fixed_dimensions": "finalizer=receiver;evidence_contract;inventory_law;verifier;artifact_format=reference_manifest",
            "varied_dimensions": "interaction=one_way|feedback",
        },
        {
            "evaluation": "B_evidence_contract",
            **common,
            "fixed_dimensions": "finalizer=receiver;interaction=one_way;channel=evidence_layer_perfect_delivery",
            "varied_dimensions": "required_evidence_contract;observation_correlation;record_encoding",
        },
        {
            "evaluation": "C_finalizer_placement_sender_assembly",
            **common,
            "fixed_dimensions": "evidence_assembly=sender;interaction=one_way;base_message_sequence;artifact_format=reference_manifest",
            "varied_dimensions": "finalizer;availability;handoff_success;handoff_delay;handoff_control_bytes",
        },
        {
            "evaluation": "C_finalizer_placement_receiver_assembly",
            **common,
            "fixed_dimensions": "evidence_assembly=receiver;interaction=one_way;base_message_sequence;artifact_format=reference_manifest",
            "varied_dimensions": "finalizer;availability;handoff_success;handoff_delay;handoff_control_bytes",
        },
    ]


FINALIZER_SENSITIVITY_GRIDS: Mapping[str, tuple[float, ...]] = {
    "sender_finalizer_availability": (0.90, 0.95, 0.98, 0.995, 1.00),
    "receiver_finalizer_availability": (0.90, 0.95, 0.98, 0.985, 1.00),
    "handoff_success": (0.90, 0.95, 0.98, 0.99, 1.00),
    "handoff_delay_ms": (0.0, 0.5, 1.0, 2.0, 5.0),
    "handoff_control_bytes": (0.0, 32.0, 64.0, 128.0, 256.0),
}


def finalizer_placement_sensitivity_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for parameter, values in FINALIZER_SENSITIVITY_GRIDS.items():
        for value in values:
            parameter_value: object = round(value) if parameter == "handoff_control_bytes" else value
            model = replace(MODEL, **{parameter: parameter_value})
            for row in finalizer_placement_rows(model):
                rows.append({"parameter": parameter, "value": value, **row})
    return rows


FRESHNESS_COMPARISON_AGES_MS = (20.0, 23.4, 24.0)


def freshness_comparison_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for visual_age in FRESHNESS_COMPARISON_AGES_MS:
        model = replace(MODEL, visual_initial_age_ms=visual_age)
        for interaction in Interaction:
            summary = communication_case_summary(Finalizer.RECEIVER, interaction, model)
            rows.append({
                "finalizer": Finalizer.RECEIVER.value,
                "interaction": interaction.value,
                "visual_initial_age_ms": visual_age,
                "radio_initial_age_ms": model.radio_initial_age_ms,
                "evidence_ttl_ms": model.evidence_ttl_ms,
                "timely_safe_world_coverage": summary["timely_safe_world_coverage"],
                "expired_evidence_abstention_probability": summary[
                    "expired_evidence_abstention_probability"
                ],
                "mean_safe_world_evidence_traffic_kib": summary[
                    "mean_safe_world_evidence_traffic_kib"
                ],
                "p95_action_ready_latency_ms": summary["p95_action_ready_latency_ms"],
            })
    return rows


def feedback_sign_change_rows(
    rank_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for finalizer in Finalizer:
        selected = sorted(
            (row for row in rank_rows
             if row["finalizer"] == finalizer.value
             and float(row["receiver_evidence_availability"]) == 0.90),
            key=lambda row: float(row["fixed_per_message_latency_ms"]),
        )
        baseline = min(selected, key=lambda row: abs(
            float(row["fixed_per_message_latency_ms"]) - MODEL.per_message_latency_ms
        ))
        after_baseline = [
            row for row in selected
            if float(row["fixed_per_message_latency_ms"]) > MODEL.per_message_latency_ms
        ]
        negative = [row for row in after_baseline
                    if float(row["feedback_minus_one_way_coverage_pp"]) < 0.0]
        both_zero = [row for row in after_baseline
                     if float(row["one_way_timely_coverage"]) == 0.0
                     and float(row["feedback_timely_coverage"]) == 0.0]
        differences = [float(row["feedback_minus_one_way_coverage_pp"]) for row in selected]
        result.append({
            "finalizer": finalizer.value,
            "receiver_evidence_availability": 0.90,
            "baseline_coverage_difference_pp": baseline["feedback_minus_one_way_coverage_pp"],
            "first_negative_latency_after_baseline_ms": min(
                (float(row["fixed_per_message_latency_ms"]) for row in negative),
                default=float("nan"),
            ),
            "first_both_zero_latency_ms": min(
                (float(row["fixed_per_message_latency_ms"]) for row in both_zero),
                default=float("nan"),
            ),
            "maximum_positive_coverage_difference_pp": max(differences),
            "minimum_coverage_difference_pp": min(differences),
            "baseline_traffic_saving_percent": baseline["feedback_traffic_saving_percent"],
            "selector": (
                f"coverage outside +/-{SELECTION_COVERAGE_TOLERANCE_PP:g} pp; "
                "then evidence traffic; then message count"
            ),
        })
    return result


def feedback_advantage_decomposition_rows() -> list[dict[str, object]]:
    """Decompose the coverage difference into gained and lost safe-state mass."""
    states = enumerate_states(MODEL)
    safe_mass = sum(state.probability for state in states if state.safe)
    rows: list[dict[str, object]] = []
    for finalizer in Finalizer:
        for delta in INTERACTION_SELECTION_LATENCY_GRID:
            sequence_model = replace(
                MODEL, per_message_latency_ms=delta,
                decision_deadline_ms=float("inf"),
            )
            one_records = tuple(
                evaluate_state(finalizer, Interaction.ONE_WAY, state, sequence_model)
                for state in states
            )
            feedback_records = tuple(
                evaluate_state(finalizer, Interaction.FEEDBACK, state, sequence_model)
                for state in states
            )
            gain = loss = common = neither = 0.0
            for state, one, feedback in zip(states, one_records, feedback_records):
                if not state.safe:
                    continue
                one_timely = (
                    one.unconstrained_outcome == "accept"
                    and one.action_ready_latency_ms <= MODEL.decision_deadline_ms
                )
                feedback_timely = (
                    feedback.unconstrained_outcome == "accept"
                    and feedback.action_ready_latency_ms <= MODEL.decision_deadline_ms
                )
                if feedback_timely and not one_timely:
                    gain += state.probability
                elif one_timely and not feedback_timely:
                    loss += state.probability
                elif one_timely and feedback_timely:
                    common += state.probability
                else:
                    neither += state.probability
            gain, loss, common, neither = (
                value / safe_mass for value in (gain, loss, common, neither)
            )
            rows.append({
                "finalizer": finalizer.value,
                "fixed_per_message_latency_ms": delta,
                "decision_deadline_ms": MODEL.decision_deadline_ms,
                "feedback_only_timely_gain_probability": gain,
                "one_way_only_timely_loss_probability": loss,
                "common_timely_accept_probability": common,
                "neither_timely_accept_probability": neither,
                "feedback_minus_one_way_coverage_pp": 100.0 * (gain - loss),
                "probability_partition_sum": gain + loss + common + neither,
                "baseline_operating_point": delta == MODEL.per_message_latency_ms,
            })
    return rows


GLOBAL_PARAMETER_RANGES: Mapping[str, tuple[float, float]] = {
    "evidence_availability": (0.75, 0.99),
    "conditional_validity": (0.97, 1.00),
    "evidence_relation_error": (0.05, 0.15),
    "endpoint_correlation": (0.0, 0.60),
    "forward_delivery_success": (0.97, 1.00),
    "reverse_delivery_success": (0.97, 1.00),
    "visual_record_kib": (4.0, 20.0),
    "radio_record_kib": (0.5, 2.0),
    "link_rate_mbps": (50.0, 250.0),
    "fixed_per_message_latency_ms": (0.1, 5.0),
    "processing_time_ms": (5.0, 15.0),
    "decision_deadline_ms": (25.0, 50.0),
    "visual_initial_age_ms": (10.0, 24.0),
    "radio_initial_age_ms": (5.0, 22.0),
    "record_ttl_ms": (30.0, 50.0),
}
GLOBAL_SAMPLE_COUNT = 64
GLOBAL_SAMPLE_SEED = 20260816


def global_parameter_range_rows() -> list[dict[str, object]]:
    return [
        {
            "parameter": parameter,
            "baseline": _baseline_parameter_value(parameter),
            "lower": bounds[0],
            "upper": bounds[1],
        }
        for parameter, bounds in GLOBAL_PARAMETER_RANGES.items()
    ]


def _latin_hypercube_rows() -> list[dict[str, float]]:
    generator = random.Random(GLOBAL_SAMPLE_SEED)
    columns: dict[str, list[float]] = {}
    for parameter, (lower, upper) in GLOBAL_PARAMETER_RANGES.items():
        bins = list(range(GLOBAL_SAMPLE_COUNT))
        generator.shuffle(bins)
        columns[parameter] = [
            lower + (upper - lower) * (index + 0.5) / GLOBAL_SAMPLE_COUNT
            for index in bins
        ]
    return [
        {parameter: columns[parameter][sample]
         for parameter in GLOBAL_PARAMETER_RANGES}
        for sample in range(GLOBAL_SAMPLE_COUNT)
    ]


def _model_from_parameter_row(row: Mapping[str, float]) -> Model:
    return replace(
        MODEL,
        sender_availability=row["evidence_availability"],
        receiver_availability=row["evidence_availability"],
        conditional_validity=row["conditional_validity"],
        evidence_relation_error=row["evidence_relation_error"],
        endpoint_availability_correlation=row["endpoint_correlation"],
        forward_delivery_success=row["forward_delivery_success"],
        reverse_delivery_success=row["reverse_delivery_success"],
        visual_record_bytes=round(row["visual_record_kib"] * 1024),
        radio_record_bytes=round(row["radio_record_kib"] * 1024),
        link_rate_mbps=row["link_rate_mbps"],
        per_message_latency_ms=row["fixed_per_message_latency_ms"],
        processing_time_ms=row["processing_time_ms"],
        decision_deadline_ms=row["decision_deadline_ms"],
        visual_initial_age_ms=row["visual_initial_age_ms"],
        radio_initial_age_ms=row["radio_initial_age_ms"],
        evidence_ttl_ms=row["record_ttl_ms"],
    )


def global_uncertainty_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sample_id, parameters in enumerate(_latin_hypercube_rows()):
        for communication_case in matched_communication_case_rows(
            _model_from_parameter_row(parameters)
        ):
            rows.append({"sample_id": sample_id, **parameters, **communication_case})
    return rows


def global_selection_rows(
    uncertainty_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    baseline = {
        (row["finalizer"], row["interaction"]): row
        for row in matched_communication_case_rows()
    }
    baseline_selection = {
        finalizer.value: select_interaction_for_requirements(
            baseline[(finalizer.value, Interaction.ONE_WAY.value)],
            baseline[(finalizer.value, Interaction.FEEDBACK.value)],
            GLOBAL_COVERAGE_REQUIREMENT,
            GLOBAL_SELECTIVE_RISK_CEILING,
        )[0]
        for finalizer in Finalizer
    }
    result: list[dict[str, object]] = []
    sample_ids = sorted({int(row["sample_id"]) for row in uncertainty_rows})
    for sample_id in sample_ids:
        for finalizer in Finalizer:
            selected_rows = [
                row for row in uncertainty_rows
                if int(row["sample_id"]) == sample_id
                and row["finalizer"] == finalizer.value
            ]
            by_interaction = {row["interaction"]: row for row in selected_rows}
            selected, basis = select_interaction_for_requirements(
                by_interaction[Interaction.ONE_WAY.value],
                by_interaction[Interaction.FEEDBACK.value],
                GLOBAL_COVERAGE_REQUIREMENT,
                GLOBAL_SELECTIVE_RISK_CEILING,
            )
            result.append({
                "sample_id": sample_id,
                "finalizer": finalizer.value,
                "coverage_floor": GLOBAL_COVERAGE_REQUIREMENT,
                "selective_risk_ceiling": GLOBAL_SELECTIVE_RISK_CEILING,
                "selected_interaction": selected,
                "selection_basis": basis,
                "baseline_selection": baseline_selection[finalizer.value],
                "ordering_reversal": (
                    selected != "infeasible"
                    and baseline_selection[finalizer.value] != "infeasible"
                    and selected != baseline_selection[finalizer.value]
                ),
            })
    return result


def global_selection_summary_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for finalizer in Finalizer:
        selected = [row for row in rows if row["finalizer"] == finalizer.value]
        count = len(selected)
        result.append({
            "finalizer": finalizer.value,
            "sample_count": count,
            "coverage_floor": GLOBAL_COVERAGE_REQUIREMENT,
            "selective_risk_ceiling": GLOBAL_SELECTIVE_RISK_CEILING,
            "baseline_selection": selected[0]["baseline_selection"],
            "one_way_selection_frequency": sum(
                row["selected_interaction"] == Interaction.ONE_WAY.value for row in selected
            ) / count,
            "feedback_selection_frequency": sum(
                row["selected_interaction"] == Interaction.FEEDBACK.value for row in selected
            ) / count,
            "infeasible_frequency": sum(
                row["selected_interaction"] == "infeasible" for row in selected
            ) / count,
            "ordering_reversal_frequency": sum(
                bool(row["ordering_reversal"]) for row in selected
            ) / count,
        })
    return result


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def global_uncertainty_summary_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    metrics = (
        "timely_safe_world_coverage", "mean_safe_world_evidence_traffic_kib",
        "p95_action_ready_latency_ms",
    )
    for finalizer in Finalizer:
        for interaction in Interaction:
            selected = [row for row in rows if row["finalizer"] == finalizer.value
                        and row["interaction"] == interaction.value]
            output: dict[str, object] = {
                "finalizer": finalizer.value, "interaction": interaction.value,
                "sample_count": len(selected),
            }
            for metric in metrics:
                values = [float(row[metric]) for row in selected
                          if isfinite(float(row[metric]))]
                output[f"{metric}_defined_sample_count"] = len(values)
                for label, probability in (("p05", 0.05), ("p50", 0.50), ("p95", 0.95)):
                    output[f"{metric}_{label}"] = (
                        _quantile(values, probability) if values else float("nan")
                    )
            result.append(output)
    return result


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        stop = start + 1
        while stop < len(ordered) and ordered[stop][1] == ordered[start][1]:
            stop += 1
        rank = 0.5 * (start + stop - 1) + 1.0
        for index in range(start, stop):
            ranks[ordered[index][0]] = rank
        start = stop
    return ranks


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = sqrt(sum((a - left_mean) ** 2 for a in left))
    right_scale = sqrt(sum((b - right_mean) ** 2 for b in right))
    return 0.0 if left_scale == 0.0 or right_scale == 0.0 else numerator / (left_scale * right_scale)


def global_sensitivity_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    metrics = ("timely_safe_world_coverage", "mean_safe_world_evidence_traffic_kib")
    for finalizer in Finalizer:
        for interaction in Interaction:
            selected = [row for row in rows if row["finalizer"] == finalizer.value
                        and row["interaction"] == interaction.value]
            for parameter in GLOBAL_PARAMETER_RANGES:
                parameter_ranks = _average_ranks([float(row[parameter]) for row in selected])
                for metric in metrics:
                    metric_ranks = _average_ranks([float(row[metric]) for row in selected])
                    coefficient = _correlation(parameter_ranks, metric_ranks)
                    result.append({
                        "finalizer": finalizer.value,
                        "interaction": interaction.value,
                        "parameter": parameter,
                        "metric": metric,
                        "spearman_rank_correlation": coefficient,
                        "absolute_rank_correlation": abs(coefficient),
                        "sample_count": len(selected),
                    })
    return result


LOCAL_PARAMETERS = (
    "evidence_availability", "conditional_validity", "evidence_relation_error",
    "endpoint_correlation", "forward_delivery_success", "reverse_delivery_success",
    "visual_record_kib", "radio_record_kib", "link_rate_mbps",
    "fixed_per_message_latency_ms", "processing_time_ms", "decision_deadline_ms",
    "visual_initial_age_ms", "radio_initial_age_ms", "record_ttl_ms",
)


def _baseline_parameter_value(parameter: str) -> float:
    values = {
        "evidence_availability": MODEL.sender_availability,
        "conditional_validity": MODEL.conditional_validity,
        "evidence_relation_error": MODEL.evidence_relation_error,
        "endpoint_correlation": MODEL.endpoint_availability_correlation,
        "forward_delivery_success": MODEL.forward_delivery_success,
        "reverse_delivery_success": MODEL.reverse_delivery_success,
        "visual_record_kib": MODEL.visual_record_bytes / 1024.0,
        "radio_record_kib": MODEL.radio_record_bytes / 1024.0,
        "link_rate_mbps": MODEL.link_rate_mbps,
        "fixed_per_message_latency_ms": MODEL.per_message_latency_ms,
        "processing_time_ms": MODEL.processing_time_ms,
        "decision_deadline_ms": MODEL.decision_deadline_ms,
        "visual_initial_age_ms": MODEL.visual_initial_age_ms,
        "radio_initial_age_ms": MODEL.radio_initial_age_ms,
        "record_ttl_ms": MODEL.evidence_ttl_ms,
    }
    return values[parameter]


def local_sensitivity_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    baseline = {(row["finalizer"], row["interaction"]): row for row in matched_communication_case_rows()}
    for parameter in LOCAL_PARAMETERS:
        center = _baseline_parameter_value(parameter)
        lower = center * 0.95
        upper = center * 1.05
        if parameter in {"conditional_validity", "forward_delivery_success", "reverse_delivery_success"}:
            upper = min(1.0, upper)
        low_rows = {(row["finalizer"], row["interaction"]): row
                    for row in matched_communication_case_rows(_sensitivity_model(parameter, lower))}
        high_rows = {(row["finalizer"], row["interaction"]): row
                     for row in matched_communication_case_rows(_sensitivity_model(parameter, upper))}
        for key, base in baseline.items():
            low, high = low_rows[key], high_rows[key]
            scale = 0.10 * center / (upper - lower)
            rows.append({
                "parameter": parameter,
                "baseline_value": center,
                "lower_value": lower,
                "upper_value": upper,
                "finalizer": key[0],
                "interaction": key[1],
                "coverage_change_pp_per_plus_10_percent": 100.0 * scale * (
                    float(high["timely_safe_world_coverage"])
                    - float(low["timely_safe_world_coverage"])
                ),
                "traffic_change_percent_per_plus_10_percent": 100.0 * scale * (
                    float(high["mean_safe_world_evidence_traffic_kib"])
                    - float(low["mean_safe_world_evidence_traffic_kib"])
                ) / float(base["mean_safe_world_evidence_traffic_kib"]),
                "p95_latency_change_ms_per_plus_10_percent": scale * (
                    float(high["p95_action_ready_latency_ms"])
                    - float(low["p95_action_ready_latency_ms"])
                ),
            })
    return rows


def local_sensitivity_summary_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for finalizer in Finalizer:
        for interaction in Interaction:
            selected = [row for row in rows if row["finalizer"] == finalizer.value
                        and row["interaction"] == interaction.value]
            coverage = max(selected, key=lambda row: abs(float(
                row["coverage_change_pp_per_plus_10_percent"])))
            traffic = max(selected, key=lambda row: abs(float(
                row["traffic_change_percent_per_plus_10_percent"])))
            result.append({
                "finalizer": finalizer.value,
                "interaction": interaction.value,
                "largest_coverage_driver": coverage["parameter"],
                "coverage_change_pp_per_plus_10_percent": coverage[
                    "coverage_change_pp_per_plus_10_percent"],
                "largest_traffic_driver": traffic["parameter"],
                "traffic_change_percent_per_plus_10_percent": traffic[
                    "traffic_change_percent_per_plus_10_percent"],
            })
    return result


def dimensionless_baseline_rows(model: Model = MODEL) -> list[dict[str, object]]:
    total_bytes = model.visual_record_bytes + model.radio_record_bytes
    return [
        {"quantity": "$D/\\delta$", "value": model.decision_deadline_ms / model.per_message_latency_ms,
         "interpretation": "deadline in fixed-message-latency units"},
        {"quantity": "$8(B_V+B_R)/(RD)$", "value": 8.0 * total_bytes / (
            model.link_rate_mbps * 1_000.0 * model.decision_deadline_ms),
         "interpretation": "full evidence serialization as a deadline fraction"},
        {"quantity": "$T_p/D$", "value": model.processing_time_ms / model.decision_deadline_ms,
         "interpretation": "common processing as a deadline fraction"},
    ]


def baseline_declaration_rows(model: Model = MODEL) -> list[dict[str, object]]:
    return [
        {"parameter": "Required evidence", "baseline": "Visual clearance + Radio no-motion", "interpretation": "two-record contract"},
        {"parameter": "Claim-truth prior $p_{\\mathrm{truth}}$", "baseline": f"{model.claim_true_probability:.2f} per claim", "interpretation": "synthetic truth prior"},
        {"parameter": "Claim-truth dependence", "baseline": "Independent", "interpretation": "the two claim truths are independent"},
        {"parameter": "Evidence availability $q$", "baseline": f"{model.sender_availability:.2f} per endpoint/item", "interpretation": "per endpoint and evidence item"},
        {"parameter": "Conditional validity", "baseline": f"{model.conditional_validity:.2f}", "interpretation": "available record passes record validation"},
        {"parameter": "Evidence-relation error", "baseline": f"{model.evidence_relation_error:.2f}", "interpretation": "incorrect support/conflict relation conditional on availability and passing record validation"},
        {"parameter": "Endpoint correlation $\\rho$", "baseline": f"{model.endpoint_availability_correlation:.2f}", "interpretation": "availability correlation per record"},
        {"parameter": "Delivery success $(p_f,p_r)$", "baseline": f"({model.forward_delivery_success:.2f}, {model.reverse_delivery_success:.2f})", "interpretation": "forward and reverse logical messages"},
        {"parameter": "Records $(B_V,B_R)$", "baseline": f"({model.visual_record_bytes / 1024:g}, {model.radio_record_bytes / 1024:g}) KiB", "interpretation": "asymmetric evidence payloads"},
        {"parameter": "Link rate $R$", "baseline": f"{model.link_rate_mbps:g} Mbit/s", "interpretation": "serialization rate"},
        {"parameter": "Per-message latency $\\delta$", "baseline": f"{model.per_message_latency_ms:g} ms", "interpretation": "once per logical message"},
        {"parameter": "Processing time $T_p$", "baseline": f"{model.processing_time_ms:g} ms", "interpretation": "validation, assembly, and finalization"},
        {"parameter": "Decision deadline $D$", "baseline": f"{model.decision_deadline_ms:g} ms", "interpretation": "one 30-Hz design period, proposal to action-ready"},
        {"parameter": "Initial ages $(A_V,A_R)$", "baseline": f"({model.visual_initial_age_ms:g}, {model.radio_initial_age_ms:g}) ms", "interpretation": "age at proposal time"},
        {"parameter": "Evidence TTL", "baseline": f"{model.evidence_ttl_ms:g} ms", "interpretation": "revalidated at action-ready time"},
        {"parameter": "Finalizer availability $(a_S,a_R)$", "baseline": f"({model.sender_finalizer_availability:.3f}, {model.receiver_finalizer_availability:.3f})", "interpretation": "used only in the matched finalizer comparison"},
        {"parameter": "Handoff $(h,\\tau_h,B_h)$", "baseline": f"({model.handoff_success:.2f}, {model.handoff_delay_ms:g} ms, {model.handoff_control_bytes} B)", "interpretation": "used only when finalizer differs from assembly"},
        {"parameter": "Sender/Feedback format", "baseline": "reference manifest", "interpretation": "self-contained is a reported sensitivity"},
    ]


def verifier_consistency_rows() -> list[dict[str, object]]:
    binding = "proposal-1"
    supporting_visual = EvidenceRecord(
        VISUAL, EvidenceRelation.SUPPORTS, "visual", "camera", "v-sup", binding
    )
    supporting_radio = EvidenceRecord(
        RADIO, EvidenceRelation.SUPPORTS, "radio", "radio", "r-sup", binding
    )
    conflicting_visual = EvidenceRecord(
        VISUAL, EvidenceRelation.CONFLICTS, "visual", "camera", "v-con", binding
    )
    invalid = replace(conflicting_visual, record_id="bad-p", provenance_valid=False)
    wrong_binding = replace(conflicting_visual, record_id="bad-b", proposal_binding="other")
    expired = replace(conflicting_visual, record_id="expired", expires_at=5.0)
    revoked = replace(conflicting_visual, record_id="revoked", calibration_valid=False)
    untrusted = replace(conflicting_visual, record_id="untrusted", source_trusted=False)
    uncertain = replace(
        conflicting_visual, record_id="uncertain", uncertainty=2.0, maximum_uncertainty=1.0
    )
    scenarios = (
        ("complete supporting evidence", (supporting_visual, supporting_radio), "accept"),
        ("incomplete supporting evidence", (supporting_visual,), "abstain"),
        ("admissible Visual conflict", (conflicting_visual, supporting_radio), "reject"),
        ("conflict before completeness", (supporting_visual, conflicting_visual), "reject"),
        ("invalid-provenance conflict", (supporting_visual, supporting_radio, invalid), "accept"),
        ("binding-mismatched conflict", (supporting_visual, supporting_radio, wrong_binding), "accept"),
        ("expired conflict", (supporting_visual, supporting_radio, expired), "accept"),
        ("revoked-calibration conflict", (supporting_visual, supporting_radio, revoked), "accept"),
        ("untrusted-source conflict", (supporting_visual, supporting_radio, untrusted), "accept"),
        ("excessive-uncertainty conflict", (supporting_visual, supporting_radio, uncertain), "accept"),
    )
    rows = []
    for name, records, expected in scenarios:
        outcome = verify_records(records, binding, now=10.0)
        rows.append({
            "scenario": name,
            "verification_outcome": outcome,
            "finalization_outcome": authorized_finalization(
                outcome, Finalizer.SENDER, Finalizer.SENDER
            ),
            "expected_outcome": expected,
            "passes": outcome == expected,
        })

    verification_outcome = verify_records(
        (supporting_visual, supporting_radio), binding, now=10.0
    )
    finalization_outcome = authorized_finalization(
        verification_outcome, Finalizer.RECEIVER, Finalizer.SENDER
    )
    rows.append({
        "scenario": "complete evidence at unauthorized endpoint",
        "verification_outcome": verification_outcome,
        "finalization_outcome": finalization_outcome,
        "expected_outcome": "abstain",
        "passes": finalization_outcome == "abstain",
    })
    return rows


def framework_structural_metric_rows(model: Model = MODEL) -> list[dict[str, object]]:
    """Machine-checkable effects used by the framework checks.

    The transfer and reachability checks remove deadline and lifetime effects so
    that they test communication structure rather than timing.  Payload saving
    is reported on the ordinary baseline episode population.
    """
    structural_model = replace(
        model, decision_deadline_ms=float("inf"), evidence_ttl_ms=float("inf")
    )
    sender_transfer_gain_mass = 0.0
    sender_transfer_gain_count = 0
    receiver_reachability_mismatch_count = 0
    receiver_reachability_mismatch_mass = 0.0
    receiver_payload_saving_bytes = 0.0
    receiver_payload_saving_state_count = 0

    for state in enumerate_states(model):
        sender_one = evaluate_state(
            Finalizer.SENDER, Interaction.ONE_WAY, state, structural_model
        )
        sender_feedback = evaluate_state(
            Finalizer.SENDER, Interaction.FEEDBACK, state, structural_model
        )
        if (
            sender_feedback.unconstrained_outcome == "accept"
            and sender_one.unconstrained_outcome != "accept"
        ):
            sender_transfer_gain_count += 1
            sender_transfer_gain_mass += state.probability

        receiver_one = evaluate_state(
            Finalizer.RECEIVER, Interaction.ONE_WAY, state, structural_model
        )
        receiver_feedback = evaluate_state(
            Finalizer.RECEIVER, Interaction.FEEDBACK, state, structural_model
        )
        if receiver_one.unconstrained_outcome != receiver_feedback.unconstrained_outcome:
            receiver_reachability_mismatch_count += 1
            receiver_reachability_mismatch_mass += state.probability
        saving = receiver_one.evidence_traffic_bytes - receiver_feedback.evidence_traffic_bytes
        receiver_payload_saving_bytes += state.probability * saving
        if saving > 0:
            receiver_payload_saving_state_count += 1

    verifier_rows = verifier_consistency_rows()
    return [
        {
            "metric": "sender_transfer_gain_mass",
            "value": sender_transfer_gain_mass,
            "state_count": sender_transfer_gain_count,
            "passes": sender_transfer_gain_mass > 0.0,
            "interpretation": "feedback strictly enlarges reachable admissible support in some sender-finalized states",
        },
        {
            "metric": "receiver_reachability_mismatch_count",
            "value": receiver_reachability_mismatch_mass,
            "state_count": receiver_reachability_mismatch_count,
            "passes": receiver_reachability_mismatch_count == 0,
            "interpretation": "coordination preserves pre-timing evidence reachability under the declared one-way fallback",
        },
        {
            "metric": "receiver_coordination_payload_saving_bytes",
            "value": receiver_payload_saving_bytes,
            "state_count": receiver_payload_saving_state_count,
            "passes": receiver_payload_saving_bytes > 0.0,
            "interpretation": "receiver status suppresses redundant evidence-record payload in some episodes",
        },
        {
            "metric": "structural_check_pass_count",
            "value": sum(bool(row["passes"]) for row in verifier_rows),
            "state_count": len(verifier_rows),
            "passes": all(bool(row["passes"]) for row in verifier_rows),
            "interpretation": "declared validation, conflict, sufficiency, and authorization checks pass",
        },
    ]


def finite_number(value: float) -> float | None:
    return value if isfinite(value) else None
