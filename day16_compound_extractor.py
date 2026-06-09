"""
day16_compound_extractor.py
============================
1. Reads ALL 1177 papers directly from the SQLite papers table
2. Extracts compound/plant names using NLP patterns
3. Adds new ones to the compounds table
4. Rewrites day12 source loading to read from DB not JSON files

Run:
  python day16_compound_extractor.py            # live
  python day16_compound_extractor.py --dry-run  # preview only
"""

import sqlite3, re, json, os, argparse
from collections import Counter
from datetime import datetime

DB_PATH  = "biopesticide.db"
LOG_PATH = "compound_extraction_log.json"

# ─────────────────────────────────────────────
# KNOWN BIOPESTICIDE PLANT GENERA
# Any paper mentioning these → extract as compound
# ─────────────────────────────────────────────
PLANT_GENERA = [
    # Neem family
    "azadirachta", "melia",
    # Pyrethrum family
    "chrysanthemum", "tanacetum", "pyrethrum",
    # Mint family
    "mentha", "thymus", "origanum", "ocimum", "lavandula",
    # Citrus
    "citrus", "limonene",
    # Nightshade / capsicum
    "capsicum", "nicotiana", "solanum",
    # Legumes
    "pongamia", "millettia", "derris", "lonchocarpus", "tephrosia",
    # Annona family
    "annona", "asimina",
    # Meliaceae
    "swietenia", "toona", "cedrela",
    # Asteraceae
    "tagetes", "artemisia", "achillea", "calendula",
    # Euphorbiaceae
    "euphorbia", "jatropha", "ricinus",
    # Other botanicals
    "calotropis", "lantana", "vitex", "clerodendrum",
    "allium", "zingiber", "curcuma", "acorus",
    "withania", "datura", "aconitum",
    "cinnamomum", "syzygium", "eugenia",
    "piper", "zanthoxylum",
    "neem", "karanja", "custard apple",
    # Microbials
    "bacillus", "beauveria", "metarhizium", "trichoderma",
    "isaria", "lecanicillium", "paecilomyces",
    "steinernema", "heterorhabditis",
    "nomuraea", "hirsutella",
    # Pure compounds
    "azadirachtin", "rotenone", "pyrethrin", "spinosad",
    "abamectin", "avermectin", "emamectin",
    "thymol", "carvacrol", "eugenol", "linalool",
    "limonene", "citronellal", "geraniol",
    "cinnamaldehyde", "methyl eugenol",
    "capsaicin", "nicotine", "anabasine",
    "karanjin", "nimbin", "gedunin",
    "quassin", "deguelin", "tephrosin",
]

# Regex: "X extract", "X oil", "X seed extract", "X leaf extract" etc.
EXTRACT_PATTERNS = [
    re.compile(
        r'\b([A-Z][a-z]+(?:\s+[a-z]+)?)\s+'
        r'(?:extract|oil|seed extract|leaf extract|bark extract|'
        r'root extract|fruit extract|essential oil|powder|'
        r'aqueous extract|ethanolic extract|methanolic extract)\b',
        re.IGNORECASE
    ),
    # "extract of X"
    re.compile(
        r'\bextract\s+of\s+([A-Z][a-z]+(?:\s+[a-z]+)?)\b',
        re.IGNORECASE
    ),
    # Latin binomial: "Genus species"
    re.compile(
        r'\b([A-Z][a-z]{2,}\s+[a-z]{3,})\s+'
        r'(?:extract|oil|leaf|seed|bark|root|fruit|powder)\b'
    ),
]

# Pure compound name patterns (chemical names)
COMPOUND_PATTERNS = [
    re.compile(
        r'\b(azadirachtin|rotenone|pyrethrin|spinosad|abamectin|'
        r'thymol|carvacrol|eugenol|linalool|limonene|citronellal|'
        r'geraniol|cinnamaldehyde|capsaicin|nicotine|karanjin|'
        r'nimbin|gedunin|quassin|deguelin|tephrosin|'
        r'nerolidol|farnesol|bisabolol|chamazulene|'
        r'methyl chavicol|estragole|safrole|asarone)\b',
        re.IGNORECASE
    ),
]

