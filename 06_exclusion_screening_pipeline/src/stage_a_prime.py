"""Stage A' (Prime Hit Reduction) for test mode — no recall guard.

Extracted from the original test pipeline script.
Public entry point: run_prime_no_recall()
"""
from __future__ import annotations

import logging
import re
import time

from pubmed_fetcher import search_pubmed


logger = logging.getLogger(__name__)


EXCLUSION_DRIVEN_BLOCKS = [
    ("english[lang]", ["english", "language", "non-english"]),
    ('NOT "Meeting Abstract"[pt]', ["conference abstract", "meeting abstract", "abstract only"]),
    ('NOT "Clinical Trial Protocol"[pt]', ["protocol", "trial protocol", "study protocol"]),
    ('NOT "Systematic Review"[pt]', ["systematic review"]),
    ('NOT "Meta-Analysis"[pt]', ["meta-analysis", "meta analysis"]),
    ('NOT "Review"[pt]', ["review", "narrative review"]),
    ('NOT "Case Reports"[pt]', ["case report"]),
    ('NOT "Letter"[pt]', ["letter"]),
    ('NOT "Comment"[pt]', ["commentary", "comment"]),
    ('NOT "Editorial"[pt]', ["editorial"]),
    ('NOT "Interview"[pt]', ["interview"]),
    ('NOT "News"[pt]', ["news"]),
    ('NOT "Published Erratum"[pt]', ["erratum"]),
    ('NOT (animals[mh] NOT humans[mh])', ["animal", "human-only", "humans only", "not humans", "animal-only"]),
    ('("Adult"[Mesh] OR "Middle Aged"[Mesh] OR "Aged"[Mesh])', ["adult", "pediatric", "paediatric", "child", "children", "adolescent"]),
]
EXCLUSION_TRIGGER_MAP = {syntax: triggers for (syntax, triggers) in EXCLUSION_DRIVEN_BLOCKS}

PHASE2_NOT_BLOCKS = [
    'NOT "Letter"[pt]',
    'NOT "Case Reports"[pt]',
    'NOT "Comment"[pt]',
    'NOT "Editorial"[pt]',
    'NOT "Interview"[pt]',
    'NOT (animals[mh] NOT humans[mh])',
]

OBSERVATIONAL_FALLBACK_BLOCKS = [
    'NOT "Review"[pt]',
    'NOT "Letter"[pt]',
    'NOT "Editorial"[pt]',
    'NOT "Comment"[pt]',
    'NOT (animals[mh] NOT humans[mh])',
    'NOT "Case Reports"[pt]',
]

PHASE4_NOT_FALLBACK_BLOCKS = [
    'NOT "Review"[pt]',
    'NOT "Letter"[pt]',
    'NOT "Editorial"[pt]',
    'NOT "Comment"[pt]',
    'NOT (animals[mh] NOT humans[mh])',
    'NOT "Case Reports"[pt]',
]

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


def _in_query(syntax: str, query: str) -> bool:
    return syntax.lower() in query.lower()


def _normalize_text(s: str) -> str:
    return (s or "").lower()


def _is_sr_of_srs(objectives_text: str, inclusion_text: str) -> bool:
    """
    Return True if inclusion criteria or objectives indicate that systematic reviews,
    meta-analyses, or other review types are eligible study types.
    In that case, NOT "Review"[pt] / NOT "Meta-Analysis"[pt] are FORBIDDEN (SR-of-SRs exception).
    """
    combined = _normalize_text(objectives_text) + " " + _normalize_text(inclusion_text)
    return any(marker in combined for marker in _SR_OF_SRS_MARKERS)


_REVIEW_NOT_BLOCKS = {
    'NOT "Review"[pt]',
    'NOT "Systematic Review"[pt]',
    'NOT "Meta-Analysis"[pt]',
    'NOT "Scoping Review"[pt]',
}


def _phase1_candidates_from_exclusion(exclusion_text: str, current_query: str, objectives_text: str = "", inclusion_text: str = "") -> list[str]:
    """
    Build Stage A' candidates only from blocks that are explicitly grounded
    in exclusion criteria text.
    SR-of-SRs exception: if objectives/inclusion indicate review-type studies are eligible,
    skip all NOT "Review"[pt] / NOT "Meta-Analysis"[pt] blocks.
    """
    ex = _normalize_text(exclusion_text)
    sr_of_srs = _is_sr_of_srs(objectives_text, inclusion_text)
    out: list[str] = []
    for syntax, triggers in EXCLUSION_DRIVEN_BLOCKS:
        if _in_query(syntax, current_query):
            continue
        if sr_of_srs and syntax in _REVIEW_NOT_BLOCKS:
            logger.info("SR-of-SRs exception: skipping '%s'", syntax)
            continue
        if any(t in ex for t in triggers):
            out.append(syntax)
    return out


