import asyncio
from datetime import datetime as dt
import datetime
from difflib import SequenceMatcher
import json
import os
import urllib

from bs4 import BeautifulSoup
import discord
from requests import get
from tabulate import tabulate

bbref_url = 'https://www.baseball-reference.com'
stats_url = bbref_url + '/leagues/daily.fcgi?request=1&type={type}&dates={dates}&level=mlb'
search_url = bbref_url + '/search/search.fcgi?search={search}'
blurb_search_url = 'http://www.rotoworld.com/content/playersearch.aspx?searchname={first}+{last}&sport=mlb'
highlights_url = 'https://search-api.mlb.com/svc/search/v2/mlb_global_sitesearch_en/query?q={search}%2B2&page=1&sort=new&type=video&hl=false&expand=image&listed=true'
batter_log_stats = ["date_game", "opp_ID", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "batting_avg", "onbase_perc", "slugging_perc", "onbase_plus_slugging"]  # derive AVG
pitcher_log_stats = ["date_game", "opp_ID", "player_game_result", "IP", "H", "R", "ER", "BB", "SO", "pitches", "GS", "W", "L", "SV", "earned_run_avg", "whip"]  # derive ERA
pitcher_stats = ["player", "", "IP", "H", "R", "ER", "BB", "SO", "pitches"]
batter_stats_good = ["player", "PA", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SB"]
batter_stats_bad = ["player", "PA", "H", "BB", "SO", "GIDP", "CS"]
pitcher_display = ["NAME"] + pitcher_stats[1:-1] + ["#P"]
PITCHER = 'p'  # need to be careful not to confuse this with searching for html elements
BATTER = 'b'
help_map = {}  # commands to descriptions, * designating required

''' TODO 5/17:
    Try streaming responses for player pages, they may be too large
    top x, bottom x for today, given day
'''


class SportsClient(discord.Client):
    
    @asyncio.coroutine
    def on_message(self, message):
        if message.channel.name in ["sportsbot-testing", "baseball"]:
            # /blurb [firstname]* [lastname]*
            if message.content.startswith('/blurb'):
                msg = message.content.split()[1:]
                try:
                    first = msg[0]
                    last = " ".join(msg[1:])  # hopefully handles the Jrs
                    if not first or not last:
                        raise ValueError('A first and last name must be provided')
                    blurb = get_blurb(first, last)
                    embedded_blurb = discord.Embed(title=" ".join([first, last]).title(), description=blurb)
                    yield from self.send_message(message.channel, embed=embedded_blurb)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            # /last [num days]* [player]*
            if message.content.startswith('/last'):
                msg = message.content.split()[1:]
                try:
                    days = int(msg[0])
                    if not days:
                        raise ValueError('A number of last days must be provided')
                    if len(msg) < 2:
                        raise ValueError('Must provide both a number of days and a name')
                    embedded_stats = get_log(" ".join(msg[1:]), last_days=days)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            # /log [player]*
            if message.content.startswith('/log'):
                try:
                    search = " ".join(message.content.split()[1:])
                    embedded_stats = get_log(search)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            # /season [player]* [year]
            if message.content.startswith('/season'):
                msg = message.content.split()[1:]
                try:
                    if msg[-1].isdigit():
                        embedded_stats = get_log(" ".join(msg[1:]), season=True, season_year=msg[0])
                    else:
                        embedded_stats = get_log(" ".join(msg), season=True)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            # /highlight [player]* [index]
            if message.content.startswith('/highlight'):
                msg = message.content.split()[1:]
                response = "\n%s\n%s"
                try:
                    if msg[-1].isdigit():
                        index = msg[-1]
                        search = msg[:-1].replace(' ', '+')
                        highlight = get_highlight(search, index-1)
                        yield from self.send_message(message.channel, content=response % highlight)
                    else:
                        highlight = get_highlight(msg.replace(' ', '+'))
                        yield from self.send_message(message.channel, content=response % highlight)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))


def get_highlight(search, index=0):
    response = json.loads(get(highlights_url.format(search=search)).text)
    urls = []
    for doc in response['docs']:
        urls.append((doc['blurb'], doc['url']))
    try:
        blurb = urls[index][0]
        video_url = urls[index][1]
    except IndexError:
        raise NoResultsError(f'No results for {search}')
    soup = BeautifulSoup(get(video_url).text, 'html.parser')
    video = soup.findChild(lambda tag: tag.name == 'meta' and tag.get('itemprop') == 'contentURL' and tag.get('content').endswith('.mp4')).get('content')
    if video:
        return video, blurb
    else:
        raise NoResultsError(f'Error parsing video url for {search}')


def get_blurb(first, last, player_url=None):
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
        return get_blurb(first, last, 'http://www.rotoworld.com' + sorted_names[0].get('href'))  # this should work?
    else:
        news = soup.findChildren('div', class_='playernews')
        if news:
            recent_news = news[0]
            report = recent_news.find('div', class_='report')
            impact = recent_news.find('div', class_='impact')
            blurb = report.text + '\n\n' + impact.text
            return blurb
        else: raise NoResultsError("No recent player news for %s %s" % (first, last))
    
    # if only one result, I think it just redirects? test this one first with "pollock"


