"""
migrate_to_sqlite.py
====================
Migrates all existing JSON data files into a single SQLite database.

Run this ONCE from your project folder:
    python migrate_to_sqlite.py

It reads:
    - knowledge_base.json
    - compound_results.json
    - molecular_analysis.json
    - fulltext_data/fulltext_results.json

It creates:
    - biopesticide.db  (your new database)
"""

import sqlite3
import json
import os
import datetime

DB_FILE = "biopesticide.db"

# ─────────────────────────────────────────────
# STEP 1: CREATE THE DATABASE SCHEMA
# ─────────────────────────────────────────────

def create_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON")

    # TABLE 1: papers
    # Stores every research paper collected
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pubmed_id       TEXT UNIQUE,
            pmcid           TEXT UNIQUE,
            title           TEXT,
            abstract        TEXT,
            content         TEXT,
            pest            TEXT NOT NULL,
            crop            TEXT NOT NULL,
            source          TEXT,        -- 'pubmed', 'europe_pmc', 'semantic_scholar'
            has_fulltext    INTEGER DEFAULT 0,
            date_added      TEXT DEFAULT (datetime('now'))
        )
    """)

    # TABLE 2: compounds
    # Stores unique compounds (deduplicated across all pests)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compounds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT UNIQUE NOT NULL,
            molecular_weight REAL,
            logp            REAL,
            h_donors        INTEGER,
            h_acceptors     INTEGER,
            smiles          TEXT,
            pubchem_cid     TEXT,
            date_added      TEXT DEFAULT (datetime('now'))
        )
    """)

    # TABLE 3: bioactivity
    # Links compounds to papers with evidence
    # This is the most important table — it answers:
    # "Which compound works against which pest, from which paper?"
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bioactivity (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            compound_id     INTEGER NOT NULL REFERENCES compounds(id),
            paper_id        INTEGER NOT NULL REFERENCES papers(id),
            pest            TEXT NOT NULL,
            crop            TEXT NOT NULL,
            activity_type   TEXT,        -- 'insecticidal', 'repellent', 'antifeedant', etc.
            lc50            REAL,
            lc50_unit       TEXT,
            efficacy_pct    REAL,
            notes           TEXT,
            evidence_grade  TEXT,        -- 'A', 'B', 'C' (from your evidence_grades.json)
            date_added      TEXT DEFAULT (datetime('now')),
            UNIQUE(compound_id, paper_id, pest)
        )
    """)

    # TABLE 4: extraction_log
    # Tracks which papers were processed and their status
    # This gives you the checkpoint system for free
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS extraction_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pest            TEXT NOT NULL,
            crop            TEXT NOT NULL,
            source          TEXT NOT NULL,   -- 'pubmed', 'europe_pmc', etc.
            status          TEXT NOT NULL,   -- 'completed', 'failed', 'skipped'
            papers_found    INTEGER DEFAULT 0,
            compounds_found INTEGER DEFAULT 0,
            error_message   TEXT,
            run_date        TEXT DEFAULT (datetime('now'))
        )
    """)

    # Full-text search index on papers (huge query speed boost)
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts
        USING fts5(title, abstract, content, pest, crop, content='papers', content_rowid='id')
    """)

    conn.commit()
    print("✓ Database schema created: 4 tables + full-text search index")
    return conn


# ─────────────────────────────────────────────
# STEP 2: MIGRATE knowledge_base.json → papers table
# ─────────────────────────────────────────────

def migrate_knowledge_base(conn):
    if not os.path.exists("knowledge_base.json"):
        print("⚠ knowledge_base.json not found — skipping")
        return 0

    with open("knowledge_base.json", "r") as f:
        database = json.load(f)

    cursor = conn.cursor()
    total_inserted = 0
    total_skipped = 0

    for key, data in database.items():
        pest = data.get("pest", "")
        crop = data.get("crop", "")
        papers = data.get("papers", [])

        for paper in papers:
            pubmed_id = paper.get("pubmed_id", "")
            content   = paper.get("content", "")

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO papers
                        (pubmed_id, content, pest, crop, source)
                    VALUES (?, ?, ?, ?, ?)
                """, (pubmed_id, content, pest, crop, "pubmed"))

                if cursor.rowcount > 0:
                    total_inserted += 1
                else:
                    total_skipped += 1

            except Exception as e:
                print(f"  ✗ Error inserting paper {pubmed_id}: {e}")

        # Log completion for this pest
        cursor.execute("""
            INSERT INTO extraction_log (pest, crop, source, status, papers_found)
            VALUES (?, ?, ?, ?, ?)
        """, (pest, crop, "pubmed", "completed", len(papers)))

    conn.commit()
    print(f"✓ Papers migrated: {total_inserted} inserted, {total_skipped} duplicates skipped")
    return total_inserted


