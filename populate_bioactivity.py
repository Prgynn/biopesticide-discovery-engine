"""
populate_bioactivity.py
========================
Reads every paper in the database, searches content for compound
names, extracts quantitative data, and populates the bioactivity table.

Run from your project folder:
    python populate_bioactivity.py
"""

import sqlite3
import re
import json
import os

DB_FILE = "biopesticide.db"

# ─────────────────────────────────────────────
# QUANTITATIVE DATA EXTRACTION PATTERNS
# ─────────────────────────────────────────────

# Matches: "LC50 = 45.2 ppm", "LC50 of 12 mg/L", "LC50: 0.5 µg/mL"
LC50_PATTERNS = [
    r'LC50\s*[=:of]+\s*(\d+\.?\d*)\s*(ppm|mg/L|µg/mL|ug/mL|mg/kg|ppb|%)',
    r'LD50\s*[=:of]+\s*(\d+\.?\d*)\s*(ppm|mg/L|µg/mL|ug/mL|mg/kg|ppb|%)',
    r'lethal concentration.*?(\d+\.?\d*)\s*(ppm|mg/L|µg/mL|ug/mL)',
]

# Matches: "85% mortality", "mortality of 92%", "90.5 % mortality"
MORTALITY_PATTERNS = [
    r'(\d+\.?\d*)\s*%\s*mortality',
    r'mortality\s*of\s*(\d+\.?\d*)\s*%',
    r'(\d+\.?\d*)\s*%\s*(?:larval\s*)?mortality',
    r'caused\s*(\d+\.?\d*)\s*%\s*(?:mortality|death|kill)',
    r'(\d+\.?\d*)\s*%\s*(?:control|efficacy|inhibition)',
    r'efficacy\s*of\s*(\d+\.?\d*)\s*%',
]

# Activity type keywords
ACTIVITY_KEYWORDS = {
    'insecticidal': ['insecticidal', 'insecticide', 'toxic', 'toxicity', 'lethal', 'mortality'],
    'repellent':    ['repellent', 'repellency', 'repel', 'deterrent'],
    'antifeedant':  ['antifeedant', 'feeding deterrent', 'anti-feeding', 'feeding inhibit'],
    'fungicidal':   ['fungicidal', 'antifungal', 'fungicide'],
    'nematicidal':  ['nematicidal', 'nematicide', 'nematode control'],
    'ovicidal':     ['ovicidal', 'egg hatching', 'oviposition'],
}


def extract_lc50(text):
    """Extract first LC50/LD50 value found in text."""
    for pattern in LC50_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1)), match.group(2)
            except:
                pass
    return None, None


def extract_efficacy(text):
    """Extract best (highest) efficacy/mortality % found in text."""
    values = []
    for pattern in MORTALITY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            try:
                val = float(match.group(1))
                if 0 < val <= 100:
                    values.append(val)
            except:
                pass
    return max(values) if values else None


def detect_activity_type(text):
    """Detect what kind of biological activity is described."""
    text_lower = text.lower()
    for activity, keywords in ACTIVITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return activity
    return 'insecticidal'  # default


def find_compound_in_text(compound_name, text):
    """Check if compound name appears in text (case-insensitive, whole word)."""
    pattern = r'\b' + re.escape(compound_name) + r'\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def get_context_window(compound_name, text, window=300):
    """Get text around where compound is mentioned — for better data extraction."""
    pattern = r'\b' + re.escape(compound_name) + r'\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        start = max(0, match.start() - window)
        end   = min(len(text), match.end() + window)
        return text[start:end]
    return text


# ─────────────────────────────────────────────
# LOAD EVIDENCE GRADES
# ─────────────────────────────────────────────

def load_evidence_grades():
    """Load evidence_grades.json if it exists."""
    if not os.path.exists("evidence_grades.json"):
        return {}
    with open("evidence_grades.json", "r") as f:
        data = json.load(f)

    # Build lookup: compound_name → grade
    grades = {}
    if isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, dict):
                name  = val.get("compound", val.get("name", key))
                grade = val.get("grade", val.get("evidence_grade", "C"))
                grades[name.lower()] = grade
            elif isinstance(val, str):
                grades[key.lower()] = val
    elif isinstance(data, list):
        for item in data:
            name  = item.get("compound", item.get("name", ""))
            grade = item.get("grade", item.get("evidence_grade", "C"))
            if name:
                grades[name.lower()] = grade
    return grades


def load_relationships():
    """Load relationships.json if it exists."""
    if not os.path.exists("relationships.json"):
        return {}
    with open("relationships.json", "r") as f:
        return json.load(f)


# ─────────────────────────────────────────────
# MAIN POPULATION LOGIC
# ─────────────────────────────────────────────

