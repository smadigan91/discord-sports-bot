from datetime import datetime as dt
import datetime
from difflib import SequenceMatcher
import json
import urllib

from bs4 import BeautifulSoup
import discord
from requests import get

bbref_url = 'https://www.baseball-reference.com'
stats_url = bbref_url + '/leagues/daily.fcgi?request=1&type={type}&dates={dates}&level=mlb'
search_url = bbref_url + '/search/search.fcgi?search={search}'
blurb_search_url = 'http://www.rotoworld.com/content/playersearch.aspx?searchname={first}+{last}&sport=mlb'
highlights_url = 'https://search-api.mlb.com/svc/search/v2/mlb_global_sitesearch_en/query?q={search}&page=1&sort=new&type=video&hl=false&expand=image&listed=true'
batter_log_stats = ["date_game", "opp_ID", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "SB", "HBP", "SF", "batting_avg", "onbase_perc", "slugging_perc", "onbase_plus_slugging"]  # derive AVG
pitcher_log_stats = ["date_game", "opp_ID", "player_game_result", "IP", "H", "R", "ER", "BB", "SO", "pitches", "GS", "W", "L", "SV", "earned_run_avg", "whip"]  # derive ERA
pitcher_stats = ["player", "", "IP", "H", "R", "ER", "BB", "SO", "pitches"]
batter_stats_good = ["player", "PA", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SB"]
batter_stats_bad = ["player", "PA", "H", "BB", "SO", "GIDP", "CS"]
pitcher_display = ["NAME"] + pitcher_stats[1:-1] + ["#P"]
PITCHER = 'p'  # need to be careful not to confuse this with searching for html elements
BATTER = 'b'
DEBUG = False


def get_highlight(search, index=0, list_index=False):
    response = json.loads(get(highlights_url.format(search=search)).text)
    urls = []
    title_index = {}
    idx = 1
    for doc in response['docs']:
        title = doc['title']
        urls.append((title, doc['url']))
        title_index[idx] = title
        idx = idx + 1
    if list_index:
        if title_index:
            body = ""
            for index, title in title_index.items():
                body += f"{index} - {title}" + "\n"
            return discord.Embed(title="Highlight Index", description=body)
        else:
            raise NoResultsError(f'No results for {search}')
    else:
        try:
            title = '**' + urls[index][0] + '**'
            video_url = urls[index][1]
        except IndexError:
            raise NoResultsError(f'No results for {search}')
        soup = BeautifulSoup(get(video_url).text, 'html.parser')
        video = soup.findChild(lambda tag: tag.name == 'meta' and tag.get('itemprop') == 'contentURL' and tag.get('content').endswith('.mp4')).get('content')
        if video:
            return title, video
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
        else:
            raise NoResultsError("No recent player news for %s %s" % (first, last))
    
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
            end_date = datetime.date.today() - datetime.timedelta(days=1)
            start_date = end_date - datetime.timedelta(days=last_days-1)
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
                else:
                    text = category.text
                    stat_map[stat] = stat_map.get(stat, 0) + int(text if text != '' else 0)
        HAB = str(stat_map['H']) + "/" + str(stat_map['AB'])
        AVG = ".000" if stat_map['AB'] == '0' else ("%.3f" % round(int(stat_map['H']) / int(stat_map['AB']), 3)).lstrip('0')
        SLG = ("%.3f" % round(((stat_map['H'] - (stat_map['2B'] + stat_map['3B'] + stat_map['HR'])) + (2*stat_map['2B']) + (3*stat_map['3B']) + (4*stat_map['HR']))/stat_map['AB'], 3)).lstrip('0')
        OBP = ("%.3f" % round((stat_map['H'] + stat_map['BB'] + stat_map['HBP']) / (stat_map['AB'] + stat_map['BB'] + stat_map['HBP'] + stat_map['SF']), 3)).lstrip('0')
        OPS = ("%.3f" % (float(SLG) + float(OBP))).lstrip('0')
        stat_map['AVG'] = AVG + (" (%s)" % HAB)
        stat_map['SLG'] = SLG
        stat_map['OBP'] = OBP
        stat_map['OPS'] = OPS
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
                    val = category.text
                    if not val:
                        pass
                    else:
                        if val.startswith('S'):
                            stat_map['SV'] = stat_map.get('SV', 0) + 1
                        elif val.startswith('W'):
                            stat_map['W'] = stat_map.get('W', 0) + 1
                        elif val.startswith('L'):
                            stat_map['L'] = stat_map.get('L', 0) + 1
                        elif val.startswith('B'):
                            stat_map['BS'] = stat_map.get('BS', 0) + 1
                        stat_map["DEC"] = val
                elif stat in ["earned_run_avg", "whip"]:
                    stat_map[stat] = category.text
                elif stat == 'IP':
                    ip_sum = stat_map.get(stat, 0.0) + float(category.text)
                    if round(ip_sum % 1, 2) == 0.3:
                        ip_sum = ip_sum - 0.3 + 1.0
                    elif round(ip_sum % 1, 2) == 0.4:
                        ip_sum = ip_sum - 0.4 + 1.1
                    stat_map[stat] = ip_sum
                else:
                    stat_map[stat] = stat_map.get(stat, 0) + int(category.text)
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
        
    if date_range: body += display_get('GP', stat_map)
    if player_type == PITCHER:
        if not date_range and not season_year:
            body += display_get('DEC', stat_map, default="N/A")
        else:
            if stat_map.get('GS', 0) != 0:
                body += display_get('GS', stat_map)
            if stat_map.get('W', 0) != 0:
                body += display_get('W', stat_map)
            if stat_map.get('L', 0) != 0:
                body += display_get('L', stat_map)
            if stat_map.get('SV', 0) != 0:
                body += display_get('SV', stat_map)
            if stat_map.get('BS', 0) != 0:
                body += display_get('BS', stat_map)
        # if 'BS' in stat_map and stat_map['BS'] != 0:
        #     body += display('BS', stat_map)
        body += display_get('IP', stat_map)
        body += display_get('H', stat_map)
        body += display_get('R', stat_map)
        body += display_get('ER', stat_map)
        body += display_get('BB', stat_map)
        body += display_get('SO', stat_map)
        if season_year:
            body += display_get('earned_run_avg', stat_map, "ERA")
            body += display_get('whip', stat_map, "WHIP")
        else:
            body += display_get('ERA', stat_map)
            body += display_get('WHIP', stat_map)
        if not season_year:
            body += display_get('pitches', stat_map, "#PITCH")
    else:
        if season_year:
            body += "**" + 'AVG' + ':** ' + str(stat_map['batting_avg']) + (" (%s/%s)" % (stat_map['H'], stat_map['AB'])) + "\n"
            body += display_get("onbase_perc", stat_map, "OBP")
            body += display_get("slugging_perc", stat_map, "SLG")
            body += display_get("onbase_plus_slugging", stat_map, "OPS")
        else:
            body += display_get('AVG', stat_map)
            body += display_get('OBP', stat_map)
            body += display_get('SLG', stat_map)
            body += display_get('OPS', stat_map)
        body += display_get('R', stat_map)
        body += display_get('2B', stat_map)
        body += display_get('3B', stat_map)
        body += display_get('HR', stat_map)
        body += display_get('RBI', stat_map)
        body += display_get('BB', stat_map)
        body += display_get('SB', stat_map)
        body += display_get('SO', stat_map)
    if DEBUG:
        print(title)
        print(body)
    return discord.Embed(title=title, description=body)


def display_get(key, stats, key_override=None, default=""):
    if key in stats:
        return "**" + (key if not key_override else key_override) + ':** ' + str(stats[key]) + "\n"
    else:
        return "**" + (key if not key_override else key_override) + ':** ' + default + "\n"


class NoResultsError(Exception):
    # TODO just log a message in whatever channel
    message = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message


# debug purposes only
# DEBUG = True
# get_log("Tony Kemp", last_days=30)
