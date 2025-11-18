import requests
from bs4 import BeautifulSoup


def crawl_website(url: str) -> str:
    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        # Remove scripts & styles
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        return text

    except Exception as e:
        return f"ERROR: {str(e)}"

