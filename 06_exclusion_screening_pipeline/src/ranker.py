"""
Stage C: Retrieval Ranker
Hybrid dense (sentence-transformers) + sparse (BM25) ranking.
Supports HyDE (Hypothetical Document Embeddings) as optional query enhancement.

Model default: all-MiniLM-L6-v2 (lightweight, no GPU needed).
MedCPT can be used as a drop-in replacement if available.
"""
from __future__ import annotations
import math
import logging
import re
import os
from typing import Optional
from collections import Counter

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# BM25 (pure Python, no external dependency)
# ─────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class BM25:
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_tokens = [_tokenize(doc) for doc in corpus]
        self.n = len(corpus)
        self.avgdl = sum(len(t) for t in self.corpus_tokens) / max(self.n, 1)
        self.df: dict[str, int] = {}
        for tokens in self.corpus_tokens:
            for term in set(tokens):
                self.df[term] = self.df.get(term, 0) + 1

    def score(self, query: str, doc_idx: int) -> float:
        query_tokens = _tokenize(query)
        doc_tokens = self.corpus_tokens[doc_idx]
        tf_map = Counter(doc_tokens)
        dl = len(doc_tokens)
        score = 0.0
        for term in query_tokens:
            if term not in self.df:
                continue
            df = self.df[term]
            idf = math.log((self.n - df + 0.5) / (df + 0.5) + 1)
            tf = tf_map.get(term, 0)
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            score += idf * numerator / denominator
        return score

    def score_all(self, query: str) -> list[float]:
        return [self.score(query, i) for i in range(self.n)]


# ─────────────────────────────────────────────
# Dense Embedder (sentence-transformers)
# ─────────────────────────────────────────────

def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


class DenseRanker:
    """Wrapper around sentence-transformers SentenceTransformer."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", device: str = "auto"):
        try:
            from sentence_transformers import SentenceTransformer
            self.device = device
            self.model = SentenceTransformer(model_name, device=None if device == "auto" else device)
            self.model_name = model_name
            logger.info("Loaded dense model: %s (device=%s)", model_name, self.device)
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. Dense ranking disabled. "
                "Run: pip install sentence-transformers"
            )
            self.model = None
            self.model_name = None
            self.device = "cpu"

    def encode(self, texts: list[str]) -> list[list[float]]:
        if self.model is None:
            return [[0.0] for _ in texts]
        vecs = self.model.encode(texts, batch_size=64, show_progress_bar=False)
        return [v.tolist() for v in vecs]

    def available(self) -> bool:
        return self.model is not None


class MedCPTDenseRanker:
    """
    Dense ranker using MedCPT dual encoders (query/article).
    Falls back to unavailable state if transformers/model load fails.
    """

    def __init__(
        self,
        query_model_name: str = "ncbi/MedCPT-Query-Encoder",
        article_model_name: str = "ncbi/MedCPT-Article-Encoder",
        device: str = "auto",
    ):
        self.query_model_name = query_model_name
        self.article_model_name = article_model_name
        self.q_tokenizer = None
        self.q_model = None
        self.a_tokenizer = None
        self.a_model = None

        self.device = "cpu"
        self.requested_device = device
        try:
            import torch
            from transformers import AutoModel, AutoTokenizer

            self._torch = torch
            if device == "auto":
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            elif str(device).startswith("cuda"):
                if torch.cuda.is_available():
                    self.device = device
                else:
                    logger.warning("Requested device=%s but CUDA is unavailable. Falling back to CPU.", device)
                    self.device = "cpu"
            else:
                self.device = "cpu"

            self.q_tokenizer = AutoTokenizer.from_pretrained(query_model_name)
            self.q_model = AutoModel.from_pretrained(query_model_name)
            self.a_tokenizer = AutoTokenizer.from_pretrained(article_model_name)
            self.a_model = AutoModel.from_pretrained(article_model_name)
            self.q_model.to(self.device)
            self.a_model.to(self.device)
            self.q_model.eval()
            self.a_model.eval()
            logger.info(
                "Loaded MedCPT models: query=%s article=%s device=%s (requested=%s)",
                query_model_name,
                article_model_name,
                self.device,
                self.requested_device,
            )
        except Exception as e:
            logger.warning("MedCPT load failed (%s). Dense ranking disabled.", e)
            self._torch = None
            self.q_model = None
            self.a_model = None
            self.device = "cpu"

    def available(self) -> bool:
        return self.q_model is not None and self.a_model is not None and self._torch is not None

    def _encode_with(self, texts: list[str], tokenizer, model) -> list[list[float]]:
        if not self.available():
            return [[0.0] for _ in texts]

        out: list[list[float]] = []
        torch = self._torch
        bs = 32
        for i in range(0, len(texts), bs):
            batch = texts[i:i + bs]
            inputs = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            with torch.no_grad():
                h = model(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1)
                summed = (h * mask).sum(dim=1)
                counts = mask.sum(dim=1).clamp(min=1)
                emb = summed / counts
                emb = torch.nn.functional.normalize(emb, p=2, dim=1)
            out.extend(emb.cpu().tolist())
        return out

    def encode_query(self, texts: list[str]) -> list[list[float]]:
        return self._encode_with(texts, self.q_tokenizer, self.q_model)

    def encode_docs(self, texts: list[str]) -> list[list[float]]:
        return self._encode_with(texts, self.a_tokenizer, self.a_model)


# ─────────────────────────────────────────────
# HyDE query builder
# ─────────────────────────────────────────────

_HYDE_PROMPT = """\
You are generating a HyDE-style pseudo abstract for biomedical retrieval (PubMed/MedCPT).

