"""Stage C harmonized scoring core (protocol 20261110_v2).

Verbatim extracts (function bodies unchanged) from the internal analysis copies used for the revised results:
  ranker.py            sha256 0679e6b573ea57731dd8422e7903bc35b29198fd2e489700750c25cbaa39d2d5: _tokenize, BM25, _cosine, MedCPTDenseRanker, _build_local_structured_hyde (T2)
  ranker_v1.0_backup.py sha256 ff706ca2afe0b0dd11fcc0aa22877de7e7c75c8d1113c9b659f2ecd56e9ae703: _build_local_structured_hyde (T1; renamed build_t1_legacy)
  stagec_final.py      sha256 6b1ee2dd8a991bbdb4f5a16d6e4a00f7a80594616f52b91743ee8c1708a423c3: rank_percentile_desc, _select_anchor_idx
  internal shared/scoring.py (protocol driver, not in this repository) sha256 56dbd95470c9260033aa08805a08f827287e9efd64fa7599ef66f0e1071d31e8: document_texts, base_scores, final_scores, final_from_sq, keep_count
The public src/ranker.py of this repository is a later edit (MedCPT batch size 16, numpy return);
the revised results used batch size 32 as below.
"""
from __future__ import annotations
import logging, math, re
from collections import Counter
import numpy as np

logger = logging.getLogger(__name__)


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


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


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


def build_t1_legacy(objectives: str, inclusion_criteria: str) -> str:
    """Deterministic structured pseudo abstract without external API calls."""
    obj = (objectives or "").strip()
    inc = (inclusion_criteria or "").strip()
    if not obj:
        obj = "This study addresses an important evidence gap in the target clinical population."
    if not inc:
        inc = (
            "Eligible studies include predefined populations, interventions or exposures, "
            "and clinically relevant outcomes aligned with the review scope."
        )

    return "\n".join([
        f"Background: {obj}",
        (
            "Methods: We conducted a structured evidence study aligned to the review question, "
            f"with eligibility criteria defined as follows: {inc}"
        ),
        (
            "Results: Candidate studies meeting these criteria showed consistent directional "
            "effects across key outcomes, with quantitative estimates and uncertainty reported."
        ),
        (
            "Conclusions: The findings support relevance to the review objective and justify "
            "further validation in larger and externally evaluated datasets."
        ),
    ])


def rank_percentile_desc(values: np.ndarray) -> np.ndarray:
    n = len(values)
    if n <= 1:
        return np.ones(n, dtype=np.float32)
    order = np.argsort(-values, kind="mergesort")
    ranks = np.empty(n, dtype=np.float32)
    ranks[order] = np.arange(n, dtype=np.float32)
    return 1.0 - (ranks / float(n - 1))


def _select_anchor_idx(s_q: np.ndarray, pmids: list[str], top: bool) -> tuple[int, int]:
    n = len(pmids)
    if n == 0:
        return 0, 0
    if top:
        order = sorted(range(n), key=lambda i: (-float(s_q[i]), pmids[i]))
    else:
        order = sorted(range(n), key=lambda i: (float(s_q[i]), pmids[i]))
    a = order[0]
    b = order[1] if n > 1 else order[0]
    return a, b


def build_t1(sr):
    return build_t1_legacy(sr['objectives'], sr['inclusion_criteria'])


def build_t2(sr):
    return _build_local_structured_hyde(sr['objectives'], sr['inclusion_criteria'], sr['exclusion_criteria'])


def document_texts(records, pmids):
    return [f"{records[k].get('title', '')} {records[k].get('abstract', '')[:500]}" for k in pmids]


def base_scores(texts, query, doc_embeddings, query_embedding, bm25_index=None):
    # Use the reference Python-double cosine, not a new float32 GEMV rounding path.
    # Callers may construct BM25(texts) once and share it across all three arms.
    raw_bm = np.asarray((bm25_index if bm25_index is not None else BM25(texts)).score_all(query), dtype=np.float64)
    maximum = float(raw_bm.max()) if len(raw_bm) else 0.
    norm = raw_bm / maximum if maximum > 0 else np.zeros_like(raw_bm)
    raw_dense = np.asarray([_cosine(query_embedding.tolist(), e.tolist()) for e in doc_embeddings], dtype=np.float64)
    return {'bm25_raw': raw_bm, 'bm25_max': np.asarray(maximum), 'bm25_normalized': norm,
            'dense_raw': raw_dense,
            'bm25': np.asarray([round(float(v), 4) for v in norm], dtype=np.float32),
            'dense': np.asarray([round(float(v), 4) for v in raw_dense], dtype=np.float32)}


def final_scores(pmids, dense, bm25, embeddings, alpha):
    if not len(pmids):
        raise ValueError('Empty candidate set')
    sq = np.float32(alpha) * np.asarray(dense, dtype=np.float32) + np.float32(1-alpha) * np.asarray(bm25, dtype=np.float32)
    pos = _select_anchor_idx(sq, pmids, top=True)
    neg = _select_anchor_idx(sq, pmids, top=False)
    return final_from_sq(sq, embeddings, pos, neg)


def final_from_sq(sq, embeddings, pos, neg):
    sq = np.asarray(sq, dtype=np.float32)
    p1, p2 = [(embeddings @ embeddings[i]).astype(np.float32) for i in pos]
    n1, n2 = [(embeddings @ embeddings[i]).astype(np.float32) for i in neg]
    pm = ((p1+p2)/2).astype(np.float32); nm = ((n1+n2)/2).astype(np.float32)
    rq = rank_percentile_desc(sq); rp = rank_percentile_desc(pm); rn = rank_percentile_desc(nm)
    final = (rq+rp-rn).astype(np.float32)
    return {'s_q': sq, 's_pos1': p1, 's_pos2': p2, 's_neg1': n1, 's_neg2': n2,
            's_pos_mean': pm, 's_neg_mean': nm, 'rank_s_q': rq, 'rank_s_pos_mean': rp,
            'rank_s_neg_mean': rn, 'final': final, 'pos_anchor_idx': np.asarray(pos),
            'neg_anchor_idx': np.asarray(neg), 'order': np.argsort(-final, kind='mergesort')}


def keep_count(n, cut, gate):
    return n if gate or cut == 0 else min(n, max(1000, int(round(n*(1-cut/100)))))
