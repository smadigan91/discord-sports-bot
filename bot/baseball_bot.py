from requests import get
from bs4 import BeautifulSoup
from tabulate import tabulate

url = 'https://www.baseball-reference.com/leagues/daily.fcgi?request=1&type={}&dates=yesterday&level=mlb'
pitcher_stats = ["player","","IP","H","R","ER","BB","SO","pitches"]
batter_stats_good = ["player","PA","R","H","2B","3B","HR","RBI","BB","SB"]
batter_stats_bad = ["player","PA","R","H","HR","RBI","BB","SO","GIDP","CS"]
pitcher_display = ["NAME"] + pitcher_stats[1:-1] + ["#P"]
    
def fetch_stats(player_type, stats):
    response = get(url.format(player_type))
    soup = BeautifulSoup(response.text, 'html.parser')
    tables = soup.findChildren('table')
    results = tables[0]
    table = results.findChildren('tr')
    pair_list = []
    for row in table[1:]:
        if not row.get('class', []):
            cells = row.findChildren('td')
            if player_type == "p":
                started = row.find('td',attrs={'data-stat':"GS"}).text == "1"
                if started:
                    vals = []
                    dc = " "
                    for cell in cells:
                        title = cell.get('data-stat')
                        if title == "W" and cell.text:
                            dc = "W"
                        elif title == "L" and cell.text:
                            dc = "L"
                        if title in stats:
                            val = cell.text
                            if title == "IP":
                                vals.append(dc)
                            vals.append(val)
                    pair_list.append(vals)
            elif player_type == "b":
                vals = []
                for cell in cells:
                    title = cell.get('data-stat')
                    if title in stats:
                        vals.append(cell.text)
                pair_list.append(vals)
    return pair_list

def best_pitchers():
    print("Top 5 Pitching:\n"+tabulate(fetch_stats("p",pitcher_stats)[:5],pitcher_display, tablefmt="grid"))

def worst_pitchers():
    print("Bottom 5 Pitching:\n"+tabulate(fetch_stats("p",pitcher_stats)[:-6:-1],pitcher_display, tablefmt="grid"))
    
def best_batters():
    print("Top 5 Batting:\n"+tabulate(fetch_stats("b",batter_stats_good)[:5],["NAME"]+batter_stats_good[1:], tablefmt="grid"))
    
def worst_batters():
    print("Bottom 5 Batting:\n"+tabulate(fetch_stats("b",batter_stats_bad)[:-6:-1],["NAME"]+batter_stats_bad[1:], tablefmt="grid"))
    

#testing
best_pitchers()
print("\n")
worst_pitchers()
print("\n")
best_batters()
print("\n")
worst_batters()