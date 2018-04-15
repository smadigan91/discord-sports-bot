from difflib import SequenceMatcher

from bs4 import BeautifulSoup
from requests import get
from tabulate import tabulate

stats_url = 'https://www.baseball-reference.com/leagues/daily.fcgi?request=1&type={type}&dates={dates}&level=mlb'
blurb_search_url = 'http://www.rotoworld.com/content/playersearch.aspx?searchname={first}{last}&sport=mlb'
pitcher_stats = ["player", "", "IP", "H", "R", "ER", "BB", "SO", "pitches"]
batter_stats_good = ["player", "PA", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SB"]
batter_stats_bad = ["player", "PA", "H", "BB", "SO", "GIDP", "CS"]
pitcher_display = ["NAME"] + pitcher_stats[1:-1] + ["#P"]

# try to fetch player by first and last name
# if can't find with first name, search by last name, then re-search results for matching first name? (T.J. McFarland)


def fetch_blurb(first, last, player_url=None, depth=1, original_first=None):
#     print(blurb_search_url.format(first=first, last=last))
    response = get(player_url if player_url else blurb_search_url.format(first=first, last=("+" + last if last else "")))
#     print(response.text)
    soup = BeautifulSoup(response.text, 'html.parser')
    # did we land a result page?
    if not soup.findChild('div', class_='RW_pn'):
    # try again with blank first name, just last name if no search results
        name_map = {}
        results_table = soup.find('table', attrs={'id':'cp1_tblSearchResults'})
        # filter results, omitting duplicate "position" links that don't include the player's name
        filtered_results = results_table.findChildren(lambda tag:tag.name == 'a' and "player" in tag["href"] and len(tag.text) > 3)
        if not filtered_results:
            if depth == 1:
                return fetch_blurb("", last, None, depth + 1, first)
            else: raise NoResultsError("No results for %s %s" % (original_first, last))
        else:
            for result in filtered_results:
                name = " ".join(result.text.split())
                name_map[result] = SequenceMatcher(None, (original_first if original_first else first) + " " + last, name).ratio()
#         sorted_names = {(k, name_map[k])for k in sorted(name_map, key=name_map.get)}
        sorted_names = sorted(name_map, key=name_map.get, reverse=True)
        return fetch_blurb(first, last, "http://www.rotoworld.com" + sorted_names[0].get('href'))  # this should work?
#             print(result.find('a').get('href'))
    else:
        news = soup.findChildren('div', class_='playernews')
        if news:
            name_div = soup.findChild('div', class_='playername')
            name = name_div.findChild('h1').text.split('|')[0].strip()
            recent_news = news[0]
            report = recent_news.find('div', class_='report')
            impact = recent_news.find('div', class_='impact')
            print(name + ":\n")
            print(report.text + '\n')
            print(impact.text)
        else: raise NoResultsError("No recent player news for %s %s" % (first, last))
    
    # if only one result, I think it just redirects? test this one first with "pollock"
    

# TODO return date, opponent
def fetch_stats(player_type, stats, dates='yesterday'):
    response = get(stats_url.format(type=player_type, dates=dates))
    soup = BeautifulSoup(response.text, 'html.parser')
    tables = soup.findChildren('table')
    if not tables:
        raise NoResultsError("no results")
    results = tables[0]
    table = results.findChildren('tr')
    pair_list = []
    for row in table[1:]:
        if not row.get('class', []):
            cells = row.findChildren('td')
            if player_type == 'p':
                started = row.find('td', attrs={'data-stat':"GS"}).text == '1'
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
            elif player_type == 'b':
                vals = []
                for cell in cells:
                    title = cell.get('data-stat')
                    if title in stats:
                        vals.append(cell.text)
                pair_list.append(vals)
    return pair_list


# playing with tabular output - it's not well-suited for discord sadly
def best_pitchers():
    print("Top 5 Pitching:\n" + tabulate(fetch_stats("p", pitcher_stats)[:5], pitcher_display, tablefmt="grid"))


def worst_pitchers():
    print("Bottom 5 Pitching:\n" + tabulate(fetch_stats("p", pitcher_stats)[:-6:-1], pitcher_display, tablefmt="grid"))

    
def best_batters():
    print("Top 5 Batting:\n" + tabulate(fetch_stats("b", batter_stats_good)[:5], ["NAME"] + batter_stats_good[1:], tablefmt="grid"))

    
def worst_batters():
    print("Bottom 5 Batting:\n" + tabulate(fetch_stats("b", batter_stats_bad)[:-6:-1], ["NAME"] + batter_stats_bad[1:], tablefmt="grid"))


class NoResultsError(Exception):
    # TODO just log a message in whatever channel
    message = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message
    

# testing\
fetch_blurb("Micah", "Johnson")
# best_pitchers()
# print("\n")
# worst_pitchers()
# print("\n")
# best_batters()
# print("\n")
# worst_batters()
