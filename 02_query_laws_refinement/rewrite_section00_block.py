from __future__ import annotations

import argparse
import re
from pathlib import Path

BEGIN_MARKER = "# SECTION_00_REWRITE_BEGIN"
END_MARKER = "# SECTION_00_REWRITE_END"

# Default target (backward-compatible)
DEFAULT_TARGET_VARIABLE = "SECTION_00_EDITABLE_BLOCK"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def normalize_rewrite_block(text: str) -> str:
    stripped = text.strip()
    # Accept any marker pair — just ensure the block ends with a newline
    return stripped + "\n"


def replace_editable_block(source_text: str, target_variable: str, replacement_block: str) -> str:
    """Replace the body of `target_variable = r\"\"\"...\"\"\"` with replacement_block."""
    pattern = re.compile(
        rf'{re.escape(target_variable)}\s*=\s*r"""(?P<body>.*?)"""',
        re.DOTALL,
    )
    match = pattern.search(source_text)
    if not match:
        raise ValueError(f"{target_variable} was not found in source file")
    body_start, body_end = match.span("body")
    return source_text[:body_start] + "\n" + replacement_block.rstrip() + "\n" + source_text[body_end:]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Replace an editable block variable in analyze_logs_ver2.py. "
            "Works for SECTION_00_EDITABLE_BLOCK and the three imperative/example blocks."
        )
    )
    ap.add_argument("--source", required=True, help="Path to analyze_logs_ver2.py")
    ap.add_argument("--rewrite-block", required=True, help="Path to the rewritten block text file")
    ap.add_argument(
        "--target-variable",
        default=DEFAULT_TARGET_VARIABLE,
        help=(
            "Name of the module-level r-string variable to replace. "
            "Default: SECTION_00_EDITABLE_BLOCK. "
            "Other valid values: TIAB_IMPERATIVE_CONDITIONAL_ADD_EDITABLE, "
            "ONE_SHOT_IMPERATIVE_PRIMARY_EDITABLE, PLACEHOLDER_INITIAL_PRIMARY_EDITABLE."
        ),
    )
    ap.add_argument("--backup-path", required=False, help="Optional backup path for the original source")
    args = ap.parse_args()

    source_path = Path(args.source)
    rewrite_path = Path(args.rewrite_block)
    backup_path = Path(args.backup_path) if args.backup_path else None

    source_text = read_text(source_path)
    replacement_block = normalize_rewrite_block(read_text(rewrite_path))
    updated_text = replace_editable_block(source_text, args.target_variable, replacement_block)

    if backup_path:
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        write_text(backup_path, source_text)

    write_text(source_path, updated_text)
    print(f"Updated {args.target_variable} in: {source_path}")
    if backup_path:
        print(f"Backup written to: {backup_path}")


if __name__ == "__main__":
    main()
