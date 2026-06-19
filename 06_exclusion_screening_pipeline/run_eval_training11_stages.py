"""
Training 11: Stage A' → Stage A → Stage B evaluation with uid-based recall.

For each paper:
  1. Base query hits + uid-based recall
  2. Stage A (parse_and_log NOT blocks) hits + uid-based recall
  3. Stage A' (if base hits > 9999) hits + uid-based recall
  4. Stage B (esummary metadata filter) hits + uid-based recall

Usage:
    python run_eval_training11_stages.py [--paper PAPER_ID] [--stages AB|APrimeAB]
"""
from __future__ import annotations
import argparse
import json
import logging
import re
import sys
from pathlib import Path

ROOT      = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "04_data"
SRC_DIR   = ROOT / "06_exclusion_screening_pipeline" / "src"
OUT_DIR   = ROOT / "06_exclusion_screening_pipeline" / "results"
sys.path.insert(0, str(SRC_DIR))

from pubmed_fetcher import search_pubmed, fetch_all_metadata
from exclusion_parser import parse_and_log, stage_b_filter

# ── SR-of-SRs exception ───────────────────────────────────────────────────────
# If inclusion criteria or objectives indicate review-type studies are eligible,
# NOT "Review"[pt] / NOT "Meta-Analysis"[pt] / NOT "Systematic Review"[pt] are FORBIDDEN.

_SR_OF_SRS_MARKERS = [
    "systematic review",
    "meta-analysis",
    "meta analysis",
    "scoping review",
    "narrative review",
    "umbrella review",
    "literature review",
    "review article",
]

_REVIEW_NOT_BLOCKS = {
    'NOT "Review"[pt]',
    'NOT "Systematic Review"[pt]',
    'NOT "Meta-Analysis"[pt]',
    'NOT "Scoping Review"[pt]',
}


def _is_sr_of_srs(objectives_text: str, inclusion_text: str) -> bool:
    combined = ((objectives_text or "") + " " + (inclusion_text or "")).lower()
    return any(marker in combined for marker in _SR_OF_SRS_MARKERS)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: PubMed query parser + Tier 1–10 + F candidate generators
# (same logic as run_test_prime_A_B_posthoc_recall.py; training uses recall guard)
# ═══════════════════════════════════════════════════════════════════════════════

_RE_MESH       = re.compile(r'"([^"]+)"\[Mesh\]',       re.IGNORECASE)
_RE_MESH_NOEXP = re.compile(r'"([^"]+)"\[Mesh:NoExp\]', re.IGNORECASE)
_RE_TIAB       = re.compile(r'(?:"([^"]+)"|([A-Za-z0-9_\-*]+))\[tiab\]', re.IGNORECASE)