def _is_observational_inclusion(inclusion_text: str) -> bool:
    t = _normalize_text(inclusion_text)
    markers = [
        "observational",
        "cohort",
        "case-control",
        "case control",
        "retrospective",
        "prospective",
    ]
    return any(m in t for m in markers)


def _find_base_query_path(paper_dir: Path, provider: str, condition: str) -> Path | None:
    p = paper_dir / "model_outputs" / provider / condition / "normalized_query.txt"
    return p if p.exists() else None


def _phase2_candidates_from_human_query(human_query: str, exclusion_text: str, current_query: str) -> list[str]:
    # v2.0: Metrics AND block (PHASE2_METRICS_BLOCK) removed — Tier 2 AND additions are forbidden.
    # Only NOT-filter blocks are allowed.
    hq = (human_query or "").lower()
    ex = _normalize_text(exclusion_text)
    out: list[str] = []

    for s in PHASE2_NOT_BLOCKS:
        triggers = EXCLUSION_TRIGGER_MAP.get(s, [])
        ex_ok = any(t in ex for t in triggers)
        if ex_ok and s.lower() in hq and not _in_query(s, current_query):
            out.append(s)

    return out


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


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4: PubMed query parser + Tier 1 / 1.5 / 1.8 / 1.9 candidate generators
# ═══════════════════════════════════════════════════════════════════════════

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
    """Strip one layer of matching outer parentheses if present."""
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
            return s  # outermost '(' closes before the last char
    return s[1:-1].strip()


def _parse_and_blocks(raw_query: str) -> list[str]:
    """Return list of OR-block strings (outer parens stripped)."""
    return [_strip_outer_parens(b) for b in _split_top_level(raw_query, ' AND ')]


def _rebuild_raw_query(blocks: list[str]) -> str:
    """Wrap each block in () and join with AND."""
    return ' AND '.join(f'({b})' for b in blocks if b.strip())


def _extract_tiab_texts(block: str) -> list[str]:
    """Return all tiab term strings (without field tag, lower-cased)."""
    texts: list[str] = []
    for m in _RE_TIAB.finditer(block):
        t = m.group(1) or m.group(2)
        if t:
            texts.append(t.lower().strip('"'))
    return texts


def _tiab_covers_mesh(mesh_name: str, tiab_texts: list[str]) -> bool:
    """
    Conservative check: does at least one tiab term in *tiab_texts* cover *mesh_name*?
    Three strategies (any one sufficient):
      1. Wildcard prefix: tiab root (≥4 chars) is a prefix of the normalised mesh name.
      2. Substring: normalised tiab root appears in (or is) normalised mesh name.
      3. Token overlap: ≥1 significant word (≥4 chars) shared.
    """
    def _norm(s: str) -> str:
        return re.sub(r'[^a-z0-9]', '', s.lower())

    mesh_norm   = _norm(mesh_name)
    mesh_tokens = {w for w in re.split(r'\W+', mesh_name.lower()) if len(w) >= 4}

    for tiab in tiab_texts:
        core      = tiab.rstrip('*').split('*')[0]
        tiab_norm = _norm(core)
        if not tiab_norm or len(tiab_norm) < 3:
            continue
        # Strategy 1: wildcard prefix
        if '*' in tiab and len(tiab_norm) >= 4 and mesh_norm.startswith(tiab_norm):
            return True
        # Strategy 2: substring (≥4 chars)
        if len(tiab_norm) >= 4 and (tiab_norm in mesh_norm or mesh_norm in tiab_norm):
            return True
        # Strategy 3: significant token overlap
        tiab_tokens = {w for w in re.split(r'\W+', core.lower()) if len(w) >= 4}
        if mesh_tokens & tiab_tokens:
            return True
    return False


