"""
query_db.py
===========
Replaces day5.py — queries the SQLite database instead of JSON.

Usage:
    python query_db.py
"""

import sqlite3

DB_FILE = "biopesticide.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row   # allows column access by name
    return conn


# ── Query 1: Summary of entire database ──────────────────────────

def show_summary():
    conn = get_connection()
    cursor = conn.cursor()

    print("\n=== KNOWLEDGE BASE SUMMARY ===")

    cursor.execute("SELECT COUNT(*) as n FROM papers")
    print(f"Total papers: {cursor.fetchone()['n']}")

    cursor.execute("SELECT COUNT(*) as n FROM compounds")
    print(f"Unique compounds: {cursor.fetchone()['n']}")

    cursor.execute("SELECT COUNT(*) as n FROM bioactivity")
    print(f"Bioactivity links: {cursor.fetchone()['n']}")

    print("\nPapers per pest:")
    cursor.execute("""
        SELECT pest, crop, COUNT(*) as n
        FROM papers GROUP BY pest, crop ORDER BY n DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row['pest']} on {row['crop']}: {row['n']} papers")

    conn.close()


# ── Query 2: All compounds for a specific pest ───────────────────

def query_by_pest(pest, crop=None):
    conn = get_connection()
    cursor = conn.cursor()

    if crop:
        print(f"\n=== Compounds for {pest} on {crop} ===")
        cursor.execute("""
            SELECT DISTINCT c.name, c.molecular_weight, c.logp,
                            b.activity_type, b.lc50, b.lc50_unit, b.efficacy_pct
            FROM compounds c
            JOIN bioactivity b ON c.id = b.compound_id
            WHERE LOWER(b.pest) LIKE ? AND LOWER(b.crop) LIKE ?
            ORDER BY c.name
        """, (f"%{pest.lower()}%", f"%{crop.lower()}%"))
    else:
        print(f"\n=== Compounds for {pest} (all crops) ===")
        cursor.execute("""
            SELECT DISTINCT c.name, c.molecular_weight, c.logp,
                            b.activity_type, b.lc50, b.lc50_unit, b.crop
            FROM compounds c
            JOIN bioactivity b ON c.id = b.compound_id
            WHERE LOWER(b.pest) LIKE ?
            ORDER BY c.name
        """, (f"%{pest.lower()}%",))

    rows = cursor.fetchall()
    if not rows:
        print("  No compounds found.")
    for row in rows:
        mw   = f", MW={row['molecular_weight']:.1f}" if row['molecular_weight'] else ""
        logp = f", LogP={row['logp']:.2f}" if row['logp'] else ""
        print(f"  + {row['name']}{mw}{logp}")

    conn.close()
    return rows


# ── Query 3: Which pests does a compound work against? ───────────

def query_by_compound(compound_name):
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n=== Pests targeted by '{compound_name}' ===")
    cursor.execute("""
        SELECT DISTINCT b.pest, b.crop, b.activity_type,
                        b.lc50, b.lc50_unit, p.pubmed_id, p.pmcid
        FROM bioactivity b
        JOIN compounds c  ON c.id = b.compound_id
        JOIN papers p     ON p.id = b.paper_id
        WHERE LOWER(c.name) LIKE ?
        ORDER BY b.pest
    """, (f"%{compound_name.lower()}%",))

    rows = cursor.fetchall()
    if not rows:
        print("  Not found in database.")
    for row in rows:
        src = row['pubmed_id'] or row['pmcid'] or "unknown"
        print(f"  → {row['pest']} on {row['crop']} (source: {src})")

    conn.close()
    return rows


# ── Query 4: Full-text search across all papers ──────────────────

def search_papers(keyword):
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n=== Papers matching '{keyword}' ===")
    try:
        cursor.execute("""
            SELECT p.pest, p.crop, p.pubmed_id, p.pmcid,
                   snippet(papers_fts, 2, '>>>', '<<<', '...', 20) as snippet
            FROM papers_fts
            JOIN papers p ON papers_fts.rowid = p.id
            WHERE papers_fts MATCH ?
            LIMIT 10
        """, (keyword,))

        rows = cursor.fetchall()
        if not rows:
            print("  No matching papers found.")
        for row in rows:
            src = row['pubmed_id'] or row['pmcid'] or "unknown"
            print(f"\n  [{row['pest']} on {row['crop']}] ID: {src}")
            print(f"  ...{row['snippet']}...")

    except Exception as e:
        print(f"  Search error: {e}")

    conn.close()


# ── Query 5: Cross-pest compounds (appears in 2+ pests) ──────────

def find_broad_spectrum_compounds(min_pests=2):
    conn = get_connection()
    cursor = conn.cursor()

    print(f"\n=== Broad-spectrum compounds (active against {min_pests}+ pests) ===")
    cursor.execute("""
        SELECT c.name, COUNT(DISTINCT b.pest) as pest_count,
               GROUP_CONCAT(DISTINCT b.pest) as pests
        FROM compounds c
        JOIN bioactivity b ON c.id = b.compound_id
        GROUP BY c.id
        HAVING pest_count >= ?
        ORDER BY pest_count DESC
    """, (min_pests,))

    rows = cursor.fetchall()
    if not rows:
        print("  None found yet.")
    for row in rows:
        print(f"  {row['name']}: {row['pest_count']} pests → {row['pests']}")

    conn.close()
    return rows


# ─────────────────────────────────────────────
# DEMO — runs when you execute this file
# ─────────────────────────────────────────────

if __name__ == "__main__":
    show_summary()

    # Same queries as your old day5.py
    query_by_pest("whitefly", "cotton")
    query_by_pest("stem borer", "rice")
    query_by_pest("thrips", "chili")

    # New queries not possible with JSON
    find_broad_spectrum_compounds(min_pests=2)
    search_papers("azadirachtin")
    query_by_compound("neem")
    