"""
extract_quantitative.py
========================
Extracts real numbers from fulltext table cells stored in the database
and updates the bioactivity table with LC50/efficacy data.

Run:
    python extract_quantitative.py
"""

import sqlite3
import re
import json

DB_FILE = "biopesticide.db"

# ─────────────────────────────────────────────
# CLEAN UNICODE GARBAGE FROM TABLE CELLS
# ─────────────────────────────────────────────

def clean_cell(text):
    """Remove unicode spaces, escape chars, and normalize text."""
    if not text:
        return ""
    # Replace unicode spaces and special chars
    text = text.replace('\u2009', ' ')   # thin space
    text = text.replace('\u00b1', '±')   # plus-minus
    text = text.replace('\u2013', '-')   # en dash
    text = text.replace('\u2014', '-')   # em dash
    text = text.replace('\u03bc', 'µ')   # mu
    text = text.replace('\u00b5', 'µ')   # micro
    text = text.replace('&gt;', '>')
    text = text.replace('&lt;', '<')
    text = text.replace('&amp;', '&')
    # Remove letter suffixes like "5.97a" → "5.97"
    text = re.sub(r'(\d+\.?\d*)[a-zA-Z]+$', r'\1', text.strip())
    return text.strip()


def extract_number(text):
    """Pull the first clean number out of a cell."""
    text = clean_cell(text)
    # Handle "45.2 ± 3.1" → take 45.2
    match = re.search(r'(\d+\.?\d*)', text)
    if match:
        try:
            return float(match.group(1))
        except:
            pass
    return None


# ─────────────────────────────────────────────
# DETECT WHAT TYPE OF DATA A COLUMN HEADER IS
# ─────────────────────────────────────────────

LC50_HEADERS = ['lc50', 'ld50', 'lc 50', 'lethal', 'lethal concentration',
                'lethal dose', 'lc', 'ic50']

EFFICACY_HEADERS = ['mortality', 'efficacy', 'control', 'inhibition',
                    'repellency', 'antifeedant', 'kill', 'death',
                    'percent', '%', 'activity']

CONCENTRATION_HEADERS = ['concentration', 'dose', 'ppm', 'mg/l',
                          'treatment', 'conc']

COMPOUND_HEADERS = ['compound', 'treatment', 'extract', 'chemical',
                    'material', 'substance', 'plant', 'botanical']


def classify_header(header):
    h = header.lower()
    if any(k in h for k in LC50_HEADERS):
        return 'lc50'
    if any(k in h for k in EFFICACY_HEADERS):
        return 'efficacy'
    if any(k in h for k in CONCENTRATION_HEADERS):
        return 'concentration'
    if any(k in h for k in COMPOUND_HEADERS):
        return 'compound_col'
    return 'other'


# ─────────────────────────────────────────────
# PARSE TABLE CELLS INTO STRUCTURED DATA
# ─────────────────────────────────────────────

def parse_table_cells(cells, caption=""):
    """
    Given a flat list of cells from a table, try to extract
    compound-efficacy pairs. Returns list of dicts.
    """
    results = []

    if not cells or len(cells) < 4:
        return results

    # Strategy 1: Look for LC50/mortality values directly in cells
    # Scan all cells for numbers adjacent to compound keywords
    COMPOUND_KEYWORDS = [
        'neem', 'azadirachtin', 'pyrethrin', 'rotenone', 'spinosad',
        'beauveria', 'metarhizium', 'bacillus', 'trichoderma', 'karanja',
        'eucalyptus', 'citronella', 'garlic', 'turmeric', 'lantana',
        'alkaloid', 'terpene', 'flavonoid', 'phenol', 'extract', 'oil'
    ]

    cells_clean = [clean_cell(c) for c in cells]

    for i, cell in enumerate(cells_clean):
        cell_lower = cell.lower()

        # Check if this cell contains a compound name
        found_compound = None
        for kw in COMPOUND_KEYWORDS:
            if kw in cell_lower:
                found_compound = kw
                break

        if found_compound:
            # Look at nearby cells for numbers
            window = cells_clean[max(0, i-3):min(len(cells_clean), i+6)]
            numbers = []
            for w in window:
                n = extract_number(w)
                if n is not None and 0 < n < 100000:
                    numbers.append(n)

            if numbers:
                # Guess if it's LC50 (usually larger) or efficacy % (0-100)
                efficacy_vals = [n for n in numbers if 0 < n <= 100]
                lc50_vals     = [n for n in numbers if n > 0]

                result = {'compound': found_compound}

                # Check caption for units
                cap_lower = caption.lower()
                if any(k in cap_lower for k in LC50_HEADERS):
                    if lc50_vals:
                        result['lc50'] = min(lc50_vals)  # take lowest LC50
                        result['lc50_unit'] = 'ppm'
                elif any(k in cap_lower for k in EFFICACY_HEADERS):
                    if efficacy_vals:
                        result['efficacy_pct'] = max(efficacy_vals)
                else:
                    # Best guess based on values
                    if efficacy_vals:
                        result['efficacy_pct'] = max(efficacy_vals)
                    if lc50_vals and min(lc50_vals) > 100:
                        result['lc50'] = min(lc50_vals)
                        result['lc50_unit'] = 'ppm'

                results.append(result)

    # Strategy 2: Scan all cells for bare LC50/mortality patterns
    full_text = " ".join(cells_clean)

    lc50_match = re.search(
        r'LC50\s*[=:of]*\s*(\d+\.?\d*)\s*(ppm|mg|µg|%)?',
        full_text, re.IGNORECASE
    )
    if lc50_match:
        results.append({
            'compound': None,  # will match to paper's pest later
            'lc50': float(lc50_match.group(1)),
            'lc50_unit': lc50_match.group(2) or 'ppm'
        })

    mortality_match = re.search(
        r'(\d+\.?\d*)\s*%\s*(?:mortality|control|efficacy)',
        full_text, re.IGNORECASE
    )
    if mortality_match:
        val = float(mortality_match.group(1))
        if 0 < val <= 100:
            results.append({
                'compound': None,
                'efficacy_pct': val
            })

    return results


