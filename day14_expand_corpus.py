"""
day14_expand_corpus.py
======================
Expands papers table to 1000+ using:
  PubMed, Semantic Scholar, Europe PMC, OpenAlex

Matches your actual papers table schema:
  id, pubmed_id, pmcid, title, abstract, content,
  pest, crop, source, has_fulltext, date_added, url, year
"""

import sqlite3, requests, time, os, sys, argparse, re
from datetime import datetime

try:
    from Bio import Entrez, Medline
    ENTREZ_OK = True
except ImportError:
    ENTREZ_OK = False

DB_PATH = "biopesticide.db"
ENTREZ_EMAIL = "prgynhandique@gmail.com"

PESTS = [
    {"pest": "Helicoverpa armigera",     "crop": "cotton",     "common": "cotton bollworm"},
    {"pest": "Spodoptera frugiperda",    "crop": "maize",      "common": "fall armyworm"},
    {"pest": "Spodoptera litura",        "crop": "soybean",    "common": "tobacco caterpillar"},
    {"pest": "Plutella xylostella",      "crop": "mustard",    "common": "diamondback moth"},
    {"pest": "Bemisia tabaci",           "crop": "tomato",     "common": "whitefly"},
    {"pest": "Nilaparvata lugens",       "crop": "rice",       "common": "brown planthopper"},
    {"pest": "Scirpophaga incertulas",   "crop": "rice",       "common": "stem borer"},
    {"pest": "Aphis gossypii",           "crop": "cotton",     "common": "cotton aphid"},
    {"pest": "Lipaphis erysimi",         "crop": "mustard",    "common": "mustard aphid"},
    {"pest": "Thrips palmi",             "crop": "chili",      "common": "chili thrips"},
    {"pest": "Meloidogyne incognita",    "crop": "tomato",     "common": "root knot nematode"},
    {"pest": "Fusarium oxysporum",       "crop": "tomato",     "common": "fusarium wilt"},
    {"pest": "Alternaria brassicae",     "crop": "mustard",    "common": "alternaria blight"},
    {"pest": "Pyricularia oryzae",       "crop": "rice",       "common": "rice blast"},
    {"pest": "Xanthomonas oryzae",       "crop": "rice",       "common": "bacterial blight"},
    {"pest": "Tetranychus urticae",      "crop": "vegetables", "common": "red spider mite"},
    {"pest": "Phenacoccus solenopsis",   "crop": "cotton",     "common": "mealybug"},
    {"pest": "Chilo partellus",          "crop": "maize",      "common": "spotted stem borer"},
    {"pest": "Callosobruchus maculatus", "crop": "chickpea",   "common": "pulse beetle"},
    {"pest": "Sitophilus oryzae",        "crop": "rice",       "common": "rice weevil"},
    {"pest": "Tribolium castaneum",      "crop": "wheat",      "common": "flour beetle"},
    {"pest": "Bactrocera dorsalis",      "crop": "mango",      "common": "fruit fly"},
    {"pest": "Leucinodes orbonalis",     "crop": "brinjal",    "common": "brinjal shoot borer"},
    {"pest": "Helicoverpa punctigera",   "crop": "chickpea",   "common": "native budworm"},
    {"pest": "Mythimna separata",        "crop": "wheat",      "common": "armyworm"},
]

QUERY_TEMPLATES = [
    "{pest} biopesticide",
    "{pest} plant extract insecticidal",
    "{pest} essential oil mortality",
    "{pest} botanical insecticide LC50",
    "{pest} microbial biocontrol",
    "{pest} natural compound efficacy",
    "{common} biopesticide control",
    "{common} natural insecticide mortality",
]

# ─────────────────────────────────────────────
# DB HELPERS — matches your exact schema
# ─────────────────────────────────────────────

def paper_exists(conn, pubmed_id=None, pmcid=None):
    if pubmed_id:
        if conn.execute("SELECT COUNT(*) FROM papers WHERE pubmed_id=?",
                        (str(pubmed_id),)).fetchone()[0] > 0:
            return True
    if pmcid:
        if conn.execute("SELECT COUNT(*) FROM papers WHERE pmcid=?",
                        (str(pmcid),)).fetchone()[0] > 0:
            return True
    return False

