import requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

def search_web(query, max_results=3):
    """
    Search the web using DuckDuckGo (no API key required).
    """
    results = []
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
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()
            
        # Get text and clean it up
        text = soup.get_text(separator=' ')
        lines = (line.strip() for line in text.splitlines())
        return '\n'.join(chunk for chunk in lines if chunk)[:8000]  # Limit to 8000 chars
    except Exception as e:
        return f"Error reading website: {str(e)}"
