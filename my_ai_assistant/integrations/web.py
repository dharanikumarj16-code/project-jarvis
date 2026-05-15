import requests
import re
import html
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except Exception:
    BeautifulSoup = None
    HAS_BS4 = False

try:
    from duckduckgo_search import DDGS
    HAS_DDGS = True
except Exception:
    DDGS = None
    HAS_DDGS = False

def search_web(query, max_results=3):
    """
    Search the web using DuckDuckGo (no API key required).
    """
    results = []
    if not HAS_DDGS:
        print("⚠️ duckduckgo_search not installed. `search_web` disabled. Install via: pip install duckduckgo-search")
        return results

    try:
        print(f"🔍 Searching web for: {query}")
        with DDGS() as ddgs:
            # ddgs.text returns an iterator
            for r in ddgs.text(query, max_results=max_results):
                results.append(r)
    except Exception as e:
        print(f"❌ Search error: {e}")
    return results

def extract_text_from_url(url):
    """
    Fetch and extract readable text from a URL.
    """
    try:
        print(f"📖 Reading content from: {url}")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        content = response.content

        if HAS_BS4:
            soup = BeautifulSoup(content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer"]):
                script.decompose()

            # Get text and clean it up
            text = soup.get_text(separator=' ')
            lines = (line.strip() for line in text.splitlines())
            return '\n'.join(chunk for chunk in lines if chunk)[:8000]  # Limit to 8000 chars
        else:
            # Fallback: strip HTML tags with regex and unescape entities
            try:
                raw = content.decode('utf-8', errors='ignore')
            except Exception:
                raw = str(content)
            # Remove script/style blocks
            raw = re.sub(r'<(script|style).*?>.*?</\1>', ' ', raw, flags=re.S|re.I)
            # Remove all tags
            text = re.sub(r'<[^>]+>', ' ', raw)
            # Collapse whitespace and unescape HTML entities
            text = html.unescape(re.sub(r'\s+', ' ', text)).strip()
            return text[:8000]
    except Exception as e:
        return f"Error reading website: {str(e)}"
