import json
import re

def score_paper_quality(content):
    score = 50
    content_lower = content.lower()
    
    high_impact = ["pest management", "journal of agricultural",
                   "crop protection", "biological control",
                   "phytochemistry", "pesticide biochemistry"]
    for journal in high_impact:
        if journal in content_lower:
            score += 15
            break
    
    if "field trial" in content_lower:
        score += 15
    elif "greenhouse" in content_lower:
        score += 8
    
    if "lc50" in content_lower:
        score += 10
    if "mortality" in content_lower:
        score += 5
    
    sample_matches = re.findall(r'n\s*=\s*(\d+)', content)
    if sample_matches:
        max_n = max(int(n) for n in sample_matches)
        if max_n > 100:
            score += 15
        elif max_n > 30:
            score += 8
    
    return min(score, 100)

def calculate_evidence_grade(paper_count, avg_quality,
                              replication_count, has_field_trial):
    score = 0
    
    if paper_count >= 10:
        score += 30
    elif paper_count >= 5:
        score += 20
    elif paper_count >= 2:
        score += 10
    
    score += (avg_quality / 100) * 25
    
    if replication_count >= 3:
        score += 25
    elif replication_count >= 2:
        score += 15
    elif replication_count >= 1:
        score += 8
    
    if has_field_trial:
        score += 20
    
    if score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "D"
    
    return round(score), grade

def analyze_compound_evidence(compound, database):
    supporting_papers = []
    quality_scores = []
    field_trial_found = False
    
    for key, data in database.items():
        for paper in data["papers"]:
            content = paper["content"].lower()
            if compound.lower() in content:
                quality = score_paper_quality(paper["content"])
                quality_scores.append(quality)
                supporting_papers.append({
                    "pest": data["pest"],
                    "crop": data["crop"],
                    "pubmed_id": paper["pubmed_id"],
                    "quality_score": quality
                })
                if "field trial" in content or "field study" in content:
                    field_trial_found = True
    
    if not supporting_papers:
        return None
    
    avg_quality = sum(quality_scores) / len(quality_scores)
    confidence, grade = calculate_evidence_grade(
        len(supporting_papers),
        avg_quality,
        len(supporting_papers),
        field_trial_found
    )
    
    return {
        "compound": compound,
        "supporting_papers": len(supporting_papers),
        "average_quality": round(avg_quality, 1),
        "field_trials_found": field_trial_found,
        "confidence_percent": confidence,
        "evidence_grade": grade,
        "paper_details": supporting_papers
    }

def run_evidence_analysis():
    with open("knowledge_base.json", "r") as f:
        database = json.load(f)
    
    COMPOUNDS_TO_TEST = [
        "neem", "azadirachtin", "pyrethrin",
        "Bacillus", "Beauveria", "Trichoderma",
        "spinosad", "rotenone", "extract",
        "Metarhizium", "limonene"
    ]
    
    print("EVIDENCE GRADING SYSTEM")
    print("="*60)
    
    results = []
    
    for compound in COMPOUNDS_TO_TEST:
        evidence = analyze_compound_evidence(compound, database)
        
        if evidence:
            results.append(evidence)
            print(f"\nCOMPOUND: {compound.upper()}")
            print(f"  Supporting papers: {evidence['supporting_papers']}")
            print(f"  Avg paper quality: {evidence['average_quality']}/100")
            print(f"  Field trials found: {evidence['field_trials_found']}")
            print(f"  CONFIDENCE: {evidence['confidence_percent']}%")
            print(f"  EVIDENCE GRADE: {evidence['evidence_grade']}")
    
    results.sort(key=lambda x: x["confidence_percent"], reverse=True)
    
    print("\n" + "="*60)
    print("TOP RANKED COMPOUNDS BY EVIDENCE STRENGTH:")
    print("="*60)
    for i, r in enumerate(results[:5]):
        print(f"{i+1}. {r['compound'].upper()}")
        print(f"   Grade: {r['evidence_grade']} | "
              f"Confidence: {r['confidence_percent']}% | "
              f"Papers: {r['supporting_papers']}")
    
    with open("evidence_grades.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nSaved to evidence_grades.json")

run_evidence_analysis()
