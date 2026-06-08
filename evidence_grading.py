"""
evidence_grading.py
====================
Builds a comprehensive evidence grading system combining:
  - Paper count (how many papers support this compound)
  - Efficacy % (how effective it is from experimental data)
  - Quality score (from your existing evidence_grades.json)
  - Field trial presence (real-world validation)

Grades:
  A = Strong evidence  (3+ papers, >70% efficacy, quality>60)
  B = Moderate evidence (2+ papers, >40% efficacy, quality>40)
  C = Weak evidence    (1 paper, some efficacy data)
  D = Insufficient     (mentioned only, no quantitative data)

Run:
    python evidence_grading.py
"""

import sqlite3
import json
import os

DB_FILE = "biopesticide.db"


# ─────────────────────────────────────────────
# LOAD EXISTING EVIDENCE GRADES JSON
# ─────────────────────────────────────────────

def load_existing_grades():
    """Parse evidence_grades.json into a lookup by compound name."""
    if not os.path.exists("evidence_grades.json"):
        print("⚠ evidence_grades.json not found")
        return {}

    with open("evidence_grades.json", "r") as f:
        data = json.load(f)

    # Build lookup: compound_name → best record found
    lookup = {}
    items = data if isinstance(data, list) else data.values()

    for item in items:
        compound = item.get("compound", "")
        if not compound:
            continue

        name = compound.strip().lower()
        existing = lookup.get(name, {})

        # Keep the record with highest quality score
        if item.get("quality_score", 0) >= existing.get("quality_score", 0):
            lookup[name] = {
                "quality_score":      item.get("quality_score", 50),
                "average_quality":    item.get("average_quality", 50),
                "field_trials_found": item.get("field_trials_found", False),
                "confidence_percent": item.get("confidence_percent", 0),
                "existing_grade":     item.get("evidence_grade", "D"),
                "supporting_papers":  item.get("supporting_papers", 1),
            }

    return lookup


# ─────────────────────────────────────────────
# GRADING ALGORITHM
# ─────────────────────────────────────────────

def calculate_grade(paper_count, avg_efficacy, max_efficacy,
                    lc50_count, quality_score, field_trials,
                    confidence_pct):
    """
    Score-based grading system.
    Returns (grade, score, reasoning)
    """
    score = 0
    reasons = []

    # ── PAPER COUNT (max 30 points) ──
    if paper_count >= 5:
        score += 30
        reasons.append(f"{paper_count} papers (+30)")
    elif paper_count >= 3:
        score += 20
        reasons.append(f"{paper_count} papers (+20)")
    elif paper_count >= 2:
        score += 12
        reasons.append(f"{paper_count} papers (+12)")
    elif paper_count == 1:
        score += 5
        reasons.append(f"1 paper (+5)")

    # ── EFFICACY % (max 35 points) ──
    if avg_efficacy is not None:
        if avg_efficacy >= 80:
            score += 35
            reasons.append(f"avg efficacy {avg_efficacy:.0f}% (+35)")
        elif avg_efficacy >= 60:
            score += 25
            reasons.append(f"avg efficacy {avg_efficacy:.0f}% (+25)")
        elif avg_efficacy >= 40:
            score += 15
            reasons.append(f"avg efficacy {avg_efficacy:.0f}% (+15)")
        elif avg_efficacy >= 20:
            score += 8
            reasons.append(f"avg efficacy {avg_efficacy:.0f}% (+8)")
        else:
            score += 2
            reasons.append(f"avg efficacy {avg_efficacy:.0f}% (+2)")
    else:
        reasons.append("no efficacy data (+0)")

    # ── LC50 DATA (max 15 points) ──
    if lc50_count >= 2:
        score += 15
        reasons.append(f"{lc50_count} LC50 values (+15)")
    elif lc50_count == 1:
        score += 8
        reasons.append("1 LC50 value (+8)")

    # ── QUALITY SCORE from existing grades (max 15 points) ──
    if quality_score >= 70:
        score += 15
        reasons.append(f"quality score {quality_score} (+15)")
    elif quality_score >= 50:
        score += 8
        reasons.append(f"quality score {quality_score} (+8)")
    elif quality_score >= 30:
        score += 3
        reasons.append(f"quality score {quality_score} (+3)")

    # ── FIELD TRIALS BONUS (5 points) ──
    if field_trials:
        score += 5
        reasons.append("field trial data (+5)")

    # ── ASSIGN GRADE ──
    if score >= 65:
        grade = "A"
    elif score >= 40:
        grade = "B"
    elif score >= 20:
        grade = "C"
    else:
        grade = "D"

    return grade, score, " | ".join(reasons)


# ─────────────────────────────────────────────
# MAIN GRADING FUNCTION
# ─────────────────────────────────────────────