def _remove_term_from_or_block(block: str, term: str) -> str | None:
    """
    Remove *term* from an OR block.
    Returns None if the block would become empty (term was the only one).
    """
    terms = _split_top_level(block, ' OR ')
    term_lo = term.lower().strip()
    new_terms = [t for t in terms if t.lower().strip() != term_lo]
    if not new_terms or len(new_terms) == len(terms):
        # Fallback: substring removal for slight whitespace variations
        new_terms = [t for t in terms if term_lo not in t.lower()]
    if not new_terms:
        return None
    return ' OR '.join(new_terms)


def _replace_term_in_or_block(block: str, old_term: str, new_term: str) -> str | None:
    """Replace *old_term* with *new_term* in an OR block. Returns None if not found."""
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


# ── Tier 1: Remove [Mesh] when tiab backup exists ───────────────────────────

def _tier1_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
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


# ── Tier 2: Remove wildcard-redundant tiab ──────────────────────────────────

def _tier2_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
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

        wildcards    = [(t, txt) for t, txt in tiab_pairs if '*' in txt]
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


# ── Tier 3: Remove generic/broad tiab via word-boundary suffix match ─────────

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
                continue  # skip wildcard terms — they define the scope
            txt_a_norm = txt_a.lower().strip('"').strip()
            if len(txt_a_norm) < 4:
                continue

            is_generic = False
            for term_b, txt_b in tiab_pairs:
                if term_a == term_b:
                    continue
                txt_b_norm = txt_b.lower().strip('"').strip()
                # txt_a is a word-boundary suffix of txt_b AND txt_b is meaningfully longer
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


# ── Tier 5: [tiab] → [ti] when [Mesh] or [Mesh:NoExp] backup exists ──────────

def _tier5_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 5: Replace [tiab] → [ti] (title-only) for terms that have a
    [Mesh] or [Mesh:NoExp] backup in the same OR block.

    Rationale:
      - [Mesh] continues to catch papers indexed under that heading regardless of title/abstract.
      - [ti] catches papers with the keyword in title but no MeSH indexing.
      - Only papers with the keyword exclusively in abstract AND no MeSH tag are lost.
    Safety condition: [Mesh] or [Mesh:NoExp] must exist in the same OR block
    and must 'cover' the tiab concept (via _tiab_covers_mesh check).
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        mesh_names_here = [m.group(1) for m in _RE_MESH.finditer(block)]
        mesh_names_here += [m.group(1) for m in _RE_MESH_NOEXP.finditer(block)]
        if not mesh_names_here:
            continue  # no MeSH backup → too risky

        for m in _RE_TIAB.finditer(block):
            tiab_full = m.group(0)  # e.g. '"heart failure"[tiab]' or 'vaccin*[tiab]'
            tiab_text = (m.group(1) or m.group(2) or '').lower().strip('"')
            if not tiab_text or len(tiab_text.rstrip('*')) < 3:
                continue

            # Only convert if a MeSH in the same block covers this tiab concept
            if any(_tiab_covers_mesh(mn, [tiab_text]) for mn in mesh_names_here):
                ti_full = re.sub(r'\[tiab\]', '[ti]', tiab_full, flags=re.IGNORECASE)
                if ti_full == tiab_full:
                    continue  # regex did not match (shouldn't happen)
                new_block = _replace_term_in_or_block(block, tiab_full, ti_full)
                if new_block is not None:
                    new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
                    candidates.append(
                        (f'ti_{tiab_text[:25]}', _rebuild_raw_query(new_blocks))
                    )

    return candidates


# ── Tier 4: Remove ambiguous uppercase acronym [tiab] when MeSH + full-form backup exist ──

_RE_UPPERCASE_ACRONYM = re.compile(r'(?:"([A-Z][A-Z0-9]{1,3})"|([A-Z][A-Z0-9]{1,3}))\[tiab\]')


def _tier4_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 4: Remove a 2-4 ALL-CAPS acronym [tiab] when the same OR block has
    at least one non-wildcard tiab with >= 8 chars (full-form proxy).
    [Mesh] backup is no longer required — full-form tiab alone is sufficient guard.
    Rationale: short uppercase acronyms (e.g. clinical shorthand) are ambiguous;
    a long full-form tiab provides the necessary coverage.
    Safety guards: no wildcards; pure uppercase letters/digits only; len 2-4.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        # Must have at least one long non-wildcard tiab (full-form proxy)
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


# ── Tier 6: Proximity/phrase substitution for scope-restrictor + content pairs ──