# Microbial patterns
MICROBIAL_PATTERNS = [
    re.compile(
        r'\b(Bacillus\s+\w+|Beauveria\s+\w+|Metarhizium\s+\w+|'
        r'Trichoderma\s+\w+|Isaria\s+\w+|Lecanicillium\s+\w+|'
        r'Paecilomyces\s+\w+|Steinernema\s+\w+|Nomuraea\s+\w+)\b'
    ),
]

# Stopwords — things that look like compounds but aren't
STOPWORDS = {
    "this extract", "plant extract", "crude extract", "test extract",
    "the extract", "leaf extract", "seed extract", "root extract",
    "bark extract", "fruit extract", "stem extract",
    "water extract", "control", "treatment", "results",
    "significant", "mortality", "concentration", "solution",
    "application", "culture", "medium", "sample",
}


# ─────────────────────────────────────────────
# EXTRACTION FUNCTIONS
# ─────────────────────────────────────────────

def extract_compounds_from_text(text):
    """Returns set of candidate compound names from text."""
    if not text:
        return set()
    found = set()

    # 1. Pure compound names
    for pat in COMPOUND_PATTERNS:
        for m in pat.finditer(text):
            found.add(m.group(1).lower().strip())

    # 2. Microbial names
    for pat in MICROBIAL_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1).strip()
            # Normalize: "Bacillus thuringiensis var kurstaki" → "bacillus thuringiensis"
            parts = name.lower().split()
            if len(parts) >= 2:
                found.add(" ".join(parts[:2]))

    # 3. Plant extract patterns
    for pat in EXTRACT_PATTERNS:
        for m in pat.finditer(text):
            name = m.group(1).lower().strip()
            if len(name) > 3 and name not in STOPWORDS:
                found.add(name)

    # 4. Known genera direct mention
    lower = text.lower()
    for genus in PLANT_GENERA:
        if re.search(r'\b' + re.escape(genus) + r'\b', lower):
            found.add(genus)

    # Filter: remove stopwords and very short names
    found = {
        f for f in found
        if len(f) > 4
        and f not in STOPWORDS
        and not f.startswith("the ")
        and not f.startswith("this ")
        and not any(sw in f for sw in ["extract of", "control", "treatment"])
    }
    return found


def normalize_compound_name(name):
    """Clean and normalize a compound name."""
    name = name.strip().lower()
    name = re.sub(r'\s+', ' ', name)
    # Remove trailing noise words
    for suffix in [" extract", " oil", " powder", " leaf", " seed", " bark", " root"]:
        if name.endswith(suffix) and len(name) > len(suffix) + 4:
            base = name[:-len(suffix)].strip()
            # Keep suffix if base alone is too vague
            if len(base) > 5:
                name = base
    return name


# ─────────────────────────────────────────────
# DB OPERATIONS
# ─────────────────────────────────────────────

def get_existing_compounds(conn):
    rows = conn.execute("SELECT id, name FROM compounds").fetchall()
    return {r[1].lower().strip(): r[0] for r in rows}


def get_all_papers(conn):
    """Read all papers from DB — title + abstract."""
    try:
        rows = conn.execute(
            "SELECT id, pubmed_id, pmcid, title, abstract, pest, crop FROM papers"
        ).fetchall()
        return [{"id": r[0], "pubmed_id": r[1], "pmcid": r[2],
                 "title": r[3] or "", "abstract": r[4] or "",
                 "pest": r[5] or "", "crop": r[6] or ""}
                for r in rows]
    except Exception as e:
        print(f"  Error reading papers: {e}")
        return []


def add_compound(conn, name):
    conn.execute("INSERT OR IGNORE INTO compounds (name) VALUES (?)", (name,))


# ─────────────────────────────────────────────
# PATCH day12 TO READ FROM DB
# ─────────────────────────────────────────────

DAY12_DB_LOADER = '''
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
'''


