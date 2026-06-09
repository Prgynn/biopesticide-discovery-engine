import sqlite3, re, json, os, sys, argparse
from datetime import datetime

DB_PATH = "biopesticide.db"
FULLTEXT_JSON = "fulltext_data/fulltext_results.json"
EXTRACTED_TABLES = "tables/extracted_tables.json"
KNOWLEDGE_BASE_JSON = "knowledge_base.json"
EVIDENCE_GRADES_JSON = "evidence_grades.json"

KNOWN_ALIASES = {
    "azadirachtin": ["azadirachtin","azadirachta","neem extract","neem oil"],
    "rotenone": ["rotenone","derris extract"],
    "pyrethrin": ["pyrethrin","pyrethrum"],
    "neem": ["neem","azadirachta indica"],
    "limonene": ["limonene","d-limonene"],
    "eugenol": ["eugenol","clove oil"],
    "thymol": ["thymol","thyme extract"],
    "carvacrol": ["carvacrol"],
    "linalool": ["linalool"],
    "spinosad": ["spinosad","spinosyn"],
    "abamectin": ["abamectin","avermectin"],
}

PEST_MAP = {
    "helicoverpa armigera": ("Helicoverpa armigera","cotton"),
    "cotton bollworm": ("Helicoverpa armigera","cotton"),
    "spodoptera frugiperda": ("Spodoptera frugiperda","maize"),
    "fall armyworm": ("Spodoptera frugiperda","maize"),
    "plutella xylostella": ("Plutella xylostella","mustard"),
    "diamondback moth": ("Plutella xylostella","mustard"),
    "bemisia tabaci": ("Bemisia tabaci","tomato"),
    "whitefly": ("Bemisia tabaci","tomato"),
    "nilaparvata lugens": ("Nilaparvata lugens","rice"),
    "brown planthopper": ("Nilaparvata lugens","rice"),
    "aphis gossypii": ("Aphis gossypii","cotton"),
    "cotton aphid": ("Aphis gossypii","cotton"),
    "lipaphis erysimi": ("Lipaphis erysimi","mustard"),
    "mustard aphid": ("Lipaphis erysimi","mustard"),
    "stem borer": ("Scirpophaga incertulas","rice"),
    "thrips": ("Thrips palmi","chili"),
}

LC50_PAT = [
    re.compile(r'LC[_\s]?50\s*(?:=|of|was|:)?\s*(\d+\.?\d*)\s*(ppm|mg[/\s]L|ug[/\s]mL|%|mg[/\s]kg)', re.I),
    re.compile(r'LD[_\s]?50\s*(?:=|of|was|:)?\s*(\d+\.?\d*)\s*(ppm|mg[/\s]kg|ug[/\s]g)', re.I),
]
MORT_PAT = [
    re.compile(r'(\d+\.?\d*)\s*%\s*(?:mortality|control|inhibition|efficacy|kill)', re.I),
    re.compile(r'(?:mortality|efficacy|control)\s*(?:of|was|:)?\s*(\d+\.?\d*)\s*%', re.I),
]

def extract_lc50(text):
    for p in LC50_PAT:
        m = p.search(text)
        if m:
            try: return float(m.group(1)), m.group(2).strip()
            except: continue
    return None, None

def extract_mortality(text):
    for p in MORT_PAT:
        m = p.search(text)
        if m:
            try:
                v = float(m.group(1))
                if 0 < v <= 100: return v
            except: continue
    return None

def extract_pest_crop(text):
    low = text.lower()
    for kw, (pest, crop) in PEST_MAP.items():
        if kw in low: return pest, crop
    return None, None

def build_compound_patterns(compounds):
    out = []
    for c in compounds:
        names = [c["name"]]
        for canon, aliases in KNOWN_ALIASES.items():
            if canon.lower() in c["name"].lower():
                names.extend(aliases)
        names = list({n.lower() for n in names})
        pat = re.compile(r'\b(?:' + '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True)) + r')\b', re.I)
        out.append((c["id"], c["name"], pat))
    return out

