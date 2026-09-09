from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from filelock import FileLock


def _sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _read_manifest_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return [dict(x) for x in r]




def _relative_path_string(path: Path, base: Path | None) -> str:
    """Return a portable relative path for persisted metadata."""
    if base is None:
        return path.as_posix()
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            return path.name

def _write_manifest_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "updated_at_utc",
        "dataset_split",
        "domain",
        "paper_id",
        "provider",
        "stage",
        "condition",
        "source_condition",
        "query_type",
        "query_length",
        "query_sha256",
        "query_path",
        "meta_path",
        "extra_json",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def save_stage_query_snapshot(
    *,
    paper_dir: Path,
    results_dir: Path,
    dataset_split: str,
    domain: str,
    paper_id: str,
    provider: str,
    stage: str,
    condition: str,
    source_condition: str,
    query_text: str,
    query_type: str,
    extra: dict[str, Any] | None = None,
    path_base: Path | None = None,
) -> tuple[Path, Path, Path]:
    """
    Save stage query to model_outputs and upsert into provider manifest.

    Returns:
      (query_path, meta_path, manifest_path)
    """
    out_dir = paper_dir / "model_outputs" / provider / condition
    out_dir.mkdir(parents=True, exist_ok=True)
    query_path = out_dir / "normalized_query.txt"
    query_path.write_text(query_text.strip(), encoding="utf-8")

    if path_base is None:
        # In the public-release layout, results_dir is usually
        # public_release/06_exclusion_screening_pipeline/results.
        path_base = results_dir.parents[1] if len(results_dir.parents) > 1 else results_dir.parent
    query_path_str = _relative_path_string(query_path, path_base)

    meta_obj = {
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_split": dataset_split,
        "domain": domain,
        "paper_id": paper_id,
        "provider": provider,
        "stage": stage,
        "condition": condition,
        "source_condition": source_condition,
        "query_type": query_type,
        "query_length": len(query_text),
        "query_sha256": _sha256_text(query_text),
        "query_path": query_path_str,
        "extra": extra or {},
    }
    meta_path = out_dir / "snapshot_meta.json"
    meta_path.write_text(json.dumps(meta_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path_str = _relative_path_string(meta_path, path_base)

    manifest_path = results_dir / f"query_stage_manifest_{provider}.csv"
    lock_path = manifest_path.with_suffix(".lock")
    
    with FileLock(str(lock_path), timeout=60):
        rows = _read_manifest_rows(manifest_path)
        key = (dataset_split, domain, paper_id, provider, stage, condition)
    
        new_row = {
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset_split": dataset_split,
            "domain": domain,
            "paper_id": paper_id,
            "provider": provider,
            "stage": stage,
            "condition": condition,
            "source_condition": source_condition,
            "query_type": query_type,
            "query_length": str(len(query_text)),
            "query_sha256": _sha256_text(query_text),
            "query_path": query_path_str,
            "meta_path": meta_path_str,
            "extra_json": json.dumps(extra or {}, ensure_ascii=False),
        }
    
        replaced = False
        for i, r in enumerate(rows):
            r_key = (
                r.get("dataset_split", ""),
                r.get("domain", ""),
                r.get("paper_id", ""),
                r.get("provider", ""),
                r.get("stage", ""),
                r.get("condition", ""),
            )
            if r_key == key:
                rows[i] = new_row
                replaced = True
                break
        if not replaced:
            rows.append(new_row)
    
        rows.sort(key=lambda x: (
            x.get("dataset_split", ""),
            x.get("domain", ""),
            x.get("paper_id", ""),
            x.get("provider", ""),
            x.get("stage", ""),
            x.get("condition", ""),
        ))
        _write_manifest_rows(manifest_path, rows)
        
    return query_path, meta_path, manifest_path