Goal:
Write ONE hypothetical abstract of a study that would be INCLUDED in the target systematic review.
The abstract is for retrieval only (not for factual reporting).

Input:
- Objective: {objectives}
- Inclusion criteria: {inclusion_criteria}
- Exclusion criteria: {exclusion_criteria}

Requirements:
- Language: English only.
- Length: 140-220 words.
- Style: PubMed-like scientific abstract with exactly 4 labeled sections:
  Background:
  Methods:
  Results:
  Conclusions:
- Preserve critical biomedical entities exactly when provided:
  disease names, interventions/exposures, population descriptors, outcomes, study design terms.
- Add common synonym/abbreviation in parentheses only when high-confidence and standard.
- Prefer broad-but-relevant wording to maximize recall within inclusion scope.
- Do NOT invent highly specific unsupported details:
  exact effect sizes, p-values, confidence intervals, trial IDs, PMIDs, institution names, precise drug doses/timelines
  unless explicitly provided in the input.
- Do NOT mention information outside inclusion scope.
- Output ONLY the abstract text (no title, no bullets, no explanations).

Now write the pseudo abstract.
"""

def _build_local_structured_hyde(
    objectives: str,
    inclusion_criteria: str,
    exclusion_criteria: str = "",
) -> str:
    """Deterministic structured pseudo abstract without external API calls."""
    obj = (objectives or "").strip()
    inc = (inclusion_criteria or "").strip()
    exc = (exclusion_criteria or "").strip()
    if not obj:
        obj = "This study addresses an important evidence gap in the target clinical population."
    if not inc:
        inc = (
            "Eligible studies include predefined populations, interventions or exposures, "
            "and clinically relevant outcomes aligned with the review scope."
        )
    if not exc:
        exc = "Studies outside the predefined inclusion scope were excluded."

    return "\n".join([
        f"Background: {obj} This pseudo abstract is optimized for retrieval of likely in-scope biomedical studies.",
        (
            "Methods: We conducted a structured evidence study aligned to the review question, "
            f"with eligibility criteria defined as follows: {inc} "
            f"Out-of-scope studies were excluded using these constraints: {exc}"
        ),
        (
            "Results: Candidate studies meeting these criteria showed consistent directional "
            "effects across key outcomes relevant to the review question, and reported findings "
            "in a clinically interpretable way without relying on unsupported exact statistics."
        ),
        (
            "Conclusions: The findings support relevance to the review objective and justify "
            "prioritization for downstream screening under the predefined inclusion criteria."
        ),
    ])


def build_hyde_query(
    objectives: str,
    inclusion_criteria: str,
    exclusion_criteria: str = "",
    provider: Optional[str] = None,
    model: str = "claude-opus-4-5",
    api_key: Optional[str] = None,
) -> str:
    """
    Generate a hypothetical ideal abstract (HyDE).
    Falls back to plain objectives+inclusion text if API call fails.
    """
    def _infer_provider(p: Optional[str], m: str) -> str:
        if p:
            return p.lower()
        ml = (m or "").lower()
        if ml.startswith("local-structured"):
            return "local"
        if ml.startswith("claude"):
            return "claude"
        if ml.startswith("gemini"):
            return "gemini"
        if ml.startswith("gpt") or "o3" in ml or "o4" in ml or "codex" in ml:
            return "codex"
        # Backward-compatible default
        return "claude"

    selected_provider = _infer_provider(provider, model)
    model_l = (model or "").lower()
    if selected_provider == "local" or model_l.startswith("local-structured"):
        text = _build_local_structured_hyde(objectives, inclusion_criteria, exclusion_criteria)
        logger.info("HyDE abstract generated via local-structured mode (%d chars)", len(text))
        return text

    prompt = _HYDE_PROMPT.format(
        objectives=objectives[:800],
        inclusion_criteria=inclusion_criteria[:800],
        exclusion_criteria=exclusion_criteria[:800],
    )

    try:
        if selected_provider == "claude":
            import anthropic

            key = api_key or os.getenv("ANTHROPIC_API_KEY")
            client = anthropic.Anthropic(api_key=key)
            resp = client.messages.create(
                model=model,
                max_tokens=300,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = resp.content[0].text.strip()
            logger.info("HyDE abstract generated via claude (%d chars)", len(text))
            return text

        if selected_provider == "codex":
            from openai import OpenAI

            key = api_key or os.getenv("OPENAI_API_KEY")
            client = OpenAI(api_key=key)
            resp = client.responses.create(
                model=model,
                input=[{"role": "user", "content": prompt}],
                temperature=0,
                max_output_tokens=300,
            )
            text = (resp.output_text or "").strip()
            if not text:
                raise RuntimeError("Empty response text from OpenAI")
            logger.info("HyDE abstract generated via codex/openai (%d chars)", len(text))
            return text

        if selected_provider == "gemini":
            key = api_key or os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            try:
                from google import genai

                client = genai.Client(api_key=key)
                resp = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                text = (resp.text or "").strip()
            except Exception:
                import google.generativeai as genai_legacy

                genai_legacy.configure(api_key=key)
                gm = genai_legacy.GenerativeModel(model)
                resp = gm.generate_content(prompt)
                text = (getattr(resp, "text", None) or "").strip()

            if not text:
                raise RuntimeError("Empty response text from Gemini")
            logger.info("HyDE abstract generated via gemini (%d chars)", len(text))
            return text

        raise ValueError(f"Unsupported HyDE provider: {selected_provider}")
    except Exception as e:
        logger.warning(
            "HyDE generation failed (provider=%s, model=%s, err=%s), falling back to local structured",
            selected_provider,
            model,
            e,
        )
        return _build_local_structured_hyde(objectives, inclusion_criteria, exclusion_criteria)


# ─────────────────────────────────────────────
# Hybrid Ranker
# ─────────────────────────────────────────────

class HybridRanker:
    """
    Combines dense similarity and BM25 for candidate ranking.
    alpha: weight for dense score (0=BM25 only, 1=dense only).
    """

    def __init__(
        self,
        dense_backend: str = "minilm",
        model_name: str = "all-MiniLM-L6-v2",
        medcpt_query_model: str = "ncbi/MedCPT-Query-Encoder",
        medcpt_article_model: str = "ncbi/MedCPT-Article-Encoder",
        alpha: float = 0.7,
        device: str = "auto",
    ):
        self.alpha = alpha
        self.dense_backend = dense_backend.lower()
        self.model_name = model_name
        self.medcpt_query_model = medcpt_query_model
        self.medcpt_article_model = medcpt_article_model
        self.device = device

        if self.dense_backend == "medcpt":
            self.dense = MedCPTDenseRanker(
                query_model_name=medcpt_query_model,
                article_model_name=medcpt_article_model,
                device=device,
            )
        else:
            self.dense_backend = "minilm"
            self.dense = DenseRanker(model_name, device=device)

    def rank(
        self,
        query_text: str,
        records: list[dict],
        top_k: int = 1500,
    ) -> list[dict]:
        """
        Rank records by hybrid score and return top_k.
        records must have keys: pmid, title, abstract.
        Returns records sorted by hybrid_score descending, with score fields added.
        """
        if not records:
            return []

        # Build corpus texts
        corpus = [
            f"{r.get('title', '')} {r.get('abstract', '')[:500]}"
            for r in records
        ]

        # BM25
        bm25 = BM25(corpus)
        bm25_scores_raw = bm25.score_all(query_text)

        # Normalise BM25 to [0, 1]
        bm25_max = max(bm25_scores_raw) if bm25_scores_raw else 1.0
        bm25_scores = [s / bm25_max if bm25_max > 0 else 0.0 for s in bm25_scores_raw]

        # Dense
        if self.dense.available():
            if self.dense_backend == "medcpt":
                query_vec = self.dense.encode_query([query_text])[0]
                corpus_vecs = self.dense.encode_docs(corpus)
            else:
                query_vec = self.dense.encode([query_text])[0]
                corpus_vecs = self.dense.encode(corpus)
            dense_scores = [_cosine(query_vec, cv) for cv in corpus_vecs]
        else:
            dense_scores = [0.0] * len(records)

        # Hybrid
        alpha = self.alpha
        for i, rec in enumerate(records):
            rec["_dense_score"] = round(dense_scores[i], 4)
            rec["_bm25_score"] = round(bm25_scores[i], 4)
            rec["_hybrid_score"] = round(
                alpha * dense_scores[i] + (1 - alpha) * bm25_scores[i], 4
            )
            rec["_dense_backend"] = self.dense_backend

        ranked = sorted(records, key=lambda r: r["_hybrid_score"], reverse=True)
        return ranked[:top_k]


def determine_k(hits_b: int, paper_type: str = "default") -> int:
    """
    Determine K (number of candidates to pass to Stage D) based on:
    - hits_b: records remaining after Stage B
    - paper_type: study type category (RCT_heavy / observational / mixed / default)

    K is variable per paper as per v2 plan.
    Minimum K table estimated from Training 11 (to be updated after Phase 1).
    Current values are conservative defaults with 20% margin.
    """
    # Base minimums by paper type (coarse prior)
    base_k_by_type: dict[str, int] = {
        "RCT_heavy": 1000,
        "observational": 1400,
        "mixed": 1600,
        "default": 1800,
    }
    base = base_k_by_type.get(paper_type, base_k_by_type["default"])

    # Size-aware uplift (Training11 showed recall loss for high-hit papers with fixed ~1800)
    # Keep this conservative until per-paper calibrated K table is learned.
    if hits_b > 8000:
        k = 4000
    elif hits_b > 6000:
        k = 3500
    elif hits_b > 3000:
        k = 2500
    elif hits_b > 1500:
        k = max(base, 1800)
    else:
        k = int(base * 1.10)  # small safety margin for low/medium hits

    k = min(k, 4000)  # hard cap
    return min(hits_b, k)