def patch_day12(dry_run=False):
    """Add DB loader to day12 and make load_sources() call it."""
    path = "day12_populate_bioactivity.py"
    if not os.path.exists(path):
        print(f"  WARNING: {path} not found — skipping patch")
        return False

    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()

    if "load_sources_from_db" in src:
        print(f"  day12 already patched — skipping")
        return True

    # Add the DB loader function before def load_sources()
    if "def load_sources():" in src:
        src = src.replace(
            "def load_sources():",
            DAY12_DB_LOADER + "\ndef load_sources():"
        )
        # Make load_sources() call the DB loader at the end
        old_return = "    print(f\"  Text sources loaded: {len(sources)}\")\n    return sources"
        new_return = (
            "    # Also load from DB (primary source)\n"
            "    db_sources = load_sources_from_db()\n"
            "    # Merge, deduplicate by paper_id\n"
            "    seen = {s['paper_id'] for s in sources}\n"
            "    for s in db_sources:\n"
            "        if s['paper_id'] not in seen:\n"
            "            sources.append(s)\n"
            "            seen.add(s['paper_id'])\n"
            "    print(f\"  Total text sources (JSON + DB): {len(sources)}\")\n"
            "    return sources"
        )
        if old_return in src:
            src = src.replace(old_return, new_return)
            print(f"  day12 patched to read from DB")
        else:
            print(f"  WARNING: Could not find return statement in load_sources() — manual patch needed")

        if not dry_run:
            with open(path, 'w', encoding='utf-8', newline='\n') as f:
                f.write(src)
        return True
    else:
        print(f"  WARNING: load_sources() not found in day12 — skipping patch")
        return False


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(dry_run=False, min_frequency=2):
    print("\n" + "="*60)
    print("  DAY 16 — COMPOUND EXTRACTOR")
    print(f"  Reads 1177 papers → extracts compound names → updates DB")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    papers = get_all_papers(conn)
    existing = get_existing_compounds(conn)

    print(f"\n  Papers in DB:           {len(papers)}")
    print(f"  Existing compounds:     {len(existing)}")

    # ── Extract from all papers ──
    print("\n  Scanning paper abstracts...")
    candidate_counter = Counter()
    paper_compound_map = {}  # compound → set of paper ids

    for paper in papers:
        text = paper["title"] + " " + paper["abstract"]
        found = extract_compounds_from_text(text)
        for compound in found:
            normalized = normalize_compound_name(compound)
            if len(normalized) < 4:
                continue
            candidate_counter[normalized] += 1
            if normalized not in paper_compound_map:
                paper_compound_map[normalized] = set()
            paper_compound_map[normalized].add(paper["id"])

    print(f"  Unique candidates found: {len(candidate_counter)}")

    # ── Filter by frequency ──
    qualified = {
        name: count
        for name, count in candidate_counter.items()
        if count >= min_frequency
    }
    print(f"  Qualified (freq >= {min_frequency}): {len(qualified)}")

    # ── Find new ones ──
    new_compounds = {
        name: count
        for name, count in qualified.items()
        if name not in existing
    }
    print(f"  New compounds to add:    {len(new_compounds)}")

    # ── Preview ──
    print(f"\n  Top new compounds by frequency:")
    for name, count in sorted(new_compounds.items(), key=lambda x: -x[1])[:20]:
        print(f"    {name:<35} mentioned in {count} papers")

    # ── Insert ──
    added = 0
    if not dry_run:
        for name in new_compounds:
            add_compound(conn, name)
            added += 1
        conn.commit()
        print(f"\n  Added {added} new compounds to DB")
    else:
        print(f"\n  DRY RUN — would add {len(new_compounds)} compounds")

    conn.close()

    # ── Patch day12 ──
    print("\n  Patching day12 to read from DB...")
    patch_day12(dry_run=dry_run)

    # ── Save log ──
    log = {
        "generated_at":    datetime.now().isoformat(),
        "dry_run":         dry_run,
        "papers_scanned":  len(papers),
        "candidates_found": len(candidate_counter),
        "qualified":       len(qualified),
        "new_added":       len(new_compounds),
        "top_compounds":   sorted(new_compounds.items(), key=lambda x: -x[1])[:50],
    }
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    # ── Summary ──
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    print(f"  Papers scanned:    {len(papers)}")
    print(f"  New compounds:     {len(new_compounds)}")
    print(f"  Log → {LOG_PATH}")
    if not dry_run:
        print(f"\n  Now run the full pipeline:")
        print(f"    python day15_compound_normalizer.py")
        print(f"    python day12_populate_bioactivity.py")
        print(f"    python day13_build_graph.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Extract compounds from all papers in DB")
    p.add_argument("--dry-run",  action="store_true")
    p.add_argument("--min-freq", type=int, default=2,
                   help="Minimum paper mentions to qualify (default 2)")
    args = p.parse_args()
    run(dry_run=args.dry_run, min_frequency=args.min_freq)
    