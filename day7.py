import requests
import time
from Bio import Entrez

Entrez.email = "prgynhandique@gmail.com"

def search_pubmed(query, max_results=3):
    print(f"  Searching PubMed...")
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

def search_semantic_scholar(query, max_results=3):
    print(f"  Searching Semantic Scholar...")
    try:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": max_results,
            "fields": "title,abstract,year,authors"
        }
        response = requests.get(url, params=params)
        data = response.json()
        
        papers = []
        for paper in data.get("data", []):
            papers.append({
                "source": "Semantic Scholar",
                "id": paper.get("paperId", ""),
                "title": paper.get("title", ""),
                "content": paper.get("abstract", "")[:800],
                "year": paper.get("year", "")
            })
        return papers
    except Exception as e:
        print(f"  Semantic Scholar error: {e}")
        return []

def search_europe_pmc(query, max_results=3):
    print(f"  Searching Europe PMC...")
    try:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        params = {
            "query": query,
            "resultType": "core",
            "pageSize": max_results,
            "format": "json"
        }
        response = requests.get(url, params=params)
        data = response.json()
        
        papers = []
        for paper in data.get("resultList", {}).get("result", []):
            papers.append({
                "source": "Europe PMC",
                "id": paper.get("id", ""),
                "title": paper.get("title", ""),
                "content": paper.get("abstractText", "")[:800],
                "year": paper.get("pubYear", "")
            })
        return papers
    except Exception as e:
        print(f"  Europe PMC error: {e}")
        return []

def federated_search(pest, crop, max_per_source=2):
    query = f"biopesticide {pest} {crop} natural compound"
    
    print(f"\nFederated search: {pest} on {crop}")
    print(f"Query: {query}")
    
    all_papers = []
    
    pubmed_papers = search_pubmed(query, max_per_source)
    all_papers.extend(pubmed_papers)
    print(f"  PubMed: {len(pubmed_papers)} papers")
    
    time.sleep(2)
    
    semantic_papers = search_semantic_scholar(query, max_per_source)
    all_papers.extend(semantic_papers)
    print(f"  Semantic Scholar: {len(semantic_papers)} papers")
    
    time.sleep(2)
    
    europe_papers = search_europe_pmc(query, max_per_source)
    all_papers.extend(europe_papers)
    print(f"  Europe PMC: {len(europe_papers)} papers")
    
    print(f"\nTotal papers found: {len(all_papers)}")
    return all_papers

papers = federated_search("aphids", "mustard")

for p in papers:
    print(f"\nSource: {p['source']}")
    print(f"Content: {p['content'][:300]}")
    print("---")
