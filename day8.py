import spacy
import json

nlp = spacy.load("en_core_web_sm")

CHEMICAL_KEYWORDS = [
    "neem", "azadirachtin", "pyrethrin", "rotenone",
    "spinosad", "beauveria", "metarhizium", "bacillus",
    "trichoderma", "karanja", "eucalyptus", "citronella",
    "garlic", "turmeric", "lantana", "extract", "oil",
    "alkaloid", "terpene", "flavonoid", "phenol"
]

def extract_compounds_smart(text):
    doc = nlp(text)
    
    found = []
    
    for keyword in CHEMICAL_KEYWORDS:
        if keyword.lower() in text.lower():
            found.append(keyword)
    
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PRODUCT", "SUBSTANCE"]:
            if len(ent.text) > 3:
                found.append(ent.text)
    
    return list(set(found))

def analyze_knowledge_base():
    with open("knowledge_base.json", "r") as f:
        database = json.load(f)
    
    print("BIOPESTICIDE COMPOUND EXTRACTION")
    print("Using spaCy NLP + Chemical Keywords")
    print("="*50)
    
    results = {}
    
    for key, data in database.items():
        pest = data['pest']
        crop = data['crop']
        
        all_text = ""
        for paper in data['papers']:
            all_text += paper['content'] + " "
        
        compounds = extract_compounds_smart(all_text)
        
        results[key] = {
            "pest": pest,
            "crop": crop,
            "compounds_found": compounds,
            "count": len(compounds)
        }
        
        print(f"\n{pest.upper()} on {crop.upper()}")
        print(f"Papers analyzed: {data['papers_found']}")
        if compounds:
            print(f"Compounds identified:")
            for c in compounds:
                print(f"  + {c}")
        else:
            print("No compounds found — need more papers")
    
    with open("compound_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print("\n" + "="*50)
    print("Results saved to compound_results.json")

analyze_knowledge_base()