# just better to do a search and find the best matching result
# maybe add specific date functionality eventually?
def get_log(search, stat_type=None, player_url=None, date=None, last_days=None, date_range=None, season=False, season_year=None, most_recent=True):
    response = get(player_url if player_url else search_url.format(search=urllib.parse.quote(search)))
    soup = BeautifulSoup(response.text, 'html.parser')
    log_holder = soup.find('span', text="Game Logs")
    
    if log_holder:
        name_node = soup.find('h1', attrs={'itemprop':'name'})
        name = name_node.text
        if last_days:
            end_date = datetime.date.today()
            start_date = end_date - datetime.timedelta(days=last_days)
            date_range = (start_date, end_date)
        elif date:
            date_range = (date)
        elif season:
            positions = name_node.find_next('p').text.split()
            player_type = PITCHER if "Pitcher" in positions and len(positions) <= 2 else BATTER
            return get_player_summary(name, response, player_type, None, season, season_year, False)
        is_pitcher = "Pitcher" in name_node.find_next('p').text  # next element after name contains positions
        batting = None if ((stat_type and stat_type != BATTER) or is_pitcher) else log_holder.find_next('div').find('p', class_='listhead', text='Batting')
        pitching = None if ((stat_type and stat_type != PITCHER) or not is_pitcher) else log_holder.find_next('div').find('p', class_='listhead', text='Pitching')
        if batting or pitching:
            batting_list = None if not batting else batting.find_next('ul').findChildren(lambda tag:tag.name == 'a' and tag.text != 'Postseason')
            pitching_list = None if not pitching else pitching.find_next('ul').findChildren(lambda tag:tag.name == 'a' and tag.text != 'Postseason')
            if batting:
                href = batting_list.pop().get('href')
                return get_player_summary(name, get(bbref_url + href), BATTER, date_range=date_range, most_recent=most_recent)
                # grab batting logs
            elif pitching:
                href = pitching_list.pop().get('href')
                return get_player_summary(name, get(bbref_url + href), PITCHER, date_range=date_range, most_recent=most_recent)
            else:
                raise ValueError("Not sure what happened, landed in a player page without accessible game logs [%s]" % search)
        else:
            if stat_type == BATTER:
                raise NoResultsError("No batting stats for %s" % name)
            elif stat_type == PITCHER:
                raise NoResultsError("No pitching stats for %s" % name)
        
    elif soup.findChild('div', class_='search-results'):
        mlb_players = soup.find('div', attrs={"id":"players"})
        if mlb_players:
            href = mlb_players.find_next('div', class_='search-item-url').text
            return get_log(search, stat_type, bbref_url + href, date, last_days, date_range, season, season_year, most_recent)
        else: raise NoResultsError("No MLB results for %s" % search)
    else:
        raise NoResultsError("No results for %s" % search)


# should be given a row of either game logs or season logs
# given a table of game data, aggregate according to parameters and return a string
def get_player_summary(name, response, player_type, date_range=None, season=False, season_year=None, most_recent=True):
    # if season, get season gamelogs
    # else get gamelogs
    table = []
    if season:
        table = [get_season_table(name, response, player_type, season_year).pop()]
        season_year = table[0].get('id').split('.')[1]
    else:
        table = get_gamelog_table(name, response, player_type, date_range, most_recent)
    cat_dict = {}
    # index the stats
    for row in table:
        index_game_row(row, player_type, cat_dict)
    return format_player_stats(name, player_type, cat_dict, date_range, season_year)


def get_gamelog_table(name, response, player_type, date_range=None, most_recent=True):
    soup = BeautifulSoup(response.text, 'html.parser')
    tag_id = 'batting_gamelogs' if player_type == BATTER else 'pitching_gamelogs'
    table = []
    if date_range:
        # filters the list of game rows down to those matching the date range
        table = soup.find('table', attrs={'id':tag_id}).find('tbody').findChildren(
            lambda tag:tag.name == 'tr' and not 'thead' == tag.get('class') and tag.findChild(
                lambda tag:tag.name == "td" and tag['data-stat'] == 'date_game'
                and ((date_range[0] <= dt.strptime(tag.get('csk').split(".")[0], "%Y-%m-%d").date() <= date_range[1]) if len(date_range) > 1 
                     else (dt.strptime(tag.get('csk').split(".")[0], "%Y-%m-%d").date() == dt.strptime(date_range[1], "%Y-%m-%d").date()))))
        if not table:
            if len(date_range) == 1:
                raise NoResultsError("No results for %s on %s" % (name, date_range[0]))
            else:
                raise NoResultsError("No results for %s from %s to %s" % (name, date_range[0], date_range[1]))
    elif most_recent:
        table = [soup.find('table', attrs={'id':tag_id}).find('tbody').find_all('tr').pop()]
        if not table:
            raise NoResultsError("No results for %s" % name)
    else:
        raise ValueError("Either most_recent or date_range must be valid")
    return table


