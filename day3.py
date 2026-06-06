import arxiv
import time 

client = arxiv.Client(
    num_retries=5,
    delay_seconds=5
)

search = arxiv.Search(
    query="biopesticide natural compounds aphids",
    max_results=3,
    sort_by=arxiv.SortCriterion.Relevance
)

print("Searching for papers....please wait")
time.sleep(5)

for paper in client.results(search):
    print(f"Title: {paper.title}")
    print(f"Year: {paper.published.year}")
    print("---")
    