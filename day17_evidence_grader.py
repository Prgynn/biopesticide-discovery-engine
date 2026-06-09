"""
day17_evidence_grader.py
========================
Grades every compound-pest pair by evidence strength:

  Grade A  — 5+ independent papers confirm activity
  Grade B  — 2-4 papers confirm activity  
  Grade C  — 1 paper with quantitative data (LC50 or mortality %)
  Grade D  — 1 paper, mention only

Outputs:
  evidence_report.json   — full graded results
  discovery_list.txt     — ranked discovery list (your engine's output)

Run:
  python day17_evidence_grader.py
  python day17_evidence_grader.py --min-papers 3  (stricter Grade A threshold)
"""

import sqlite3, json, os, argparse
from collections import defaultdict
from datetime import datetime

DB_PATH       = "biopesticide.db"
REPORT_JSON   = "evidence_report.json"
DISCOVERY_TXT = "discovery_list.txt"


# ─────────────────────────────────────────────
# GRADE LOGIC
# ─────────────────────────────────────────────

def compute_grade(n_papers, has_lc50, has_mortality):
    """
    A  = 5+ papers
    B  = 2-4 papers OR 1 paper with LC50
    C  = 1 paper with mortality %
    D  = mention only
    """
    if n_papers >= 5:
        return "A"
    elif n_papers >= 2 or (n_papers >= 1 and has_lc50):
        return "B"
    elif has_mortality:
        return "C"
    else:
        return "D"


def grade_weight(g):
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(g, 0)


# ─────────────────────────────────────────────
# DB QUERIES
# ─────────────────────────────────────────────

def load_bioactivity(conn):
    """Load all bioactivity rows with compound names."""
    rows = conn.execute("""
        SELECT
            b.id, b.compound_id, c.name, b.paper_id,
            b.pest, b.crop, b.lc50, b.efficacy_pct, b.evidence_grade
        FROM bioactivity b
        JOIN compounds c ON c.id = b.compound_id
        WHERE b.pest IS NOT NULL AND b.pest != ''
    """).fetchall()
    return [
        {"id": r[0], "compound_id": r[1], "compound": r[2],
         "paper_id": r[3], "pest": r[4], "crop": r[5],
         "lc50": r[6], "mortality": r[7], "grade": r[8]}
        for r in rows
    ]


def update_grades(conn, updates):
    """Bulk update evidence grades in bioactivity table."""
    conn.executemany(
        "UPDATE bioactivity SET evidence_grade=? WHERE compound_id=? AND pest=?",
        [(g, cid, pest) for (cid, pest), g in updates.items()]
    )
    conn.commit()


# ─────────────────────────────────────────────
# GRADING ENGINE
# ─────────────────────────────────────────────

def grade_all(rows, min_grade_a=5):
    """
    Group by (compound, pest), count unique papers,
    compute grade, return graded pairs.
    """
    # Group rows by (compound_id, compound_name, pest, crop)
    groups = defaultdict(lambda: {
        "papers": set(), "lc50_values": [], "mortality_values": [],
        "compound": "", "crop": "", "compound_id": None
    })

    for r in rows:
        key = (r["compound_id"], r["pest"])
        g   = groups[key]
        g["compound"]    = r["compound"]
        g["compound_id"] = r["compound_id"]
        g["crop"]        = r["crop"]
        g["papers"].add(r["paper_id"])
        if r["lc50"] is not None:
            g["lc50_values"].append(r["lc50"])
        if r["mortality"] is not None:
            g["mortality_values"].append(r["mortality"])

    results = []
    for (compound_id, pest), data in groups.items():
        n_papers    = len(data["papers"])
        has_lc50    = len(data["lc50_values"]) > 0
        has_mort    = len(data["mortality_values"]) > 0
        grade = compute_grade(n_papers, has_lc50, has_mort)

        # Override threshold if user set --min-papers
        if min_grade_a != 5:
            if n_papers >= min_grade_a:
                grade = "A"
            elif n_papers >= 2:
                grade = "B"

        avg_lc50 = (sum(data["lc50_values"]) / len(data["lc50_values"])
                    if data["lc50_values"] else None)
        avg_mort = (sum(data["mortality_values"]) / len(data["mortality_values"])
                    if data["mortality_values"] else None)

        results.append({
            "compound_id":  compound_id,
            "compound":     data["compound"],
            "pest":         pest,
            "crop":         data["crop"],
            "n_papers":     n_papers,
            "grade":        grade,
            "has_lc50":     has_lc50,
            "avg_lc50":     round(avg_lc50, 3) if avg_lc50 else None,
            "has_mortality": has_mort,
            "avg_mortality": round(avg_mort, 2) if avg_mort else None,
            "paper_ids":    list(data["papers"])[:10],  # sample
        })

    # Sort: grade desc, then n_papers desc
    results.sort(key=lambda x: (-grade_weight(x["grade"]), -x["n_papers"]))
    return results