def _split_top_level(text: str, sep: str) -> list[str]:
    """Split *text* by *sep* only at parenthesis depth 0."""
    parts: list[str] = []
    depth = 0
    start = 0
    sl = sep.lower()
    slen = len(sep)
    tl = text.lower()
    i = 0
    while i < len(text):
        c = text[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif depth == 0 and tl[i:i + slen] == sl:
            parts.append(text[start:i].strip())
            start = i + slen
            i += slen
            continue
        i += 1
    parts.append(text[start:].strip())
    return [p for p in parts if p]


def _strip_outer_parens(s: str) -> str:
    s = s.strip()
    if not (s.startswith('(') and s.endswith(')')):
        return s
    depth = 0
    for i, c in enumerate(s):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        if depth == 0 and i < len(s) - 1:
            return s
    return s[1:-1].strip()


def _parse_and_blocks(raw_query: str) -> list[str]:
    return [_strip_outer_parens(b) for b in _split_top_level(raw_query, ' AND ')]


def _rebuild_raw_query(blocks: list[str]) -> str:
    return ' AND '.join(f'({b})' for b in blocks if b.strip())


def _extract_tiab_texts(block: str) -> list[str]:
    texts: list[str] = []
    for m in _RE_TIAB.finditer(block):
        t = m.group(1) or m.group(2)
        if t:
            texts.append(t.lower().strip('"'))
    return texts


def _tiab_covers_mesh(mesh_name: str, tiab_texts: list[str]) -> bool:
    def _norm(s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower())
    mesh_norm   = _norm(mesh_name)
    mesh_tokens = {w for w in re.split(r'\W+', mesh_name.lower()) if len(w) >= 4}
    for tiab in tiab_texts:
        core      = tiab.rstrip('*').split('*')[0]
        tiab_norm = _norm(core)
        if not tiab_norm or len(tiab_norm) < 3:
            continue
        if '*' in tiab and len(tiab_norm) >= 4 and mesh_norm.startswith(tiab_norm):
            return True
        if len(tiab_norm) >= 4 and (tiab_norm in mesh_norm or mesh_norm in tiab_norm):
            return True
        tiab_tokens = {w for w in re.split(r'\W+', core.lower()) if len(w) >= 4}
        if mesh_tokens & tiab_tokens:
            return True
    return False


def _remove_term_from_or_block(block: str, term: str) -> str | None:
    terms = _split_top_level(block, ' OR ')
    term_lo = term.lower().strip()
    new_terms = [t for t in terms if t.lower().strip() != term_lo]
    if not new_terms or len(new_terms) == len(terms):
        new_terms = [t for t in terms if term_lo not in t.lower()]
    if not new_terms:
        return None
    return ' OR '.join(new_terms)


def _replace_term_in_or_block(block: str, old_term: str, new_term: str) -> str | None:
    terms = _split_top_level(block, ' OR ')
    old_lo = old_term.lower().strip()
    replaced = False
    result = []
    for t in terms:
        if t.lower().strip() == old_lo:
            result.append(new_term)
            replaced = True
        else:
            result.append(t)
    return ' OR '.join(result) if replaced else None


def _split_raw_and_suffix(query: str) -> tuple[str, str]:
    ql = query.lower()
    idxs: list[int] = []
    for tok in [' not ', ' english[lang]', ' ("adult"[mesh]']:
        i = ql.find(tok)
        if i != -1:
            idxs.append(i)
    if not idxs:
        return query.strip(), ""
    s = min(idxs)
    return query[:s].strip(), " " + query[s:].strip()


def _tier1_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 1: Remove [Mesh] when tiab backup exists in same OR block."""
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []
    for idx, block in enumerate(blocks):
        tiabs = _extract_tiab_texts(block)
        if not tiabs:
            continue
        for m in _RE_MESH.finditer(block):
            full, name = m.group(0), m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                new_block = _remove_term_from_or_block(block, full)
                if new_block is not None:
                    new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                    candidates.append(
                        (f'remove_{name[:30]}[Mesh]', _rebuild_raw_query(new_blocks))
                    )
    return candidates


def _tier2_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 2: Remove wildcard-redundant tiab terms (Pattern A)."""
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []
    for idx, block in enumerate(blocks):
        terms = _split_top_level(block, ' OR ')
        tiab_pairs = []
        for t in terms:
            if '[tiab]' not in t.lower():
                continue
            txts = _extract_tiab_texts(t)
            if txts:
                tiab_pairs.append((t, txts[0]))
        wildcards     = [(t, txt) for t, txt in tiab_pairs if '*' in txt]
        non_wildcards = [(t, txt) for t, txt in tiab_pairs if '*' not in txt]
        for nw_term, nw_txt in non_wildcards:
            for _, wc_txt in wildcards:
                wc_root = wc_txt.rstrip('*').lower()
                if len(wc_root) >= 4 and nw_txt.lower().startswith(wc_root):
                    new_block = _remove_term_from_or_block(block, nw_term)
                    if new_block is not None:
                        new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                        candidates.append(
                            (f'redundant_{nw_txt[:30]}[tiab]', _rebuild_raw_query(new_blocks))
                        )
                    break
    return candidates


def _tier3_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 3: Remove generic/broad tiab when a more-specific tiab covers it
    in the same OR block via word-boundary suffix match.

    Pattern: if txt_a is a word-boundary suffix of txt_b (e.g. 'RNA' in 'microRNA',
    'cancer' in 'breast cancer'), txt_a is redundant and can be removed.
    Safety guards: min 4 chars; txt_b must be at least 2 chars longer than txt_a;
    wildcards in txt_a are skipped.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        terms = _split_top_level(block, ' OR ')
        tiab_pairs: list[tuple[str, str]] = []
        for t in terms:
            if '[tiab]' not in t.lower():
                continue
            txts = _extract_tiab_texts(t)
            if txts:
                tiab_pairs.append((t, txts[0]))

        if len(tiab_pairs) < 2:
            continue

        already_removed: set[str] = set()
        for term_a, txt_a in tiab_pairs:
            if term_a in already_removed:
                continue
            if '*' in txt_a:
                continue
            txt_a_norm = txt_a.lower().strip('"').strip()
            if len(txt_a_norm) < 4:
                continue

            is_generic = False
            for term_b, txt_b in tiab_pairs:
                if term_a == term_b:
                    continue
                txt_b_norm = txt_b.lower().strip('"').strip()
                if (txt_b_norm.endswith(txt_a_norm)
                        and len(txt_b_norm) >= len(txt_a_norm) + 2):
                    is_generic = True
                    break

            if is_generic:
                new_block = _remove_term_from_or_block(block, term_a)
                if new_block is not None:
                    new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                    candidates.append(
                        (f'generic_{txt_a_norm[:25]}[tiab]', _rebuild_raw_query(new_blocks))
                    )
                    already_removed.add(term_a)

    return candidates


def _tier5_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 5: Replace [tiab] → [ti] (title-only) for terms that have a
    [Mesh] or [Mesh:NoExp] backup in the same OR block.

    Safety condition: [Mesh] or [Mesh:NoExp] must exist in the same OR block
    and cover the tiab concept (via _tiab_covers_mesh).
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        mesh_names_here = [m.group(1) for m in _RE_MESH.finditer(block)]
        mesh_names_here += [m.group(1) for m in _RE_MESH_NOEXP.finditer(block)]
        if not mesh_names_here:
            continue

        for m in _RE_TIAB.finditer(block):
            tiab_full = m.group(0)
            tiab_text = (m.group(1) or m.group(2) or '').lower().strip('"')
            if not tiab_text or len(tiab_text.rstrip('*')) < 3:
                continue

            if any(_tiab_covers_mesh(mn, [tiab_text]) for mn in mesh_names_here):
                ti_full = re.sub(r'\[tiab\]', '[ti]', tiab_full, flags=re.IGNORECASE)
                if ti_full == tiab_full:
                    continue
                new_block = _replace_term_in_or_block(block, tiab_full, ti_full)
                if new_block is not None:
                    new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                    candidates.append(
                        (f'ti_{tiab_text[:25]}', _rebuild_raw_query(new_blocks))
                    )

    return candidates


_RE_UPPERCASE_ACRONYM = re.compile(r'(?:"([A-Z][A-Z0-9]{1,3})"|([A-Z][A-Z0-9]{1,3}))\[tiab\]')

_SCOPE_RESTRICTOR_STEMS = (
    'predict', 'prognos', 'screen', 'diagnos', 'mortalit', 'surviv',
    'inciden', 'prevalenc', 'assess', 'measur', 'outcom',
)


def _tier4_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 4: Remove 2-4 ALL-CAPS acronym [tiab] when the same OR block has
    at least one non-wildcard tiab with >= 8 chars (full-form proxy).
    [Mesh] backup is no longer required — full-form tiab alone is sufficient guard.
    Recall guard (training mode) handles edge cases.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        tiabs = _extract_tiab_texts(block)
        if not any(len(t.rstrip('*')) >= 8 and '*' not in t for t in tiabs):
            continue
        terms = _split_top_level(block, ' OR ')
        for term in terms:
            if '[tiab]' not in term.lower():
                continue
            if '*' in term:
                continue
            m = _RE_UPPERCASE_ACRONYM.search(term)
            if not m:
                continue
            acronym = (m.group(1) or m.group(2) or '').strip()
            if not acronym or len(acronym) < 2 or len(acronym) > 4:
                continue
            new_block = _remove_term_from_or_block(block, term)
            if new_block is not None:
                new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                candidates.append(
                    (f'acronym_{acronym}[tiab]', _rebuild_raw_query(new_blocks))
                )
    return candidates


def _tier6_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 6: Replace a scope-restrictor [tiab] with a proximity phrase.
    Condition: block >= 3 tiab terms; one is a scope-restrictor stem (predict*,
    prognos*, screen*, diagnos*, mortalit*, surviv*, inciden*, prevalenc*, assess*,
    measur*, outcom*); another is a content term (>= 6 chars, no wildcard).
    Proximity window N=5. Recall guard (training mode) handles potential recall drop.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        terms = _split_top_level(block, ' OR ')
        tiab_pairs: list[tuple[str, str]] = []
        for t in terms:
            if '[tiab]' not in t.lower():
                continue
            txts = _extract_tiab_texts(t)
            if txts:
                tiab_pairs.append((t, txts[0]))

        if len(tiab_pairs) < 3:
            continue

        restrictors: list[tuple[str, str]] = []
        content_terms: list[tuple[str, str]] = []
        for term, txt in tiab_pairs:
            txt_norm = txt.lower().strip('"').rstrip('*')
            if any(txt_norm.startswith(stem) for stem in _SCOPE_RESTRICTOR_STEMS):
                restrictors.append((term, txt))
            elif len(txt_norm) >= 6 and '*' not in txt:
                content_terms.append((term, txt))

        if not restrictors or not content_terms:
            continue

        restr_term, restr_txt = restrictors[0]
        content_term, content_txt = max(content_terms, key=lambda x: len(x[1]))
        restr_base = restr_txt.strip('"').rstrip('*')
        content_base = content_txt.strip('"')

        prox_phrase = f'"{restr_base}* {content_base}"[tiab:~5]'
        new_block = _remove_term_from_or_block(block, restr_term)
        if new_block is None:
            continue
        new_block = new_block + f' OR {prox_phrase}'
        new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
        candidates.append(
            (f'prox_{restr_base[:12]}_{content_base[:12]}', _rebuild_raw_query(new_blocks))
        )
    return candidates


def _tier9_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 9: Batch-convert ALL eligible [Mesh:NoExp] and [Mesh] to [majr] in a
    single AND-block (>= 2 convertible terms). More aggressive than Tier 8.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        tiabs = _extract_tiab_texts(block)
        if not tiabs:
            continue
        conversions: list[tuple[str, str]] = []
        for m in _RE_MESH_NOEXP.finditer(block):
            name = m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                conversions.append((m.group(0), f'"{name}"[majr]'))
        for m in _RE_MESH.finditer(block):
            name = m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                conversions.append((m.group(0), f'"{name}"[majr]'))
        if len(conversions) < 2:
            continue
        new_block = block
        for old, new_term in conversions:
            new_block = new_block.replace(old, new_term)
        if new_block != block:
            new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
            candidates.append(
                (f'batch_majr_blk{idx}', _rebuild_raw_query(new_blocks))
            )
    return candidates


def _tier10_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 10: Replace a pair of wildcard [tiab] terms in the same OR block
    with a proximity phrase "stem1* stem2*"[tiab:~3].
    Conditions:
      - both stems >= 4 chars (after stripping wildcard)
      - block must have >= 3 tiab terms total (safety margin)
    More general than Tier 6: not limited to scope-restrictors.
    Recall guard (training mode) handles potential recall drop.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        terms = _split_top_level(block, ' OR ')
        all_tiabs = [t for t in terms if '[tiab]' in t.lower()]
        if len(all_tiabs) < 3:
            continue

        tiab_wildcards: list[tuple[str, str]] = []  # (term, stem)
        for t in terms:
            if '[tiab]' not in t.lower():
                continue
            txts = _extract_tiab_texts(t)
            if txts and '*' in txts[0]:
                stem = txts[0].strip('"').rstrip('*')
                if len(stem) >= 4:
                    tiab_wildcards.append((t, stem))

        if len(tiab_wildcards) < 2:
            continue

        for i, (term_a, stem_a) in enumerate(tiab_wildcards):
            for j, (term_b, stem_b) in enumerate(tiab_wildcards):
                if j <= i:
                    continue
                prox_phrase = f'"{stem_a}* {stem_b}*"[tiab:~3]'
                new_block = _remove_term_from_or_block(block, term_a)
                if new_block is None:
                    continue
                new_block2 = _replace_term_in_or_block(new_block, term_b, prox_phrase)
                if new_block2 is None:
                    continue
                new_blocks = blocks[:idx] + [new_block2] + blocks[idx + 1:]
                candidates.append(
                    (f'prox_pair_{stem_a[:10]}_{stem_b[:10]}', _rebuild_raw_query(new_blocks))
                )

    return candidates


def _tier7_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 7: Replace [Mesh] → [Mesh:NoExp]."""
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []
    for idx, block in enumerate(blocks):
        tiabs = _extract_tiab_texts(block)
        if not tiabs:
            continue
        for m in _RE_MESH.finditer(block):
            full, name = m.group(0), m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                new_block = _replace_term_in_or_block(block, full, f'"{name}"[Mesh:NoExp]')
                if new_block is not None:
                    new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                    candidates.append(
                        (f'noexp_{name[:30]}', _rebuild_raw_query(new_blocks))
                    )
    return candidates


def _tier8_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 8: Replace [Mesh:NoExp] → [majr]."""
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []
    for idx, block in enumerate(blocks):
        tiabs = _extract_tiab_texts(block)
        if not tiabs:
            continue
        for m in _RE_MESH_NOEXP.finditer(block):
            full, name = m.group(0), m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                new_block = _replace_term_in_or_block(block, full, f'"{name}"[majr]')
                if new_block is not None:
                    new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                    candidates.append(
                        (f'majr_{name[:30]}', _rebuild_raw_query(new_blocks))
                    )
    return candidates


# Tier F: safe NOT publication-type filters appended to full query
_TIER_F_FILTERS: list[tuple[str, str]] = [
    ("tierF_news",     'NOT "News"[pt]'),
    ("tierF_comment",  'NOT "Comment"[pt]'),
    ("tierF_letter",   'NOT "Letter"[pt]'),
    ("tierF_editorial",'NOT "Editorial"[pt]'),
    ("tierF_erratum",  'NOT "Published Erratum"[pt]'),
    ("tierF_case_rep", 'NOT "Case Reports"[pt]'),
    ("tierF_animals",  'NOT (animals[mh] NOT humans[mh])'),
]


def _tierF_candidates_from_raw(raw_query: str, _full_query: str = "") -> list[tuple[str, str]]:
    """Tier F: append safe NOT publication-type filters not already in full query."""
    full_lo = (_full_query or raw_query).lower()
    candidates: list[tuple[str, str]] = []
    for desc, filt in _TIER_F_FILTERS:
        if filt.lower() in full_lo:
            continue
        candidates.append((desc, (_full_query or raw_query) + " " + filt))
    return candidates


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── uid-based recall ─────────────────────────────────────────────────────────

def _gold_filter(gold_pmids: set[str]) -> str:
    return "(" + " OR ".join(f"{p}[uid]" for p in sorted(gold_pmids)) + ")"


def true_recall(query: str, gold_pmids: set[str]) -> tuple[int, float]:
    """Uid-based TP count and recall (bypasses 9,999 PMID retrieval cap)."""
    if not gold_pmids:
        return 0, 0.0
    combined = f"({query}) AND {_gold_filter(gold_pmids)}"
    tp, _ = search_pubmed(combined, retmax=len(gold_pmids) + 10)
    return tp, tp / len(gold_pmids)


# ── paper loader ─────────────────────────────────────────────────────────────

def load_paper(domain: str, paper_id: str, provider: str = "claude") -> dict | None:
    data_dir   = DATA_DIR  / domain / paper_id

    wl_path      = data_dir / "model_outputs" / provider / "with_laws_test_eval" / "normalized_query.txt"
    gold_path    = data_dir  / "input_config.json"
    detail_path  = data_dir  / "input_config_detailed.json"

    for p in (wl_path, gold_path, detail_path):
        if not p.exists():
            logger.warning("Missing: %s", p)
            return None

    gold_data   = json.loads(gold_path.read_text("utf-8"))
    detail_data = json.loads(detail_path.read_text("utf-8"))

    return {
        "paper_id":           paper_id,
        "domain":             domain,
        "query":              wl_path.read_text("utf-8").strip(),
        "gold_pmids":         set(str(p) for p in gold_data.get("gold_pmids", [])),
        "exclusion_criteria": detail_data.get("exclusion_criteria", ""),
        "inclusion_criteria": detail_data.get("inclusion_criteria", ""),
        "objectives":         detail_data.get("objectives", ""),
        "pmid_query":         str(detail_data.get("pmid_query", "")),
    }


# ── Stage A' candidate blocks (priority order) ───────────────────────────────

# A_PRIME_BLOCKS_REWRITE_BEGIN
A_PRIME_BLOCKS = [
    {"name": "english",          "syntax": "english[lang]"},
    # Keep SR-of-SRs trio adjacent; place early to capture strong gain from systematic_review.
    {"name": "systematic_review","syntax": 'NOT "Systematic Review"[pt]'},
    {"name": "meta_analysis",    "syntax": 'NOT "Meta-Analysis"[pt]'},
    {"name": "review",           "syntax": 'NOT "Review"[pt]'},
    {"name": "clin_trial_proto", "syntax": 'NOT "Clinical Trial Protocol"[pt]'},
    {"name": "preprint",         "syntax": 'NOT "Preprint"[pt]'},
    {"name": "retracted",        "syntax": 'NOT "Retracted Publication"[pt]'},
    {"name": "meeting_abstract", "syntax": 'NOT "Meeting Abstract"[pt]'},
    {"name": "adult_age",        "syntax": '("Adult"[Mesh] OR "Middle Aged"[Mesh] OR "Aged"[Mesh])'},
    {"name": "journal_article",  "syntax": '"Journal Article"[pt]'},
]
# A_PRIME_BLOCKS_REWRITE_END

# Blocks that Stage A allowlist handles — skip in Stage A'
STAGE_A_ALLOWLIST = {
    'NOT "Case Reports"[pt]', 'NOT "Letter"[pt]', 'NOT "Editorial"[pt]',
    'NOT "Comment"[pt]', 'NOT "Published Erratum"[pt]', 'NOT "News"[pt]',
    'NOT (animals[mh] NOT humans[mh])',
}

# v2.0: METRICS_AND_BLOCK removed — Tier 2 AND additions are forbidden.
# Adding new mandatory AND concepts (c-statistic, dates, disease progression)
# causes catastrophic recall loss and is permanently prohibited (2026-03-30).


def run_stage_a_prime_phase1(base_query: str, gold_pmids: set[str],
                              initial_hits: int, paper_id: str,
                              hit_target: int = 9999,
                              objectives_text: str = "",
                              inclusion_text: str = "",
                              recall_threshold: float = 0.02) -> dict:
    """Apply Phase 1 blocks until hits ≤ 9,999 or all blocks exhausted.
    SR-of-SRs exception: skips NOT Review/Meta-Analysis/Systematic Review blocks
    when objectives or inclusion criteria indicate review-type studies are eligible.
    """
    sr_of_srs = _is_sr_of_srs(objectives_text, inclusion_text)
    if sr_of_srs:
        logger.info("[%s] SR-of-SRs exception ACTIVE: NOT Review/Meta-Analysis blocks will be skipped", paper_id)

    current_query  = base_query
    current_hits   = initial_hits
    tp0, recall0   = true_recall(base_query, gold_pmids)
    current_recall = recall0

    blocks_added: list[dict] = []
    blocks_rejected: list[dict] = []

    for blk in A_PRIME_BLOCKS:
        syntax = blk["syntax"]
        if syntax in STAGE_A_ALLOWLIST:
            continue
        if syntax.lower() in current_query.lower():
            continue
        if sr_of_srs and syntax in _REVIEW_NOT_BLOCKS:
            logger.info("[%s] SR-of-SRs exception: skipping '%s'", paper_id, syntax)
            continue

        test_q = current_query + " " + syntax
        total_test, _ = search_pubmed(test_q, retmax=1)
        tp_test, recall_test = true_recall(test_q, gold_pmids)
        dr = round(current_recall - recall_test, 4)
        dh = current_hits - total_test

        entry = {"name": blk["name"], "syntax": syntax, "hits_before": current_hits, "hits_after": total_test,
                 "delta_hits": dh, "delta_recall": dr,
                 "recall_before": round(current_recall, 4), "recall_after": round(recall_test, 4)}

        if dr > recall_threshold:
            entry["action"] = "REJECTED"
            blocks_rejected.append(entry)
            logger.info("[%s] A' REJECTED %s  ΔR=%.3f", paper_id, syntax, dr)
        else:
            entry["action"] = "ACCEPTED"
            blocks_added.append(entry)
            current_query  = test_q
            current_hits   = total_test
            current_recall = recall_test
            logger.info("[%s] A' ACCEPTED %s  hits=%d recall=%.3f", paper_id, syntax, current_hits, current_recall)

        if current_hits <= hit_target:
            break

    return {
        "optimized_query": current_query,
        "initial_hits": initial_hits,
        "final_hits":   current_hits,
        "initial_recall": round(recall0, 4),
        "final_recall":   round(current_recall, 4),
        "goal_achieved":  current_hits <= hit_target,
        "blocks_added":   blocks_added,
        "blocks_rejected": blocks_rejected,
    }


# ── main evaluation ──────────────────────────────────────────────────────────

TRAINING_PAPERS = [
    ("02_Cardiovascular_Disease", "41522206_2026"),
    ("02_Cardiovascular_Disease", "41684373_2026"),
    ("02_Cardiovascular_Disease", "41707176_2026"),
    ("03_Psychiatry",             "40357797_2026"),
    ("03_Psychiatry",             "41582468_2026"),
    ("03_Psychiatry",             "41582599_2026"),
    ("03_Psychiatry",             "41694153_2026"),
    ("05_Infectious_Diseases",    "41770456_2026"),
    ("05_Infectious_Diseases",    "41781415_2026"),
    ("05_Infectious_Diseases",    "41789521_2026"),
    ("05_Infectious_Diseases",    "41790564_2026"),
]

HIT_TARGET = 9999


def eval_paper(
    paper: dict,
    run_stage_b: bool = True,
    recall_threshold: float = 0.02,
) -> dict:
    pid        = paper["paper_id"]
    base_q     = paper["query"]
    gold       = paper["gold_pmids"]
    excl_text  = paper["exclusion_criteria"]
    gold_n     = len(gold)

    logger.info("== %s  gold=%d ==", pid, gold_n)

    # ── Base query ────────────────────────────────────────────────────
    base_hits, _ = search_pubmed(base_q, retmax=1)
    tp_base, recall_base = true_recall(base_q, gold)
    logger.info("[%s] Base: hits=%d  recall=%.4f (%d/%d)", pid, base_hits, recall_base, tp_base, gold_n)

    result = {
        "paper_id":    pid,
        "domain":      paper["domain"],
        "gold_n":      gold_n,
        "base_hits":   base_hits,
        "base_recall": round(recall_base, 4),
        "base_tp":     tp_base,
        "a_prime_hits":   None,
        "a_prime_recall": None,
        "a_prime_tp":     None,
        "a_prime_phase":  None,
        "a_prime_note":   "",
        "stage_a_hits":   None,
        "stage_a_recall": None,
        "stage_a_tp":     None,
        "stage_a_not_applied": "",
        "stage_b_hits":   None,
        "stage_b_recall": None,
        "stage_b_tp":     None,
    }

    objectives_text = paper.get("objectives", "")
    inclusion_text  = paper.get("inclusion_criteria", "")

    # ── Stage A' (only if base hits > HIT_TARGET) ─────────────────────
    query_for_stage_a = base_q
    if base_hits > HIT_TARGET:
        logger.info("[%s] Base hits %d > %d → running Stage A'", pid, base_hits, HIT_TARGET)
        ap = run_stage_a_prime_phase1(
            base_q, gold, base_hits, pid, HIT_TARGET,
            objectives_text=objectives_text,
            inclusion_text=inclusion_text,
            recall_threshold=recall_threshold,
        )
        result["a_prime_hits"]   = ap["final_hits"]
        result["a_prime_recall"] = round(ap["final_recall"], 4)
        result["a_prime_tp"]     = round(ap["final_recall"] * gold_n)
        result["a_prime_phase"]  = 1
        result["a_prime_note"]   = "goal_achieved" if ap["goal_achieved"] else "hit_ceiling (Phase1 only)"
        query_for_stage_a        = ap["optimized_query"]
        logger.info("[%s] A' complete: hits=%d  recall=%.4f", pid, ap["final_hits"], ap["final_recall"])

        # Phase 2 (Tier F NOT blocks from Phase1 not yet applied) — no AND blocks (Tier 2 forbidden)
        # v2.0: METRICS_AND_BLOCK removed permanently.

        # ── Phase 3: Tier 1-10, F (raw query narrowing, with recall guard ΔR≤0.02) ──
        if not ap["goal_achieved"]:
            logger.info("[%s] A' Phase3: trying Tier 1-10, F candidates", pid)
            raw_part, suffix_part = _split_raw_and_suffix(query_for_stage_a)
            current_hits_p4 = ap["final_hits"]
            current_recall_p4 = ap["final_recall"]
            phase4_applied = 0

            # Build ordered candidate list: Tier 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → F
            tier_candidates: list[tuple[str, str]] = []
            for desc, new_raw in _tier1_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier1_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier2_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier2_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier3_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier3_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier4_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier4_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier5_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier5_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier6_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier6_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier7_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier7_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier8_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier8_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier9_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier9_{desc}", new_raw + suffix_part))
            for desc, new_raw in _tier10_candidates_from_raw(raw_part):
                tier_candidates.append((f"tier10_{desc}", new_raw + suffix_part))
            for desc, cand_q in _tierF_candidates_from_raw(raw_part, query_for_stage_a):
                tier_candidates.append((desc, cand_q))

            for desc, cand_q in tier_candidates:
                if current_hits_p4 <= HIT_TARGET:
                    break
                hits_cand, _ = search_pubmed(cand_q, retmax=1)
                if hits_cand >= current_hits_p4:
                    continue  # no reduction
                tp_cand, recall_cand = true_recall(cand_q, gold)
                dr = round(current_recall_p4 - recall_cand, 4)
                if dr > recall_threshold:
                    logger.info("[%s] Phase3 REJECTED %s  ΔR=%.3f", pid, desc, dr)
                    continue
                logger.info("[%s] Phase3 ACCEPTED %s  hits=%d→%d  recall=%.4f",
                            pid, desc, current_hits_p4, hits_cand, recall_cand)
                query_for_stage_a = cand_q
                raw_part, suffix_part = _split_raw_and_suffix(query_for_stage_a)
                current_hits_p4 = hits_cand
                current_recall_p4 = recall_cand
                phase4_applied += 1

            if phase4_applied > 0:
                result["a_prime_hits"]   = current_hits_p4
                result["a_prime_recall"] = round(current_recall_p4, 4)
                result["a_prime_tp"]     = round(current_recall_p4 * gold_n)
                result["a_prime_phase"]  = 3
                result["a_prime_note"]   = (
                    "goal_achieved" if current_hits_p4 <= HIT_TARGET
                    else f"hit_ceiling (Phase3: {phase4_applied} applied)"
                )
                logger.info("[%s] A' Phase3 done: hits=%d  recall=%.4f",
                            pid, current_hits_p4, current_recall_p4)

            # Phase 5 (LLM full rewrite) is handled externally by the main Claude Code
            # conversation via Agent tool subagents. See phase5_manual_prompt.md.

    # ── Stage A (exclusion criteria NOT blocks) ───────────────────────
    import tempfile
    log_path = Path(tempfile.gettempdir()) / f"{pid}_stage_a_eval.jsonl"
    parsed, query_a = parse_and_log(
        paper_id=pid,
        exclusion_text=excl_text,
        base_query=query_for_stage_a,
        log_path=log_path,
    )
    hits_a, _ = search_pubmed(query_a, retmax=1)
    tp_a, recall_a = true_recall(query_a, gold)
    result["stage_a_hits"]        = hits_a
    result["stage_a_recall"]      = round(recall_a, 4)
    result["stage_a_tp"]          = tp_a
    result["stage_a_not_applied"] = "; ".join(parsed.safe_not_applied)
    logger.info("[%s] Stage A: hits=%d  recall=%.4f  NOT=%s",
                pid, hits_a, recall_a, result["stage_a_not_applied"])

    # ── Stage B (metadata filter) ─────────────────────────────────────
    if not run_stage_b:
        return result

    if hits_a > 20_000:
        result["stage_b_note"] = f"SKIPPED (hits_a={hits_a} > 20,000)"
        logger.info("[%s] Stage B skipped (too large)", pid)
        return result

    logger.info("[%s] Stage B: fetching metadata for %d records…", pid, hits_a)
    _, pmids_a = search_pubmed(query_a, sort="relevance", retmax=hits_a + 100)
    records = fetch_all_metadata(pmids_a, batch_size=200)
    kept, _ = stage_b_filter(records, parsed)
    pmids_b = {r["pmid"] for r in kept}

    # uid-based recall for Stage B (Stage B doesn't change the query, so use query_a)
    tp_b  = len(gold & pmids_b)
    recall_b = tp_b / gold_n if gold_n else 0.0
    result["stage_b_hits"]   = len(pmids_b)
    result["stage_b_recall"] = round(recall_b, 4)
    result["stage_b_tp"]     = tp_b
    logger.info("[%s] Stage B: hits=%d  recall=%.4f  tp=%d", pid, len(pmids_b), recall_b, tp_b)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", action="append", default=[])
    parser.add_argument("--no-stage-b", action="store_true", default=False)
    parser.add_argument("--provider", default="claude", choices=["claude", "codex", "gemini"],
                        help="Provider whose with_laws_test_eval query is used as input (default: claude)")
    args = parser.parse_args()
    paper_filter = set(args.paper) if args.paper else None
    # Phase 5 (LLM full rewrite) is handled externally by the main Claude Code
    # conversation via Agent tool subagents. See phase5_manual_prompt.md.

    papers = []
    for domain, pid in TRAINING_PAPERS:
        if paper_filter and pid not in paper_filter and pid.split("_")[0] not in paper_filter:
            continue
        p = load_paper(domain, pid, provider=args.provider)
        if p:
            papers.append(p)
        else:
            logger.warning("Could not load paper %s/%s", domain, pid)

    logger.info("Loaded %d papers", len(papers))

    results = []
    for paper in papers:
        r = eval_paper(paper, run_stage_b=not args.no_stage_b)
        results.append(r)

    # ── Print summary table ───────────────────────────────────────────
    print("\n" + "=" * 110)
    print(f"{'paper_id':<18} {'gold':>4}  "
          f"{'base_hits':>9} {'base_R':>6}  "
          f"{'A\'_hits':>9} {'A\'_R':>6} {'A\'_note':<22}  "
          f"{'A_hits':>9} {'A_R':>6} {'A_NOT':<35}  "
          f"{'B_hits':>9} {'B_R':>6}")
    print("-" * 110)
    for r in results:
        ap_hits = str(r.get("a_prime_hits") or "-").rjust(9)
        ap_rec  = f"{r['a_prime_recall']:.4f}" if r.get("a_prime_recall") is not None else "  -  "
        ap_note = (r.get("a_prime_note") or "-")[:22]
        bh      = str(r.get("stage_b_hits") or r.get("stage_b_note") or "-").rjust(9)
        br      = f"{r['stage_b_recall']:.4f}" if r.get("stage_b_recall") is not None else "  -  "
        not_app = (r.get("stage_a_not_applied") or "-")[:35]
        print(
            f"{r['paper_id']:<18} {r['gold_n']:>4}  "
            f"{r['base_hits']:>9} {r['base_recall']:.4f}  "
            f"{ap_hits} {ap_rec} {ap_note:<22}  "
            f"{r['stage_a_hits']:>9} {r['stage_a_recall']:.4f} {not_app:<35}  "
            f"{bh} {br}"
        )
    print("=" * 110)

    # Save JSON
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"eval_training11_stages_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("Saved: %s", out_path)


if __name__ == "__main__":
    main()
