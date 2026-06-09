"""
day15_compound_normalizer.py
============================
Normalizes all compound names in the database so that:
  "Azadirachtin", "azadirachtin", "AZADIRACHTIN", "Neem limonoid",
  "azadirachtin A", "Azadirachta indica extract"
  → all map to canonical: "azadirachtin"

What this script does:
  1. Loads all compounds from the compounds table
  2. Loads all bioactivity records
  3. Applies normalization rules (lowercase, alias mapping, fuzzy dedup)
  4. Merges duplicate compound records in the DB
  5. Updates all bioactivity rows to point to canonical compound_id
  6. Saves a normalization_log.json for audit

Run:
  python day15_compound_normalizer.py            # live
  python day15_compound_normalizer.py --dry-run  # preview only
"""

import sqlite3
import json
import re
import os
import sys
import argparse
from datetime import datetime

DB_PATH = "biopesticide.db"
LOG_PATH = "normalization_log.json"

# ─────────────────────────────────────────────
# MASTER CANONICAL MAP
# Format: "canonical_name": ["alias1", "alias2", ...]
# Canonical is always lowercase
# ─────────────────────────────────────────────

CANONICAL_MAP = {

    # ── Neem / Azadirachtin family ──
    "azadirachtin": [
        "azadirachtin", "azadirachtin a", "azadirachtin b",
        "neem limonoid", "neem extract", "neem oil", "neem seed extract",
        "neem kernel extract", "nske", "neem cake", "nimbecidine",
        "azadirachta indica extract", "azadirachta", "neemix",
        "nim extract", "margosa extract", "azatin",
    ],

    # ── Pyrethrin family ──
    "pyrethrin": [
        "pyrethrin", "pyrethrin i", "pyrethrin ii", "pyrethrins",
        "pyrethrum", "pyrethrum extract", "chrysanthemum extract",
        "tanacetum cinerariifolium extract", "natural pyrethroid",
    ],

    # ── Rotenone ──
    "rotenone": [
        "rotenone", "derris extract", "derris root extract",
        "tuba root extract", "cube resin", "fish poison",
        "lonchocarpus extract",
    ],

    # ── Spinosad / Spinosyn ──
    "spinosad": [
        "spinosad", "spinosyn a", "spinosyn d", "spinosyns",
        "saccharopolyspora spinosa extract", "tracer", "entrust",
        "naturalyte",
    ],

    # ── Abamectin / Avermectin ──
    "abamectin": [
        "abamectin", "avermectin", "avermectin b1", "ivermectin",
        "streptomyces avermitilis extract", "vertimec",
        "abacide", "agri-mek",
    ],

    # ── Bacillus thuringiensis ──
    "bacillus thuringiensis": [
        "bacillus thuringiensis", "bt", "b. thuringiensis",
        "bt var kurstaki", "bt kurstaki", "btk",
        "bt var israelensis", "bti", "bt var aizawai",
        "dipel", "thuricide", "agree", "javelin",
        "bacillus thuringiensis kurstaki", "bacillus thuringiensis israelensis",
    ],

    # ── Beauveria bassiana ──
    "beauveria bassiana": [
        "beauveria bassiana", "b. bassiana", "beauveria",
        "boverin", "naturalis", "mycotrol", "ostrinil",
        "beauveria brongniartii",
    ],

    # ── Metarhizium ──
    "metarhizium anisopliae": [
        "metarhizium anisopliae", "metarhizium", "m. anisopliae",
        "metarhizium robertsii", "metarhizium flavoviride",
        "bio-blast", "metarhizium sp",
    ],

    # ── Trichoderma ──
    "trichoderma": [
        "trichoderma", "trichoderma viride", "trichoderma harzianum",
        "trichoderma asperellum", "trichoderma atroviride",
        "t. harzianum", "trichoderma sp", "trichoderma spp",
        "trichodermin",
    ],

    # ── Limonene ──
    "limonene": [
        "limonene", "d-limonene", "l-limonene", "citrus oil",
        "orange peel extract", "orange oil", "citrus limon extract",
    ],

    # ── Eugenol ──
    "eugenol": [
        "eugenol", "clove oil", "clove extract",
        "syzygium aromaticum extract", "eugenia caryophyllata extract",
        "isoeugenol",
    ],

    # ── Thymol ──
    "thymol": [
        "thymol", "thyme oil", "thyme extract",
        "thymus vulgaris extract", "thymoquinone",
    ],

    # ── Carvacrol ──
    "carvacrol": [
        "carvacrol", "oregano oil", "oregano extract",
        "origanum vulgare extract", "isothymol",
    ],

    # ── Linalool ──
    "linalool": [
        "linalool", "lavender oil", "lavender extract",
        "lavandula extract", "coriander oil",
    ],

    # ── Cinnamaldehyde ──
    "cinnamaldehyde": [
        "cinnamaldehyde", "cinnamic aldehyde", "cinnamon oil",
        "cinnamon extract", "cinnamomum extract", "cinnamon bark extract",
    ],

    # ── Neem + Karanja (often confused) ──
    "karanjin": [
        "karanjin", "karanja oil", "karanja extract",
        "pongamia extract", "pongam oil", "honge oil",
        "millettia pinnata extract",
    ],

    # ── Nicotine ──
    "nicotine": [
        "nicotine", "nicotine sulfate", "tobacco extract",
        "nicotiana extract", "nicotiana tabacum extract",
    ],

    # ── Capsaicin ──
    "capsaicin": [
        "capsaicin", "capsicum extract", "hot pepper extract",
        "chili extract", "capsaicin extract", "capsicum oleoresin",
    ],

    # ── Neem + Azadirachtin clarification ──
    "nimbin": [
        "nimbin", "nimbidin", "nimbiol",
        "neem bitter compound",
    ],

    # ── Plant general (catch-all - keep separate) ──
    "plant extract": [
        "plant extract", "botanical extract", "herbal extract",
        "crude extract", "ethanolic extract", "methanolic extract",
        "aqueous extract", "hexane extract", "chloroform extract",
    ],
}

