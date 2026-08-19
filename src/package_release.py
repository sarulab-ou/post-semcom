"""Create a deterministic, commit-bound ZIP for the fixed artifact release."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
from typing import Optional, Sequence
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from verify_artifacts import DEFAULT_ARTIFACT_DIR, REPOSITORY_ROOT, verify_tracked_artifacts


FIXED_ZIP_TIME = (2026, 8, 18, 0, 0, 0)
ROOT_FILES = (
    ".dockerignore",
    ".gitattributes",
    ".gitignore",
    ".python-version",
    "Dockerfile",
    "RELEASE_VERSION",
    "README.md",
    "CITATION.cff",
    "LICENSES/README.md",
    "paper.pdf",
    "arxiv.tex",
    "reference.bib",
    "requirements.lock",
    "main/arxiv24.tex",
    "schemas/post_semantic_episode.schema.json",
    "examples/post_semantic_episode.example.json",
    "examples/post_semantic_episode.invalid.json",
    "docs/reporting_checklist.md",
    "generated/reporting_checklist.csv",
    "generated/reporting_checklist.json",
    "artifacts/README.md",
    "src/README.md",
    ".github/workflows/reproducibility.yml",
    ".github/workflows/release-artifact.yml",
)
SOURCE_FILES = (
    "src/generate_artifacts.py",
    "src/generate_figures.py",
    "src/run_validation.py",
    "src/package_release.py",
    "src/verify_artifacts.py",
    "src/companion/__init__.py",
    "src/companion/availability_model.py",
    "src/companion/artifacts.py",
    "src/companion/reporting_schema.py",
    "src/companion/figures.py",
    "src/companion/validation.py",
    "src/validate_reporting_schema.py",
)
GENERATED_FIGURE_STEMS = (
    "fig_requirement_regime_map",
)
FIGURE_FILES = (
    "fig1_test-crop.pdf",
    "fig2_test-crop.pdf",
    *(f"{stem}.{suffix}" for stem in GENERATED_FIGURE_STEMS
      for suffix in ("pdf",)),
)


def digest_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def release_files() -> list[Path]:
    paths = [REPOSITORY_ROOT / relative for relative in (*ROOT_FILES, *SOURCE_FILES)]
    paths.extend(sorted(DEFAULT_ARTIFACT_DIR.iterdir()))
    paths.extend(REPOSITORY_ROOT / "fig" / name for name in FIGURE_FILES)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"release inputs are missing: {missing}")
    return sorted(set(paths), key=lambda path: path.relative_to(REPOSITORY_ROOT).as_posix())


def zip_entry(name: str, data: bytes) -> tuple[ZipInfo, bytes]:
    info = ZipInfo(name, date_time=FIXED_ZIP_TIME)
    info.compress_type = ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info, data


def verify_git_binding(source_revision: str, allow_dirty: bool) -> None:
    actual_revision = subprocess.check_output(
        ("git", "rev-parse", "HEAD"), cwd=REPOSITORY_ROOT, text=True
    ).strip()
    if actual_revision.lower() != source_revision.lower():
        raise AssertionError(
            f"source revision {source_revision} does not match checkout {actual_revision}"
        )
    status = subprocess.check_output(
        ("git", "status", "--porcelain", "--untracked-files=normal"),
        cwd=REPOSITORY_ROOT,
        text=True,
    )
    if status.strip() and not allow_dirty:
        raise AssertionError("fixed releases must be built from a clean checkout")


def create_release(
    output_dir: Path, source_revision: str, allow_dirty: bool = False
) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", source_revision):
        raise ValueError("source revision must be a full 40-character Git commit hash")
    verify_git_binding(source_revision, allow_dirty)
    verify_tracked_artifacts()
    release_id = (REPOSITORY_ROOT / "RELEASE_VERSION").read_text("utf-8").strip()
    files = release_files()
    records = []
    for path in files:
        data = path.read_bytes()
        records.append(
            {
                "path": path.relative_to(REPOSITORY_ROOT).as_posix(),
                "sha256": digest_bytes(data),
                "bytes": len(data),
            }
        )
    release_record = {
        "schema": "post-semcom.fixed-release.v6",
        "release_id": release_id,
        "source_revision": source_revision.lower(),
        "files": records,
    }
    record_bytes = (
        json.dumps(release_record, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"post-semcom-{release_id}.zip"
    with ZipFile(archive_path, mode="w") as archive:
        for path in files:
            relative = path.relative_to(REPOSITORY_ROOT).as_posix()
            info, data = zip_entry(relative, path.read_bytes())
            archive.writestr(info, data)
        info, data = zip_entry("release_record.json", record_bytes)
        archive.writestr(info, data)

    checksum_path = output_dir / f"{archive_path.name}.sha256"
    checksum_path.write_text(
        f"{sha256(archive_path.read_bytes()).hexdigest()}  {archive_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    return archive_path, checksum_path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="development-only escape hatch; the release workflow never uses it",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    for path in create_release(args.output_dir, args.source_revision, args.allow_dirty):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