_SCOPE_RESTRICTOR_STEMS = (
    'predict', 'prognos', 'screen', 'diagnos', 'mortalit', 'surviv',
    'inciden', 'prevalenc', 'assess', 'measur', 'outcom',
)


def _tier6_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 6: Replace a scope-restrictor [tiab] with a proximity phrase paired with
    the longest content term in the same OR block.
    Condition: block must have >= 3 tiab terms (safety margin); one is a scope-restrictor
    (predict*, prognos*, screen*, diagnos*, mortalit*, surviv*, inciden*, prevalenc*,
    assess*, measur*, outcom*); another is a content term (>= 6 chars, no wildcard).
    The restrictor is removed standalone and replaced with "restrictor* content"[tiab:~5].
    Proximity window N=5 is generous to minimise recall loss.
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
            continue  # need >= 3 tiab terms for safe removal of one

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

        # Remove standalone restrictor, add proximity phrase
        new_block = _remove_term_from_or_block(block, restr_term)
        if new_block is None:
            continue
        new_block = new_block + f' OR {prox_phrase}'
        new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
        candidates.append(
            (f'prox_{restr_base[:12]}_{content_base[:12]}', _rebuild_raw_query(new_blocks))
        )

    return candidates


# ── Tier 9: Batch-apply [majr] to all eligible terms in the largest AND-block ─

def _tier9_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 9: Batch-convert ALL eligible [Mesh:NoExp] and [Mesh] terms to [majr]
    within the SINGLE AND-block that has the most convertible terms (>= 2).
    More aggressive than Tier 8 (one-at-a-time); use after Tier 8 is exhausted.
    Tiab backup must exist for each term converted. Generates one candidate per
    qualifying block.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        tiabs = _extract_tiab_texts(block)
        if not tiabs:
            continue

        conversions: list[tuple[str, str]] = []  # (old_text, new_text)
        for m in _RE_MESH_NOEXP.finditer(block):
            name = m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                conversions.append((m.group(0), f'"{name}"[majr]'))
        for m in _RE_MESH.finditer(block):
            name = m.group(1)
            if _tiab_covers_mesh(name, tiabs):
                conversions.append((m.group(0), f'"{name}"[majr]'))

        if len(conversions) < 2:
            continue  # only batch when >= 2 terms

        new_block = block
        for old, new_term in conversions:
            new_block = new_block.replace(old, new_term)

        if new_block != block:
            new_blocks = blocks[:idx] + [new_block] + blocks[idx + 1:]
            candidates.append(
                (f'batch_majr_blk{idx}', _rebuild_raw_query(new_blocks))
            )

    return candidates


# ── Tier 10: Wildcard-pair proximity substitution ────────────────────────────

def _tier10_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
    """Tier 10: Replace a pair of wildcard [tiab] terms in the same OR block
    with a proximity phrase "stem1* stem2*"[tiab:~3].
    Conditions:
      - both stems >= 4 chars (after stripping wildcard)
      - block must have >= 3 tiab terms total (safety margin)
    More general than Tier 6: not limited to scope-restrictors.
    Generates one candidate per qualifying wildcard pair.
    """
    blocks = _parse_and_blocks(raw_query)
    candidates: list[tuple[str, str]] = []

    for idx, block in enumerate(blocks):
        terms = _split_top_level(block, ' OR ')
        all_tiabs = [t for t in terms if '[tiab]' in t.lower()]
        if len(all_tiabs) < 3:
            continue  # need >= 3 tiab terms for safe removal of one

        # Collect wildcard tiab terms with their stems
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

        # Generate one candidate per ordered pair (i < j)
        for i, (term_a, stem_a) in enumerate(tiab_wildcards):
            for j, (term_b, stem_b) in enumerate(tiab_wildcards):
                if j <= i:
                    continue
                prox_phrase = f'"{stem_a}* {stem_b}*"[tiab:~3]'
                # Remove term_a, replace term_b with proximity phrase
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


# ── Tier 7: [Mesh] → [Mesh:NoExp] ───────────────────────────────────────────

def _tier7_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
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


# ── Tier 8: [Mesh:NoExp] → [majr] ───────────────────────────────────────────

def _tier8_candidates_from_raw(raw_query: str) -> list[tuple[str, str]]:
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


