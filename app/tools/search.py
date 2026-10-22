try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None
from app.permissions import check_permission, PermissionLevel

def web_search(query: str, max_results: int = 5) -> dict:
    if not check_permission("web_search", PermissionLevel.READ, {"query": query}):
        return {"success": False, "error": "Permission denied"}
    if DDGS is None:
        return {"success": False, "error": "duckduckgo_search library is not available"}
    """
    Provider-independent search interface.
    Currently uses duckduckgo-search.
    """
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
        return {"success": True, "query": query, "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}
