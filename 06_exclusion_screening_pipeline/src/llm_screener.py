"""
Stage D: Bounded LLM Screener
Applies Abstract ScreenPrompt to candidates_C (capped at K per paper).

Hard rules:
- Abstract missing → UNCERTAIN → retain (no LLM call)
- temperature=0 for reproducibility
- INCLUDE + UNCERTAIN → keep; EXCLUDE → drop
"""
from __future__ import annotations
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_SCREEN_PROMPT = """\
You are an expert systematic review screener.

## Study objective
{objectives}

## Inclusion criteria
{inclusion_criteria}

## Exclusion criteria
{exclusion_criteria}

## Task
Read the abstract below. Decide: INCLUDE, EXCLUDE, or UNCERTAIN.
Rules:
- INCLUDE: meets inclusion criteria, no clear exclusion criterion applies
- EXCLUDE: a specific exclusion criterion clearly applies — state which one
- UNCERTAIN: information missing, abstract unavailable, or borderline — default to UNCERTAIN (err toward inclusion)
Output format (two lines only):
DECISION: <INCLUDE|EXCLUDE|UNCERTAIN>
REASON: <one sentence; if EXCLUDE, name the specific criterion>

## Abstract
PMID: {pmid}
Title: {title}
Abstract: {abstract}"""


def _parse_decision(text: str) -> tuple[str, str]:
    """Extract DECISION and REASON from LLM output."""
    decision = "UNCERTAIN"
    reason = ""
    for line in text.strip().splitlines():
        line = line.strip()
        m = re.match(r"DECISION:\s*(INCLUDE|EXCLUDE|UNCERTAIN)", line, re.IGNORECASE)
        if m:
            decision = m.group(1).upper()
        m2 = re.match(r"REASON:\s*(.+)", line, re.IGNORECASE)
        if m2:
            reason = m2.group(1).strip()
    return decision, reason


class LLMScreener:
    """
    Screens a list of records using Claude API.
    Budget-aware: skips if record count exceeds cap (should be pre-truncated by ranker).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-5",
        batch_size: int = 50,
        min_interval: float = 0.2,
    ):
        self.model = model
        self.batch_size = batch_size
        self.min_interval = min_interval
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self._available = True
        except ImportError:
            logger.warning("anthropic package not installed. LLM screening disabled.")
            self.client = None
            self._available = False

    def screen(
        self,
        records: list[dict],
        objectives: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
        log_path: Optional[Path] = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Screen records. Returns (retained, excluded).
        retained = INCLUDE + UNCERTAIN
        excluded = EXCLUDE only
        """
        retained: list[dict] = []
        excluded: list[dict] = []
        log_entries: list[dict] = []

        for rec in records:
            pmid = rec.get("pmid", "")
            title = rec.get("title", "")
            abstract = rec.get("abstract", "")

            # Hard rule: abstract missing → UNCERTAIN → retain
            if not abstract or not abstract.strip():
                result = {
                    **rec,
                    "_stage_d_decision": "UNCERTAIN",
                    "_stage_d_reason": "Abstract not available — retained by default (recall protection)",
                    "_stage_d_llm_called": False,
                }
                retained.append(result)
                log_entries.append({
                    "pmid": pmid,
                    "decision": "UNCERTAIN",
                    "reason": result["_stage_d_reason"],
                    "llm_called": False,
                })
                continue

            if not self._available:
                # No LLM → default UNCERTAIN
                result = {
                    **rec,
                    "_stage_d_decision": "UNCERTAIN",
                    "_stage_d_reason": "LLM not available — retained by default",
                    "_stage_d_llm_called": False,
                }
                retained.append(result)
                continue

            decision, reason = self._call_llm(
                pmid=pmid,
                title=title,
                abstract=abstract,
                objectives=objectives,
                inclusion_criteria=inclusion_criteria,
                exclusion_criteria=exclusion_criteria,
            )

            result = {
                **rec,
                "_stage_d_decision": decision,
                "_stage_d_reason": reason,
                "_stage_d_llm_called": True,
            }

            log_entries.append({
                "pmid": pmid,
                "decision": decision,
                "reason": reason,
                "llm_called": True,
            })

            if decision == "EXCLUDE":
                excluded.append(result)
            else:
                retained.append(result)

            time.sleep(self.min_interval)

        if log_path:
            with open(log_path, "w", encoding="utf-8") as f:
                for entry in log_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(
            "Stage D: %d retained, %d excluded (of %d total)",
            len(retained), len(excluded), len(records),
        )
        return retained, excluded

    def _call_llm(
        self,
        pmid: str,
        title: str,
        abstract: str,
        objectives: str,
        inclusion_criteria: str,
        exclusion_criteria: str,
        retries: int = 3,
    ) -> tuple[str, str]:
        prompt = _SCREEN_PROMPT.format(
            objectives=objectives[:600],
            inclusion_criteria=inclusion_criteria[:600],
            exclusion_criteria=exclusion_criteria[:600],
            pmid=pmid,
            title=title[:300],
            abstract=abstract[:800],
        )

        for attempt in range(retries):
            try:
                resp = self.client.messages.create(
                    model=self.model,
                    max_tokens=120,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = resp.content[0].text
                decision, reason = _parse_decision(text)
                return decision, reason
            except Exception as e:
                logger.warning("LLM call failed (attempt %d/%d): %s", attempt + 1, retries, e)
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)

        # All retries failed → UNCERTAIN (recall protection)
        return "UNCERTAIN", "LLM call failed — retained by default (recall protection)"