# ─────────────────────────────────────────────
# COMPOUND SUMMARY
# ─────────────────────────────────────────────

def compound_summary(graded):
    """Which compounds have the broadest + strongest evidence?"""
    summary = defaultdict(lambda: {
        "pests": set(), "grade_A": 0, "grade_B": 0,
        "grade_C": 0, "grade_D": 0, "total_papers": 0
    })
    for r in graded:
        c = r["compound"]
        summary[c]["pests"].add(r["pest"])
        summary[c][f"grade_{r['grade']}"] += 1
        summary[c]["total_papers"] += r["n_papers"]

    result = []
    for compound, data in summary.items():
        score = (data["grade_A"] * 4 + data["grade_B"] * 3 +
                 data["grade_C"] * 2 + data["grade_D"])
        result.append({
            "compound":     compound,
            "n_pests":      len(data["pests"]),
            "pests":        list(data["pests"]),
            "grade_A":      data["grade_A"],
            "grade_B":      data["grade_B"],
            "grade_C":      data["grade_C"],
            "grade_D":      data["grade_D"],
            "total_papers": data["total_papers"],
            "score":        score,
        })
    result.sort(key=lambda x: -x["score"])
    return result


# ─────────────────────────────────────────────
# REPORT WRITERS
# ─────────────────────────────────────────────

def write_json_report(graded, comp_summary, stats):
    report = {
        "generated_at": datetime.now().isoformat(),
        "stats":        stats,
        "top_compounds": comp_summary[:20],
        "graded_pairs": graded[:200],
    }
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


