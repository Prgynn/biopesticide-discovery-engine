"""
day13_build_graph.py
====================
Builds a knowledge graph from the populated bioactivity table.

Graph structure:
  Pest ↔ Compound ↔ Plant/Crop ↔ Evidence ↔ Paper

Node types:  compound | pest | crop | paper
Edge types:  ACTIVE_AGAINST | FOUND_IN_PAPER | TREATS_CROP | SUPPORTED_BY

Outputs:
  knowledge_graph.json   — full graph (nodes + edges) for serialization
  graph_report.txt       — human-readable summary + traversal queries

Dependencies: sqlite3, json, collections (all stdlib)
Optional:     networkx (pip install networkx) for advanced graph algorithms
"""

import sqlite3
import json
import os
import sys
from collections import defaultdict, Counter
from datetime import datetime

DB_PATH    = "biopesticide.db"
OUTPUT_JSON = "knowledge_graph.json"
REPORT_TXT  = "graph_report.txt"


# ─────────────────────────────────────────────
# NODE / EDGE BUILDERS
# ─────────────────────────────────────────────

def build_graph(conn):
    """
    Query bioactivity + compounds + papers and construct
    nodes and edges dicts.
    """
    nodes = {}   # node_id → {type, label, properties}
    edges = []   # list of {source, target, relation, weight, properties}

    # ── Load compounds ──
    for row in conn.execute("SELECT id, name FROM compounds"):
        nid = f"compound:{row[0]}"
        nodes[nid] = {
            "id":    nid,
            "type":  "compound",
            "label": row[1],
            "properties": {"db_id": row[0]},
        }

    # ── Load bioactivity rows ──
    query = """
        SELECT
            b.id,
            b.compound_id,
            b.paper_id,
            b.pest,
            b.crop,
            b.lc50,
            b.lc50_unit,
            b.efficacy_pct,
            b.evidence_grade,
            c.name AS compound_name
        FROM bioactivity b
        JOIN compounds c ON c.id = b.compound_id
    """
    rows = conn.execute(query).fetchall()

    if not rows:
        print("  ERROR: bioactivity table is empty.")
        print("  Run day12_populate_bioactivity.py first.")
        sys.exit(1)

    print(f"  bioactivity rows: {len(rows)}")

    # Track which (compound, pest) pairs appear in multiple papers
    # for grade-A evidence scoring
    evidence_counter = Counter()

    for row in rows:
        (bio_id, compound_id, paper_id, pest, crop,
         lc50, lc50_unit, efficacy_pct, grade, cname) = row

        # ── Pest node ──
        pest_nid = f"pest:{pest.lower().replace(' ', '_')}" if pest else None
        if pest_nid and pest_nid not in nodes:
            nodes[pest_nid] = {
                "id":    pest_nid,
                "type":  "pest",
                "label": pest,
                "properties": {},
            }

        # ── Crop node ──
        crop_nid = f"crop:{crop.lower().replace(' ', '_')}" if crop else None
        if crop_nid and crop_nid not in nodes:
            nodes[crop_nid] = {
                "id":    crop_nid,
                "type":  "crop",
                "label": crop,
                "properties": {},
            }

        # ── Paper node ──
        paper_nid = f"paper:{paper_id}"
        if paper_nid not in nodes:
            nodes[paper_nid] = {
                "id":    paper_nid,
                "type":  "paper",
                "label": f"Paper {paper_id}",
                "properties": {"paper_id": paper_id},
            }

        # ── Evidence node (one per bioactivity row) ──
        evi_nid = f"evidence:{bio_id}"
        nodes[evi_nid] = {
            "id":    evi_nid,
            "type":  "evidence",
            "label": f"Evidence #{bio_id}",
            "properties": {
                "lc50":         lc50,
                "lc50_unit":    lc50_unit,
                "efficacy_pct": efficacy_pct,
                "grade":        grade,
            },
        }

        compound_nid = f"compound:{compound_id}"
        evidence_counter[(compound_nid, pest_nid)] += 1

        # ── Edges ──

        # Compound –[ACTIVE_AGAINST]→ Pest
        if pest_nid:
            edges.append({
                "source":   compound_nid,
                "target":   pest_nid,
                "relation": "ACTIVE_AGAINST",
                "weight":   _grade_weight(grade),
                "properties": {
                    "evidence_grade": grade,
                    "lc50":           lc50,
                    "lc50_unit":      lc50_unit,
                    "efficacy_pct":   efficacy_pct,
                },
            })

        # Compound –[SUPPORTED_BY]→ Evidence
        edges.append({
            "source":   compound_nid,
            "target":   evi_nid,
            "relation": "SUPPORTED_BY",
            "weight":   1,
            "properties": {},
        })

        # Evidence –[FOUND_IN_PAPER]→ Paper
        edges.append({
            "source":   evi_nid,
            "target":   paper_nid,
            "relation": "FOUND_IN_PAPER",
            "weight":   1,
            "properties": {},
        })

        # Pest –[ATTACKS_CROP]→ Crop
        if pest_nid and crop_nid:
            attack_edge = {
                "source":   pest_nid,
                "target":   crop_nid,
                "relation": "ATTACKS_CROP",
                "weight":   1,
                "properties": {},
            }
            # Add only once per (pest, crop) pair
            if attack_edge not in edges:
                edges.append(attack_edge)

        # Compound –[TREATS_CROP]→ Crop  (via this bioactivity record)
        if crop_nid:
            edges.append({
                "source":   compound_nid,
                "target":   crop_nid,
                "relation": "TREATS_CROP",
                "weight":   _grade_weight(grade),
                "properties": {"evidence_grade": grade},
            })

    return nodes, edges, evidence_counter


