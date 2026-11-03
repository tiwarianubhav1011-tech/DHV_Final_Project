import requests
from bs4 import BeautifulSoup
import pandas as pd

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

CATEGORIES = [
    "Overall", "University", "College", "Research", "Engineering",
    "Management", "Pharmacy", "Medical", "Dental", "Law",
    "Architecture", "Agriculture", "Innovation", "OPENUNIVERSITY",
    "SKILLUNIVERSITY", "STATEPUBLICUNIVERSITY", "SDGInstitutions"
]

all_data = []

for year in range(2017, 2026):
    for category in CATEGORIES:
        url = f"https://www.nirfindia.org/Rankings/{year}/{category}Ranking.html"
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            continue

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table", id="tbl_overall")
        if not table:
            continue

        rows = table.select("tbody > tr") or table.find_all("tr", recursive=False)
        count_before = len(all_data)

        for row in rows:
            # Skip any row that is inside the hidden parameter sub-table
            if row.find_parent("table") != table:
                continue

            tds = row.find_all("td", recursive=False)
            if len(tds) < 4:
                continue

            cols = [list(td.stripped_strings)[0] if list(td.stripped_strings) else "" for td in tds]

            # Double check: Every real college row has an Institute_ID starting with 'IR'
            if not cols[0].startswith("IR"):
                continue

            if len(cols) == 6:
                inst_id, name, city, state, score, rank = cols
            elif len(cols) == 5:
                inst_id, name, city, state, rank = cols
                score = None
            else:
                continue

            # Extract the 5 parameters from the nested sub-table inside the Name cell (tds[1])
            sub_table = tds[1].find("table") if len(tds) > 1 else None
            params = [td.get_text(strip=True) for td in sub_table.find_all("td")] if sub_table else []
            tlr, rpc, go, oi, perception = params[:5] if len(params) >= 5 else [None] * 5

            all_data.append({
                "Year": year,
                "Category": category,
                "Institute_ID": inst_id,
                "Name": name,
                "City": city,
                "State": state,
                "Score": score,
                "Rank": rank,
                "TLR": tlr,
                "RPC": rpc,
                "GO": go,
                "OI": oi,
                "Perception": perception
            })

        rows_added = len(all_data) - count_before
        if rows_added > 0:
            print(f"Scraped: {year} - {category:<22} ({rows_added} rows)")

# Save everything to a single CSV
df = pd.DataFrame(all_data)
df.to_csv("nirf_2017_2025_clean.csv", index=False, encoding="utf-8-sig")
print(f"\nDone! Saved {len(df)} total rows.")