# ─────────────────────────────────────────────
# STEP 3: MIGRATE compound_results.json → compounds + bioactivity tables
# ─────────────────────────────────────────────

def migrate_compounds(conn):
    if not os.path.exists("compound_results.json"):
        print("⚠ compound_results.json not found — skipping")
        return 0

    with open("compound_results.json", "r") as f:
        results = json.load(f)

    cursor = conn.cursor()
    compounds_inserted = 0
    bioactivity_inserted = 0

    for key, data in results.items():
        pest      = data.get("pest", "")
        crop      = data.get("crop", "")
        compounds = data.get("compounds_found", [])

        for compound_name in compounds:
            if not compound_name or len(compound_name.strip()) < 2:
                continue

            # Insert compound (ignore if already exists)
            cursor.execute("""
                INSERT OR IGNORE INTO compounds (name)
                VALUES (?)
            """, (compound_name.strip().lower(),))

            if cursor.rowcount > 0:
                compounds_inserted += 1

            # Get compound id
            cursor.execute("SELECT id FROM compounds WHERE name = ?",
                           (compound_name.strip().lower(),))
            row = cursor.fetchone()
            if not row:
                continue
            compound_id = row[0]

            # Find a paper for this pest/crop to link to
            cursor.execute("""
                SELECT id FROM papers WHERE pest = ? AND crop = ? LIMIT 1
            """, (pest, crop))
            paper_row = cursor.fetchone()

            if paper_row:
                paper_id = paper_row[0]
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO bioactivity
                            (compound_id, paper_id, pest, crop)
                        VALUES (?, ?, ?, ?)
                    """, (compound_id, paper_id, pest, crop))

                    if cursor.rowcount > 0:
                        bioactivity_inserted += 1
                except Exception as e:
                    pass

    conn.commit()
    print(f"✓ Compounds migrated: {compounds_inserted} unique compounds")
    print(f"✓ Bioactivity links created: {bioactivity_inserted}")
    return compounds_inserted


# ─────────────────────────────────────────────
# STEP 4: MIGRATE molecular_analysis.json → compounds table (add RDKit data)
# ─────────────────────────────────────────────

def migrate_molecular_analysis(conn):
    if not os.path.exists("molecular_analysis.json"):
        print("⚠ molecular_analysis.json not found — skipping")
        return 0

    with open("molecular_analysis.json", "r") as f:
        analysis = json.load(f)

    cursor = conn.cursor()
    updated = 0

    # Handle both list and dict formats
    items = analysis if isinstance(analysis, list) else analysis.values()

    for item in items:
        name = item.get("name", item.get("compound", ""))
        if not name:
            continue

        mw  = item.get("molecular_weight", item.get("mw", None))
        logp = item.get("logp", item.get("LogP", None))
        hd  = item.get("h_donors", item.get("hbd", None))
        ha  = item.get("h_acceptors", item.get("hba", None))
        smi = item.get("smiles", None)

        cursor.execute("""
            UPDATE compounds
            SET molecular_weight = COALESCE(?, molecular_weight),
                logp             = COALESCE(?, logp),
                h_donors         = COALESCE(?, h_donors),
                h_acceptors      = COALESCE(?, h_acceptors),
                smiles           = COALESCE(?, smiles)
            WHERE name = ?
        """, (mw, logp, hd, ha, smi, name.strip().lower()))

        if cursor.rowcount > 0:
            updated += 1

    conn.commit()
    print(f"✓ Molecular properties updated: {updated} compounds enriched")
    return updated


# ─────────────────────────────────────────────
# STEP 5: MIGRATE fulltext_results.json → papers table (add full text + titles)
# ─────────────────────────────────────────────

def migrate_fulltext(conn):
    path = os.path.join("fulltext_data", "fulltext_results.json")
    if not os.path.exists(path):
        print("⚠ fulltext_data/fulltext_results.json not found — skipping")
        return 0

    with open(path, "r") as f:
        fulltext_data = json.load(f)

    cursor = conn.cursor()
    inserted = 0
    updated  = 0

    for key, data in fulltext_data.items():
        pest   = data.get("pest", "")
        crop   = data.get("crop", "")
        papers = data.get("papers", [])

        for paper in papers:
            pmcid    = paper.get("pmcid", "")
            title    = paper.get("title", "")
            abstract = paper.get("abstract", "")
            tables   = paper.get("experimental_tables", [])
            table_text = json.dumps(tables) if tables else None

            if not pmcid:
                continue

            # Try to update existing paper (matched by pmcid)
            cursor.execute("""
                UPDATE papers
                SET title = COALESCE(NULLIF(title,''), ?),
                    abstract = COALESCE(NULLIF(abstract,''), ?),
                    content = COALESCE(NULLIF(content,''), ?),
                    has_fulltext = 1
                WHERE pmcid = ?
            """, (title, abstract, table_text, pmcid))

            if cursor.rowcount > 0:
                updated += 1
            else:
                # Insert as new paper
                cursor.execute("""
                    INSERT OR IGNORE INTO papers
                        (pmcid, title, abstract, content, pest, crop, source, has_fulltext)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (pmcid, title, abstract, table_text, pest, crop, "europe_pmc", 1))

                if cursor.rowcount > 0:
                    inserted += 1

    conn.commit()
    print(f"✓ Full text migrated: {inserted} new papers, {updated} existing papers enriched")
    return inserted + updated