def _grade_weight(grade):
    return {"A": 4, "B": 3, "C": 2, "D": 1}.get(grade, 1)


# ─────────────────────────────────────────────
# TRAVERSAL QUERIES (pure Python, no networkx)
# ─────────────────────────────────────────────

def query_compounds_for_pest(nodes, edges, pest_label):
    """Which compounds are active against a given pest?"""
    pest_nid = f"pest:{pest_label.lower().replace(' ', '_')}"
    results  = []
    for e in edges:
        if e["target"] == pest_nid and e["relation"] == "ACTIVE_AGAINST":
            cnode = nodes.get(e["source"], {})
            results.append({
                "compound":       cnode.get("label", e["source"]),
                "evidence_grade": e["properties"].get("evidence_grade"),
                "lc50":           e["properties"].get("lc50"),
                "lc50_unit":      e["properties"].get("lc50_unit"),
                "efficacy_pct":   e["properties"].get("efficacy_pct"),
            })
    # Sort by grade weight descending
    results.sort(key=lambda x: _grade_weight(x["evidence_grade"] or "D"), reverse=True)
    return results


def query_pests_for_compound(nodes, edges, compound_name):
    """Which pests does a compound treat?"""
    # Find compound node id by label
    comp_nid = None
    for nid, n in nodes.items():
        if n["type"] == "compound" and compound_name.lower() in n["label"].lower():
            comp_nid = nid
            break
    if not comp_nid:
        return []

    results = []
    for e in edges:
        if e["source"] == comp_nid and e["relation"] == "ACTIVE_AGAINST":
            pnode = nodes.get(e["target"], {})
            results.append({
                "pest":           pnode.get("label", e["target"]),
                "evidence_grade": e["properties"].get("evidence_grade"),
                "lc50":           e["properties"].get("lc50"),
            })
    results.sort(key=lambda x: _grade_weight(x["evidence_grade"] or "D"), reverse=True)
    return results


def query_broad_spectrum_compounds(nodes, edges, min_pests=2):
    """Which compounds are active against ≥ N different pests?"""
    compound_pest_map = defaultdict(set)
    for e in edges:
        if e["relation"] == "ACTIVE_AGAINST":
            src = nodes.get(e["source"], {})
            tgt = nodes.get(e["target"], {})
            if src.get("type") == "compound" and tgt.get("type") == "pest":
                compound_pest_map[src.get("label", e["source"])].add(
                    tgt.get("label", e["target"])
                )
    return {
        cname: list(pests)
        for cname, pests in compound_pest_map.items()
        if len(pests) >= min_pests
    }


def query_best_evidence_per_pest(nodes, edges):
    """For each pest, return the top compound by evidence grade."""
    pest_best = {}
    for e in edges:
        if e["relation"] != "ACTIVE_AGAINST":
            continue
        src  = nodes.get(e["source"], {})
        tgt  = nodes.get(e["target"], {})
        pest = tgt.get("label", "")
        comp = src.get("label", "")
        grade = e["properties"].get("evidence_grade", "D")
        w = _grade_weight(grade)
        if pest not in pest_best or w > _grade_weight(pest_best[pest]["grade"]):
            pest_best[pest] = {
                "compound": comp,
                "grade":    grade,
                "lc50":     e["properties"].get("lc50"),
            }
    return pest_best


# ─────────────────────────────────────────────
# GRAPH STATS
# ─────────────────────────────────────────────

def graph_stats(nodes, edges):
    type_counts = Counter(n["type"] for n in nodes.values())
    rel_counts  = Counter(e["relation"] for e in edges)
    return type_counts, rel_counts


# ─────────────────────────────────────────────
# OPTIONAL: NETWORKX EXPORT
# ─────────────────────────────────────────────

