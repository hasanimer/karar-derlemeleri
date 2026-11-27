#!/usr/bin/env python3
"""Build a separate, conservative Bedesten ID index from local Parquet files."""
import argparse
import gzip
import json
import re
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path
from html import unescape

ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://bedesten.adalet.gov.tr/emsal-karar/getDocumentContent"

def norm(s):
    s = unicodedata.normalize("NFKC", str(s or "")).casefold()
    s = s.replace("ı", "i")
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return s

def textnorm(s):
    s = unescape(re.sub(r"<[^>]+>", " ", str(s or "")))
    return " ".join(re.findall(r"[a-z0-9]+", norm(s)))

def unit(s):
    s = norm(s)
    s = re.sub(r"\bhukuk genel kurulu\b", "hgk", s)
    s = re.sub(r"\bceza genel kurulu\b", "cgk", s)
    s = re.sub(r"\bhukuk dairesi\b", "hd", s)
    s = re.sub(r"\bceza dairesi\b", "cd", s)
    s = re.sub(r"\byargitay\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)

def number(s):
    m = re.fullmatch(r"\s*(\d{4})\s*/\s*(\d+)\s*", str(s or ""))
    return f"{m[1]}/{int(m[2])}" if m else None

def evidence(excerpt, full):
    # Require a substantial exact contiguous passage, not just shared legal phrases.
    a, b = textnorm(excerpt).split(), textnorm(full)
    if len(a) < 50:
        return False
    return any(" ".join(a[i:i+50]) in b for i in range(0, len(a)-49, 10))

def run(args):
    import pyarrow.parquet as pq
    wanted = defaultdict(list)
    counts = Counter()
    for p in sorted((ROOT/"veri/kararlar").glob("*.jsonl.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                k = number(r.get("karar"))
                u = unit(r.get("daire"))
                if (r.get("tur") == "yargitay" and k and u
                        and len(r.get("kararlar") or []) == 1
                        and not set(r.get("bayrak") or []) & {"cok_karar","yil_supheli","yazim"}):
                    wanted[u,k].append(r)
                else:
                    counts["unsupported"] += 1
    if not wanted:
        raise SystemExit("No eligible repository records found")
    hits = defaultdict(dict)
    for path in args.parquet:
        pf = pq.ParquetFile(path)
        columns = [args.court, args.decision, args.esas, args.text, args.id]
        missing = set(columns) - set(pf.schema_arrow.names)
        if missing:
            raise SystemExit(f"{path}: missing columns {sorted(missing)}")
        for batch in pf.iter_batches(batch_size=512, columns=columns):
            for row in batch.to_pylist():
                k = unit(row[args.court]), number(row[args.decision])
                if k not in wanted:
                    continue
                doc = str(row[args.id] or "")
                if not doc.isdigit():
                    continue
                for r in wanted[k]:
                    e = number(r.get("esas"))
                    if e and e != number(row[args.esas]):
                        continue
                    if evidence(r.get("metin"), row[args.text]):
                        hits[r["id"]][doc] = True
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as f:
        for records in wanted.values():
            for r in records:
                ids = sorted(hits.get(r["id"], {}))
                status = "unique_in_input" if len(ids)==1 else "ambiguous" if ids else "unmatched"
                counts[status] += 1
                result = {"id":r["id"], "status":status,
                          "bedesten_document_id":ids[0] if len(ids)==1 else None,
                          "candidate_ids":ids, "bedesten_url":None,
                          "api_endpoint":ENDPOINT, "source":args.source,
                          "method":"court_decision_exact_excerpt_50_words"}
                f.write(json.dumps(result, ensure_ascii=False)+"\n")
    print(json.dumps(counts, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("parquet", nargs="+", help="Local files containing verified Bedesten IDs; Yargitay only")
    p.add_argument("--source", required=True, help="Dataset name and immutable revision")
    p.add_argument("--court", default="court")
    p.add_argument("--decision", default="karar_no")
    p.add_argument("--esas", default="esas_no")
    p.add_argument("--text", default="text")
    p.add_argument("--id", default="document_id")
    p.add_argument("--output", default=str(ROOT/"veri/bedesten/eslesmeler.jsonl"))
    run(p.parse_args())