def run_evidence_grading():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("EVIDENCE GRADING SYSTEM")
    print("="*65)

    existing_grades = load_existing_grades()
    print(f"Loaded {len(existing_grades)} compounds from evidence_grades.json")
    print()

    # Get all compounds with their bioactivity stats
    cursor.execute("""
        SELECT
            c.id,
            c.name,
            COUNT(DISTINCT b.paper_id)          AS paper_count,
            AVG(b.efficacy_pct)                 AS avg_efficacy,
            MAX(b.efficacy_pct)                 AS max_efficacy,
            COUNT(b.lc50)                       AS lc50_count,
            GROUP_CONCAT(DISTINCT b.pest)       AS pests,
            COUNT(DISTINCT b.pest)              AS pest_count
        FROM compounds c
        LEFT JOIN bioactivity b ON c.id = b.compound_id
        GROUP BY c.id
        ORDER BY paper_count DESC, avg_efficacy DESC
    """)
    compounds = cursor.fetchall()

    results = []

    print(f"{'Compound':<15} {'Papers':>6} {'AvgEff':>8} {'LC50s':>5} "
          f"{'QScore':>7} {'Score':>6} {'Grade':>5} {'Pests':>5}")
    print("-"*65)

    for comp in compounds:
        name        = comp['name']
        paper_count = comp['paper_count'] or 0
        avg_eff     = comp['avg_efficacy']
        max_eff     = comp['max_efficacy']
        lc50_count  = comp['lc50_count'] or 0
        pests       = comp['pests'] or ""
        pest_count  = comp['pest_count'] or 0

        # Pull data from existing evidence_grades.json
        existing    = existing_grades.get(name, {})
        quality     = existing.get("quality_score", 40)
        field_trials= existing.get("field_trials_found", False)
        confidence  = existing.get("confidence_percent", 0)
        old_grade   = existing.get("existing_grade", "D")

        grade, score, reasoning = calculate_grade(
            paper_count, avg_eff, max_eff,
            lc50_count, quality, field_trials, confidence
        )

        avg_str = f"{avg_eff:.0f}%" if avg_eff else "  -  "
        print(f"{name:<15} {paper_count:>6} {avg_str:>8} {lc50_count:>5} "
              f"{quality:>7} {score:>6} {grade:>5}  [{pest_count} pests]")

        results.append({
            "compound":        name,
            "grade":           grade,
            "score":           score,
            "paper_count":     paper_count,
            "avg_efficacy":    round(avg_eff, 1) if avg_eff else None,
            "max_efficacy":    max_eff,
            "lc50_count":      lc50_count,
            "quality_score":   quality,
            "field_trials":    field_trials,
            "pest_count":      pest_count,
            "pests_covered":   pests,
            "previous_grade":  old_grade,
            "reasoning":       reasoning,
        })

        # Update the bioactivity table with the new grade
        cursor.execute("""
            UPDATE bioactivity
            SET evidence_grade = ?
            WHERE compound_id = ?
        """, (grade, comp['id']))

    conn.commit()

    # ── SAVE GRADED RESULTS ──────────────────
    output_file = "graded_compounds.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    # ── SUMMARY BY GRADE ─────────────────────
    print("\n" + "="*65)
    print("GRADE SUMMARY")
    print("="*65)

    for grade_letter in ["A", "B", "C", "D"]:
        grade_compounds = [r for r in results if r["grade"] == grade_letter]
        label = {
            "A": "Strong evidence   — recommend for field testing",
            "B": "Moderate evidence — promising, needs more data",
            "C": "Weak evidence     — early stage, collect more papers",
            "D": "Insufficient      — mentioned only, no quantitative data"
        }[grade_letter]

        print(f"\n  Grade {grade_letter} — {label}")
        for r in grade_compounds:
            eff = f"eff={r['avg_efficacy']}%" if r['avg_efficacy'] else "no efficacy data"
            print(f"    • {r['compound']:<15} ({r['paper_count']} papers, {eff})")

    # ── TOP RECOMMENDATIONS ──────────────────
    print("\n" + "="*65)
    print("TOP COMPOUND RECOMMENDATIONS")
    print("="*65)
    top = sorted(results, key=lambda x: x["score"], reverse=True)[:5]
    for i, r in enumerate(top, 1):
        print(f"\n  #{i} {r['compound'].upper()}")
        print(f"     Grade: {r['grade']}  |  Score: {r['score']}/100")
        print(f"     Papers: {r['paper_count']}  |  "
              f"Avg Efficacy: {r['avg_efficacy']}%  |  "
              f"Pests covered: {r['pest_count']}")
        print(f"     Reasoning: {r['reasoning']}")

    print(f"\n  Full results saved to: {output_file}")
    print("="*65)

    conn.close()
    return results


if __name__ == "__main__":
    run_evidence_grading()
    