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
]

def search_pubmed(query, max_results=3):
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=max_results
    )
    record = Entrez.read(handle)
    handle.close()
    return record["IdList"]

def fetch_paper(pubmed_id):
    time.sleep(2)
    handle = Entrez.efetch(
        db="pubmed",
        id=pubmed_id,
        rettype="medline",
        retmode="text"
    )
    text = handle.read()
    handle.close()
    return text[:600]

def build_knowledge_database():
    database = {}

    for item in INDIAN_PESTS:
        pest = item["pest"]
        crop = item["crop"]

        print(f"\nSearching: {pest} on {crop}")
        time.sleep(3)

        query = f"biopesticide {pest} {crop} natural"
        ids = search_pubmed(query, max_results=2)

        papers = []
        for pid in ids:
            print(f"  Fetching paper {pid}...")
            text = fetch_paper(pid)
            papers.append({
                "pubmed_id": pid,
                "content": text
            })

        database[f"{pest}_{crop}"] = {
            "pest": pest,
            "crop": crop,
            "papers_found": len(papers),
            "papers": papers
        }

        print(f"  Saved {len(papers)} papers for {pest} on {crop}")

    with open("knowledge_base.json", "w") as f:
        json.dump(database, f, indent=2)

    print("\nKnowledge database saved to knowledge_base.json")
    return database

build_knowledge_database()
