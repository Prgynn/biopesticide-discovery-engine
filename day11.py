import requests
import json
import time
import os

def search_europe_pmc_fulltext(pest, crop, max_results=10):
    print(f"  Searching Europe PMC full text: {pest} on {crop}")
    
    query = f"biopesticide {pest} {crop} natural compound"
    
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": query,
        "resultType": "core",
        "pageSize": max_results,
        "format": "json",
        "hasFullText": "Y"
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        data = response.json()
        results = data.get("resultList", {}).get("result", [])
        return results
    except Exception as e:
        print(f"  Search error: {e}")
        return []

def get_full_text_tables(pmcid):
    try:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/tables"
        params = {"format": "json"}
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        return None

def get_full_text_xml(pmcid):
    try:
        url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            return response.text[:70000]
        return None
    except Exception as e:
        return None

def extract_table_data(xml_text):
    tables = []
    if not xml_text:
        return tables
    
    import re
    
    # Find any table-like structures
    patterns = [
        r'<table[^>]*>(.*?)</table>',
        r'<Table[^>]*>(.*?)</Table>',
        r'<tbody[^>]*>(.*?)</tbody>',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, xml_text, re.DOTALL)
        for match in matches:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', 
                             match, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() 
                    for c in cells if c.strip()]
            
            if len(cells) > 3:
                tables.append({
                    "caption": "Table found",
                    "cells": cells[:50],
                    "cell_count": len(cells)
                })
    
    # Also extract any numerical data with units
    numbers = re.findall(
        r'(\d+\.?\d*)\s*(ppm|%|mg|µg|ug|LC50|LD50)', 
        xml_text
    )
    
    if numbers:
        tables.append({
            "caption": "Numerical data extracted",
            "cells": [f"{n[0]} {n[1]}" for n in numbers[:20]],
            "cell_count": len(numbers)
        })
    
    return tables
    
    import re
    
    table_pattern = r'<table-wrap[^>]*>(.*?)</table-wrap>'
    table_matches = re.findall(table_pattern, xml_text, re.DOTALL)
    
    for table_xml in table_matches:
        caption_match = re.search(r'<caption>(.*?)</caption>', table_xml, re.DOTALL)
        caption = caption_match.group(1) if caption_match else "No caption"
        caption = re.sub(r'<[^>]+>', '', caption).strip()
        
        cell_pattern = r'<t[dh][^>]*>(.*?)</t[dh]>'
        cells = re.findall(cell_pattern, table_xml, re.DOTALL)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        
        if cells:
            tables.append({
                "caption": caption[:200],
                "cells": cells[:50],
                "cell_count": len(cells)
            })
    
    return tables

def build_fulltext_database():
    os.makedirs("fulltext_data", exist_ok=True)
    
    PESTS = [
        {"pest": "Helicoverpa armigera", "crop": "cotton"},
        {"pest": "Spodoptera frugiperda", "crop": "maize"},
        {"pest": "Plutella xylostella", "crop": "mustard"},
        {"pest": "Bemisia tabaci", "crop": "tomato"},
        {"pest": "Nilaparvata lugens", "crop": "rice"},
    ]
    
    all_results = {}
    total_tables = 0
    
    print("EUROPE PMC FULL TEXT EXTRACTION ENGINE")
    print("="*55)
    
    for item in PESTS:
        pest = item["pest"]
        crop = item["crop"]
        key = f"{pest}_{crop}".replace(" ", "_")
        
        print(f"\nProcessing: {pest} on {crop}")
        
        papers = search_europe_pmc_fulltext(pest, crop, max_results=5)
        print(f"  Found {len(papers)} open access papers")
        
        pest_data = []
        
        for paper in papers[:3]:
            pmcid = paper.get("pmcid", "")
            title = paper.get("title", "")
            abstract = paper.get("abstractText", "")[:500]
            
            if not pmcid:
                continue
            
            print(f"  Getting full text for {pmcid}")
            time.sleep(2)
            
            xml_text = get_full_text_xml(pmcid)
            if xml_text:
                print(f" XML preview:{xml_text[:200]}")
            tables = extract_table_data(xml_text) if xml_text else []
            
            experimental_tables = tables
            print(f"  Tables found: {len(tables)} total, {len(experimental_tables)} experimental")
            total_tables += len(experimental_tables)
            
            pest_data.append({
                "pmcid": pmcid,
                "title": title,
                "abstract": abstract,
                "total_tables": len(tables),
                "experimental_tables": experimental_tables
            })
        
        all_results[key] = {
            "pest": pest,
            "crop": crop,
            "papers_processed": len(pest_data),
            "papers": pest_data
        }
        
        with open("fulltext_data/fulltext_results.json", "w") as f:
            json.dump(all_results, f, indent=2)
        
        print(f"  Progress saved")
        time.sleep(3)
    
    print("\n" + "="*55)
    print(f"Total experimental tables extracted: {total_tables}")
    print("Saved to fulltext_data/fulltext_results.json")

build_fulltext_database()