def export_networkx(nodes, edges):
    """Build a NetworkX graph if available."""
    try:
        import networkx as nx
        G = nx.DiGraph()
        for nid, n in nodes.items():
            G.add_node(nid, **n)
        for e in edges:
            G.add_edge(e["source"], e["target"],
                       relation=e["relation"],
                       weight=e["weight"],
                       **e["properties"])
        return G
    except ImportError:
        return None


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print("\n" + "="*60)
    print("  DAY 13 — KNOWLEDGE GRAPH BUILDER")
    print("="*60)

    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)

    # ── Build graph ──
    print("\n  Building graph from bioactivity table...")
    nodes, edges, evi_counter = build_graph(conn)
    conn.close()

    type_counts, rel_counts = graph_stats(nodes, edges)

    print(f"\n  Graph summary:")
    print(f"    Nodes:  {len(nodes)}")
    for t, c in sorted(type_counts.items()):
        print(f"      {t:<12} {c}")
    print(f"    Edges:  {len(edges)}")
    for r, c in sorted(rel_counts.items()):
        print(f"      {r:<25} {c}")

    # ── Traversal queries ──
    print("\n  Running traversal queries...")

    broad = query_broad_spectrum_compounds(nodes, edges, min_pests=2)
    best  = query_best_evidence_per_pest(nodes, edges)

    # ── Save graph JSON ──
    graph_data = {
        "metadata": {
            "generated_at":  datetime.now().isoformat(),
            "node_count":    len(nodes),
            "edge_count":    len(edges),
            "node_types":    dict(type_counts),
            "edge_relations": dict(rel_counts),
        },
        "nodes": list(nodes.values()),
        "edges": edges,
        "queries": {
            "broad_spectrum_compounds": broad,
            "best_evidence_per_pest":   best,
        },
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(graph_data, f, indent=2)
    print(f"\n  Graph saved → {OUTPUT_JSON}")

    # ── Write report ──
    lines = []
    lines.append("="*60)
    lines.append("  BIOPESTICIDE KNOWLEDGE GRAPH REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("="*60)
    lines.append(f"\nNODES: {len(nodes)}")
    for t, c in sorted(type_counts.items()):
        lines.append(f"  {t:<14} {c}")
    lines.append(f"\nEDGES: {len(edges)}")
    for r, c in sorted(rel_counts.items()):
        lines.append(f"  {r:<28} {c}")

    lines.append("\n\nBROAD-SPECTRUM COMPOUNDS (active against ≥2 pests)")
    lines.append("-"*50)
    if broad:
        for cname, pests in sorted(broad.items(), key=lambda x: -len(x[1])):
            lines.append(f"  {cname}")
            for p in pests:
                lines.append(f"    → {p}")
    else:
        lines.append("  None found (need more bioactivity data)")

    lines.append("\n\nBEST EVIDENCE COMPOUND PER PEST")
    lines.append("-"*50)
    for pest, info in sorted(best.items()):
        lc50_str = f"LC50={info['lc50']}" if info.get("lc50") else "no LC50"
        lines.append(f"  {pest:<35} {info['compound']:<25} Grade={info['grade']}  {lc50_str}")

    lines.append("\n\nHOW TO QUERY THIS GRAPH")
    lines.append("-"*50)
    lines.append("""
  In Python:
    from day13_build_graph import *
    import sqlite3, json

    conn = sqlite3.connect('biopesticide.db')
    nodes, edges, _ = build_graph(conn)
    conn.close()

    # Which compounds treat aphids?
    results = query_compounds_for_pest(nodes, edges, 'Lipaphis erysimi')

    # What pests does azadirachtin treat?
    results = query_pests_for_compound(nodes, edges, 'azadirachtin')

    # Broad-spectrum candidates
    broad = query_broad_spectrum_compounds(nodes, edges, min_pests=3)
""")

    report = "\n".join(lines)
    with open(REPORT_TXT, "w") as f:
        f.write(report.encode('ascii','ignore').decode())
    print(f"  Report saved  → {REPORT_TXT}")

    # ── NetworkX ──
    G = export_networkx(nodes, edges)
    if G:
        try:
            import networkx as nx
            print(f"\n  NetworkX graph: {G.number_of_nodes()} nodes, "
                  f"{G.number_of_edges()} edges")
            # Degree centrality — which compounds are most connected?
            centrality = nx.degree_centrality(G)
            top_nodes  = sorted(centrality.items(), key=lambda x: -x[1])[:5]
            print("  Most connected nodes (centrality):")
            for nid, score in top_nodes:
                label = nodes.get(nid, {}).get("label", nid)
                print(f"    {label:<30} {score:.3f}")
        except Exception:
            pass
    else:
        print("\n  (Install networkx for centrality analysis: pip install networkx)")

    print("\n  Next step: python day14_evidence_grader.py")
    print("="*60 + "\n")

    # Quick preview
    print("  GRAPH EDGE SAMPLE (first 10 ACTIVE_AGAINST edges):")
    count = 0
    for e in edges:
        if e["relation"] == "ACTIVE_AGAINST" and count < 10:
            src_label = nodes.get(e["source"], {}).get("label", e["source"])
            tgt_label = nodes.get(e["target"], {}).get("label", e["target"])
            grade     = e["properties"].get("evidence_grade", "?")
            lc50      = e["properties"].get("lc50")
            lc50_str  = f" LC50={lc50}" if lc50 else ""
            print(f"    {src_label:<25} –ACTIVE_AGAINST→  {tgt_label:<30} Grade={grade}{lc50_str}")
            count += 1
    if count == 0:
        print("    (no ACTIVE_AGAINST edges — bioactivity table may be empty)")
    print()


if __name__ == "__main__":
    main()
    