def _phase4_dynamic_candidates(current_query: str, current_raw: str, current_suffix: str, sr_of_srs: bool = False) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    # Tier 1: Remove [Mesh] when tiab backup exists in same OR block
    for desc, new_raw in _tier1_candidates_from_raw(current_raw):
        candidates.append((f"tier1_{desc}", new_raw + current_suffix))

    # Tier 2: Remove wildcard-redundant tiab terms
    for desc, new_raw in _tier2_candidates_from_raw(current_raw):
        candidates.append((f"tier2_{desc}", new_raw + current_suffix))

    # Tier 3: Remove generic/broad tiab via word-boundary suffix match
    for desc, new_raw in _tier3_candidates_from_raw(current_raw):
        candidates.append((f"tier3_{desc}", new_raw + current_suffix))

    # Tier 4: Remove ambiguous uppercase acronym [tiab] when full-form tiab backup exists (>= 8 chars)
    for desc, new_raw in _tier4_candidates_from_raw(current_raw):
        candidates.append((f"tier4_{desc}", new_raw + current_suffix))

    # Tier 5: Replace [tiab] → [ti] when [Mesh] or [Mesh:NoExp] backup exists
    for desc, new_raw in _tier5_candidates_from_raw(current_raw):
        candidates.append((f"tier5_{desc}", new_raw + current_suffix))

    # Tier 6: Proximity/phrase substitution for scope-restrictor + content pairs
    for desc, new_raw in _tier6_candidates_from_raw(current_raw):
        candidates.append((f"tier6_{desc}", new_raw + current_suffix))

    # Tier 7: Replace [Mesh] → [Mesh:NoExp]
    for desc, new_raw in _tier7_candidates_from_raw(current_raw):
        candidates.append((f"tier7_{desc}", new_raw + current_suffix))

    # Tier 8: Replace [Mesh:NoExp] → [majr]
    for desc, new_raw in _tier8_candidates_from_raw(current_raw):
        candidates.append((f"tier8_{desc}", new_raw + current_suffix))

    # Tier 9: Batch-apply [majr] to all eligible terms in the largest AND-block
    for desc, new_raw in _tier9_candidates_from_raw(current_raw):
        candidates.append((f"tier9_{desc}", new_raw + current_suffix))

    # Tier 10: Wildcard-pair proximity substitution (any pair in same OR block)
    for desc, new_raw in _tier10_candidates_from_raw(current_raw):
        candidates.append((f"tier10_{desc}", new_raw + current_suffix))

    # Tier F: NOT publication-type filters (suffix expansion)
    for blk in PHASE4_NOT_FALLBACK_BLOCKS:
        if sr_of_srs and blk in _REVIEW_NOT_BLOCKS:
            logger.info("SR-of-SRs exception: skipping Phase 4 '%s'", blk)
            continue
        if not _in_query(blk, current_query):
            candidates.append((f"tierF_{blk}", (current_raw + current_suffix + " " + blk).strip()))

    return candidates


def _run_phase4_infinite_no_recall(
    current_query: str,
    current_hits: int,
    target_hits: int,
    strict_less_than: bool,
    history: list[dict],
    sr_of_srs: bool = False,
) -> tuple[str, int, dict]:
    """
    Phase 4 infinite iteration (v2.0: Tier 2 AND blocks removed):
      - regenerate candidates every round from current query
      - continue until goal achieved OR no candidate reduces hits in a full round
    """
    def _reached(h: int) -> bool:
        return (h < target_hits) if strict_less_than else (h <= target_hits)

    rounds = 0
    accepted_mods = 0
    current_raw, current_suffix = _split_raw_and_suffix(current_query)

    while not _reached(current_hits):
        rounds += 1
        candidates = _phase4_dynamic_candidates(current_query, current_raw, current_suffix, sr_of_srs=sr_of_srs)
        if not candidates:
            return current_query, current_hits, {
                "phase4_attempted": True,
                "phase4_rounds": rounds,
                "phase4_modifications_applied": accepted_mods,
                "phase4_no_further_reduction": True,
            }

        improved: list[tuple[str, str, int]] = []
        for name, test_query in candidates:
            test_hits, _ = search_pubmed(test_query, retmax=1)
            is_improved = test_hits < current_hits
            history.append(
                {
                    "phase": 4,
                    "round": rounds,
                    "block": name,
                    "hits_before": current_hits,
                    "hits_after": test_hits,
                    "accepted": False,
                    "reason": "candidate_evaluated",
                }
            )
            # Guard: reject 0-hit candidates (likely PubMed rate-limit soft-throttle response)
            if is_improved and test_hits > 0:
                improved.append((name, test_query, test_hits))

        if not improved:
            return current_query, current_hits, {
                "phase4_attempted": True,
                "phase4_rounds": rounds,
                "phase4_modifications_applied": accepted_mods,
                "phase4_no_further_reduction": True,
            }

        # Objective: closest hit count to target among improved candidates.
        name, next_query, next_hits = min(improved, key=lambda x: abs(x[2] - target_hits))
        prev_hits = current_hits
        current_query = next_query
        current_hits = next_hits
        accepted_mods += 1
        current_raw, current_suffix = _split_raw_and_suffix(current_query)

        history.append(
            {
                "phase": 4,
                "round": rounds,
                "block": name,
                "hits_before": prev_hits,
                "hits_after": current_hits,
                "accepted": True,
                "reason": "objective_closest_to_target",
            }
        )

    return current_query, current_hits, {
        "phase4_attempted": True,
        "phase4_rounds": rounds,
        "phase4_modifications_applied": accepted_mods,
        "phase4_no_further_reduction": False,
    }



