import asyncio
from datetime import datetime as dt
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
PITCHER = 'p'
BATTER = 'b'

''' TODO 5/17:
    Season stats
    top x, bottom x for today, given day
'''


class SportsClient(discord.Client):
    
    @asyncio.coroutine
    def on_message(self, message):
        if(message.channel.name == "sportsbot-testing"):
            if(message.content.startswith('/blurb')):
                msg = message.content.split()[1:]
                try:
                    first = msg[0]
                    last = " ".join(msg[1:])  # hopefully handles the Jrs
                    if not first or not last:
                        raise ValueError('A first and last name must be provided')
                    blurb = fetch_blurb(first, last)
                    embedded_blurb = discord.Embed(title=" ".join([first, last]).title(), description=blurb)
                    yield from self.send_message(message.channel, embed=embedded_blurb)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            if(message.content.startswith('/last')):
                msg = message.content.split()[1:]
                try:
                    days = int(msg[0])
                    if not days:
                        raise ValueError('A number of last days must be provided')
                    if(len(msg) < 2):
                        raise ValueError('Must provide both a number of days and a name')
                    embedded_stats = fetch_player_stats(" ".join(msg[1:]), last_days=days)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            if(message.content.startswith('/log')):
                try:
                    search = " ".join(message.content.split()[1:])
                    embedded_stats = fetch_player_stats(search)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))


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
def fetch_player_stats(search, stat_type=None, player_url=None, date=None, last_days=None, date_range=None):
    response = get(player_url if player_url else search_url.format(search=urllib.parse.quote(search)))
    soup = BeautifulSoup(response.text, 'html.parser')
    log_holder = soup.find('span', text="Game Logs")
    if log_holder:
        name_node = soup.find('h1', attrs={'itemprop':'name'})
        name = name_node.text
        is_pitcher = "Pitcher" in name_node.find_next(PITCHER).text  # next element after name contains positions
        batting = None if ((stat_type and stat_type != BATTER) or is_pitcher) else log_holder.find_next('div').find(PITCHER, class_='listhead', text='Batting')
        pitching = None if ((stat_type and stat_type != PITCHER) or not is_pitcher) else log_holder.find_next('div').find(PITCHER, class_='listhead', text='Pitching')
        if batting or pitching:
            batting_list = None if not batting else batting.find_next('ul').findChildren(lambda tag:tag.name == 'a' and tag.text != 'Postseason')
            pitching_list = None if not pitching else pitching.find_next('ul').findChildren(lambda tag:tag.name == 'a' and tag.text != 'Postseason')
            if batting:
                href = batting_list.pop().get('href')
                return parse_player_stats(name, bbref_url + href, BATTER, date, last_days, date_range)
                # grab batting logs
            elif pitching:
                href = pitching_list.pop().get('href')
                return parse_player_stats(name, bbref_url + href, PITCHER, date, last_days, date_range)
            else:
                raise ValueError("Not sure what happened, landed in a player page without accessible game logs [%s]" % search)
        else:
            if stat_type == BATTER:
                raise NoResultsError("No batting stats for %s" % name)
            elif stat_type == PITCHER:
                raise NoResultsError("No pitching stats for %s" % name)
        
    elif soup.findChild('div', class_='search-results'):
        href = soup.find('div', attrs={"id":"players"}).find_next('div', class_='search-item-url').text
        return fetch_player_stats(search, stat_type, bbref_url + href, date, last_days, date_range)
    else:
        raise NoResultsError("No results for %s" % search)

    
