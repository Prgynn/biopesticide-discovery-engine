import requests
import pdfplumber
import json
import os
import time
from Bio import Entrez

Entrez.email = "prgynhandique@gmail.com"

def get_open_access_pdf_url(pubmed_id):
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id=PMC{pubmed_id}&format=pdf"
        response = requests.get(url, timeout=10)
        
        handle = Entrez.elink(
            dbfrom="pubmed",
            db="pmc",
            id=pubmed_id
        )
        record = Entrez.read(handle)
        handle.close()
        
        if record[0]["LinkSetDb"]:
            pmc_id = record[0]["LinkSetDb"][0]["Link"][0]["Id"]
            pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
            return pdf_url, pmc_id
        return None, None
    except Exception as e:
        return None, None

def download_pdf(url, filename):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            return True
        return False
    except Exception as e:
        return False

def extract_tables_from_pdf(pdf_path):
    tables_data = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        headers = table[0]
                        rows = table[1:]
                        tables_data.append({
                            "page": page_num + 1,
                            "headers": headers,
                            "rows": rows,
                            "row_count": len(rows)
                        })
    except Exception as e:
        print(f"  Table extraction error: {e}")
    return tables_data

def extract_experimental_data(tables):
    experimental = []
    
    compound_keywords = [
        "compound", "treatment", "extract",
        "chemical", "substance", "formulation"
    ]
    result_keywords = [
        "mortality", "lc50", "efficacy",
        "control", "inhibition", "activity"
    ]
    
    for table in tables:
        headers = [str(h).lower() if h else "" 
                  for h in table["headers"]]
        
        has_compound = any(
            any(kw in h for kw in compound_keywords)
            for h in headers
        )
        has_result = any(
            any(kw in h for kw in result_keywords)
            for h in headers
        )
        
        if has_compound or has_result:
            experimental.append({
                "page": table["page"],
                "headers": table["headers"],
                "data_rows": table["rows"][:10],
                "type": "experimental_results"
            })
    
    return experimental

def process_papers_for_tables():
    with open("knowledge_base.json", "r") as f:
        database = json.load(f)
    
    os.makedirs("pdfs", exist_ok=True)
    os.makedirs("tables", exist_ok=True)
    
    all_tables = {}
    papers_processed = 0
    tables_found = 0
    
    print("PDF TABLE EXTRACTION ENGINE")
    print("="*55)
    
    for key, data in database.items():
        pest = data["pest"]
        crop = data["crop"]
        
        print(f"\nProcessing: {pest} on {crop}")
        
        pest_tables = []
        
        for paper in data["papers"][:3]:
            pubmed_id = paper["pubmed_id"]
            
            print(f"  Getting PDF for PubMed ID: {pubmed_id}")
            time.sleep(2)
            
            pdf_url, pmc_id = get_open_access_pdf_url(pubmed_id)
            
            if not pdf_url:
                print(f"  No open access PDF available")
                continue
            
            pdf_path = f"pdfs/{pubmed_id}.pdf"
            
            if not os.path.exists(pdf_path):
                print(f"  Downloading PDF...")
                success = download_pdf(pdf_url, pdf_path)
                if not success:
                    print(f"  Download failed")
                    continue
            
            print(f"  Extracting tables...")
            tables = extract_tables_from_pdf(pdf_path)
            
            if tables:
                experimental = extract_experimental_data(tables)
                print(f"  Found {len(tables)} tables, {len(experimental)} experimental")
                
                pest_tables.append({
                    "pubmed_id": pubmed_id,
                    "total_tables": len(tables),
                    "experimental_tables": experimental
                })
                tables_found += len(experimental)
            else:
                print(f"  No tables found in PDF")
            
            papers_processed += 1
        
        all_tables[key] = {
            "pest": pest,
            "crop": crop,
            "papers_with_tables": pest_tables
        }
    
    with open("tables/extracted_tables.json", "w") as f:
        json.dump(all_tables, f, indent=2)
    
    print("\n" + "="*55)
    print(f"Papers processed: {papers_processed}")
    print(f"Experimental tables found: {tables_found}")
    print("Saved to tables/extracted_tables.json")

process_papers_for_tables()
