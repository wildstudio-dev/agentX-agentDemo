from bs4 import BeautifulSoup
import requests

url = "http://localhost:8080"
response = requests.get(url, timeout=10)

# print(response.content)
# print("divider ======= ====== ")
# print(response.text)

soup = BeautifulSoup(response.text, 'html.parser')
print("here3")
tds = soup.find_all("td", class_="large-text-center")
print(f"here4 {len(tds)} rates found")
count = 0
latest_rate = 0
for td in tds:
    # print(td.text.strip())
    count += 1
    text = td.text.strip()
    print(f"Rate {count}: {text}")
    if "15‑Yr" in td.text.strip():
        print("Found 30-Year rate!")
        print(td.text.strip())
        parts = text.split(" ")
        for part in parts:
            if part.endswith("%"):
                # This is the percentage value
                print(f"Found percentage: {part}")
                latest_rate = part
                break
        break

print(latest_rate)