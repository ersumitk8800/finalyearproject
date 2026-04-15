import requests
import pandas as pd

BASE = "https://disease.sh/v3/covid-19"

def get_country_data(country: str):
    try:
        r = requests.get(f"{BASE}/countries/{country}", timeout=8)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def get_all_global():
    try:
        r = requests.get(f"{BASE}/all", timeout=8)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def get_top_countries(n=10):
    try:
        r = requests.get(f"{BASE}/countries?sort=cases", timeout=8)
        data = r.json()
        return pd.DataFrame(data).head(n)
    except Exception:
        return pd.DataFrame()

def get_all_countries_map():
    try:
        r = requests.get(f"{BASE}/countries", timeout=10)
        return pd.DataFrame(r.json())
    except Exception:
        return pd.DataFrame()

def get_india_states():
    try:
        r = requests.get(f"{BASE}/gov/India", timeout=8)
        data = r.json()
        return pd.DataFrame(data.get('states', []))
    except Exception:
        return pd.DataFrame()

def get_vaccination_countries():
    try:
        r = requests.get(f"{BASE}/vaccine/coverage/countries?lastdays=1", timeout=8)
        data = r.json()
        return sorted([item['country'] for item in data])
    except Exception:
        return []

def get_vaccination_timeline(country, days=30):
    try:
        r = requests.get(f"{BASE}/vaccine/coverage/countries/{country}?lastdays={days}", timeout=8)
        data = r.json()
        if 'timeline' in data:
            return pd.DataFrame(list(data['timeline'].items()), columns=['Date', 'Total Doses'])
        return None
    except Exception:
        return None

def get_global_vaccination():
    try:
        r = requests.get(f"{BASE}/vaccine/coverage?lastdays=1", timeout=8)
        data = r.json()
        return list(data.values())[0] if data else None
    except Exception:
        return None

def get_historical_global(days=365):
    try:
        r = requests.get(f"{BASE}/historical/all?lastdays={days}", timeout=10)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

def fetch_news_items(query="covid health india", limit=10):
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    try:
        from bs4 import BeautifulSoup
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.content, "html.parser")
        items = soup.findAll('item', limit=limit)
        results = []
        for item in items:
            raw_desc = item.description.text if item.description else ""
            clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text()
            title = item.title.text if item.title else "Live Update"
            link_tag = item.find('link')
            link = link_tag.next_sibling.strip() if link_tag and link_tag.next_sibling else "#"
            pub_date = item.pubDate.text if item.pubDate else "Recently"
            if len(clean_desc) < 50:
                clean_desc = f"{title}. Healthcare professionals globally are monitoring this situation closely."
            results.append({
                "title": title,
                "link": link,
                "date": pub_date,
                "desc": clean_desc[:280] + "..." if len(clean_desc) > 280 else clean_desc,
            })
        return results
    except Exception as e:
        return []
