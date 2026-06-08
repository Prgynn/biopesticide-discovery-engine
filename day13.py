import json
import re

def extract_relationships(content, pest, crop):
    relationships = []
    content_lower = content.lower()
    
    COMPOUNDS = [
        "azadirachtin", "neem", "pyrethrin", "rotenone",
        "spinosad", "limonene", "eucalyptus", "citronella",
        "bacillus thuringiensis", "beauveria bassiana",
        "metarhizium anisopliae", "trichoderma",
        "karanja", "pongamia", "lantana", "calotropis",
        "garlic", "turmeric", "ginger", "pepper",
        "chrysanthemum", "tobacco", "nicotine",
        "essential oil", "plant extract", "botanical"
    ]
    
    EFFECTS = [
        "mortality", "repellent", "antifeedant",
        "ovicidal", "larvicidal", "pupicidal",
        "growth inhibition", "oviposition deterrent",
        "knockdown", "paralysis"
    ]
    
    for compound in COMPOUNDS:
        if compound not in content_lower:
            continue
        
        for effect in EFFECTS:
            if effect not in content_lower:
                continue
            
            percent_matches = re.findall(
                r'(\d+\.?\d*)\s*%', content
            )
            
            lc50_matches = re.findall(
                r'lc50\s*[=:]\s*(\d+\.?\d*)\s*(ppm|mg|µg|ug)',
                content_lower
            )
            
            concentration_matches = re.findall(
                r'(\d+\.?\d*)\s*(ppm|mg/l|µg/ml|%)',
                content_lower
            )
            
            study_type = "laboratory"
            if "field trial" in content_lower:
                study_type = "field_trial"
            elif "greenhouse" in content_lower:
                study_type = "greenhouse"
            elif "semi-field" in content_lower:
                study_type = "semi_field"
            
            relationship = {
                "compound": compound,
                "pest": pest,
                "crop": crop,
                "effect_type": effect,
                "study_type": study_type,
                "mortality_values": percent_matches[:5],
                "lc50_values": [
                    f"{m[0]} {m[1]}" for m in lc50_matches[:3]
                ],
                "concentrations_tested": [
                    f"{m[0]} {m[1]}" 
                    for m in concentration_matches[:5]
                ],
                "confidence": "high" if study_type == "field_trial"
                             else "medium" if study_type == "greenhouse"
                             else "low"
            }
            
            relationships.append(relationship)
            break
    
    return relationships

def build_relationship_database():
    with open("knowledge_base.json", "r") as f:
        database = json.load(f)
    
    all_relationships = []
    
    print("RELATIONSHIP EXTRACTOR")
    print("Building compound-pest-effect knowledge graph")
    print("="*60)
    
    for key, data in database.items():
        pest = data["pest"]
        crop = data["crop"]
        
        pest_relationships = []
        
        for paper in data["papers"]:
            content = paper["content"]
            relationships = extract_relationships(
                content, pest, crop
            )
            
            for rel in relationships:
                rel["pubmed_id"] = paper["pubmed_id"]
                pest_relationships.append(rel)
                all_relationships.append(rel)
        
        if pest_relationships:
            print(f"\n{pest} on {crop}:")
            unique_compounds = list(set(
                r["compound"] for r in pest_relationships
            ))
            for compound in unique_compounds:
                compound_rels = [
                    r for r in pest_relationships
                    if r["compound"] == compound
                ]
                field_trials = sum(
                    1 for r in compound_rels
                    if r["study_type"] == "field_trial"
                )
                print(f"  + {compound}: "
                      f"{len(compound_rels)} relationships, "
                      f"{field_trials} field trials")
    
    with open("relationships.json", "w") as f:
        json.dump(all_relationships, f, indent=2)
    
    print("\n" + "="*60)
    print(f"Total relationships extracted: {len(all_relationships)}")
    print("Saved to relationships.json")
    
    return all_relationships

def summarize_relationships(relationships):
    print("\nKNOWLEDGE SUMMARY")
    print("="*60)
    
    compound_counts = {}
    for rel in relationships:
        c = rel["compound"]
        if c not in compound_counts:
            compound_counts[c] = {
                "total": 0, 
                "field_trials": 0,
                "pests_covered": set()
            }
        compound_counts[c]["total"] += 1
        if rel["study_type"] == "field_trial":
            compound_counts[c]["field_trials"] += 1
        compound_counts[c]["pests_covered"].add(rel["pest"])
    
    sorted_compounds = sorted(
        compound_counts.items(),
        key=lambda x: x[1]["total"],
        reverse=True
    )
    
    print("\nTop compounds by evidence count:")
    for compound, data in sorted_compounds[:10]:
        pests = len(data["pests_covered"])
        print(f"  {compound}:")
        print(f"    Evidence records: {data['total']}")
        print(f"    Field trials: {data['field_trials']}")
        print(f"    Pests covered: {pests}")

relationships = build_relationship_database()
summarize_relationships(relationships)