# Build reverse lookup: alias → canonical
ALIAS_TO_CANONICAL = {}
for canonical, aliases in CANONICAL_MAP.items():
    for alias in aliases:
        ALIAS_TO_CANONICAL[alias.lower().strip()] = canonical


# ─────────────────────────────────────────────
# NORMALIZATION FUNCTIONS
# ─────────────────────────────────────────────

def normalize_name(raw_name):
    """
    Returns (canonical_name, method) where method explains how it was normalized.
    Falls back to cleaned lowercase if no alias match found.
    """
    if not raw_name:
        return None, "empty"

    # Step 1: Clean
    cleaned = raw_name.strip().lower()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = re.sub(r'[^\w\s\-]', '', cleaned)

    # Step 2: Direct alias lookup
    if cleaned in ALIAS_TO_CANONICAL:
        return ALIAS_TO_CANONICAL[cleaned], "alias_match"

    # Step 3: Partial match — check if any canonical key is contained in name
    for canonical in CANONICAL_MAP:
        if canonical in cleaned:
            return canonical, "partial_match"

    # Step 4: Check if name contains any alias
    for alias, canonical in ALIAS_TO_CANONICAL.items():
        if len(alias) > 5 and alias in cleaned:
            return canonical, "substring_match"

    # Step 5: No match — return cleaned version as-is
    return cleaned, "cleaned_only"


def find_duplicate_compounds(compounds):
    """
    Group compounds that normalize to the same canonical name.
    Returns list of groups: [{canonical, ids: [...], names: [...]}]
    """
    groups = {}
    for c in compounds:
        canonical, method = normalize_name(c["name"])
        if canonical not in groups:
            groups[canonical] = {"canonical": canonical, "ids": [], "names": [], "methods": []}
        groups[canonical]["ids"].append(c["id"])
        groups[canonical]["names"].append(c["name"])
        groups[canonical]["methods"].append(method)

    # Only return groups with duplicates or mismatched names
    dupes = []
    for canonical, group in groups.items():
        # Check if any name differs from canonical
        has_mismatch = any(n.lower().strip() != canonical for n in group["names"])
        if has_mismatch or len(group["ids"]) > 1:
            dupes.append(group)
    return dupes


# ─────────────────────────────────────────────
# DB OPERATIONS
# ─────────────────────────────────────────────

def get_all_compounds(conn):
    return [{"id": r[0], "name": r[1]}
            for r in conn.execute("SELECT id, name FROM compounds ORDER BY id")]


def get_compound_bioactivity_count(conn, compound_id):
    return conn.execute(
        "SELECT COUNT(*) FROM bioactivity WHERE compound_id=?", (compound_id,)
    ).fetchone()[0]