# ─────────────────────────────────────────────
# MAIN EXTRACTION LOGIC
# ─────────────────────────────────────────────

def extract_from_fulltext():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("QUANTITATIVE DATA EXTRACTION FROM FULLTEXT TABLES")
    print("="*55)

    # Get all papers with fulltext
    cursor.execute("""
        SELECT id, pest, crop, content, pubmed_id, pmcid
        FROM papers
        WHERE has_fulltext = 1 AND content IS NOT NULL
    """)
    papers = cursor.fetchall()
    print(f"Papers with fulltext to scan: {len(papers)}")

    # Get compound lookup
    cursor.execute("SELECT id, name FROM compounds")
    compounds = {row['name']: row['id'] for row in cursor.fetchall()}

    updated  = 0
    inserted = 0

    for paper in papers:
        paper_id = paper['id']
        pest     = paper['pest']
        crop     = paper['crop']

        try:
            # Content is stored as JSON (list of table dicts)
            tables = json.loads(paper['content'])
            if not isinstance(tables, list):
                continue
        except:
            continue

        for table in tables:
            caption = table.get('caption', '')
            cells   = table.get('cells', [])

            if not cells:
                continue

            parsed = parse_table_cells(cells, caption)

            for record in parsed:
                compound_name = record.get('compound')
                lc50          = record.get('lc50')
                lc50_unit     = record.get('lc50_unit', 'ppm')
                efficacy_pct  = record.get('efficacy_pct')

                if not lc50 and not efficacy_pct:
                    continue

                if compound_name and compound_name in compounds:
                    compound_id = compounds[compound_name]
                else:
                    # Link to first compound already associated with this paper
                    cursor.execute("""
                        SELECT compound_id FROM bioactivity
                        WHERE paper_id = ? LIMIT 1
                    """, (paper_id,))
                    row = cursor.fetchone()
                    if not row:
                        continue
                    compound_id = row['compound_id']

                # Update existing bioactivity record with quantitative data
                cursor.execute("""
                    UPDATE bioactivity
                    SET lc50         = COALESCE(lc50, ?),
                        lc50_unit    = COALESCE(lc50_unit, ?),
                        efficacy_pct = COALESCE(efficacy_pct, ?)
                    WHERE compound_id = ? AND paper_id = ?
                    AND (lc50 IS NULL AND efficacy_pct IS NULL)
                """, (lc50, lc50_unit, efficacy_pct, compound_id, paper_id))

                if cursor.rowcount > 0:
                    updated += 1
                    name = [k for k, v in compounds.items() if v == compound_id]
                    name = name[0] if name else "unknown"
                    print(f"  ★ [{pest}] {name}"
                          + (f" LC50={lc50} {lc50_unit}" if lc50 else "")
                          + (f" Efficacy={efficacy_pct}%" if efficacy_pct else ""))

    conn.commit()

    # ── FINAL SUMMARY ────────────────────────
    print("\n" + "="*55)
    print("EXTRACTION COMPLETE")
    print("="*55)

    cursor.execute("""
        SELECT COUNT(*) FROM bioactivity
        WHERE lc50 IS NOT NULL OR efficacy_pct IS NOT NULL
    """)
    quant = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bioactivity")
    total = cursor.fetchone()[0]

    print(f"  Total bioactivity records:      {total}")
    print(f"  Records with quantitative data: {quant}")
    print(f"  Records updated this run:       {updated}")

    if quant > 0:
        print("\n  Sample quantitative records:")
        cursor.execute("""
            SELECT c.name, b.pest, b.lc50, b.lc50_unit, b.efficacy_pct
            FROM bioactivity b
            JOIN compounds c ON c.id = b.compound_id
            WHERE b.lc50 IS NOT NULL OR b.efficacy_pct IS NOT NULL
            LIMIT 10
        """)
        for row in cursor.fetchall():
            print(f"    {row[0]:<15} | {row[1]:<30}"
                  + (f" | LC50={row[2]} {row[3]}" if row[2] else "")
                  + (f" | Eff={row[4]}%" if row[4] else ""))

    conn.close()
    print("="*55)


if __name__ == "__main__":
    extract_from_fulltext()
    