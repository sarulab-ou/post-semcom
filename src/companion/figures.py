"""Generate deterministic figures for the current reproducible artifact."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Rectangle

from . import availability_model


OUTPUT_DIR = Path(__file__).resolve().parents[2] / "fig"


def configure_matplotlib() -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["DejaVu Serif"], "font.size": 8.0,
        "axes.titlesize": 8.4, "axes.labelsize": 8.0, "xtick.labelsize": 7.0,
        "ytick.labelsize": 7.0, "legend.fontsize": 7.0, "pdf.fonttype": 42,
        "ps.fonttype": 42, "savefig.dpi": 300,
    })


def save_figure(
    figure: plt.Figure,
    stem: str,
    output_dir: Path = OUTPUT_DIR,
    suffixes: Sequence[str] = ("pdf", "png", "eps"),
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for suffix in suffixes:
        target = output_dir / f"{stem}.{suffix}"
        metadata: dict[str, object] = {"Creator": "post-semcom deterministic figure generator"}
        if suffix == "pdf":
            fixed_time = datetime(2000, 1, 1, tzinfo=timezone.utc)
            metadata.update({"CreationDate": fixed_time, "ModDate": fixed_time})
        figure.savefig(target, bbox_inches="tight", pad_inches=0.03, metadata=metadata)
        if suffix == "eps":
            source = target.read_text(encoding="latin-1")
            source = re.sub(r"^%%CreationDate:.*$", "%%CreationDate: 2000-01-01T00:00:00Z",
                            source, flags=re.MULTILINE)
            target.write_bytes(source.replace("\r\n", "\n").encode("latin-1"))
    plt.close(figure)


def _cell_edges(values: Sequence[float]) -> np.ndarray:
    points = np.asarray(values, dtype=float)
    midpoints = 0.5 * (points[:-1] + points[1:])
    return np.concatenate((
        [points[0] - 0.5 * (points[1] - points[0])],
        midpoints,
        [points[-1] + 0.5 * (points[-1] - points[-2])],
    ))


def _box(axis: plt.Axes, xy: tuple[float, float], wh: tuple[float, float], text: str,
         color: str, size: float = 8.0) -> None:
    axis.add_patch(FancyBboxPatch(
        xy, *wh, boxstyle="round,pad=0.012,rounding_size=0.02",
        facecolor=color, edgecolor="#404040", linewidth=0.9,
    ))
    axis.text(xy[0] + wh[0] / 2, xy[1] + wh[1] / 2, text,
              ha="center", va="center", fontsize=size, linespacing=1.22)


def _arrow(axis: plt.Axes, start: tuple[float, float], end: tuple[float, float]) -> None:
    axis.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=9,
                                  color="#404040", linewidth=0.9))


def make_finalization_interaction_matrix(output_dir: Path = OUTPUT_DIR) -> None:
    figure, axis = plt.subplots(figsize=(7.15, 3.7))
    axis.set_xlim(-0.92, 2.03); axis.set_ylim(-0.93, 2.55); axis.axis("off")
    colors = [["#DCE6F1", "#E2F0D9"], ["#FCE4D6", "#FFF2CC"]]
    labels = [[
        "Sender sends sufficient evidence\nand finalizes.",
        "Receiver transfers missing evidence;\nSender assembles and finalizes.",
    ], [
        "Sender sends all available evidence;\nReceiver combines it\nwith local records.",
        "Receiver coordinates delivery;\nSender sends only missing records;\nReceiver finalizes.",
    ]]
    for row, row_label in enumerate(("Sender finalizes", "Receiver finalizes")):
        y = 1 - row
        for col in range(2):
            axis.add_patch(Rectangle((col + 0.02, y + 0.02), 0.96, 0.96,
                                     facecolor=colors[row][col], edgecolor="#404040", linewidth=0.9))
            axis.text(col + 0.5, y + 0.50, labels[row][col], ha="center", va="center",
                      fontsize=6.45, linespacing=1.23)
        axis.text(-0.05, y + 0.5, row_label, ha="right", va="center",
                  fontweight="bold", fontsize=7.2)
    axis.text(1.0, 2.45, "Is receiver information used before positive-action finalization?",
              ha="center", fontsize=8.1, fontweight="bold")
    axis.text(0.5, 2.17, "One-way", ha="center", fontweight="bold")
    axis.text(1.5, 2.17, "Feedback", ha="center", fontweight="bold")
    axis.text(-0.76, 1.0, "Who may finalize the positive action?", rotation=90,
              ha="center", va="center", fontsize=8.0, fontweight="bold")
    axis.text(1.0, -0.12, "Finalization authority $\\ne$ evidence location.",
              ha="center", fontsize=6.25, fontweight="bold")
    axis.text(1.0, -0.34, "Valid conflict $\\rightarrow$ Reject.",
              ha="center", fontsize=6.05)
    axis.text(1.0, -0.56, "Insufficient valid evidence $\\rightarrow$ Abstain.",
              ha="center", fontsize=6.05)
    axis.text(1.0, -0.78, "Runtime safety remains downstream.",
              ha="center", fontsize=6.0, fontstyle="italic")
    save_figure(figure, "fig_finalization_interaction_matrix", output_dir)


def make_framework_architecture(output_dir: Path = OUTPUT_DIR) -> None:
    """Show the canonical framework boundary and the two feedback functions."""
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 3.55),
                               gridspec_kw={"width_ratios": (1.38, 0.92)})
    left, right = axes
    for axis in axes:
        axis.set_xlim(0, 1); axis.set_ylim(0, 1); axis.axis("off")

    left.text(0.0, 0.98, "(a) Post-semantic framework", fontsize=8.2,
              fontweight="bold", va="top")
    _box(left, (0.01, 0.78), (0.29, 0.12),
         "Semantic Proposal\naction candidate + binding",
         "#D9EAF7", 5.6)
    _box(left, (0.01, 0.55), (0.29, 0.17),
         "Evidence Requirements\n(Evidence Contract)\nclaims + sources/modalities\nfreshness + provenance\nuncertainty + deadline",
         "#D9EAF7", 5.25)
    _box(left, (0.01, 0.30), (0.29, 0.18),
         "Available Evidence Records\nclaim + support/conflict\nsource + modality + time\nprovenance + proposal binding",
         "#E8EEF5", 5.25)
    _box(left, (0.42, 0.56), (0.26, 0.20),
         "Verifier at decision time\ncommon validation path\nAccept / Reject / Abstain",
         "#FFF2CC", 5.6)
    _arrow(left, (0.30, 0.84), (0.42, 0.71))
    _arrow(left, (0.30, 0.635), (0.42, 0.66))
    _arrow(left, (0.30, 0.39), (0.42, 0.61))
    left.text(0.35, 0.79, "binding", ha="center", fontsize=4.7,
              color="#555555")

    _box(left, (0.73, 0.74), (0.25, 0.14),
         "Resolved negative outcome\nadmissible conflict\nReject",
         "#F4CCCC", 5.25)
    _arrow(left, (0.68, 0.70), (0.73, 0.80))

    _box(left, (0.73, 0.47), (0.25, 0.14),
         "Authorized Finalization\nVerifier Accept +\nAuthorization Policy",
         "#FCE4D6", 5.25)
    _arrow(left, (0.68, 0.63), (0.73, 0.55))
    _box(left, (0.39, 0.14), (0.28, 0.10),
         "Authorization Policy\nauthorized finalizer set\n"
         "unavailable -> Authority gap\n"
         "handoff / Abstain",
         "#E8EEF5", 4.35)
    _arrow(left, (0.67, 0.19), (0.73, 0.50))

    left.add_patch(FancyBboxPatch(
        (0.37, 0.28), 0.30, 0.13,
        boxstyle="round,pad=0.010,rounding_size=0.015",
        facecolor="#FCE4D6", edgecolor="#C65911", linewidth=0.9,
    ))
    left.text(0.52, 0.345,
              "Evidence gap -> Abstain\nmissing / invalid / stale / incomplete\n"
              "or unavailable at the finalizer",
              ha="center", va="center", fontsize=4.65, color="#8B2500")
    _arrow(left, (0.55, 0.56), (0.53, 0.41))
    loop = FancyArrowPatch(
        (0.39, 0.29), (0.29, 0.35), arrowstyle="-|>", mutation_scale=8,
        connectionstyle="arc3,rad=-0.28", color="#E07018", linewidth=1.1,
        linestyle="--",
    )
    left.add_patch(loop)
    left.text(0.19, 0.18,
              "request / transfer / coordinate / re-evaluate\n"
              "the loop may end in Accept, Reject, or Abstain",
              ha="center", va="center", fontsize=4.35, color="#A34800")

    _box(left, (0.72, 0.01), (0.26, 0.105),
         "Runtime Gate (downstream)\nACT / STOP   [not evaluated]",
         "#E2F0D9", 5.05)
    _arrow(left, (0.855, 0.47), (0.85, 0.115))
    left.plot((0.69, 0.995), (0.125, 0.125), color="#777777", linewidth=0.8,
              linestyle=":")
    left.text(0.695, 0.132, "evaluation boundary", fontsize=4.15,
              va="bottom", color="#666666")

    right.text(0.0, 0.98, "(b) Two functions of feedback", fontsize=8.2,
               fontweight="bold", va="top")
    right.text(0.50, 0.855, "Transfer: expand evidence reachability",
               ha="center", fontsize=6.25, fontweight="bold", color="#9E480E")
    _box(right, (0.03, 0.64), (0.29, 0.14),
         "Receiver transfers\nmissing admissible\nrecord", "#E8EEF5", 5.0)
    _box(right, (0.68, 0.64), (0.29, 0.14),
         "Finalizer re-evaluates\nthe evidence set", "#E2F0D9", 5.35)
    right.add_patch(FancyArrowPatch(
        (0.32, 0.71), (0.68, 0.71), arrowstyle="-|>", mutation_scale=9,
        color="#E07018", linewidth=1.1,
    ))
    right.text(0.50, 0.735, "evidence record", ha="center", fontsize=5.0,
               color="#A34800")

    right.text(0.50, 0.49, "Coordination: suppress redundant payload",
               ha="center", fontsize=6.25, fontweight="bold", color="#9E480E")
    _box(right, (0.03, 0.27), (0.29, 0.14), "Receiver-held\nrecord IDs", "#E8EEF5", 5.6)
    _box(right, (0.68, 0.27), (0.29, 0.14), "Sender forwards\nonly missing records", "#E2F0D9", 5.4)
    right.add_patch(FancyArrowPatch(
        (0.32, 0.36), (0.68, 0.36), arrowstyle="-|>", mutation_scale=9,
        color="#E07018", linewidth=1.1,
    ))
    right.add_patch(FancyArrowPatch(
        (0.68, 0.30), (0.32, 0.30), arrowstyle="-|>", mutation_scale=8,
        color="#5B9BD5", linewidth=0.9,
    ))
    right.text(0.50, 0.385, "evidence status", ha="center", fontsize=5.0,
               color="#A34800")
    right.text(0.50, 0.255, "selected records", ha="center", fontsize=5.0,
               color="#1F4E79")
    right.add_patch(FancyBboxPatch(
        (0.07, 0.04), 0.86, 0.12, boxstyle="round,pad=0.010,rounding_size=0.014",
        facecolor="#F2F2F2", edgecolor="#777777", linewidth=0.7,
    ))
    right.text(0.50, 0.10,
               "Status is not evidence. Reverse loss, latency,\n"
               "ageing, and expiry can offset either benefit.",
               ha="center", va="center", fontsize=5.35, linespacing=1.15)
    figure.subplots_adjust(left=0.012, right=0.995, bottom=0.01, top=0.99, wspace=0.07)
    save_figure(figure, "fig_framework_architecture", output_dir)


def make_requirement_regime_map(output_dir: Path = OUTPUT_DIR) -> None:
    """Plot the declared three-region application rule without interpolation."""
    rows = availability_model.requirement_regime_rows()
    x_values = availability_model.REQUIREMENT_REGIME_MESSAGE_LATENCY_MS_GRID
    y_values = availability_model.REQUIREMENT_REGIME_DECISION_DEADLINE_MS_GRID
    codes = {"infeasible": 0, "one_way": 1, "feedback": 2}
    colors = matplotlib.colors.ListedColormap(["#C9C9C9", "#4C78A8", "#F58518"])
    norm = matplotlib.colors.BoundaryNorm((-0.5, 0.5, 1.5, 2.5), colors.N)
    x_edges, y_edges = _cell_edges(x_values), _cell_edges(y_values)
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 2.95), sharex=True, sharey=True)
    for axis, finalizer in zip(axes, availability_model.Finalizer):
        selected = [row for row in rows if row["finalizer"] == finalizer.value]
        lookup = {
            (float(row["decision_deadline_ms"]),
             float(row["fixed_per_logical_message_latency_ms"])): row
            for row in selected
        }
        grid = np.zeros((len(y_values), len(x_values)))
        for i, deadline in enumerate(y_values):
            for j, delta in enumerate(x_values):
                grid[i, j] = codes[str(lookup[(deadline, delta)]["selected_interaction"])]
        # Rasterize the discrete cell field inside vector outputs.  Keeping
        # thousands of adjacent vector rectangles can create false white seams
        # in PDF viewers even when the cells share exact boundaries.
        axis.pcolormesh(
            x_edges, y_edges, grid, shading="flat", cmap=colors, norm=norm,
            edgecolors="none", antialiased=False,
            rasterized=True,
        )
        axis.scatter(0.5, 33.0, marker="*", s=92, color="#FFD54F",
                     edgecolor="black", linewidth=0.7, zorder=5)
        axis.set_xlim(0.0, 8.0); axis.set_ylim(10.0, 50.0)
        axis.set_xticks((0, 2, 4, 6, 8)); axis.set_yticks((10, 20, 30, 40, 50))
        axis.set_xlabel(r"Fixed latency per logical message $\delta$ (ms)")
        effect = (
            "Feedback effect: expands evidence reachability"
            if finalizer is availability_model.Finalizer.SENDER
            else "Feedback effect: suppresses redundant payload"
        )
        axis.set_title(f"{finalizer.value.capitalize()} finalization fixed\n{effect}")
    axes[0].set_ylabel("Decision deadline $D$ (ms)")
    figure.legend(handles=[
        Patch(facecolor="#4C78A8", label="One-way"),
        Patch(facecolor="#F58518", label="Feedback"),
        Patch(facecolor="#C9C9C9", label="Infeasible"),
        plt.Line2D([0], [0], marker="*", color="none", markerfacecolor="#FFD54F",
                   markeredgecolor="black", markersize=8, label="baseline $(0.5,33)$"),
    ], loc="lower center", ncol=4, frameon=False)
    figure.subplots_adjust(bottom=0.25, top=0.88, wspace=0.10)
    save_figure(
        figure,
        "fig_requirement_regime_map",
        output_dir,
        suffixes=("pdf",),
    )


def make_execution_gates(output_dir: Path = OUTPUT_DIR) -> None:
    figure, axis = plt.subplots(figsize=(7.15, 2.65))
    axis.set_xlim(0, 1); axis.set_ylim(0, 1); axis.axis("off")
    boxes = (
        (0.01, 0.12, "Proposal\nproducer", "#D9EAF7"),
        (0.16, 0.17, "Evidence layer\ntyped records\n+ validation", "#E8E8E8"),
        (0.35, 0.19, "Evidence sufficient?\naccept / reject / abstain", "#FFF2CC"),
        (0.56, 0.17, "Permitted finalizer?\nSender / Receiver", "#FCE4D6"),
        (0.75, 0.14, "Runtime\nsafe now?", "#E2F0D9"),
        (0.92, 0.07, "Act", "#DDEBF7"),
    )
    y, h = 0.57, 0.23
    for x, width, label, color in boxes:
        _box(axis, (x, y), (width, h), label, color, 6.3)
    for left, right in zip(boxes[:-1], boxes[1:]):
        _arrow(axis, (left[0] + left[1] + 0.004, y + h / 2), (right[0] - 0.004, y + h / 2))
    inputs = (
        (0.445, 0.17, "evidence status or\nevidence record"),
        (0.645, 0.16, "finalization\nauthority state"),
        (0.82, 0.14, "current state\nbackup + stop"),
    )
    for x, width, label in inputs:
        _box(axis, (x - width / 2, 0.20), (width, 0.16), label, "#F4F4F4", 5.7)
        _arrow(axis, (x, 0.36), (x, y - 0.01))
    _box(axis, (0.12, 0.018), (0.79, 0.12),
         "Pre-action processing $T_p=10$ ms: record validation + assembly + positive finalization\n"
         "Completion is tested against $D=33$ ms; the runtime gate remains separate",
         "#F2F2F2", 5.1)
    save_figure(figure, "fig_execution_gates", output_dir)


def make_primary_regime_map(output_dir: Path = OUTPUT_DIR) -> None:
    """Appendix sensitivity: traffic effect, not a claimed general boundary."""
    rows = availability_model.primary_regime_rows()
    x_values = availability_model.RECEIVER_AVAILABILITY_GRID
    y_values = availability_model.VISUAL_SIZE_KIB_GRID
    values = [float(row["feedback_evidence_traffic_saving_percent"]) for row in rows]
    limit = max(abs(min(values)), abs(max(values)), 1.0)
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 2.95), sharex=True, sharey=True)
    image = None
    for axis, finalizer in zip(axes, availability_model.Finalizer):
        grid = np.zeros((len(y_values), len(x_values)))
        for i, visual_kib in enumerate(y_values):
            for j, receiver_q in enumerate(x_values):
                row = next(item for item in rows if item["finalizer"] == finalizer.value
                           and item["visual_record_kib"] == visual_kib
                           and item["receiver_evidence_availability"] == receiver_q)
                grid[i, j] = float(row["feedback_evidence_traffic_saving_percent"])
        image = axis.imshow(grid, origin="lower", aspect="auto", interpolation="nearest",
                            cmap="RdBu", vmin=-limit, vmax=limit)
        axis.scatter(x_values.index(0.90), y_values.index(10), marker="*", s=105,
                     color="#FFD700", edgecolor="black", linewidth=0.7, zorder=5)
        axis.set_xticks(range(len(x_values)), [f"{value:.2f}" for value in x_values], rotation=30)
        axis.set_yticks(range(len(y_values)), [f"{value:g}" for value in y_values])
        axis.set_xlabel("Receiver valid-record availability $q_R$")
        axis.set_title(f"{finalizer.value.capitalize()} finalization")
    axes[0].set_ylabel("Visual record size $B_V$ (KiB)")
    if image is not None:
        colorbar = figure.colorbar(image, ax=axes, fraction=0.028, pad=0.025)
        colorbar.set_label("Feedback evidence-traffic saving (%)", fontsize=6.7)
    figure.suptitle("Sensitivity of evidence traffic to receiver availability and record size", y=0.99, fontsize=8.2)
    figure.subplots_adjust(bottom=0.19, top=0.87, wspace=0.10, right=0.87)
    save_figure(figure, "fig_primary_regime_map", output_dir)


def make_deadline_latency_regime_map(output_dir: Path = OUTPUT_DIR) -> None:
    rows = availability_model.deadline_latency_regime_rows()
    x_values = availability_model.MESSAGE_LATENCY_MS_GRID
    y_values = availability_model.DECISION_DEADLINE_MS_GRID
    differences = [float(row["feedback_minus_one_way_timely_coverage_pp"]) for row in rows]
    limit = max(abs(min(differences)), abs(max(differences)), 1.0)
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 3.25), sharex=True, sharey=True)
    image = None
    x_edges, y_edges = _cell_edges(x_values), _cell_edges(y_values)
    baseline = {(row["finalizer"], row["interaction"]): row
                for row in availability_model.matched_communication_case_rows()}
    for axis, finalizer in zip(axes, availability_model.Finalizer):
        grid = np.zeros((len(y_values), len(x_values)))
        miss = np.zeros_like(grid)
        both_zero = np.zeros_like(grid, dtype=bool)
        for i, deadline in enumerate(y_values):
            for j, delta in enumerate(x_values):
                row = next(item for item in rows if item["finalizer"] == finalizer.value
                           and item["decision_deadline_ms"] == deadline
                           and item["fixed_per_message_latency_ms"] == delta)
                grid[i, j] = float(row["feedback_minus_one_way_timely_coverage_pp"])
                miss[i, j] = 100.0 * float(row["feedback_deadline_caused_abstention_probability"])
                both_zero[i, j] = bool(row["both_zero_timely_coverage"])
        image = axis.pcolormesh(x_edges, y_edges, grid, shading="flat", cmap="RdBu",
                                vmin=-limit, vmax=limit)
        for i, j in zip(*np.where(both_zero)):
            axis.add_patch(Rectangle((x_edges[j], y_edges[i]),
                                     x_edges[j + 1] - x_edges[j],
                                     y_edges[i + 1] - y_edges[i],
                                     fill=False, hatch="////", edgecolor="#666666", linewidth=0.0))
        if float(grid.min()) < 0.0 < float(grid.max()):
            axis.contour(x_values, y_values, grid, levels=[0.0], colors="black", linewidths=0.9)
        levels = [level for level in (25, 50)
                  if float(miss.min()) < level < float(miss.max())]
        if levels:
            axis.contour(x_values, y_values, miss, levels=levels,
                         colors="#555555", linestyles="--", linewidths=0.65)
        axis.scatter(0.5, 33.0, marker="*", s=105, color="#FFD700",
                     edgecolor="black", linewidth=0.7, zorder=6)
        one = baseline[(finalizer.value, "one_way")]
        feedback = baseline[(finalizer.value, "feedback")]
        one_bytes = float(one["mean_safe_world_evidence_traffic_bytes"])
        saving = 100.0 * (one_bytes - float(feedback["mean_safe_world_evidence_traffic_bytes"])) / one_bytes
        axis.set_title(f"{finalizer.value.capitalize()} finalization\nbaseline traffic saving: {saving:.1f}%")
        axis.set_xlabel("Fixed per-message latency $\\delta$ (ms)")
        axis.set_xlim(x_edges[0], x_edges[-1]); axis.set_ylim(y_edges[0], y_edges[-1])
    axes[0].set_ylabel("Decision deadline $D$ (ms)")
    if image is not None:
        colorbar = figure.colorbar(image, ax=axes, fraction=0.028, pad=0.025)
        colorbar.set_label("Feedback minus one-way timely coverage (percentage points)", fontsize=6.2)
    figure.legend(handles=[
        Patch(facecolor="white", edgecolor="#666666", hatch="////",
              label="both timely coverages are zero"),
        plt.Line2D([0], [0], color="#555555", linestyle="--", linewidth=0.8,
                   label="Feedback deadline miss: 25% or 50%"),
    ],
                  loc="lower center", frameon=False)
    figure.suptitle("When is feedback worth its extra message?", y=0.995, fontsize=8.2)
    figure.subplots_adjust(bottom=0.22, top=0.82, wspace=0.10, right=0.87)
    save_figure(figure, "fig_deadline_latency_regime_map", output_dir)


def make_pattern_sensitivity_curves(output_dir: Path = OUTPUT_DIR) -> None:
    rows = availability_model.pattern_sensitivity_curve_rows()
    panels = (
        ("evidence_availability", "Evidence availability $q$", "timely_safe_world_coverage", "Timely coverage"),
        ("evidence_relation_error", "Conditional evidence-relation error", "selective_risk", "Selective risk"),
        ("fixed_per_message_latency_ms", "Fixed latency $\\delta$ (ms)", "timely_safe_world_coverage", "Timely coverage"),
        ("decision_deadline_ms", "Decision deadline $D$ (ms)", "timely_safe_world_coverage", "Timely coverage"),
        ("visual_initial_age_ms", "Visual initial age $A_V(0)$ (ms)", "timely_safe_world_coverage", "Timely coverage"),
        ("record_ttl_ms", "Evidence TTL (ms)", "timely_safe_world_coverage", "Timely coverage"),
    )
    styles = {
        ("sender", "one_way"): ("#1f77b4", "-", "S1"),
        ("receiver", "one_way"): ("#2ca02c", "-", "R1"),
        ("sender", "feedback"): ("#d95f02", "--", "SF"),
        ("receiver", "feedback"): ("#7b3294", "--", "RF"),
    }
    figure, axes = plt.subplots(3, 2, figsize=(7.15, 7.2))
    for axis, (parameter, xlabel, metric, ylabel) in zip(axes.flat, panels):
        values = availability_model.PATTERN_CURVE_GRIDS[parameter]
        for key, (color, linestyle, label) in styles.items():
            selected = [row for row in rows if row["parameter"] == parameter
                        and row["finalizer"] == key[0] and row["interaction"] == key[1]]
            selected.sort(key=lambda row: float(row["value"]))
            y = [100.0 * float(row[metric]) for row in selected]
            axis.plot(values, y, color=color, linestyle=linestyle, linewidth=1.4,
                      marker="o", markersize=2.4, label=label)
        axis.axvline({
            "evidence_availability": 0.90, "evidence_relation_error": 0.10,
            "fixed_per_message_latency_ms": 0.5, "decision_deadline_ms": 33.0,
            "visual_initial_age_ms": 20.0, "record_ttl_ms": 35.0,
        }[parameter], color="#777777", linewidth=0.7, linestyle=":")
        axis.set_xlabel(xlabel); axis.set_ylabel(f"{ylabel} (%)")
        if parameter == "evidence_relation_error":
            axis.set_xlim(0.0, 0.20)
        axis.grid(True, color="#dddddd", linewidth=0.45)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    figure.suptitle("Pattern-specific sensitivity under one declared accounting model", fontsize=8.5)
    figure.subplots_adjust(bottom=0.09, top=0.94, hspace=0.42, wspace=0.28)
    save_figure(figure, "fig_pattern_sensitivity_curves", output_dir)


def make_interaction_selection_map(output_dir: Path = OUTPUT_DIR) -> None:
    rows = availability_model.interaction_selection_map_rows()
    x_values = availability_model.INTERACTION_SELECTION_LATENCY_GRID
    y_values = availability_model.RECEIVER_AVAILABILITY_GRID
    colors = matplotlib.colors.ListedColormap(["#4C78A8", "#F58518"])
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 3.0), sharex=True, sharey=True)
    x_edges, y_edges = _cell_edges(x_values), _cell_edges(y_values)
    for axis, finalizer in zip(axes, availability_model.Finalizer):
        grid = np.zeros((len(y_values), len(x_values)))
        difference = np.zeros_like(grid)
        for i, receiver_q in enumerate(y_values):
            for j, delta in enumerate(x_values):
                row = next(item for item in rows if item["finalizer"] == finalizer.value
                           and item["receiver_evidence_availability"] == receiver_q
                           and item["fixed_per_message_latency_ms"] == delta)
                grid[i, j] = 1 if row["selected_interaction"] == "feedback" else 0
                difference[i, j] = float(row["feedback_minus_one_way_coverage_pp"])
        axis.pcolormesh(x_edges, y_edges, grid, shading="flat",
                        cmap=colors, vmin=-0.5, vmax=1.5)
        if float(difference.min()) < 0.0 <= float(difference.max()):
            axis.contour(x_values, y_values, difference, levels=[0.0], colors="white",
                         linewidths=1.0)
        axis.scatter(0.5, 0.90, marker="*", s=105, color="#FFD700",
                     edgecolor="black", linewidth=0.7, zorder=6)
        axis.set_title(f"{finalizer.value.capitalize()} authority")
        axis.set_xlabel("Fixed per-message latency $\\delta$ (ms)")
    axes[0].set_ylabel("Receiver evidence availability $q_R$")
    figure.legend(handles=[
        Patch(facecolor="#4C78A8", label="One-way selected"),
        Patch(facecolor="#F58518", label="Feedback selected"),
        Patch(facecolor="white", edgecolor="#777777", label="white: zero coverage difference"),
    ], loc="lower center", ncol=3, frameon=False)
    figure.suptitle(
        "Interaction selected under changing evidence and latency conditions",
        fontsize=8.2,
    )
    figure.subplots_adjust(bottom=0.24, top=0.85, wspace=0.10)
    save_figure(figure, "fig_interaction_selection_map", output_dir)


def make_interaction_requirement_map(output_dir: Path = OUTPUT_DIR) -> None:
    rows = availability_model.interaction_requirement_rows()
    x_values = availability_model.COVERAGE_REQUIREMENT_GRID
    y_values = availability_model.SELECTIVE_RISK_CEILING_GRID
    colors = matplotlib.colors.ListedColormap(["#C9C9C9", "#4C78A8", "#F58518"])
    codes = {"infeasible": 0, "one_way": 1, "feedback": 2}
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 3.05), sharex=True, sharey=True)
    for axis, finalizer in zip(axes, availability_model.Finalizer):
        grid = np.zeros((len(y_values), len(x_values)))
        for i, risk_ceiling in enumerate(y_values):
            for j, coverage_floor in enumerate(x_values):
                row = next(item for item in rows if item["finalizer"] == finalizer.value
                           and item["coverage_floor"] == coverage_floor
                           and item["selective_risk_ceiling"] == risk_ceiling)
                grid[i, j] = codes[str(row["selected_interaction"])]
        axis.imshow(grid, origin="lower", aspect="auto", interpolation="nearest",
                    cmap=colors, vmin=-0.5, vmax=2.5)
        axis.set_xticks(range(len(x_values)), [f"{100*value:.1f}" for value in x_values], rotation=30)
        axis.set_yticks(range(len(y_values)), [f"{100*value:.3f}" for value in y_values])
        axis.set_xlabel("Required unconditional coverage $C_{\\min}$ (%)")
        axis.set_title(f"{finalizer.value.capitalize()} finalization fixed")
    axes[0].set_ylabel("Allowed selective risk $R_{\\max}$ (%)")
    figure.legend(handles=[
        Patch(facecolor="#C9C9C9", label="infeasible"),
        Patch(facecolor="#4C78A8", label="One-way"),
        Patch(facecolor="#F58518", label="Feedback"),
    ], loc="lower center", ncol=3, frameon=False)
    figure.suptitle("Minimum-traffic interaction satisfying application requirements", fontsize=8.3)
    figure.subplots_adjust(bottom=0.25, top=0.84, wspace=0.10)
    save_figure(figure, "fig_interaction_requirement_map", output_dir)


def make_evidence_contract_comparison(output_dir: Path = OUTPUT_DIR) -> None:
    rows = [row for row in availability_model.evidence_contract_comparison_rows()
            if float(row["observation_correlation"]) == 0.25]
    paths = [path[0] for path in availability_model.EVIDENCE_PATHS]
    encodings = list(availability_model.EVIDENCE_PATH_ENCODINGS)
    specifications = (
        ("unconditional_coverage", 100.0, "Unconditional coverage (%)", "YlGnBu"),
        ("selective_risk", 100.0, "Selective risk (%)", "PuRd"),
        ("mean_record_cost_kib", 1.0, "Mean record cost (KiB)", "OrRd"),
    )
    figure, axes = plt.subplots(1, 3, figsize=(7.15, 2.85), sharey=True)
    for axis, (metric, scale, title, cmap) in zip(axes, specifications):
        grid = np.zeros((len(paths), len(encodings)))
        for i, path_id in enumerate(paths):
            for j, encoding in enumerate(encodings):
                row = next(item for item in rows if item["path_id"] == path_id
                           and item["record_encoding"] == encoding)
                grid[i, j] = scale * float(row[metric])
        image = axis.imshow(grid, aspect="auto", cmap=cmap)
        for i in range(len(paths)):
            for j in range(len(encodings)):
                digits = 3 if metric == "selective_risk" else 2
                axis.text(j, i, f"{grid[i,j]:.{digits}f}", ha="center", va="center", fontsize=5.8)
        axis.set_xticks(range(len(encodings)), [value.capitalize() for value in encodings])
        axis.set_yticks(range(len(paths)), [f"$\\pi_{index+1}$" for index in range(len(paths))])
        axis.set_title(title)
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.03)
    axes[0].set_ylabel("Evidence requirement")
    figure.suptitle(
        "Evidence-contract comparison at observation correlation $\\rho_E=0.25$",
        fontsize=8.3,
    )
    figure.subplots_adjust(bottom=0.18, top=0.82, wspace=0.34)
    save_figure(figure, "fig_evidence_contract_comparison", output_dir)


def make_global_uncertainty(output_dir: Path = OUTPUT_DIR) -> None:
    rows = availability_model.global_uncertainty_rows()
    summary = availability_model.global_uncertainty_summary_rows(rows)
    selection = availability_model.global_selection_summary_rows(
        availability_model.global_selection_rows(rows)
    )
    labels = [
        f"{str(row['finalizer'])[0].upper()}{'1' if row['interaction'] == 'one_way' else 'F'}"
        for row in summary
    ]
    figure, axes = plt.subplots(1, 3, figsize=(7.15, 2.75))
    specifications = (
        ("timely_safe_world_coverage", 100.0, "Timely coverage (%)"),
        ("mean_safe_world_evidence_traffic_kib", 1.0, "Evidence traffic (KiB)"),
    )
    for axis, (metric, scale, ylabel) in zip(axes, specifications):
        medians = np.array([scale * float(row[f"{metric}_p50"]) for row in summary])
        lower = np.array([scale * float(row[f"{metric}_p05"]) for row in summary])
        upper = np.array([scale * float(row[f"{metric}_p95"]) for row in summary])
        axis.errorbar(range(4), medians, yerr=(medians - lower, upper - medians),
                      fmt="o", color="#1f4e79", ecolor="#7ea6c9", capsize=4)
        axis.set_xticks(range(4), labels)
        axis.set_ylabel(ylabel)
        axis.grid(True, axis="y", color="#dddddd", linewidth=0.45)
    selection_axis = axes[2]
    finalizer_labels = [str(row["finalizer"])[0].upper() for row in selection]
    bottom = np.zeros(len(selection))
    for key, label, color in (
        ("one_way_selection_frequency", "One-way", "#4C78A8"),
        ("feedback_selection_frequency", "Feedback", "#F58518"),
        ("infeasible_frequency", "infeasible", "#C9C9C9"),
    ):
        values = 100.0 * np.array([float(row[key]) for row in selection])
        selection_axis.bar(range(len(selection)), values, bottom=bottom,
                           color=color, label=label, width=0.62)
        bottom += values
    for index, row in enumerate(selection):
        selection_axis.text(index, 102.0,
                            f"rev. {100*float(row['ordering_reversal_frequency']):.1f}%",
                            ha="center", va="bottom", fontsize=5.4)
    selection_axis.set_xticks(range(len(selection)), finalizer_labels)
    selection_axis.set_ylim(0, 112)
    selection_axis.set_ylabel("Fraction of uncertainty points (%)")
    selection_axis.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16),
                          ncol=3, fontsize=5.4, frameon=False)
    selection_axis.set_title("Requirement-based selection")
    figure.suptitle("Declared design uncertainty: metric intervals and selection stability", fontsize=8.3)
    figure.subplots_adjust(bottom=0.25, top=0.82, wspace=0.40)
    save_figure(figure, "fig_global_uncertainty", output_dir)


def make_local_sensitivity_heatmap(output_dir: Path = OUTPUT_DIR) -> None:
    rows = availability_model.local_sensitivity_rows()
    parameters = availability_model.LOCAL_PARAMETERS
    communication_cases = (
        ("sender", "one_way", "S1"), ("sender", "feedback", "SF"),
        ("receiver", "one_way", "R1"), ("receiver", "feedback", "RF"),
    )
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
    specifications = (
        ("coverage_change_pp_per_plus_10_percent", "Coverage response (percentage points)"),
        ("traffic_change_percent_per_plus_10_percent", "Traffic response (%)"),
    )
    figure, axes = plt.subplots(1, 2, figsize=(7.15, 5.35), sharey=True)
    for axis, (metric, title) in zip(axes, specifications):
        grid = np.zeros((len(parameters), len(communication_cases)))
        for i, parameter in enumerate(parameters):
            for j, (finalizer, interaction, _) in enumerate(communication_cases):
                row = next(item for item in rows if item["parameter"] == parameter
                           and item["finalizer"] == finalizer
                           and item["interaction"] == interaction)
                grid[i, j] = float(row[metric])
        limit = max(float(np.abs(grid).max()), 1.0)
        image = axis.imshow(grid, aspect="auto", cmap="RdBu_r", vmin=-limit, vmax=limit)
        for i in range(len(parameters)):
            for j in range(len(communication_cases)):
                value = grid[i, j]
                color = "white" if abs(value) > 0.55 * limit else "black"
                axis.text(j, i, f"{value:+.1f}", ha="center", va="center",
                          fontsize=4.7, color=color)
        axis.set_xticks(
            range(len(communication_cases)),
            [communication_case[2] for communication_case in communication_cases],
        )
        axis.set_yticks(range(len(parameters)), [labels[p] for p in parameters])
        axis.set_title(title)
        colorbar = figure.colorbar(image, ax=axis, fraction=0.046, pad=0.03)
        colorbar.ax.tick_params(labelsize=5.5)
    figure.suptitle(
        "Baseline-neighborhood finite differences, normalized to a +10% parameter change",
        fontsize=8.2,
    )
    figure.subplots_adjust(left=0.23, right=0.96, bottom=0.08, top=0.90, wspace=0.28)
    save_figure(figure, "fig_local_sensitivity_heatmap", output_dir)


def generate_all(output_dir: Path = OUTPUT_DIR) -> None:
    configure_matplotlib()
    # The public repository keeps only the numerical figure used by arxiv24.
    # Figures 1 and 2 are supplied publication assets and are not regenerated.
    make_requirement_regime_map(output_dir)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args(argv)
    generate_all(args.output_dir)
    print(f"generated fair-comparison figures in {args.output_dir}")


if __name__ == "__main__":
    main()