# ─────────────────────────────────────────────
# STEP 6: REBUILD FULL-TEXT SEARCH INDEX
# ─────────────────────────────────────────────

def rebuild_fts_index(conn):
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO papers_fts(papers_fts) VALUES('rebuild')")
        conn.commit()
        print("✓ Full-text search index rebuilt")
    except Exception as e:
        print(f"⚠ FTS rebuild warning (non-critical): {e}")


# ─────────────────────────────────────────────
# STEP 7: PRINT FINAL SUMMARY
# ─────────────────────────────────────────────

def print_summary(conn):
    cursor = conn.cursor()

    print("\n" + "="*55)
    print("MIGRATION COMPLETE — DATABASE SUMMARY")
    print("="*55)

    cursor.execute("SELECT COUNT(*) FROM papers")
    print(f"  Papers total:        {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM papers WHERE has_fulltext = 1")
    print(f"  Papers with fulltext:{cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM compounds")
    print(f"  Unique compounds:    {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM bioactivity")
    print(f"  Bioactivity links:   {cursor.fetchone()[0]}")

    cursor.execute("SELECT COUNT(*) FROM extraction_log")
    print(f"  Log entries:         {cursor.fetchone()[0]}")

    print("\n  Papers by pest:")
    cursor.execute("""
        SELECT pest, crop, COUNT(*) as n
        FROM papers
        GROUP BY pest, crop
        ORDER BY n DESC
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]} on {row[1]}: {row[2]} papers")

    print("\n  Top compounds found:")
    cursor.execute("""
        SELECT c.name, COUNT(b.id) as links
        FROM compounds c
        LEFT JOIN bioactivity b ON c.id = b.compound_id
        GROUP BY c.id
        ORDER BY links DESC
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]}: {row[1]} pest links")

    print(f"\n  Database saved to: {DB_FILE}")
    print("="*55)


# ─────────────────────────────────────────────
# MAIN — run all steps
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("BIOPESTICIDE DATABASE MIGRATION")
    print("Reading JSON files → SQLite")
    print("="*55)

    # Safety check: don't overwrite existing DB without warning
    if os.path.exists(DB_FILE):
        answer = input(f"\n⚠ {DB_FILE} already exists. Overwrite? (yes/no): ")
        if answer.strip().lower() != "yes":
            print("Migration cancelled.")
            exit()
        os.remove(DB_FILE)
        print(f"  Deleted old {DB_FILE}")

    print()
    conn = create_database()
    migrate_knowledge_base(conn)
    migrate_compounds(conn)
    migrate_molecular_analysis(conn)
    migrate_fulltext(conn)
    rebuild_fts_index(conn)
    print_summary(conn)
    conn.close()
    