import json

BIOPESTICIDE_COMPOUNDS = [
    "neem", "azadirachtin", "pyrethrin", "rotenone",
    "spinosad", "beauveria", "metarhizium", "bacillus",
    "trichoderma", "nimbecidine", "karanja", "pongamia",
    "eucalyptus", "citronella", "garlic", "ginger",
    "turmeric", "lantana", "calotropis", "parthenium"
]

def load_knowledge_base():
    with open("knowledge_base.json", "r") as f:
        return json.load(f)

def extract_compounds(text):
    text_lower = text.lower()
    found = []
    for compound in BIOPESTICIDE_COMPOUNDS:
        if compound in text_lower:
            found.append(compound)
    return found

def analyze_pest(pest, crop, database):
    key = f"{pest}_{crop}"
    
    if key not in database:
        print(f"No data for {pest} on {crop}")
        return
    
    data = database[key]
    all_compounds = []
    
    print(f"\n{'='*50}")
    print(f"ANALYSIS: {pest.upper()} on {crop.upper()}")
    print(f"{'='*50}")
    print(f"Papers analyzed: {data['papers_found']}")
    
    for paper in data['papers']:
        compounds = extract_compounds(paper['content'])
        all_compounds.extend(compounds)
    
    unique_compounds = list(set(all_compounds))
    
    if unique_compounds:
        print(f"\nNatural compounds identified:")
        for c in unique_compounds:
            print(f"  + {c}")
    else:
        print("\nNo known compounds found in current papers")
        print("Recommendation: expand search with broader query")
    
    print(f"\nConfidence: {'HIGH' if len(unique_compounds) > 2 else 'LOW — need more papers'}")

def run_full_analysis():
    database = load_knowledge_base()
    
    print("BIOPESTICIDE DISCOVERY ENGINE")
    print("Running analysis on all pests...\n")
    
    for key, data in database.items():
        pest = data['pest']
        crop = data['crop']
        analyze_pest(pest, crop, database)

run_full_analysis()
