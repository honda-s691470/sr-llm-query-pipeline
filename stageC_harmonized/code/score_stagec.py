"""Step 1 (GPU): recompute harmonized Stage C score components from public inputs.

Inputs: data/candidate_manifest.csv, data/candidates/*.json, data/query_texts.json (this package) and
pubmed_cache.zip (Zenodo deposit; title/abstract of every candidate). No gold is read here.
Output: one <condition_id>.npz per ranked condition in --out (gate conditions are not ranked).

MedCPT encoders are loaded from the local Hugging Face cache at the pinned revisions in
environment/protocol.json (download them once beforehand). No network access is attempted.
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time, zipfile
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(HERE))
import numpy as np
import pandas as pd
import stagec_core as core

ARMS = ["T1", "T2", "LLM"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_encoder(p):
    import torch, transformers
    from huggingface_hub import snapshot_download
    torch.set_num_threads(p["torch_threads"])
    torch.manual_seed(42)
    np.random.seed(42)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; the reported scores were computed on GPU")
    paths = [Path(snapshot_download(m, revision=r, local_files_only=True)) for m, r in [
        ("ncbi/MedCPT-Query-Encoder", p["query_revision"]), ("ncbi/MedCPT-Article-Encoder", p["article_revision"])]]
    enc = core.MedCPTDenseRanker(str(paths[0]), str(paths[1]), device="cuda")
    if not enc.available() or enc.device != "cuda":
        raise RuntimeError("MedCPT load failed")
    env = {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__,
           "python": sys.version.split()[0], "gpu": torch.cuda.get_device_name(),
           "model_files_sha256": {pth.name: {str(f.relative_to(pth)): sha(f) for f in sorted(pth.rglob("*")) if f.is_file()}
                                  for pth in paths}}
    return enc, env


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="path to pubmed_cache.zip")
    ap.add_argument("--out", required=True, help="new output directory")
    ap.add_argument("--conditions", nargs="*", help="optional subset of condition_id")
    a = ap.parse_args()
    p = json.loads((PKG / "environment/protocol.json").read_text(encoding="utf-8"))
    if sha(a.zip) != p["zip_sha256"]:
        raise SystemExit("pubmed_cache.zip SHA-256 differs from the protocol")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    man = pd.read_csv(PKG / "data/candidate_manifest.csv", dtype={"paper_id": str})
    texts = json.loads((PKG / "data/query_texts.json").read_text(encoding="utf-8"))
    todo = man[~man.gate]
    if a.conditions:
        todo = todo[todo.condition_id.isin(a.conditions)]
    enc, env = load_encoder(p)
    z = zipfile.ZipFile(a.zip)
    log = []
    for _, c in todo.iterrows():
        dst = out / f"{c.condition_id}.npz"
        if dst.exists():
            continue
        t0 = time.time()
        pmids = json.loads((PKG / f"data/candidates/{c.condition_id}.json").read_text(encoding="utf-8"))["pmids"]
        assert pmids == sorted(set(pmids)) and len(pmids) == c.n_candidates
        recs = json.loads(z.read(c.zip_entry))
        missing = [k for k in pmids if k not in recs]
        if missing:
            raise SystemExit(f"{c.condition_id}: {len(missing)} candidates absent from ZIP entry")
        docs_text = core.document_texts(recs, pmids)
        docs = np.asarray(enc.encode_docs(docs_text), dtype=np.float32)
        index = core.BM25(docs_text)
        save = {"pmids": np.asarray(pmids)}
        for arm in ARMS:
            q = texts[c.model][c.paper_id][arm]
            qv = np.asarray(enc.encode_query([q]), dtype=np.float32)
            b = core.base_scores(docs_text, q, docs, qv[0], bm25_index=index)
            save[f"{arm}_dense"], save[f"{arm}_bm25"] = b["dense"], b["bm25"]
            for alpha in p["alphas"]:
                r = core.final_scores(pmids, b["dense"], b["bm25"], docs, alpha)
                k = f"{arm}_a{alpha}"
                save[f"{k}_s_pos_mean"], save[f"{k}_s_neg_mean"] = r["s_pos_mean"], r["s_neg_mean"]
                save[f"{k}_pos_anchor"], save[f"{k}_neg_anchor"] = r["pos_anchor_idx"], r["neg_anchor_idx"]
                save[f"{k}_final"] = r["final"]
        np.savez_compressed(dst, **save)
        log.append({"condition_id": c.condition_id, "n": len(pmids), "seconds": round(time.time() - t0, 1),
                    "doc_texts_sha256": hashlib.sha256("\n".join(hashlib.sha256(t.encode()).hexdigest()
                                                                  for t in docs_text).encode()).hexdigest()})
        print(log[-1], flush=True)
    (out / "score_run.json").write_text(json.dumps({"environment": env, "protocol_sha256": sha(PKG / "environment/protocol.json"),
                                                     "conditions": log}, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
