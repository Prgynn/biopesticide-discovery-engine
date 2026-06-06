import json

def load_knowledge_base():
    with open("knowledge_base.json", "r") as f:
        return json.load(f)

def query_pest(pest, crop, database):
    key = f"{pest}_{crop}"
    
    if key in database:
        data = database[key]
        print(f"\nResults for {pest} on {crop}:")
        print(f"Papers found: {data['papers_found']}")
        print("\nPaper contents:")
        for paper in data['papers']:
            print(f"\nPubMed ID: {paper['pubmed_id']}")
            print(f"Content: {paper['content'][:400]}")
            print("---")
    else:
        print(f"\nNo data found for {pest} on {crop}")
        print("Available searches:")
        for key in database.keys():
            print(f"  - {key}")

def show_summary(database):
    print("\n=== KNOWLEDGE BASE SUMMARY ===")
    print(f"Total pest-crop combinations: {len(database)}")
    total_papers = 0
    for key, data in database.items():
        total_papers += data['papers_found']
        print(f"  {key}: {data['papers_found']} papers")
    print(f"Total papers stored: {total_papers}")
    print("==============================")

database = load_knowledge_base()

show_summary(database)

print("\nQuerying your knowledge base...")
query_pest("whitefly", "cotton", database)
query_pest("stem borer", "rice", database)
query_pest("thrips", "chili", database)
