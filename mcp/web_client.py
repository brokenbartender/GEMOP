import requests
try:
    # New package name (preferred).
    from ddgs import DDGS  # type: ignore
except Exception:  # pragma: no cover
    from duckduckgo_search import DDGS  # type: ignore
import json
import sys
import argparse

def search(query, max_results=5):
    print(f"?? Searching: {query}...")
    try:
        with DDGS() as ddgs:
            results = [r for r in ddgs.text(query, max_results=max_results)]
            return {"ok": True, "results": results}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch(url):
    print(f"?? Fetching: {url}...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return {
            "ok": True, 
            "status_code": response.status_code,
            "content": response.text[:10000] # Cap at 10k chars for agent context
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    s = subparsers.add_parser("search")
    s.add_argument("query")
    s.add_argument("--max", type=int, default=5)
    
    f = subparsers.add_parser("fetch")
    f.add_argument("url")
    
    args = parser.parse_args()
    
    if args.command == "search":
        print(json.dumps(search(args.query, args.max), indent=2))
    elif args.command == "fetch":
        print(json.dumps(fetch(args.url), indent=2))
