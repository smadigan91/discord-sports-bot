import asyncio
import datetime
from difflib import SequenceMatcher
import json
import urllib

from bs4 import BeautifulSoup
import discord
from requests import get
from tabulate import tabulate

bbref_url = 'https://www.baseball-reference.com'
stats_url = bbref_url + '/leagues/daily.fcgi?request=1&type={type}&dates={dates}&level=mlb'
search_url = bbref_url + '/search/search.fcgi?search={search}'
blurb_search_url = 'http://www.rotoworld.com/content/playersearch.aspx?searchname={first}+{last}&sport=mlb'
batter_log_stats = ["date_game", "opp_ID", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO"]  # derive AVG
pitcher_log_stats = ["date_game", "opp_ID", "player_game_result", "IP", "H", "R", "ER", "BB", "SO", "pitches"]  # derive ERA
pitcher_stats = ["player", "", "IP", "H", "R", "ER", "BB", "SO", "pitches"]
batter_stats_good = ["player", "PA", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SB"]
batter_stats_bad = ["player", "PA", "H", "BB", "SO", "GIDP", "CS"]
pitcher_display = ["NAME"] + pitcher_stats[1:-1] + ["#P"]

# try to fetch player by first and last name
# if can't find with first name, search by last name, then re-search results for matching first name? (T.J. McFarland)


class SportsClient(discord.Client):
    
    @asyncio.coroutine
    def on_message(self, message):
        if(message.content.startswith('/blurb')):
            if(message.channel.name == "sportsbot-testing"):
                try:
                    name = message.content.split()[1:]
                    first = name[0]
                    last = " ".join(name[1:])  # hopefully handles the Jrs
                    if not first or not last:
                        raise ValueError('A first and last name must be provided')
                    blurb = fetch_blurb(first, last)
                    embedded_blurb = discord.Embed(title=" ".join([first, last]).title(), description=blurb)
                    yield from self.send_message(message.channel, embed=embedded_blurb)
                except NoResultsError as ex:
                    yield from self.send_message(message.channel, content=ex.message)


def fetch_blurb(first, last, player_url=None):
    # for some weird reason its actually better to omit the first name in the search form
    response = get(player_url if player_url else blurb_search_url.format(first="", last=last))
    soup = BeautifulSoup(response.text, 'html.parser')
    # did we land a result page?
    if not soup.findChild('div', class_='RW_pn'):
        name_map = {}
        results_table = soup.find('table', attrs={'id':'cp1_tblSearchResults'})
        # filter results, omitting duplicate "position" links that don't include the player's name
        filtered_results = results_table.findChildren(lambda tag:tag.name == 'a' and 'player' in tag['href'] and len(tag.text) > 3)
        if not filtered_results:
            raise NoResultsError("No results for %s %s" % (first, last))
        else:
            for result in filtered_results:
                name = " ".join(result.text.split())
                name_map[result] = SequenceMatcher(None, first + " " + last, name).ratio()
        # sort names by similarity to search criteria
        sorted_names = sorted(name_map, key=name_map.get, reverse=True)
        return fetch_blurb(first, last, 'http://www.rotoworld.com' + sorted_names[0].get('href'))  # this should work?
#             print(result.find('a').get('href'))
    else:
        news = soup.findChildren('div', class_='playernews')
        if news:
            name_div = soup.findChild('div', class_='playername')
            name = name_div.findChild('h1').text.split('|')[0].strip()
            recent_news = news[0]
            report = recent_news.find('div', class_='report')
            impact = recent_news.find('div', class_='impact')
            blurb = report.text + '\n\n' + impact.text
            return blurb
        else: raise NoResultsError("No recent player news for %s %s" % (first, last))
    
    # if only one result, I think it just redirects? test this one first with "pollock"


# just better to do a search and find the best matching result
# maybe add specific date functionality eventually?
def fetch_player_stats(search, stat_type=None, player_url=None):
    response = get(player_url if player_url else search_url.format(search=urllib.parse.quote(search)))
    soup = BeautifulSoup(response.text, 'html.parser')
    log_holder = soup.find('span', text="Game Logs")
    if log_holder:
        name = soup.find('h1', attrs={'itemprop':'name'}).text
        batting = None if (stat_type and stat_type != "b") else log_holder.find_next('div').find('p', class_='listhead', text='Batting')
        pitching = None if (stat_type and stat_type != "p") else log_holder.find_next('div').find('p', class_='listhead', text='Pitching')
        if batting or pitching:
            batting_list = [] if not batting else batting.find_next('ul').findChildren(lambda tag:tag.name == 'a' and tag.text != 'Postseason')
            pitching_list = [] if not pitching else pitching.find_next('ul').findChildren(lambda tag:tag.name == 'a' and tag.text != 'Postseason')
            if len(batting_list) > len(pitching_list):
                href = batting_list.pop().get('href')
                return print_most_recent_game(name, bbref_url + href, 'b',)
                # grab batting logs
            elif len(pitching_list) > len(batting_list):
                href = pitching_list.pop().get('href')
                return print_most_recent_game(name, bbref_url + href, 'p')
                # grab pitching logs
            elif len(batting_list) == len(pitching_list):
                # ask to disambiguate
                raise ValueError("Equal number of years of recorded batting and pitching logs. Try disambiguating with `/logb` for batting and `/logp` for pitching")
            else:
                raise ValueError("Not sure what happened, landed in a player page without accessible game logs [%s]" % search)
        else:
            if stat_type == "b":
                raise NoResultsError("No batting stats for %s" % search)
            elif stat_type == "p":
                raise NoResultsError("No pitching stats for %s" % search)
        
    elif soup.findChild('div', class_='search-results'):
        href = soup.find('div', attrs={"id":"players"}).find_next('div', class_='search-item-url').text
        return fetch_player_stats(search, stat_type, bbref_url + href)
    else:
        raise NoResultsError("No results for %s" % search)

    
def print_most_recent_game(name, gamelog_url, player_type):
    response = get(gamelog_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    tag_id = 'batting_gamelogs' if player_type == 'b' else 'pitching_gamelogs'
    table = soup.find('table', attrs={'id':tag_id}).find('tbody').find_all('tr')
    most_recent = table.pop()
    cat_dict = {}
    # index the stats
    if player_type == 'b':
        for category in most_recent.find_all('td'):
            stat = category.get('data-stat')
            if stat in batter_log_stats:
                if stat == "date_game":
                    val = category.get('csk').split(".")[0]
                    cat_dict["DATE"] = val
                elif stat == "opp_ID":
                    val = category.findChild('a').text
                    cat_dict["VS"] = val
                else: cat_dict[stat] = category.text
        HAB = cat_dict['H'] + "/" + cat_dict['AB']
        AVG = ("%.3f" % round(int(cat_dict['H']) / int(cat_dict['AB']), 3)).lstrip('0')
        cat_dict['AVG'] = AVG + (" (%s)" % HAB)
    else:
        for category in most_recent.find_all('td'):
            stat = category.get('data-stat')
            if stat in pitcher_log_stats:
                if stat == "date_game":
                    val = category.get('csk').split(".")[0]
                    cat_dict["DATE"] = val
                elif stat == "opp_ID":
                    val = category.findChild('a').text
                    cat_dict["VS"] = val
                elif stat == "player_game_result":
                    val = "N/A" if not category.text else category.text
                    cat_dict["DEC"] = val
                else: cat_dict[stat] = category.text
        ERA = str(round((9 * (int(cat_dict['ER']) / float(cat_dict['IP']))), 2))
        WHIP = str(round(((int(cat_dict['BB']) + int(cat_dict['H']))) / float(cat_dict['IP']), 2))
        cat_dict["ERA"] = ERA
        cat_dict["WHIP"] = WHIP
    print(name)
    print(cat_dict)


# TODO return date, opponent, make top x configurable
def fetch_daily_stats(player_type, stats, dates='yesterday'):
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
    print("Top 5 Pitching:\n" + tabulate(fetch_daily_stats("p", pitcher_stats)[:5], pitcher_display, tablefmt="grid"))


def worst_pitchers():
    print("Bottom 5 Pitching:\n" + tabulate(fetch_daily_stats("p", pitcher_stats)[:-6:-1], pitcher_display, tablefmt="grid"))

    
def best_batters():
    print("Top 5 Batting:\n" + tabulate(fetch_daily_stats("b", batter_stats_good)[:5], ["NAME"] + batter_stats_good[1:], tablefmt="grid"))

    
def worst_batters():
    print("Bottom 5 Batting:\n" + tabulate(fetch_daily_stats("b", batter_stats_bad)[:-6:-1], ["NAME"] + batter_stats_bad[1:], tablefmt="grid"))


class NoResultsError(Exception):
    # TODO just log a message in whatever channel
    message = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message


fetch_player_stats("Grandal", stat_type="b")
# testing\
# TOKEN = json.loads(open('../token.json','r').read())["APP_TOKEN"]
# client = SportsClient()
# client.run(TOKEN)
# fetch_blurb("JD", "Martinez")
# best_pitchers()
# print("\n")
# worst_pitchers()
# print("\n")
# best_batters()
# print("\n")
# worst_batters()