def write_discovery_list(graded, comp_summary, stats):
    lines = []
    lines.append("=" * 65)
    lines.append("  BIOPESTICIDE DISCOVERY ENGINE — RANKED EVIDENCE REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 65)

    lines.append(f"""
CORPUS SUMMARY
  Papers analysed:        {stats['total_papers']}
  Bioactivity records:    {stats['total_records']}
  Compound-pest pairs:    {stats['total_pairs']}
  Grade A pairs:          {stats['grade_A']}
  Grade B pairs:          {stats['grade_B']}
  Grade C pairs:          {stats['grade_C']}
  Grade D pairs:          {stats['grade_D']}
""")

    lines.append("=" * 65)
    lines.append("  TOP COMPOUNDS BY EVIDENCE STRENGTH")
    lines.append("  (Score = weighted sum across all pest targets)")
    lines.append("=" * 65)
    for i, c in enumerate(comp_summary[:15], 1):
        lines.append(f"""
  #{i:02d}  {c['compound'].upper()}
       Score:        {c['score']}
       Pest targets: {c['n_pests']}  {', '.join(c['pests'][:4])}{'...' if c['n_pests'] > 4 else ''}
       Grade A:      {c['grade_A']}  Grade B: {c['grade_B']}  Grade C: {c['grade_C']}
       Total papers: {c['total_papers']}""")

    lines.append("\n\n" + "=" * 65)
    lines.append("  GRADE A PAIRS  (confirmed by 5+ independent papers)")
    lines.append("=" * 65)
    grade_a = [r for r in graded if r["grade"] == "A"]
    if grade_a:
        for r in grade_a:
            lc50_str = f"  avg LC50={r['avg_lc50']}" if r["avg_lc50"] else ""
            mort_str = f"  avg mortality={r['avg_mortality']}%" if r["avg_mortality"] else ""
            lines.append(
                f"  {r['compound']:<28} -> {r['pest']:<30} "
                f"[{r['n_papers']} papers]{lc50_str}{mort_str}"
            )
    else:
        lines.append("  None yet — need more quantitative data in abstracts")
        lines.append("  (Run day10/day11 for full-text extraction to unlock Grade A)")

    lines.append("\n\n" + "=" * 65)
    lines.append("  GRADE B PAIRS  (2-4 papers or LC50 confirmed)")
    lines.append("=" * 65)
    grade_b = [r for r in graded if r["grade"] == "B"][:30]
    for r in grade_b:
        lc50_str = f"  LC50={r['avg_lc50']}" if r["avg_lc50"] else ""
        lines.append(
            f"  {r['compound']:<28} -> {r['pest']:<30} "
            f"[{r['n_papers']} papers]{lc50_str}"
        )

    lines.append("\n\n" + "=" * 65)
    lines.append("  BROAD-SPECTRUM CANDIDATES  (active against 3+ pests)")
    lines.append("=" * 65)
    broad = [c for c in comp_summary if c["n_pests"] >= 3]
    if broad:
        for c in broad[:10]:
            lines.append(f"  {c['compound']:<30} {c['n_pests']} pests: {', '.join(c['pests'])}")
    else:
        broad2 = [c for c in comp_summary if c["n_pests"] >= 2]
        lines.append("  (No compound active against 3+ pests yet)")
        if broad2:
            lines.append("  Compounds active against 2 pests:")
            for c in broad2[:5]:
                lines.append(f"    {c['compound']:<30} {', '.join(c['pests'])}")

    lines.append("\n\n" + "=" * 65)
    lines.append("  EVIDENCE GRADE EXPLANATION")
    lines.append("=" * 65)
    lines.append("""
  A  = 5+ independent papers confirm bioactivity (publication consensus)
  B  = 2-4 papers OR single paper with LC50 value
  C  = Single paper with mortality percentage only
  D  = Compound mentioned near pest, no quantitative data

  To upgrade D -> C: run day10/day11 full text extraction
  To upgrade C -> B: need LC50 values in paper text
  To upgrade B -> A: need 5+ papers per compound-pest pair
""")

    with open(DISCOVERY_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(min_grade_a=5, update_db=True):
    print("\n" + "="*60)
    print("  DAY 17 — EVIDENCE GRADER")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    rows = load_bioactivity(conn)
    print(f"\n  Bioactivity records: {len(rows)}")

    if not rows:
        print("  ERROR: bioactivity table empty. Run day12 first.")
        conn.close()
        return

    # ── Grade all pairs ──
    print("  Grading compound-pest pairs...")
    graded = grade_all(rows, min_grade_a=min_grade_a)

    # ── Stats ──
    grade_counts = {"A":0,"B":0,"C":0,"D":0}
    for r in graded:
        grade_counts[r["grade"]] += 1

    unique_papers = len({r["paper_id"] for r in rows})
    stats = {
        "total_records": len(rows),
        "total_pairs":   len(graded),
        "total_papers":  unique_papers,
        "grade_A":       grade_counts["A"],
        "grade_B":       grade_counts["B"],
        "grade_C":       grade_counts["C"],
        "grade_D":       grade_counts["D"],
    }

    # ── Compound summary ──
    comp_summary = compound_summary(graded)

    # ── Update DB grades ──
    if update_db:
        updates = {(r["compound_id"], r["pest"]): r["grade"] for r in graded}
        update_grades(conn, updates)
        print(f"  Updated {len(updates)} compound-pest grades in DB")

    conn.close()

    # ── Write reports ──
    write_json_report(graded, comp_summary, stats)
    write_discovery_list(graded, comp_summary, stats)

    # ── Print summary ──
    print("\n" + "="*60)
    print("  RESULTS")
    print("="*60)
    print(f"  Bioactivity records:  {len(rows)}")
    print(f"  Compound-pest pairs:  {len(graded)}")
    print(f"  Papers linked:        {unique_papers}")
    print(f"\n  Grade breakdown:")
    print(f"    A (5+ papers):      {grade_counts['A']}")
    print(f"    B (2-4 papers):     {grade_counts['B']}")
    print(f"    C (mortality data): {grade_counts['C']}")
    print(f"    D (mention only):   {grade_counts['D']}")

    print(f"\n  Top 10 compounds by evidence score:")
    for i, c in enumerate(comp_summary[:10], 1):
        print(f"    {i:2d}. {c['compound']:<30} score={c['score']:3d}  "
              f"pests={c['n_pests']}  papers={c['total_papers']}")

    print(f"\n  Grade A pairs (strongest evidence):")
    grade_a = [r for r in graded if r["grade"] == "A"]
    if grade_a:
        for r in grade_a[:10]:
            print(f"    {r['compound']:<25} -> {r['pest']:<28} [{r['n_papers']} papers]")
    else:
        print("    None yet — abstracts lack enough quantitative data")
        print("    Grade B pairs (next best):")
        for r in [x for x in graded if x["grade"]=="B"][:5]:
            print(f"      {r['compound']:<25} -> {r['pest']:<28} [{r['n_papers']} papers]")

    print(f"\n  Reports saved:")
    print(f"    {REPORT_JSON}")
    print(f"    {DISCOVERY_TXT}")
    print("="*60 + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Grade compound-pest evidence")
    p.add_argument("--min-papers", type=int, default=5,
                   help="Papers needed for Grade A (default 5)")
    p.add_argument("--no-update",  action="store_true",
                   help="Don't update grades in DB")
    args = p.parse_args()
    run(min_grade_a=args.min_papers, update_db=not args.no_update)
    