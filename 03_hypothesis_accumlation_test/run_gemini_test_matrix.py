import argparse
import json
import os
import shutil
import time
from pathlib import Path

from google import genai
from google.genai import types
from google.genai.errors import APIError

from pipeline_common import (
    TEST_DATA_DIR,
    TEST_PIPELINE_DIR,
    extract_pubmed_query_from_text,
    normalize_query,
    scan_papers,
    test_paper_dir,
    timestamp_for_paths,
    utc_timestamp,
    write_json,
)

# Configuration for different conditions
CONDITION_CONFIG = {
    "with_laws_v5": {
        "prompt_file": "test_prompt_with.md",
        "bundle_files": ("test_prompt_with.md", "input_config.json", "query_laws.txt"),
        "wrapper": "Read `test_prompt_with.md` and start the task with the attached files.\nAt the end, output your final PubMed query on a single line in this exact format:\nFULL_QUERY: <PubMed Boolean query>",
    },
    "with_laws_v4": {
        "prompt_file": "test_prompt_with.md",
        "bundle_files": ("test_prompt_with.md", "input_config.json", "query_laws_ver4.txt"),
        "wrapper": "Read `test_prompt_with.md` and start the task with the attached files.\nAt the end, output your final PubMed query on a single line in this exact format:\nFULL_QUERY: <PubMed Boolean query>",
    },
    "without_laws": {
        "prompt_file": "test_prompt_without.md",
        "bundle_files": ("test_prompt_without.md", "input_config.json"),
        "wrapper": "Read `test_prompt_without.md` and start the task with the attached files.\nAt the end, output your final PubMed query on a single line in this exact format:\nFULL_QUERY: <PubMed Boolean query>",
    },
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run Gemini test-phase jobs matrix.")
    parser.add_argument("--domain", action="append", default=[])
    parser.add_argument("--paper", action="append", default=[])
    parser.add_argument("--condition", choices=["without_laws", "with_laws_v4", "with_laws_v5", "all"], default="all")
    parser.add_argument("--model", default="gemini-3.0-pro", help="Gemini model to use.")
    parser.add_argument("--skip-existing", action="store_true")
    return parser.parse_args()


def get_conditions(condition_arg):
    if condition_arg == "all":
        return ["without_laws", "with_laws_v4", "with_laws_v5"]
    return [condition_arg]


def prepare_files_for_gemini(paper_dir, condition, run_dir):
    cfg = CONDITION_CONFIG[condition]
    prompt_src = TEST_PIPELINE_DIR / cfg["prompt_file"]
    
    contents = []
    
    # 1. Prompt MD
    p_text = prompt_src.read_text(encoding="utf-8")
    contents.append(f"--- File: {cfg['prompt_file']} ---\n{p_text}\n")
    
    # 2. Input Config
    ic_text = (paper_dir / "input_config.json").read_text(encoding="utf-8")
    contents.append(f"--- File: input_config.json ---\n{ic_text}\n")
    
    # 3. Laws
    if condition == "with_laws_v5":
        laws_txt = (TEST_PIPELINE_DIR.parent / "03_meta_extraction_prompt" / "query_laws.txt").read_text(encoding="utf-8")
        contents.append(f"--- File: query_laws.txt ---\n{laws_txt}\n")
    elif condition == "with_laws_v4":
        v4_path = TEST_PIPELINE_DIR.parent / "03_meta_extraction_prompt" / "query_laws_ver4.txt"
        if v4_path.exists():
            text = v4_path.read_text(encoding="utf-8")
            blocks = text.split("=====")
            kept = []
            for b in blocks:
                if "NOISE" in b or "CONDITIONAL" in b:
                    continue
                kept.append(b)
            contents.append(f"--- File: query_laws.txt ---\n{'====='.join(kept)}\n")
        else:
             contents.append(f"--- File: query_laws.txt ---\n[RECALL PROTECTIVE AND AVOID RULESETS]\n")
    
    # 4. Wrapper
    contents.append(f"\n{cfg['wrapper']}")
    
    full_prompt = "\n".join(contents)
    (run_dir / "full_prompt.txt").write_text(full_prompt, encoding="utf-8")
    return full_prompt


def main():
    args = parse_args()
    
    from dotenv import load_dotenv
    from pathlib import Path
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    
    client = genai.Client()

    domain_filter = set(args.domain) if args.domain else None
    paper_filter = set(args.paper) if args.paper else None
    run_stamp = timestamp_for_paths()
    run_root = TEST_PIPELINE_DIR / "runs" / run_stamp / "gemini"

    jobs = []
    for domain_folder, paper_folder in scan_papers(TEST_DATA_DIR, domain_filter=domain_filter):
        if paper_filter and paper_folder not in paper_filter:
            continue
        paper_dir = test_paper_dir(domain_folder, paper_folder)
        if not paper_dir.exists():
            continue
        for condition in get_conditions(args.condition):
            jobs.append({"domain_folder": domain_folder, "paper_folder": paper_folder, "condition": condition})

    summary = {
        "generated_at": utc_timestamp(),
        "run_root": str(run_root),
        "jobs": [],
    }

    # API limits could be tight (e.g. 5 RPM normally, but depends on account)
    # We will just retry on API errors
    for idx, job in enumerate(jobs):
        domain_folder = job["domain_folder"]
        paper_folder = job["paper_folder"]
        condition = job["condition"]
        
        paper_dir = test_paper_dir(domain_folder, paper_folder)
        output_dir = paper_dir / "model_outputs" / "gemini" / condition
        
        if args.skip_existing and (output_dir / "result.json").exists():
            print(f"Skipping existing: {paper_folder} - {condition}")
            summary["jobs"].append({**job, "status": "skipped_existing"})
            continue

        run_dir = run_root / domain_folder / paper_folder / condition
        run_dir.mkdir(parents=True, exist_ok=True)
        
        prompt_text = prepare_files_for_gemini(paper_dir, condition, run_dir)
        
        print(f"[{idx+1}/{len(jobs)}] Running Gemini for {paper_folder} - {condition}")
        
        max_retries = 10
        for attempt in range(max_retries):
            try:
                chat = client.chats.create(model=args.model)
                response = chat.send_message(prompt_text)
                
                raw_message = response.text
                extracted_query = normalize_query(extract_pubmed_query_from_text(raw_message))
                
                output_dir.mkdir(parents=True, exist_ok=True)
                (output_dir / "raw_last_message.txt").write_text(raw_message, encoding="utf-8")
                (output_dir / "normalized_query.txt").write_text(extracted_query + "\n", encoding="utf-8")
                
                res_data = {
                    "generated_at": utc_timestamp(),
                    "provider": "gemini",
                    "condition": condition,
                    "paper_folder": paper_folder,
                    "domain_folder": domain_folder,
                    "status": "ok" if extracted_query else "completed_no_query",
                    "query": extracted_query,
                    "run_dir": str(run_dir),
                }
                write_json(output_dir / "result.json", res_data)
                
                summary["jobs"].append({**job, "status": "completed", "query_length": len(extracted_query)})
                
                # Sleep aggressively to avoid rate limiting
                time.sleep(15) 
                break
                
            except APIError as e: # This handles 429
                if "429" in str(e):
                    print(f"  Rate limit hit (429). Retrying in {(attempt+1) * 20} seconds...")
                    time.sleep((attempt+1) * 20)
                else:
                    print(f"  API Error on {paper_folder} {condition}: {e}")
                    summary["jobs"].append({**job, "status": "failed", "error": str(e)})
                    break
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"  Error on {paper_folder} {condition}: {e}")
                summary["jobs"].append({**job, "status": "failed", "error": str(e)})
                break
        else:
             print(f"  Failed permanently after {max_retries} retries on {paper_folder} {condition}")
             summary["jobs"].append({**job, "status": "failed_retries"})
             

    write_json(run_root / "run_summary.json", summary)
    print("FINISHED ALL JOBS")

if __name__ == "__main__":
    main()