def populate_bioactivity():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("BIOACTIVITY TABLE POPULATION")
    print("="*55)

    # Load all compounds
    cursor.execute("SELECT id, name FROM compounds")
    compounds = cursor.fetchall()
    print(f"Compounds to search for: {len(compounds)}")

    # Load all papers
    cursor.execute("SELECT id, pubmed_id, pmcid, pest, crop, content, abstract, title FROM papers")
    papers = cursor.fetchall()
    print(f"Papers to scan: {len(papers)}")

    # Load supporting data
    evidence_grades = load_evidence_grades()
    relationships   = load_relationships()
    print(f"Evidence grades loaded: {len(evidence_grades)}")
    print(f"Relationships loaded: {len(relationships)}")
    print()

    inserted    = 0
    skipped     = 0
    no_match    = 0

    for paper in papers:
        paper_id = paper['id']
        pest     = paper['pest']
        crop     = paper['crop']

        # Combine all text fields for searching
        full_text = " ".join(filter(None, [
            paper['title']    or "",
            paper['abstract'] or "",
            paper['content']  or "",
        ]))

        if not full_text.strip():
            no_match += 1
            continue

        for compound in compounds:
            compound_id   = compound['id']
            compound_name = compound['name']

            # Check if compound appears in this paper
            if not find_compound_in_text(compound_name, full_text):
                continue

            # Get text window around compound mention for better extraction
            context = get_context_window(compound_name, full_text)

            # Extract quantitative data
            lc50_val, lc50_unit = extract_lc50(context)
            efficacy_pct        = extract_efficacy(context)
            activity_type       = detect_activity_type(context)

            # Get evidence grade
            grade = evidence_grades.get(compound_name.lower(), "C")

            # Build notes
            notes_parts = []
            if lc50_val:
                notes_parts.append(f"LC50={lc50_val} {lc50_unit}")
            if efficacy_pct:
                notes_parts.append(f"Efficacy={efficacy_pct}%")
            notes = "; ".join(notes_parts) if notes_parts else None

            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO bioactivity
                        (compound_id, paper_id, pest, crop,
                         activity_type, lc50, lc50_unit,
                         efficacy_pct, evidence_grade, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    compound_id, paper_id, pest, crop,
                    activity_type, lc50_val, lc50_unit,
                    efficacy_pct, grade, notes
                ))

                if cursor.rowcount > 0:
                    inserted += 1
                    marker = "★" if (lc50_val or efficacy_pct) else "·"
                    print(f"  {marker} [{pest}] {compound_name}"
                          + (f" | LC50={lc50_val} {lc50_unit}" if lc50_val else "")
                          + (f" | Efficacy={efficacy_pct}%" if efficacy_pct else ""))
                else:
                    skipped += 1

            except Exception as e:
                print(f"  ✗ Error: {e}")

    conn.commit()

    # ── PRINT FINAL SUMMARY ──────────────────
    print("\n" + "="*55)
    print("BIOACTIVITY POPULATION COMPLETE")
    print("="*55)
    print(f"  Records inserted:     {inserted}")
    print(f"  Duplicates skipped:   {skipped}")
    print(f"  Papers with no text:  {no_match}")

    print("\n  Top compounds by evidence count:")
    cursor.execute("""
        SELECT c.name, COUNT(b.id) as n,
               SUM(CASE WHEN b.lc50 IS NOT NULL THEN 1 ELSE 0 END) as has_lc50,
               SUM(CASE WHEN b.efficacy_pct IS NOT NULL THEN 1 ELSE 0 END) as has_efficacy
        FROM compounds c
        JOIN bioactivity b ON c.id = b.compound_id
        GROUP BY c.id
        ORDER BY n DESC
        LIMIT 15
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]:<20} {row[1]:>3} papers  "
              f"| LC50 data: {row[2]}  | Efficacy data: {row[3]}")

    print("\n  Bioactivity by pest:")
    cursor.execute("""
        SELECT pest, COUNT(DISTINCT compound_id) as compounds,
               COUNT(*) as records
        FROM bioactivity
        GROUP BY pest
        ORDER BY records DESC
    """)
    for row in cursor.fetchall():
        print(f"    {row[0]:<35} {row[1]} compounds, {row[2]} records")

    print("\n  Records WITH quantitative data:")
    cursor.execute("""
        SELECT COUNT(*) FROM bioactivity
        WHERE lc50 IS NOT NULL OR efficacy_pct IS NOT NULL
    """)
    print(f"    {cursor.fetchone()[0]} records have LC50 or efficacy % data")

    conn.close()
    print(f"\n  Database: {DB_FILE}")
    print("="*55)


if __name__ == "__main__":
    populate_bioactivity()
    