def merge_compounds(conn, keep_id, merge_ids, canonical_name, dry_run=False):
    """
    Reassign all bioactivity rows from merge_ids to keep_id,
    then delete the duplicate compound rows,
    then update the kept compound's name to canonical.
    """
    actions = []

    for mid in merge_ids:
        if mid == keep_id:
            continue
        count = get_compound_bioactivity_count(conn, mid)
        actions.append(f"    Reassign {count} bioactivity rows: compound_id {mid} → {keep_id}")
        if not dry_run:
            conn.execute(
                "UPDATE bioactivity SET compound_id=? WHERE compound_id=?",
                (keep_id, mid)
            )
            conn.execute("DELETE FROM compounds WHERE id=?", (mid,))

    actions.append(f"    Rename compound {keep_id} → '{canonical_name}'")
    if not dry_run:
        conn.execute(
            "UPDATE compounds SET name=? WHERE id=?",
            (canonical_name, keep_id)
        )

    return actions


def add_missing_canonicals(conn, dry_run=False):
    """
    For any canonical compound in CANONICAL_MAP that doesn't exist
    in the DB yet, add it so future bioactivity records can reference it.
    """
    existing = {r[0].lower() for r in conn.execute("SELECT name FROM compounds")}
    added = []
    for canonical in CANONICAL_MAP:
        if canonical not in existing:
            added.append(canonical)
            if not dry_run:
                conn.execute("INSERT OR IGNORE INTO compounds (name) VALUES (?)", (canonical,))
    return added


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def run(dry_run=False):
    print("\n" + "="*60)
    print("  DAY 15 — COMPOUND NORMALIZER")
    print("="*60)

    conn = sqlite3.connect(DB_PATH)
    compounds = get_all_compounds(conn)
    print(f"\n  Compounds in DB:     {len(compounds)}")

    # ── Step 1: Find duplicates ──
    print("\n  Step 1: Scanning for duplicates and mismatches...")
    dupes = find_duplicate_compounds(compounds)
    print(f"  Groups needing normalization: {len(dupes)}")

    log = {
        "generated_at": datetime.now().isoformat(),
        "dry_run": dry_run,
        "normalizations": [],
        "added_canonicals": [],
    }

    total_merged = 0
    total_renamed = 0

    for group in dupes:
        canonical = group["canonical"]
        ids       = group["ids"]
        names     = group["names"]

        print(f"\n  Canonical: '{canonical}'")
        for i, (cid, name) in enumerate(zip(ids, names)):
            bio_count = get_compound_bioactivity_count(conn, cid)
            marker = "★ KEEP" if i == 0 else "  merge"
            print(f"    {marker}  id={cid}  '{name}'  ({bio_count} bioactivity rows)")

        # Keep the compound with the most bioactivity rows (most data)
        keep_id = max(ids, key=lambda cid: get_compound_bioactivity_count(conn, cid))
        merge_ids = [cid for cid in ids if cid != keep_id]

        actions = merge_compounds(conn, keep_id, merge_ids, canonical, dry_run)
        for a in actions:
            print(a)

        log["normalizations"].append({
            "canonical":  canonical,
            "keep_id":    keep_id,
            "merged_ids": merge_ids,
            "original_names": names,
            "actions":    actions,
        })

        total_merged  += len(merge_ids)
        total_renamed += 1

    # ── Step 2: Add missing canonical compounds ──
    print("\n  Step 2: Adding missing canonical compounds...")
    added = add_missing_canonicals(conn, dry_run)
    if added:
        for name in added:
            print(f"    + Added: '{name}'")
    else:
        print("    All canonical compounds already present.")
    log["added_canonicals"] = added

    # ── Step 3: Normalize names of existing compounds ──
    print("\n  Step 3: Normalizing remaining compound names...")
    compounds_fresh = get_all_compounds(conn)
    rename_count = 0
    for c in compounds_fresh:
        canonical, method = normalize_name(c["name"])
        if canonical and canonical != c["name"].lower().strip():
            print(f"    Rename: '{c['name']}' → '{canonical}'  ({method})")
            if not dry_run:
                conn.execute("UPDATE compounds SET name=? WHERE id=?", (canonical, c["id"]))
            rename_count += 1

    if not dry_run:
        conn.commit()

    conn.close()

    # ── Save log ──
    with open(LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)

    # ── Summary ──
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    print(f"  Duplicate groups merged:   {total_merged}")
    print(f"  Compounds renamed:         {total_renamed + rename_count}")
    print(f"  New canonicals added:      {len(added)}")
    print(f"  Log saved → {LOG_PATH}")
    if dry_run:
        print(f"\n  DRY RUN — no changes written.")
        print(f"  Run without --dry-run to apply.")
    else:
        print(f"\n  Done. Your compounds table is now normalized.")
        print(f"  Re-run day12 + day13 to rebuild bioactivity and graph.")
    print("="*60 + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Normalize compound names in DB")
    p.add_argument("--dry-run", action="store_true", help="Preview only, no DB writes")
    args = p.parse_args()
    run(dry_run=args.dry_run)
    