def parse_player_stats(name, gamelog_url, player_type, date=None, last_days=None, date_range=None):
    response = get(gamelog_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    tag_id = 'batting_gamelogs' if player_type == BATTER else 'pitching_gamelogs'
    table = []
    if last_days or date:
        end_date = datetime.date.today()
        start_date = end_date - datetime.timedelta(days=last_days)
        date_range = (start_date, end_date)
        # filters the list of game rows down to those matching the date range
        table = soup.find('table', attrs={'id':tag_id}).find('tbody').findChildren(
            lambda tag:tag.name == 'tr' and not tag.get('class') == 'thead' and tag.findChild(
                lambda tag:tag.name == "td" and tag['data-stat'] == 'date_game'
                and ((start_date <= dt.strptime(tag.get('csk').split(".")[0], "%Y-%m-%d").date() <= end_date) if not date 
                     else (dt.strptime(tag.get('csk').split(".")[0], "%Y-%m-%d").date() == dt.strptime(date, "%Y-%m-%d").date()))))
    else:
        table = [soup.find('table', attrs={'id':tag_id}).find('tbody').find_all('tr').pop()]
    if not table:
        if date:
            raise NoResultsError("No results for %s on %s" % (name, date))
        else:
            raise NoResultsError("No results for %s from %s to %s" % (name, start_date, end_date))
        # check if today >= date >= today - end_date
    # if last_days, do a lambda to include the last days worth of table rows:
    # for each row that has a child with date_game data stat and the csk split value within the range
#     most_recent = table.pop()
    cat_dict = {}
    # index the stats
    for row in table:
        rollup_game_row(row, player_type, cat_dict)
    return format_player_stats(name, player_type, cat_dict, date_range)

    
def format_player_stats(name, player_type, stat_map, date_range):
    title = ""
    body = ""
    if not date_range:
        title = "**%s** on **%s** vs **%s**" % (name, stat_map['DATE'], stat_map['VS'])
    else:
        title = "**%s** from **%s** through **%s**" % (name, date_range[0], date_range[1])
        
    if date_range: body += display('GP', stat_map)
    if player_type == PITCHER:
        if not date_range: body += display('DEC', stat_map)
        body += display('IP', stat_map)
        body += display('H', stat_map)
        body += display('R', stat_map)
        body += display('ER', stat_map)
        body += display('BB', stat_map)
        body += display('SO', stat_map)
        body += display('ERA', stat_map)
        body += display('WHIP', stat_map)
        body += display('pitches', stat_map, "#PITCH")
    else:
        body += display('AVG', stat_map)
        body += display('R', stat_map)
        body += display('2B', stat_map)
        body += display('3B', stat_map)
        body += display('HR', stat_map)
        body += display('RBI', stat_map)
        body += display('BB', stat_map)
        body += display('SO', stat_map)
    return discord.Embed(title=title, description=body)
    # if just one day, title should be:
    # "Stats for <Name> on <Date> vs <OPP>
    # if multi days, title should be:
    # "Stats for <Name> from <start> thru <end>


def display(key, stats, override=None):
    return "**" + (key if not override else override) + ':** ' + str(stats[key]) + "\n"

    
def rollup_game_row(row, player_type, stat_map):
    stat_map['GP'] = stat_map.get('GP', 0) + 1
    if player_type == BATTER:
        for category in row.find_all('td'):
            stat = category.get('data-stat')
            if stat in batter_log_stats:
                if stat == "date_game":
                    val = category.get('csk').split(".")[0]
                    stat_map['DATE'] = val
                elif stat == "opp_ID":
                    val = category.findChild('a').text
                    stat_map['VS'] = val
                else: stat_map[stat] = stat_map.get(stat, 0) + int(category.text)
        HAB = str(stat_map['H']) + "/" + str(stat_map['AB'])
        AVG = ".000" if stat_map['AB'] == '0' else ("%.3f" % round(int(stat_map['H']) / int(stat_map['AB']), 3)).lstrip('0')
        stat_map['AVG'] = AVG + (" (%s)" % HAB)
    else:
        for category in row.find_all('td'):
            stat = category.get('data-stat')
            if stat in pitcher_log_stats:
                if stat == "date_game":
                    val = category.get('csk').split(".")[0]
                    stat_map["DATE"] = val
                elif stat == "opp_ID":
                    val = category.findChild('a').text
                    stat_map["VS"] = val
                elif stat == "player_game_result":
                    val = "N/A" if not category.text else category.text
                    stat_map["DEC"] = val
                else: stat_map[stat] = stat_map.get(stat, 0) + (int(category.text) if not stat == 'IP' else float(category.text))
        ERA = "0.00" if stat_map['IP'] == '0' else '{0:.2f}'.format(round((9 * (int(stat_map['ER']) / float(stat_map['IP']))), 3))
        WHIP = "0.00" if stat_map['IP'] == '0' else '{0:.2f}'.format(round(((int(stat_map['BB']) + int(stat_map['H']))) / float(stat_map['IP']), 3))
        stat_map['ERA'] = ERA
        stat_map['WHIP'] = WHIP


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
            if player_type == PITCHER:
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
            elif player_type == BATTER:
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


# fetch_player_stats("Joe Kelly")
# testing\
TOKEN = json.loads(open('../token.json', 'r').read())["APP_TOKEN"]
client = SportsClient()
client.run(TOKEN)
# fetch_blurb("JD", "Martinez")
# best_pitchers()
# print("\n")
# worst_pitchers()
# print("\n")
# best_batters()
# print("\n")
# worst_batters()
