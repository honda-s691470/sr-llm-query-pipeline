"""
Stage A + B: Exclusion Criteria Parser
Parses free-text exclusion_criteria -> structured tags + safe NOT candidates.

Hard constraint: only publication_type and animal_only NOT templates are allowed
at query time. All other NOT suggestions from LLM are silently dropped.
"""
from __future__ import annotations
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Hard-coded allowlist (Stage A hard constraint)
# LLM may suggest others, but only these are applied.
# ─────────────────────────────────────────────
ALLOWED_NOT_TEMPLATES: dict[str, list[str]] = {
    "publication_type": [
        'NOT "Case Reports"[pt]',
        'NOT "Letter"[pt]',
        'NOT "Editorial"[pt]',
        'NOT "Comment"[pt]',
        'NOT "News"[pt]',
        'NOT "Published Erratum"[pt]',
        'NOT "Retracted Publication"[pt]',
    ],
    "animal_only": [
        'NOT (animals[mh] NOT humans[mh])',
    ],
}

# Flat set for lookup
_ALL_ALLOWED: set[str] = {t for group in ALLOWED_NOT_TEMPLATES.values() for t in group}

# ─────────────────────────────────────────────
# Tag definitions (Stage B metadata filter)
# ─────────────────────────────────────────────
ExclusionTag = Literal[
    "STUDY_TYPE_EXCLUDE",
    "SPECIES_EXCLUDE",
    "LANGUAGE_EXCLUDE",
    "POPULATION_EXCLUDE",
    "DATA_QUALITY_EXCLUDE",
    "OTHER",
]


@dataclass
class ParsedExclusion:
    raw_text: str
    tags: list[ExclusionTag] = field(default_factory=list)
    safe_not_candidates: list[str] = field(default_factory=list)  # pre-filter by allowlist
    safe_not_applied: list[str] = field(default_factory=list)      # after allowlist filter
    dropped_not_candidates: list[str] = field(default_factory=list)  # rejected by allowlist
    confidence: float = 0.0  # 0-1, rough estimate based on keyword hits


# ─────────────────────────────────────────────
# Rule-based pre-parser (no LLM needed for common patterns)
# ─────────────────────────────────────────────

_STUDY_TYPE_PATTERNS = [
    r"\bcase\s+report[s]?\b",
    r"\bcase\s+series\b",
    r"\bletter[s]?\b",
    r"\beditorial[s]?\b",
    r"\bcomment[s]?\b",
    r"\bnews\b",
    r"\bconference\s+abstract[s]?\b",
    r"\bmeeting\s+abstract[s]?\b",
    r"\bprotocol[s]?\b",
    r"\berrat[ua]m\b",
    r"\bnarrative\s+review[s]?\b",
    r"\bbook\s+chapter[s]?\b",
]

_STUDY_TYPE_TO_NOT: dict[str, str] = {
    r"\bcase\s+report[s]?\b":        'NOT "Case Reports"[pt]',
    r"\bcase\s+series\b":            'NOT "Case Reports"[pt]',
    r"\bletter[s]?\b":               'NOT "Letter"[pt]',
    r"\beditorial[s]?\b":            'NOT "Editorial"[pt]',
    r"\bcomment[s]?\b":              'NOT "Comment"[pt]',
    r"\bnews\b":                     'NOT "News"[pt]',
    r"\bconference\s+abstract[s]?\b": 'NOT "Published Erratum"[pt]',
    r"\bmeeting\s+abstract[s]?\b":   'NOT "Published Erratum"[pt]',
}

_ANIMAL_PATTERNS = [
    r"\banimal[s]?\s+(stud|model|experiment|only)\b",
    r"\bnon-human\b",
    r"\bin\s+vitro\s+only\b",
    r"\bcell\s+line[s]?\b",
    r"\bmurine\b",
    r"\brodent[s]?\b",
]

