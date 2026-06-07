from Bio import Entrez
import json
import os
import time

Entrez.email = "prgynhandique@gmail.com"

INDIAN_PESTS = [
    {"pest": "whitefly", "crop": "cotton"},
    {"pest": "aphids", "crop": "mustard"},
    {"pest": "stem borer", "crop": "rice"},
    {"pest": "thrips", "crop": "chili"},
    {"pest": "brown planthopper", "crop": "rice"},
    {"pest": "Spodoptera frugiperda", "crop": "maize"},
    {"pest": "Helicoverpa armigera", "crop": "cotton"},
    {"pest": "Nilaparvata lugens", "crop": "rice"},
    {"pest": "Scirpophaga incertulas", "crop": "rice"},
    {"pest": "Bemisia tabaci", "crop": "tomato"},
    {"pest": "Tuta absoluta", "crop": "tomato"},
    {"pest": "Plutella xylostella", "crop": "mustard"},
    {"pest": "Leucinodes orbonalis", "crop": "brinjal"},
    {"pest": "Bactrocera dorsalis", "crop": "mango"},
    {"pest": "Meloidogyne incognita", "crop": "vegetables"},
]

def load_existing_database():
    if os.path.exists("knowledge_base.json"):
        with open("knowledge_base.json", "r") as f:
            return json.load(f)
    return {}

def save_database(database):
    with open("knowledge_base.json", "w") as f:
        json.dump(database, f, indent=2)

def search_pubmed(query, max_results=15):
    try:
        handle = Entrez.esearch(
            db="pubmed",
            term=query,
            retmax=max_results
        )
        record = Entrez.read(handle)
        handle.close()
        return record["IdList"]
    except Exception as e:
        print(f"  Search error: {e}")
        return []

def fetch_paper(pubmed_id):
    try:
        time.sleep(2)
        handle = Entrez.efetch(
            db="pubmed",
            id=pubmed_id,
            rettype="medline",
            retmode="text"
        )
        text = handle.read()
        handle.close()
        return text[:1000]
    except Exception as e:
        print(f"  Fetch error for {pubmed_id}: {e}")
        return ""

def build_knowledge_database():
    database = load_existing_database()
    
    print("BIOPESTICIDE KNOWLEDGE BASE BUILDER")
    print("Target: 15 papers per pest")
    print("Progress saves automatically after each pest")
    print("="*55)

    for item in INDIAN_PESTS:
        pest = item["pest"]
        crop = item["crop"]
        key = f"{pest}_{crop}".replace(" ", "_")

        if key in database and database[key]["papers_found"] >= 10:
            print(f"\nSkipping {pest} on {crop} — already has {database[key]['papers_found']} papers")
            continue

        print(f"\nSearching: {pest} on {crop}")
        time.sleep(5)

        query = f"biopesticide {pest} {crop} natural compound biological control management"
        ids = search_pubmed(query, max_results=15)
        
        if not ids:
            query = f"{pest} {crop} natural biological control"
            ids = search_pubmed(query, max_results=15)

        print(f"  Found {len(ids)} paper IDs")

        papers = []
        for i, pid in enumerate(ids):
            print(f"  Fetching paper {i+1}/{len(ids)}: {pid}")
            text = fetch_paper(pid)
            if text:
                papers.append({
                    "pubmed_id": pid,
                    "content": text
                })

        database[key] = {
            "pest": pest,
            "crop": crop,
            "papers_found": len(papers),
            "papers": papers
        }

        save_database(database)
        print(f"  Saved {len(papers)} papers — progress saved")
        time.sleep(5)

    print("\n" + "="*55)
    print("COMPLETE. Knowledge base saved to knowledge_base.json")
    
    total = sum(v["papers_found"] for v in database.values())
    print(f"Total papers in database: {total}")

build_knowledge_database()
