import sys
from duckduckgo_search import DDGS
import argparse

def main():
    parser = argparse.ArgumentParser(description="Agentic Web Search")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--max", type=int, default=5, help="Max results")
    args = parser.parse_args()

    print(f"?? GEMINI SEARCH: Looking up '{args.query}'...")
    
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(args.query, max_results=args.max))
            if not results:
                print("No results found.")
                return

            for i, r in enumerate(results, 1):
                print(f"\n[{i}] {r['title']}")
                print(f"URL: {r['href']}")
                print(f"Snippet: {r['body']}")
    except Exception as e:
        print(f"? SEARCH ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
