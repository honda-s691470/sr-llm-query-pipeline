from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TEXT_EXTS = {'.csv', '.json', '.jsonl', '.md', '.txt', '.py'}
EXCLUDE_DIR_NAMES = {'audit_model_names_and_paths', 'repro_check', '__pycache__'}

TARGETS = [
    ROOT / 'public_release' / '05_test_data',
    ROOT / 'public_release' / 'revision_reruns' / 'test24_rulebook_sensitivity',
    ROOT / 'public_release' / '06_exclusion_screening_pipeline' / 'results',
    ROOT / 'paper' / 'JMIR' / 'review' / 'test24_rulebook_sensitivity',
    ROOT / 'paper' / 'results' / 'test24_eval',
]


def slash_variants(path: Path) -> list[str]:
    s = str(path)
    return sorted({s, s.replace('\\', '/'), s.replace('\\', '\\\\')}, key=len, reverse=True)

PUBLIC_RELEASE_ABS = slash_variants(ROOT / 'public_release')
ROOT_ABS = slash_variants(ROOT)


def normalize_separators_after_prefix(text: str, prefixes: list[str]) -> str:
    for prefix in prefixes:
        # Non-JSON/ordinary strings.
        text = text.replace(prefix + '\\\\', 'public_release/')
        text = text.replace(prefix + '\\', 'public_release/')
        text = text.replace(prefix + '/', 'public_release/')
    return text


def sanitize_text(text: str) -> str:
    for prefix in PUBLIC_RELEASE_ABS:
        text = text.replace(prefix + '\\\\', 'public_release/')
        text = text.replace(prefix + '\\', 'public_release/')
        text = text.replace(prefix + '/', 'public_release/')
        text = text.replace(prefix, 'public_release')
    for prefix in ROOT_ABS:
        text = text.replace(prefix + '\\\\', '')
        text = text.replace(prefix + '\\', '')
        text = text.replace(prefix + '/', '')
        text = text.replace(prefix, '.')
    # Normalize separators only in common path-valued substrings. This keeps
    # PubMed Boolean queries and JSON escaping otherwise untouched.
    text = re.sub(r'(public_release|paper|05_test_data|04_data)\\+', lambda m: m.group(1) + '/', text)
    return text


def iter_files() -> list[Path]:
    files = []
    for target in TARGETS:
        if not target.exists():
            continue
        if target.is_file():
            candidates = [target]
        else:
            candidates = [p for p in target.rglob('*') if p.is_file()]
        for p in candidates:
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            parts = set(p.parts)
            if parts & EXCLUDE_DIR_NAMES:
                continue
            files.append(p)
    return sorted(set(files))


def main() -> int:
    changed = []
    for path in iter_files():
        try:
            text = path.read_text(encoding='utf-8-sig')
            encoding = 'utf-8-sig'
        except UnicodeDecodeError:
            text = path.read_text(encoding='utf-8', errors='replace')
            encoding = 'utf-8'
        new_text = sanitize_text(text)
        if new_text != text:
            path.write_text(new_text, encoding=encoding)
            changed.append(path)
    report = ROOT / 'public_release' / 'revision_reruns' / 'test24_rulebook_sensitivity' / 'absolute_path_sanitization_report.txt'
    report.write_text('\n'.join(str(p.relative_to(ROOT)) for p in changed) + ('\n' if changed else ''), encoding='utf-8')
    print(f'changed_files={len(changed)}')
    print(report)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