_LANGUAGE_PATTERNS = [
    r"\bnon-english\b",
    r"\bnon\s+english\b",
    r"\bnot\s+(?:in\s+)?english\b",
    r"\blanguage\s+(?:restriction|limit)\b",
    r"\benglish[\s-]only\b",
    r"\bpublished\s+in\s+(?:languages?\s+other\s+than\s+)?english\b",
]

_POPULATION_PATTERNS = [
    r"\bpediatric[s]?\b",
    r"\bchildren\s+only\b",
    r"\belderly\s+only\b",
    r"\bage\s+(?:restriction|limit)\b",
]

_DATA_QUALITY_PATTERNS = [
    r"\binsufficient\s+(?:data|outcome|information)\b",
    r"\bnot\s+(?:enough|sufficient)\s+data\b",
    r"\bno\s+comparator\b",
    r"\bmissing\s+(?:data|outcome)\b",
    r"\bextract(?:able|ion)\s+(?:data|quantitative)\b",
    r"\bincomplete\s+data\b",
]


def _match_any(text: str, patterns: list[str]) -> bool:
    text_lower = text.lower()
    return any(re.search(p, text_lower) for p in patterns)


def _collect_not_candidates(text: str) -> list[str]:
    """Collect potential NOT terms from text using rule matching."""
    candidates: list[str] = []
    text_lower = text.lower()
    for pattern, not_term in _STUDY_TYPE_TO_NOT.items():
        if re.search(pattern, text_lower):
            if not_term not in candidates:
                candidates.append(not_term)
    if _match_any(text, _ANIMAL_PATTERNS):
        t = 'NOT (animals[mh] NOT humans[mh])'
        if t not in candidates:
            candidates.append(t)
    return candidates


def parse_exclusion_criteria(exclusion_text: str) -> ParsedExclusion:
    """
    Rule-based parse of free-text exclusion criteria.
    Returns ParsedExclusion with tags and safe NOT candidates (allowlist-filtered).
    """
    result = ParsedExclusion(raw_text=exclusion_text)

    if _match_any(exclusion_text, _STUDY_TYPE_PATTERNS):
        result.tags.append("STUDY_TYPE_EXCLUDE")

    if _match_any(exclusion_text, _ANIMAL_PATTERNS):
        result.tags.append("SPECIES_EXCLUDE")

    if _match_any(exclusion_text, _LANGUAGE_PATTERNS):
        result.tags.append("LANGUAGE_EXCLUDE")

    if _match_any(exclusion_text, _POPULATION_PATTERNS):
        result.tags.append("POPULATION_EXCLUDE")

    if _match_any(exclusion_text, _DATA_QUALITY_PATTERNS):
        result.tags.append("DATA_QUALITY_EXCLUDE")

    if not result.tags:
        result.tags.append("OTHER")

    # Collect NOT candidates
    candidates = _collect_not_candidates(exclusion_text)
    result.safe_not_candidates = candidates

    # Apply allowlist hard constraint
    for cand in candidates:
        if cand in _ALL_ALLOWED:
            result.safe_not_applied.append(cand)
        else:
            result.dropped_not_candidates.append(cand)
            logger.warning(
                "NOT candidate rejected by allowlist (hard constraint): %s", cand
            )

    # Deduplicate applied
    result.safe_not_applied = list(dict.fromkeys(result.safe_not_applied))

    # Confidence: simple heuristic based on tag count and NOT match count
    tag_score = min(len([t for t in result.tags if t != "OTHER"]) / 3.0, 1.0)
    not_score = min(len(result.safe_not_applied) / 2.0, 1.0)
    result.confidence = round((tag_score * 0.6 + not_score * 0.4), 2)

    return result


def apply_safe_not_to_query(base_query: str, parsed: ParsedExclusion) -> str:
    """
    Append safe NOT clauses to a PubMed Boolean query.
    Only uses safe_not_applied (already allowlist-filtered).
    """
    if not parsed.safe_not_applied:
        return base_query

    not_block = " ".join(parsed.safe_not_applied)
    return f"({base_query}) {not_block}"


