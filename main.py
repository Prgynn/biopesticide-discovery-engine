import json
import time
from Bio import Entrez
from rdkit import Chem
from rdkit.Chem import Descriptors
from rdkit.Chem import rdMolDescriptors
import spacy
import requests

Entrez.email = "prgynhandique@gmail.com"
nlp = spacy.load("en_core_web_sm")

INDIAN_PESTS = [
    {"pest": "whitefly", "crop": "cotton"},
    {"pest": "aphids", "crop": "mustard"},
    {"pest": "stem borer", "crop": "rice"},
]

KNOWN_COMPOUNDS = {
    "neem": "CC1=C(C(=O)O)C(C)(C)OC1",
    "limonene": "CC1=CCC(=CC1)C(C)=C",
    "pyrethrin": "CC1=CC(=O)C(C)(C)C1CC=C",
    "rotenone": "O=C1OC2CC3=CC=CC=C3OC2C1",
}

def search_pubmed(query, max_results=2):
    try:
        handle = Entrez.esearch(
            db="pubmed",
            term=query,
            retmax=max_results
        )
        record = Entrez.read(handle)
        handle.close()
        ids = record["IdList"]
        
        papers = []
        for pid in ids:
            time.sleep(1)
            fetch = Entrez.efetch(
                db="pubmed",
                id=pid,
                rettype="medline",
                retmode="text"
            )
            text = fetch.read()
            fetch.close()
            papers.append({
                "source": "PubMed",
                "id": pid,
                "content": text[:800]
            })
        return papers
    except Exception as e:
        print(f"PubMed error: {e}")
        return []

def extract_compounds(text):
    doc = nlp(text)
    found = []
    
    keywords = ["neem", "pyrethrin", "rotenone",
                "limonene", "extract", "alkaloid",
                "terpene", "bacillus", "beauveria"]
    
    for keyword in keywords:
        if keyword.lower() in text.lower():
            found.append(keyword)
    
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PRODUCT"]:
            if len(ent.text) > 3:
                found.append(ent.text)
    
    return list(set(found))

def analyze_molecule(name):
    if name.lower() not in KNOWN_COMPOUNDS:
        return None
    
    smiles = KNOWN_COMPOUNDS[name.lower()]
    mol = Chem.MolFromSmiles(smiles)
    
    if mol is None:
        return None
    
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    
    safe = mw < 500 and logp < 5 and hbd <= 5 and hba <= 10
    
    return {
        "molecular_weight": round(mw, 2),
        "logP": round(logp, 2),
        "passes_safety_filter": safe
    }

def run_pipeline():
    print("\n" + "="*60)
    print("  BIOPESTICIDE DISCOVERY ENGINE")
    print("  Automated Pipeline for Indian Crop Pests")
    print("="*60)
    
    final_results = {}
    
    for item in INDIAN_PESTS:
        pest = item["pest"]
        crop = item["crop"]
        
        print(f"\n[SEARCHING] {pest} on {crop}")
        
        query = f"biopesticide {pest} {crop} natural"
        time.sleep(3)
        papers = search_pubmed(query, max_results=2)
        
        print(f"  Papers found: {len(papers)}")
        
        all_text = " ".join([p["content"] for p in papers])
        compounds = extract_compounds(all_text)
        
        print(f"  Compounds extracted: {compounds}")
        
        molecular_data = {}
        for compound in compounds:
            mol_analysis = analyze_molecule(compound)
            if mol_analysis:
                molecular_data[compound] = mol_analysis
                status = "PASS" if mol_analysis["passes_safety_filter"] else "FAIL"
                print(f"  {compound}: MW={mol_analysis['molecular_weight']} LogP={mol_analysis['logP']} Safety={status}")
        
        final_results[f"{pest}_{crop}"] = {
            "pest": pest,
            "crop": crop,
            "papers_analyzed": len(papers),
            "compounds_found": compounds,
            "molecular_analysis": molecular_data
        }
    
    with open("final_results.json", "w") as f:
        json.dump(final_results, f, indent=2)
    
    print("\n" + "="*60)
    print("PIPELINE COMPLETE")
    print(f"Results saved to final_results.json")
    print("="*60)

run_pipeline()
