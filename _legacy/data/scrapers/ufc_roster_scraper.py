import requests
from bs4 import BeautifulSoup
import psycopg2
import time
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '../../.env'))
DB_URL = os.environ.get('DATABASE_URL', 'postgresql://ufc_user:ufc_password@localhost:5432/ufc_predictor')

def scrape_active_fighters():
    print("Connecting to algorithmic database engine...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("UPDATE fighters SET is_active = FALSE;")
    conn.commit()
    print("Cleared legacy active constraints.")
    
    page = 0
    active_count = 0
    
    while True:
        url = f"https://www.ufc.com/athletes/all?filters%5B0%5D=status%3A23&page={page}"
        print(f"Paginating active roster scrape logic on depth {page}...")
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            print("Failed to map endpoint bounds. Breaking execution loop.")
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        names = soup.select('.c-listing-athlete__name')
        
        if not names:
            print(f"Scrape evaluated total boundary capacity at {page} depths.")
            break
            
        for name_span in names:
            raw_name = name_span.get_text(strip=True)
            cleaned_name = " ".join(raw_name.split())  # normalize whitespace, preserve spaces

            cur.execute("""
                UPDATE fighters
                SET is_active = TRUE
                WHERE name ILIKE %s
            """, (cleaned_name,))
            
            if cur.rowcount > 0:
                active_count += 1
                 
        conn.commit()
        page += 1
        time.sleep(1)
        
    print(f"Algorithms parsed and synchronized {active_count} active fighters into the PostgreSQL stack.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    scrape_active_fighters()
