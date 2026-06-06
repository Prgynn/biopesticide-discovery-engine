from Bio import Entrez
import json
import os
import time

Entrez.email = "prgynhandique@gmail.com"

def search_pubmed(query, max_results=5):
    print(f"Searching: {query}")
    
    handle = Entrez.esearch(
        db="pubmed",
        term=query,
        retmax=max_results,
        usehistory="y"
    )
    record = Entrez.read(handle)
    handle.close()
    
    count = int(record["Count"])
    print(f"Total results found: {count}")
    
    ids = record["IdList"]
    print(f"IDs retrieved: {ids}")
    return ids

def fetch_paper(pubmed_id):
    time.sleep(1)
    handle = Entrez.efetch(
        db="pubmed",
        id=pubmed_id,
        rettype="abstract",
        retmode="text"
    )
    text = handle.read()
    handle.close()
    return text[:600]

ids = search_pubmed("biopesticide insect plant")

if ids:
    print("\nFetching papers...")
    for pid in ids[:3]:
        paper = fetch_paper(pid)
        print(f"\nPubMed ID: {pid}")
        print(paper)
        print("---")
else:
    print("No results found")
    