def insert_paper(conn, p):
    try:
        conn.execute("""
            INSERT INTO papers
                (pubmed_id, pmcid, title, abstract, pest, crop,
                 source, url, year, has_fulltext, date_added)
            VALUES (?,?,?,?,?,?,?,?,?,0,?)
        """, (
            str(p.get("pubmed_id","")) or None,
            str(p.get("pmcid",""))     or None,
            p.get("title","")[:500],
            p.get("abstract","")[:2000],
            p.get("pest",""),
            p.get("crop",""),
            p.get("source",""),
            p.get("url",""),
            p.get("year"),
            datetime.now().strftime("%Y-%m-%d"),
        ))
        return True
    except Exception as e:
        return False

def count_papers(conn):
    return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

def parse_year(s):
    m = re.search(r'\b(19|20)\d{2}\b', str(s))
    return int(m.group()) if m else None

# ─────────────────────────────────────────────
# SOURCE 1: PUBMED
# ─────────────────────────────────────────────

def search_pubmed(query, pest, crop, limit=100):
    if not ENTREZ_OK:
        return []
    results = []
    try:
        Entrez.email = ENTREZ_EMAIL
        handle = Entrez.esearch(db="pubmed", term=query, retmax=limit, sort="relevance")
        record = Entrez.read(handle)
        handle.close()
        ids = record.get("IdList", [])
        if not ids:
            return []
        time.sleep(0.4)
        handle = Entrez.efetch(db="pubmed", id=",".join(ids),
                               rettype="medline", retmode="text")
        for r in Medline.parse(handle):
            pmid = r.get("PMID","")
            if not pmid:
                continue
            results.append({
                "pubmed_id": pmid, "pmcid": "",
                "title":    r.get("TI",""),
                "abstract": r.get("AB",""),
                "pest": pest, "crop": crop,
                "source": "pubmed",
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "year": parse_year(r.get("DP","")),
            })
        handle.close()
        time.sleep(0.4)
    except Exception as e:
        print(f"    PubMed error: {e}")
    return results

# ─────────────────────────────────────────────
# SOURCE 2: SEMANTIC SCHOLAR
# ─────────────────────────────────────────────

def search_semantic_scholar(query, pest, crop, limit=100):
    results = []
    try:
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": min(limit,100),
                    "fields": "paperId,title,abstract,year,externalIds,openAccessPdf"},
            timeout=15)
        if r.status_code != 200:
            return []
        for p in r.json().get("data", []):
            ext = p.get("externalIds",{}) or {}
            pmid  = str(ext.get("PubMed",""))
            pmcid = str(ext.get("PubMedCentral",""))
            pid   = p.get("paperId","")
            pdf   = (p.get("openAccessPdf") or {}).get("url","")
            results.append({
                "pubmed_id": pmid,
                "pmcid":     pmcid,
                "title":     p.get("title","") or "",
                "abstract":  p.get("abstract","") or "",
                "pest": pest, "crop": crop,
                "source": "semantic_scholar",
                "url": pdf or f"https://www.semanticscholar.org/paper/{pid}",
                "year": p.get("year"),
                "_s2id": pid,
            })
        time.sleep(1.0)
    except Exception as e:
        print(f"    S2 error: {e}")
    return results

# ─────────────────────────────────────────────
# SOURCE 3: EUROPE PMC
# ─────────────────────────────────────────────

def search_europe_pmc(query, pest, crop, limit=100):
    results = []
    try:
        r = requests.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={"query": query, "resultType": "core",
                    "pageSize": min(limit,100), "format": "json"},
            timeout=15)
        if r.status_code != 200:
            return []
        for p in r.json().get("resultList",{}).get("result",[]):
            pmid  = str(p.get("pmid",""))
            pmcid = str(p.get("pmcid",""))
            if not pmid and not pmcid:
                continue
            results.append({
                "pubmed_id": pmid,
                "pmcid":     pmcid,
                "title":     p.get("title",""),
                "abstract":  p.get("abstractText","") or "",
                "pest": pest, "crop": crop,
                "source": "europe_pmc",
                "url": f"https://europepmc.org/article/MED/{pmid}" if pmid else "",
                "year": parse_year(str(p.get("pubYear",""))),
            })
        time.sleep(0.5)
    except Exception as e:
        print(f"    EuropePMC error: {e}")
    return results

# ─────────────────────────────────────────────
# SOURCE 4: OPENALEX
# ─────────────────────────────────────────────