# returns a tuple of the year mapped to the table cont
def get_season_table(name, response, player_type, year=None):
    soup = BeautifulSoup(response.text, 'html.parser')
    tag_id = 'batting_standard' if player_type == BATTER else 'pitching_standard'
    table = soup.find('table', attrs={'id':tag_id}).find('tbody').findChildren(
        lambda tag:tag.name == 'tr' and 'full' in tag.get('class') and ((tag.get('id').split('.')[1] == str(year)) if year else True))
    if not table:
        if year:
            raise NoResultsError("No results for %s in %s" % (name, year))
        else:
            raise NoResultsError("No results for %s" % name)
    return table


def index_game_row(row, player_type, stat_map):
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
                elif stat in ["batting_avg", "onbase_perc", "slugging_perc", "onbase_plus_slugging"]:
                    stat_map[stat] = category.text
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
                elif stat in ["earned_run_avg", "whip"]:
                    stat_map[stat] = category.text
                else: stat_map[stat] = stat_map.get(stat, 0) + (int(category.text) if not stat == 'IP' else float(category.text))
        ERA = "0.00" if stat_map['IP'] == '0' else '{0:.2f}'.format(round((9.0 * (float(stat_map['ER']) / float(stat_map['IP']))), 3))
        WHIP = "0.00" if stat_map['IP'] == '0' else '{0:.2f}'.format(round((float(stat_map['BB']) + float(stat_map['H'])) / float(stat_map['IP']), 3))
        stat_map['ERA'] = ERA
        stat_map['WHIP'] = WHIP


# given a name and a map of categories to values, return a formatted string
def format_player_stats(name, player_type, stat_map, date_range, season_year=None):
    title = ""
    body = ""
    if season_year:
        title = "%s in %s" % (name, season_year)
    elif not date_range:
        title = "%s on %s vs %s" % (name, stat_map['DATE'], stat_map['VS'])
    else:
        title = "%s from %s through %s" % (name, date_range[0], date_range[1])
        
    if date_range: body += display('GP', stat_map)
    if player_type == PITCHER:
        if not date_range and not season_year:
            body += display('DEC', stat_map)
        if 'GS' in stat_map and stat_map['GS'] != '0':
            body += display('GS', stat_map)
        if season_year:
            body += display('W', stat_map)
            body += display('L', stat_map)
        if 'SV' in stat_map and stat_map['SV'] != '0':
            body += display('SV', stat_map)
        body += display('IP', stat_map)
        body += display('H', stat_map)
        body += display('R', stat_map)
        body += display('ER', stat_map)
        body += display('BB', stat_map)
        body += display('SO', stat_map)
        if season_year:
            body += display('earned_run_avg', stat_map, "ERA")
            body += display('whip', stat_map, "WHIP")
        else:
            body += display('ERA', stat_map)
            body += display('WHIP', stat_map)
        if not season_year:
            body += display('pitches', stat_map, "#PITCH")
    else:
        if season_year:
            body += "**" + 'AVG' + ':** ' + str(stat_map['batting_avg']) + (" (%s/%s)" % (stat_map['H'], stat_map['AB'])) + "\n"
            body += display("onbase_perc", stat_map, "OBP")
            body += display("slugging_perc", stat_map, "SLG")
            body += display("onbase_plus_slugging", stat_map, "OPS")
        else:
            body += display('AVG', stat_map)
        body += display('R', stat_map)
        body += display('2B', stat_map)
        body += display('3B', stat_map)
        body += display('HR', stat_map)
        body += display('RBI', stat_map)
        body += display('BB', stat_map)
        body += display('SB', stat_map)
        body += display('SO', stat_map)
    print(body)
#     print(title + "\n")
#     print(body)
    return discord.Embed(title=title, description=body)
    # if just one day, title should be:
    # "Stats for <Name> on <Date> vs <OPP>
    # if multi days, title should be:
    # "Stats for <Name> from <start> thru <end>


def display(key, stats, override=None):
    if key in stats:
        return "**" + (key if not override else override) + ':** ' + str(stats[key]) + "\n"


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


def find(key, dictionary):
    for k, v in dictionary.items():
        if k == key:
            yield v
        elif isinstance(v, dict):
            for result in find(key, v):
                yield result
        elif isinstance(v, list):
            for d in v:
                for result in find(key, d):
                    yield result


class NoResultsError(Exception):
    # TODO just log a message in whatever channel
    message = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message


if __name__ == "__main__":
    # token = json.loads(open('token.json', 'r').read())["APP_TOKEN"]
    token = os.environ.get('TOKEN', '')
    client = SportsClient()
    client.run(token)


# get_log("Shohei", stat_type=PITCHER, season=True)
# testing\
# fetch_blurb("JD", "Martinez")
# best_pitchers()
# print("\n")
# worst_pitchers()
# print("\n")
# best_batters()
# print("\n")
# worst_batters()