def parse_and_log(
    paper_id: str,
    exclusion_text: str,
    base_query: str,
    log_path=None,
) -> tuple[ParsedExclusion, str]:
    """
    Parse exclusion criteria, apply safe NOTs, and optionally write a JSON log.
    Returns (parsed_result, modified_query).
    """
    parsed = parse_exclusion_criteria(exclusion_text)
    modified_query = apply_safe_not_to_query(base_query, parsed)

    log_entry = {
        "paper_id": paper_id,
        "tags": parsed.tags,
        "safe_not_applied": parsed.safe_not_applied,
        "dropped_not_candidates": parsed.dropped_not_candidates,
        "confidence": parsed.confidence,
        "query_changed": modified_query != base_query,
    }

    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    else:
        logger.info("Exclusion parse result: %s", json.dumps(log_entry, ensure_ascii=False))

    return parsed, modified_query


# ─────────────────────────────────────────────
# Stage B: Deterministic metadata post-filter
# ─────────────────────────────────────────────

# PubMed publication types that are safe to exclude
_EXCLUDE_PUB_TYPES: set[str] = {
    "letter",
    "editorial",
    "comment",
    "news",
    "published erratum",
    "retracted publication",
    "congress",
    "biography",
    "address",
}


def _case_reports_exclusion_enabled(parsed: ParsedExclusion) -> bool:
    """
    Enable case-report exclusion only when explicitly indicated in exclusion criteria.
    We treat explicit indication as presence of the allowlisted NOT term.
    """
    return 'NOT "Case Reports"[pt]' in parsed.safe_not_applied


def stage_b_filter(
    records: list[dict],
    parsed: ParsedExclusion,
    conservative: bool = True,
) -> tuple[list[dict], list[dict]]:
    """
    Stage B deterministic post-filter using PubMed metadata.

    Args:
        records: list of dicts with keys: pmid, pub_types (list[str]),
                 species_mesh (list[str]), languages (list[str])
        parsed: ParsedExclusion with tags
        conservative: if True, keep records with missing metadata (default True)

    Returns:
        (kept, excluded) record lists
    """
    kept: list[dict] = []
    excluded: list[dict] = []

    for rec in records:
        reason = _stage_b_check(rec, parsed, conservative)
        if reason:
            rec = {**rec, "_stage_b_exclude_reason": reason}
            excluded.append(rec)
        else:
            kept.append(rec)

    return kept, excluded


def _stage_b_check(
    rec: dict,
    parsed: ParsedExclusion,
    conservative: bool,
) -> str | None:
    """Return exclusion reason string, or None if the record should be kept."""

    pub_types: list[str] = [t.lower() for t in rec.get("pub_types", [])]
    species: list[str] = [s.lower() for s in rec.get("species_mesh", [])]
    langs: list[str] = [l.lower() for l in rec.get("languages", [])]

    # Publication type filter
    if "STUDY_TYPE_EXCLUDE" in parsed.tags:
        if not pub_types:
            if conservative:
                return None  # missing metadata → keep
        else:
            case_reports_enabled = _case_reports_exclusion_enabled(parsed)
            for pt in pub_types:
                if pt == "case reports":
                    if case_reports_enabled:
                        return "STUDY_TYPE_EXCLUDE: pub_type=case reports"
                    continue
                if pt in _EXCLUDE_PUB_TYPES:
                    return f"STUDY_TYPE_EXCLUDE: pub_type={pt}"

    # Species filter: exclude if animal-only (no humans)
    if "SPECIES_EXCLUDE" in parsed.tags:
        if species:
            has_animal = any("animal" in s for s in species)
            has_human = any("human" in s for s in species)
            if has_animal and not has_human:
                return "SPECIES_EXCLUDE: animal-only"
        # If species metadata missing → conservative keep

    # Language filter (only apply if tag is present and metadata available)
    if "LANGUAGE_EXCLUDE" in parsed.tags:
        if langs and langs != [""]:
            # Keep English; exclude if non-English confirmed
            has_english = any("eng" in l for l in langs)
            if not has_english and langs:
                return f"LANGUAGE_EXCLUDE: language={langs}"
        # If missing → keep

    return None