def run_prime_no_recall(
    base_query: str,
    inclusion_text: str,
    exclusion_text: str,
    human_query: str,
    target_hits: int = 9999,
    strict_less_than: bool = True,
    phase2_max_rounds: int = 10,
    objectives_text: str = "",
) -> tuple[str, int, dict]:
    """
    Stage A' in test mode (v2.3):
    - hit-reduction only, no recall calculation
    - Tier 2 AND blocks removed; SR-of-SRs exception enforced
    - Phase 5 (LLM full rewrite) triggered if Phase 4 exhausted and still > target
    """
    current_query = base_query
    current_hits, _ = search_pubmed(current_query, retmax=1)
    history = []

    sr_of_srs = _is_sr_of_srs(objectives_text, inclusion_text)
    if sr_of_srs:
        logger.info("SR-of-SRs exception ACTIVE: NOT 'Review'[pt] / NOT 'Meta-Analysis'[pt] will be skipped")

    # Phase 1 (exclusion-driven only)
    phase1_blocks = _phase1_candidates_from_exclusion(exclusion_text, current_query, objectives_text=objectives_text, inclusion_text=inclusion_text)
    rejected_by_overshoot: set[str] = set()

    while True:
        candidates = [
            b for b in phase1_blocks
            if (b not in rejected_by_overshoot) and (not _in_query(b, current_query))
        ]
        if not candidates:
            break

        evaluations = []
        for blk in candidates:
            test_query = current_query + " " + blk
            test_hits, _ = search_pubmed(test_query, retmax=1)
            improved = test_hits < current_hits
            history.append(
                {
                    "phase": 1,
                    "block": blk,
                    "hits_before": current_hits,
                    "hits_after": test_hits,
                    "accepted": False,
                    "reason": "candidate_evaluated",
                }
            )
            if improved:
                evaluations.append((blk, test_hits, test_query))

        if not evaluations:
            break

        # Objective function: prioritize query hits closest to target (9999).
        # Prefer values below target only if they are at least as close as the best above-target option.
        under = [(b, h, q) for (b, h, q) in evaluations if (h < target_hits if strict_less_than else h <= target_hits)]
        over = [(b, h, q) for (b, h, q) in evaluations if (h >= target_hits if strict_less_than else h > target_hits)]

        best_under = min(under, key=lambda x: abs(x[1] - target_hits)) if under else None
        best_over = min(over, key=lambda x: abs(x[1] - target_hits)) if over else None

        chosen = None
        if best_under and best_over:
            # Overshoot backtrack guard: if below-target candidate is farther than a viable above-target candidate,
            # do not overshoot now; move closer from above first.
            if abs(best_under[1] - target_hits) > abs(best_over[1] - target_hits):
                rejected_by_overshoot.add(best_under[0])
                history.append(
                    {
                        "phase": 1,
                        "block": best_under[0],
                        "hits_before": current_hits,
                        "hits_after": best_under[1],
                        "accepted": False,
                        "reason": "overshoot_backtrack",
                    }
                )
                chosen = best_over
            else:
                chosen = best_under
        elif best_under:
            chosen = best_under
        else:
            chosen = best_over

        prev_hits = current_hits
        blk, next_hits, next_query = chosen
        current_query = next_query
        current_hits = next_hits
        history.append(
            {
                "phase": 1,
                "block": blk,
                "hits_before": prev_hits,
                "hits_after": current_hits,
                "accepted": True,
                "reason": "objective_closest_to_target",
            }
        )

        reached = (current_hits < target_hits) if strict_less_than else (current_hits <= target_hits)
        if reached:
            return current_query, current_hits, {"phase2_attempted": False, "history": history}

    # Phase 2: inclusion-based fallback (only when observational inclusion is present)
    if current_hits > target_hits and _is_observational_inclusion(inclusion_text):
        while True:
            candidates = [
                b for b in OBSERVATIONAL_FALLBACK_BLOCKS
                if not _in_query(b, current_query)
                and not (sr_of_srs and b in _REVIEW_NOT_BLOCKS)
            ]
            if not candidates:
                break

            evaluations = []
            for blk in candidates:
                test_query = current_query + " " + blk
                test_hits, _ = search_pubmed(test_query, retmax=1)
                improved = test_hits < current_hits
                history.append(
                    {
                        "phase": 2,
                        "block": blk,
                        "hits_before": current_hits,
                        "hits_after": test_hits,
                        "accepted": False,
                        "reason": "candidate_evaluated",
                    }
                )
                if improved:
                    evaluations.append((blk, test_hits, test_query))

            if not evaluations:
                break

            chosen = min(evaluations, key=lambda x: abs(x[1] - target_hits))
            prev_hits = current_hits
            blk, next_hits, next_query = chosen
            current_query = next_query
            current_hits = next_hits
            history.append(
                {
                    "phase": 2,
                    "block": blk,
                    "hits_before": prev_hits,
                    "hits_after": current_hits,
                    "accepted": True,
                    "reason": "observational_fallback_closest_to_target",
                }
            )

            reached = (current_hits < target_hits) if strict_less_than else (current_hits <= target_hits)
            if reached:
                return current_query, current_hits, {"phase2_attempted": True, "phase2_no_further_reduction": False, "history": history}

    # Phase 3 (mandatory if still > target): human-query-informed additions
    phase2_attempted = current_hits > target_hits
    phase2_no_further_reduction = False
    if phase2_attempted:
        phase2_blocks = _phase2_candidates_from_human_query(human_query, exclusion_text, current_query)
        for round_idx in range(1, phase2_max_rounds + 1):
            any_accepted = False
            for blk in phase2_blocks:
                if _in_query(blk, current_query):
                    continue
                test_query = current_query + " " + blk
                test_hits, _ = search_pubmed(test_query, retmax=1)
                accepted = test_hits < current_hits
                history.append(
                    {
                        "phase": 2,
                        "round": round_idx,
                        "block": blk,
                        "hits_before": current_hits,
                        "hits_after": test_hits,
                        "accepted": accepted,
                    }
                )
                if accepted:
                    current_query = test_query
                    current_hits = test_hits
                    any_accepted = True
                    reached = (current_hits < target_hits) if strict_less_than else (current_hits <= target_hits)
                    if reached:
                        return current_query, current_hits, {
                            "phase2_attempted": True,
                            "phase2_no_further_reduction": False,
                            "history": history,
                        }
            if not any_accepted:
                phase2_no_further_reduction = True
                break

    phase4_meta = {
        "phase4_attempted": False,
        "phase4_rounds": 0,
        "phase4_modifications_applied": 0,
        "phase4_no_further_reduction": False,
    }
    reached = (current_hits < target_hits) if strict_less_than else (current_hits <= target_hits)
    if not reached:
        current_query, current_hits, phase4_meta = _run_phase4_infinite_no_recall(
            current_query=current_query,
            current_hits=current_hits,
            target_hits=target_hits,
            strict_less_than=strict_less_than,
            history=history,
            sr_of_srs=sr_of_srs,
        )

    # Phase 5 (LLM full query rewrite) is handled externally by the main Claude Code
    # conversation via Agent tool subagents. See phase5_llm_rewrite_prompt.md.
    return current_query, current_hits, {
        "phase2_attempted": phase2_attempted,
        "phase2_no_further_reduction": phase2_no_further_reduction,
        "history": history,
        **phase4_meta,
    }