def grade(has_lc50, has_mort, lc50, mort):
    if has_lc50 and lc50 is not None: return "B"
    if has_mort and mort is not None: return "C"
    return "D"


def load_sources_from_db(db_path="biopesticide.db"):
    """Load text sources directly from papers table."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, pubmed_id, pmcid, title, abstract, pest, crop FROM papers"
        ).fetchall()
    except Exception as e:
        print(f"  DB read error: {e}")
        conn.close()
        return []
    conn.close()
    sources = []
    for r in rows:
        pid   = str(r[1] or r[2] or r[0])
        title = r[3] or ""
        abstr = r[4] or ""
        text  = f"{title} {abstr}".strip()
        if text:
            sources.append({
                "paper_id": pid,
                "pest":     r[5] or "",
                "crop":     r[6] or "",
                "text":     text,
                "source":   "sqlite_papers",
            })
    print(f"  Text sources loaded from DB: {len(sources)}")
    return sources

def load_sources():
    sources = []
    if os.path.exists(FULLTEXT_JSON):
        data = json.load(open(FULLTEXT_JSON))
        for key, item in data.items():
            for paper in item.get("papers", []):
                parts = [paper.get("abstract","")]
                for t in paper.get("experimental_tables",[]):
                    parts.append(t.get("caption",""))
                    parts.extend(t.get("cells",[]))
                sources.append({"paper_id": paper.get("pmcid",""), "pest": item.get("pest",""),
                    "crop": item.get("crop",""), "text": " ".join(str(p) for p in parts), "source": "europepmc"})
    if os.path.exists(EXTRACTED_TABLES):
        data = json.load(open(EXTRACTED_TABLES))
        for key, item in data.items():
            for paper in item.get("papers_with_tables",[]):
                parts = []
                for t in paper.get("experimental_tables",[]):
                    parts.append(str(t.get("headers","")))
                    for row in t.get("data_rows",[]):
                        parts.append(" ".join(str(c) for c in row if c))
                if parts:
                    sources.append({"paper_id": str(paper.get("pubmed_id","")), "pest": item.get("pest",""),
                        "crop": item.get("crop",""), "text": " ".join(parts), "source": "pdf_tables"})
    if os.path.exists(KNOWLEDGE_BASE_JSON):
        data = json.load(open(KNOWLEDGE_BASE_JSON))
        for key, item in data.items():
            for paper in item.get("papers",[]):
                pid = str(paper.get("pubmed_id", paper.get("id","")))
                txt = paper.get("title","") + " " + paper.get("abstract","")
                if txt.strip():
                    sources.append({"paper_id": pid, "pest": item.get("pest",""),
                        "crop": item.get("crop",""), "text": txt, "source": "knowledge_base"})
    # Also load from DB (primary source)
    db_sources = load_sources_from_db()
    # Merge, deduplicate by paper_id
    seen = {s['paper_id'] for s in sources}
    for s in db_sources:
        if s['paper_id'] not in seen:
            sources.append(s)
            seen.add(s['paper_id'])
    print(f"  Total text sources (JSON + DB): {len(sources)}")
    return sources

def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS bioactivity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compound_id INTEGER NOT NULL, paper_id TEXT NOT NULL,
        pest TEXT, crop TEXT, lc50 REAL, lc50_unit TEXT,
        efficacy_pct REAL, evidence_grade TEXT DEFAULT 'D',
        extraction_method TEXT, context_snippet TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()

def already_exists(conn, cid, pid, pest):
    return conn.execute("SELECT COUNT(*) FROM bioactivity WHERE compound_id=? AND paper_id=? AND pest=?",
        (cid, pid, pest)).fetchone()[0] > 0

def insert_row(conn, r):
    conn.execute("""INSERT INTO bioactivity
        (compound_id,paper_id,pest,crop,lc50,lc50_unit,efficacy_pct,evidence_grade,extraction_method,context_snippet)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (r["compound_id"], r["paper_id"], r["pest"], r["crop"],
         r.get("lc50"), r.get("lc50_unit"), r.get("efficacy_pct"),
         r.get("evidence_grade","D"), r.get("source","regex"), r.get("ctx","")[:500]))

