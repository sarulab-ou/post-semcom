"""Generate and validate portable post-semantic episode reporting assets."""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from . import availability_model


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPOSITORY_ROOT / "schemas" / "post_semantic_episode.schema.json"
VALID_EXAMPLE_PATH = REPOSITORY_ROOT / "examples" / "post_semantic_episode.example.json"
INVALID_EXAMPLE_PATH = REPOSITORY_ROOT / "examples" / "post_semantic_episode.invalid.json"
CHECKLIST_CSV_PATH = REPOSITORY_ROOT / "generated" / "reporting_checklist.csv"
CHECKLIST_JSON_PATH = REPOSITORY_ROOT / "generated" / "reporting_checklist.json"
SCHEMA_VERSION = "1.0.0"
SOURCE_STATE_INDEX = "3143"

CHECKLIST = (
    {
        "layer": "Evidence",
        "required_fields": (
            "synchronized sender/receiver records; ground truth; contract item; "
            "support/conflict relation; source; measurement time; age at decision; "
            "calibration; provenance; proposal binding"
        ),
        "what_can_be_evaluated": (
            "validity, evidence sufficiency, selective risk, and false-safe behavior"
        ),
    },
    {
        "layer": "Delivery",
        "required_fields": (
            "forward/reverse message; message role; bytes; loss; delay; "
            "retransmission and packetization when available"
        ),
        "what_can_be_evaluated": (
            "feedback function, communication cost, and comparison fairness"
        ),
    },
    {
        "layer": "Finalization",
        "required_fields": (
            "finalizer; assembly location; credential state; handoff; finalization outcome"
        ),
        "what_can_be_evaluated": "authority feasibility and completion failure",
    },
    {
        "layer": "Runtime",
        "required_fields": (
            "plant state; runtime-gate outcome; fallback; actuation; physical result"
        ),
        "what_can_be_evaluated": "closed-loop safety beyond pre-action verification",
    },
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _source_row() -> dict[str, str]:
    # Derive the portable example from the evaluator rather than a previously
    # generated CSV. This keeps clean-clone generation acyclic; the emitted CSV
    # is later checked against the same evaluator rows byte-for-byte.
    for source in availability_model.episode_rows():
        row = {key: str(value) for key, value in source.items()}
        if row["state_index"] == SOURCE_STATE_INDEX and row["finalizer"] == "sender" and row["interaction"] == "feedback":
            assert row["outcome"] == "accept"
            assert row["reverse_message_type"] == "evidence_record"
            assert row["reverse_delivered"] == "True"
            return row
    raise AssertionError(f"source episode {SOURCE_STATE_INDEX} not found")


def valid_example() -> dict[str, Any]:
    """Map one current synthetic ledger row into the portable schema."""
    row = _source_row()
    latency = float(row["action_ready_latency_ms"])
    return {
        "schema_version": SCHEMA_VERSION,
        "record_type": "post_semantic_episode",
        "synthetic_or_measured": "SYNTHETIC",
        "proposal": {
            "proposal_id": f"synthetic-proposal-{SOURCE_STATE_INDEX}",
            "version": "1",
            "action": "proceed_through_aisle",
            "target": "warehouse_aisle_A",
            "validity_window": {
                "start": "2026-08-16T00:00:00Z",
                "end": "2026-08-16T00:00:00.033Z",
            },
            "evidence_contract_id": "visual-clearance+radio-no-motion-v1",
        },
        "ground_truth": {
            "availability": "RECORDED",
            "reference": f"synthetic://state/{SOURCE_STATE_INDEX}/truth",
            "labels": {
                "corridor_is_clear": row["clearance_true"] == "True",
                "no_moving_obstacle": row["no_motion_true"] == "True",
            },
        },
        "evidence_records": [
            {
                "record_id": f"receiver-visual-{SOURCE_STATE_INDEX}",
                "contract_item": "visual_clearance",
                "claim": "corridor_is_clear",
                "relation": "SUPPORTS",
                "modality": "VISUAL",
                "source": "receiver_camera",
                "measurement_time": "2026-08-15T23:59:59.980Z",
                "age_at_decision": 20.0 + latency,
                "validity": "VALID",
                "calibration_reference": "synthetic://calibration/receiver_camera",
                "provenance_reference": "synthetic://state/3143/receiver_visual",
                "proposal_binding": f"synthetic-proposal-{SOURCE_STATE_INDEX}:1",
            },
            {
                "record_id": f"receiver-radio-{SOURCE_STATE_INDEX}",
                "contract_item": "radio_no_motion",
                "claim": "no_moving_obstacle",
                "relation": "SUPPORTS",
                "modality": "RADIO",
                "source": "receiver_radio",
                "measurement_time": "2026-08-15T23:59:59.985Z",
                "age_at_decision": 15.0 + latency,
                "validity": "VALID",
                "calibration_reference": "synthetic://calibration/receiver_radio",
                "provenance_reference": "synthetic://state/3143/receiver_radio",
                "proposal_binding": f"synthetic-proposal-{SOURCE_STATE_INDEX}:1",
            },
        ],
        "messages": [
            {
                "direction": "SENDER_TO_RECEIVER",
                "role": "PROPOSAL",
                "bytes": 0,
                "send_time": 0.0,
                "receive_time": 0.5,
                "delivery_outcome": "DELIVERED",
                "retransmission_count": None,
                "packet_count": None,
            },
            {
                "direction": "RECEIVER_TO_SENDER",
                "role": "EVIDENCE_TRANSFER",
                "bytes": int(row["reverse_bytes"]),
                "send_time": 0.5,
                "receive_time": latency - 10.5,
                "delivery_outcome": "DELIVERED",
                "retransmission_count": None,
                "packet_count": None,
            },
            {
                "direction": "SENDER_TO_RECEIVER",
                "role": "FINALIZATION",
                "bytes": int(row["forward_bytes"]),
                "send_time": latency - 10.5,
                "receive_time": latency - 10.0,
                "delivery_outcome": "DELIVERED",
                "retransmission_count": None,
                "packet_count": None,
            },
        ],
        "decision": {
            "evidence_outcome": "ACCEPT",
            "failure_reason": None,
            "assembly_location": row["assembly_location"].upper(),
            "finalizer": row["finalizer"].upper(),
            "credential_state": "NOT_RECORDED",
            "handoff_outcome": "NOT_REQUIRED",
            "finalization_outcome": "FINALIZED",
            "deadline_met": row["deadline_miss"] == "False",
        },
        "runtime": {
            "gate_outcome": "NOT_RECORDED",
            "plant_state_reference": None,
            "fallback": None,
            "actuation": None,
            "action_outcome": None,
        },
        "requirements": {
            "minimum_coverage": 0.60,
            "maximum_selective_risk": 0.0075,
            "freshness_limit": 35.0,
            "deadline": 33.0,
            "finalization_authority": "SENDER",
        },
    }


def invalid_example() -> dict[str, Any]:
    """Return a deliberate schema violation used by the regression test."""
    value = copy.deepcopy(valid_example())
    value["evidence_records"][0]["relation"] = "UNKNOWN"
    return value


def generate() -> tuple[Path, ...]:
    """Write deterministic examples and machine-readable checklist tables."""
    _write_json(VALID_EXAMPLE_PATH, valid_example())
    _write_json(INVALID_EXAMPLE_PATH, invalid_example())
    _write_json(CHECKLIST_JSON_PATH, list(CHECKLIST))
    CHECKLIST_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CHECKLIST_CSV_PATH.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(CHECKLIST[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(CHECKLIST)
    return VALID_EXAMPLE_PATH, INVALID_EXAMPLE_PATH, CHECKLIST_CSV_PATH, CHECKLIST_JSON_PATH


def validate_assets() -> None:
    """Validate the schema, require the valid sample, and reject the invalid sample."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    valid = json.loads(VALID_EXAMPLE_PATH.read_text(encoding="utf-8"))
    invalid = json.loads(INVALID_EXAMPLE_PATH.read_text(encoding="utf-8"))
    validator.validate(valid)
    errors = sorted(validator.iter_errors(invalid), key=lambda item: tuple(item.path))
    assert errors, "invalid reporting example unexpectedly passed schema validation"
    assert any("UNKNOWN" in error.message for error in errors), errors