def search_openalex(query, pest, crop, limit=100):
    results = []
    try:
        r = requests.get(
            "https://api.openalex.org/works",
            params={"search": query, "per-page": min(limit,100),
                    "select": "id,title,abstract_inverted_index,publication_year,open_access,doi,ids",
                    "mailto": ENTREZ_EMAIL},
            timeout=15)
        if r.status_code != 200:
            return []
        for p in r.json().get("results",[]):
            ids_block = p.get("ids",{}) or {}
            pmid  = str(ids_block.get("pmid","")).replace("https://pubmed.ncbi.nlm.nih.gov/","").strip("/")
            pmcid = str(ids_block.get("pmcid","")).replace("https://www.ncbi.nlm.nih.gov/pmc/articles/","").strip("/")
            oa_id = p.get("id","").replace("https://openalex.org/","")
            abstract = _reconstruct_abstract(p.get("abstract_inverted_index"))
            oa_url = (p.get("open_access",{}) or {}).get("oa_url","") or p.get("doi","") or ""
            results.append({
                "pubmed_id": pmid or "",
                "pmcid":     pmcid or "",
                "title":     p.get("title","") or "",
                "abstract":  abstract,
                "pest": pest, "crop": crop,
                "source": "openalex",
                "url": oa_url,
                "year": p.get("publication_year"),
                "_oaid": oa_id,
            })
        time.sleep(0.3)
    except Exception as e:
        print(f"    OpenAlex error: {e}")
    return results

def _reconstruct_abstract(inv):
    if not inv:
        return ""
    try:
        pos_word = {}
        for word, positions in inv.items():
            for pos in positions:
                pos_word[pos] = word
        return " ".join(pos_word[i] for i in sorted(pos_word))
    except Exception:
        return ""

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(dry_run=False, limit_per_query=100, target=1000):
    print("\n" + "="*60)
    print("  DAY 14 — CORPUS EXPANSION ENGINE")
    print(f"  Target: {target} | Sources: PubMed, S2, EuropePMC, OpenAlex")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    start = count_papers(conn)
    print(f"\n  Papers now: {start}  |  Need {max(0,target-start)} more\n")

    if start >= target:
        print(f"  Already at target. Use --target {target+500} to expand further.")
        conn.close()
        return

    total_new = 0
    total_dup = 0
    source_counts = {}

    # Track seen S2/OA ids within this run to avoid cross-source dupes
    seen_titles = set()

    for pest_item in PESTS:
        pest, crop, common = pest_item["pest"], pest_item["crop"], pest_item["common"]
        current = count_papers(conn) if not dry_run else start + total_new
        if current >= target:
            print(f"\n  Reached target of {target}. Stopping.")
            break

        print(f"\n  [{current}/{target}] {pest}")

        for template in QUERY_TEMPLATES:
            query = template.format(pest=pest, common=common)
            all_results = []
            all_results += search_pubmed(query, pest, crop, limit_per_query)
            all_results += search_semantic_scholar(query, pest, crop, limit_per_query)
            all_results += search_europe_pmc(query, pest, crop, limit_per_query)
            all_results += search_openalex(query, pest, crop, limit_per_query)

            new_q = 0
            for paper in all_results:
                title = (paper.get("title","") or "").strip().lower()[:80]
                if not title:
                    continue
                # Skip dupes by title within this run
                if title in seen_titles:
                    total_dup += 1
                    continue
                # Skip if already in DB
                pmid  = paper.get("pubmed_id","")
                pmcid = paper.get("pmcid","")
                if (pmid or pmcid) and paper_exists(conn, pmid, pmcid):
                    total_dup += 1
                    continue
                seen_titles.add(title)
                src = paper.get("source","unknown")
                source_counts[src] = source_counts.get(src,0) + 1
                total_new += 1
                new_q += 1
                if not dry_run:
                    insert_paper(conn, paper)

            if not dry_run:
                conn.commit()
            print(f"    {query[:55]:<55} +{new_q}")

            if not dry_run and count_papers(conn) >= target:
                break

    conn.close()

    final = (count_papers(sqlite3.connect(DB_PATH)) if not dry_run else start + total_new)
    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    print(f"  Started:  {start}")
    print(f"  Added:    {total_new}")
    print(f"  Dupes:    {total_dup}")
    print(f"  Total:    {final}")
    print(f"\n  By source:")
    for src, cnt in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"    {src:<22} {cnt}")
    if dry_run:
        print(f"\n  DRY RUN — nothing written.")
    else:
        print(f"\n  Next: python day12_populate_bioactivity.py")
        print(f"        python day13_build_graph.py")
    print("="*60 + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run",  action="store_true")
    p.add_argument("--limit",    type=int, default=100)
    p.add_argument("--target",   type=int, default=1000)
    args = p.parse_args()
    run(dry_run=args.dry_run, limit_per_query=args.limit, target=args.target)
    