def run(dry_run=False, reset=False):
    print("\n" + "="*55)
    print("  DAY 12 — POPULATE BIOACTIVITY")
    print("="*55)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    if reset and not dry_run:
        conn.execute("DELETE FROM bioactivity")
        conn.commit()
        print("  bioactivity table cleared.")
    compounds = [{"id": r[0], "name": r[1]} for r in conn.execute("SELECT id, name FROM compounds")]
    print(f"  Compounds: {len(compounds)}")
    if not compounds:
        print("  ERROR: No compounds in DB."); conn.close(); sys.exit(1)
    patterns = build_compound_patterns(compounds)
    sources = load_sources()
    if not sources:
        print("  ERROR: No text sources found. Run day10.py or day11.py first.")
        conn.close(); sys.exit(1)
    ext_grades = {}
    if os.path.exists(EVIDENCE_GRADES_JSON):
        ext_grades = json.load(open(EVIDENCE_GRADES_JSON))
    inserted = 0
    skipped = 0
    grade_counts = {}
    compound_hits = {}
    print("\n  Scanning...\n" + "-"*55)
    for i, src in enumerate(sources):
        text = src["text"]
        pid = src["paper_id"]
        pest = src.get("pest","")
        crop = src.get("crop","")
        if not pest:
            pest, crop = extract_pest_crop(text)
            pest = pest or ""
            crop = crop or ""
        if not pest:
            continue
        for cid, cname, pat in patterns:
            m = pat.search(text)
            if not m:
                continue
            start = max(0, m.start()-400)
            end = min(len(text), m.end()+400)
            ctx = text[start:end]
            lc50_val, lc50_unit = extract_lc50(ctx)
            mort_val = extract_mortality(ctx)
            if lc50_val is None and mort_val is None:
                lc50_val, lc50_unit = extract_lc50(text)
                mort_val = extract_mortality(text)
            g = grade(lc50_val is not None, mort_val is not None, lc50_val, mort_val)
            ext_key = f"{cname.lower()}_{pest.lower()}"
            if ext_key in ext_grades:
                g = ext_grades[ext_key].get("grade", g)
            rec = {"compound_id": cid, "compound_name": cname, "paper_id": pid,
                   "pest": pest, "crop": crop, "lc50": lc50_val, "lc50_unit": lc50_unit,
                   "efficacy_pct": mort_val, "evidence_grade": g, "source": src["source"], "ctx": ctx}
            if dry_run:
                print(f"  [DRY] {cname} | {pest} | LC50={lc50_val} {lc50_unit or ''} | Mort={mort_val}% | Grade={g}")
            else:
                if already_exists(conn, cid, pid, pest):
                    skipped += 1
                    continue
                insert_row(conn, rec)
            inserted += 1
            grade_counts[g] = grade_counts.get(g, 0) + 1
            compound_hits[cname] = compound_hits.get(cname, 0) + 1
        if (i+1) % 10 == 0:
            print(f"  Progress: {i+1}/{len(sources)} sources | records: {inserted}")
    if not dry_run:
        conn.commit()
    conn.close()
    print("\n" + "="*55)
    print(f"  {'DRY RUN — ' if dry_run else ''}Records: {inserted}  |  Skipped: {skipped}")
    print(f"  Grade breakdown: {grade_counts}")
    print(f"  Top compounds:")
    for name, cnt in sorted(compound_hits.items(), key=lambda x: -x[1])[:8]:
        print(f"    {name:<28} {cnt}")
    if not dry_run:
        print("\n  Done. Next: python day13_build_graph.py")
    print("="*55 + "\n")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()
    run(dry_run=args.dry_run, reset=args.reset)
    