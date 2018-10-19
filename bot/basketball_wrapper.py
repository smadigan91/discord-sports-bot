import urllib
import re
import discord
from util import NoResultsError, get_blurb, get_soup
from datetime import datetime
from difflib import SequenceMatcher

bbref_url = 'https://www.basketball-reference.com'
search_url = bbref_url + '/search/search.fcgi?search={search}'
top_url = bbref_url + '/friv/dailyleaders.fcgi'
letters = re.compile('[^a-zA-Z]')
DEBUG = False

highlight_map = {}
lowlight_map = {}


def get_basketball_blurb(first, last):
    return get_blurb(first, last, 'nba')


def get_log(search):
    log_map = get_log_map(search)
    embed = format_log(log_map)
    return embed


def get_highlight(cached=False):
    if not cached:
        populate_highlight_lowlight()
    if not highlight_map:
        return None
    title = "Yesterday's stat line of the day: **%s**"
    embed = format_log(highlight_map, title=title)
    return embed


def get_lowlight():
    if not lowlight_map:
        return None
    title = "Yesterday's lowlight of the day: **%s%%"
    embed = format_log(lowlight_map, title=title)
    return embed


def get_log_map(search):
    name, table = get_player_log_table(search=search)
    row = table.find_all('tr').pop()
    stat_map = index_row(row)
    stat_map['name'] = name
    return stat_map


def index_row(row):
    stat_map = {}
    for cell in row.findChildren('td'):
        stat = cell.get('data-stat', default=None)
        if stat:
            if stat == 'player':
                stat_map['name'] = cell.text
            else:
                stat_map[stat] = cell.text
    if 'date_game' not in stat_map:
        stat_map['date_game'] = datetime.today().strftime('%Y-%m-%d')
    if DEBUG:
        print(stat_map)
    return stat_map


# returns a tuple of the maps
def populate_highlight_lowlight():
    global highlight_map, lowlight_map
    top_soup = get_soup(top_url)
    table = top_soup.find('table', attrs={'id': 'stats'})
    if not table:
        highlight_map = lowlight_map = {}
        return None
    else:
        rows = table.find('tbody').findChildren(lambda tag: tag.name == 'tr' and not 'thead' == tag.get('class')
                                                and tag.findChild(lambda child: child.name == 'td'
                                                and child.get('data-stat') == 'mp'
                                                    and int(child.text.split(':')[0]) >= 25)
                                                )
        highlight_map = index_row(rows[0])
        lowlight_map = index_row(rows[-1])


def get_player_log_table(search=None, url=None):
    soup = get_soup(url if url else search_url.format(search=urllib.parse.quote(search)))
    log_holder = soup.find('span', text="Game Logs")
    if log_holder:
        name_node = soup.find('h1', attrs={'itemprop': 'name'})
        name = name_node.text
        href = log_holder.find_next('div').find('ul').findChildren('a').pop().get('href')
        log_soup = get_soup(bbref_url + href)
        table = log_soup.find('table', attrs={'id': 'pgl_basic'}).find('tbody')
        return name, table
    elif soup.findChild('div', class_='search-results'):
        nba_players = soup.find('div', attrs={"id": "players"})
        if nba_players:
            results = nba_players.findChildren('div', class_='search-item')
            if len(results) == 1:
                href = nba_players.find_next('div', class_='search-item-url').text
                return get_player_log_table(url=bbref_url + href)
            else:
                result_map = {}
                for result in results:
                    a = result.find_next('div', class_='search-item-name').find_next('a')
                    name = letters.sub('', a.text)
                    match = SequenceMatcher(None, search, name).ratio()
                    result_map[a.get('href')] = match
                href = sorted(result_map, key=result_map.get, reverse=True)[0]
                return get_player_log_table(url=bbref_url + href)
        else:
            raise NoResultsError("No NBA results for %s" % search)
    else:
        raise NoResultsError("No results for %s" % search)


def get_stat(row, stat, default='0'):
    try:
        cell = row.find('td', attrs={'data-stat': stat})
        if cell.text:
            return cell.text
        else:
            return default
    except Exception:
        return default


def format_log(log_map, title="**%s**'s most recent game"):
    title = title % log_map['name']
    date = log_map['date_game']
    opp = log_map['opp_id']
    mins = log_map['mp']
    pts = log_map['pts']
    fgm = log_map['fg']
    fga = log_map['fga']
    fgp = log_map['fg_pct']
    tpm = log_map['fg3']
    tpa = log_map['fg3a']
    ftm = log_map['ft']
    fta = log_map['fta']
    reb = log_map['trb']
    ast = log_map['ast']
    stl = log_map['stl']
    blk = log_map['blk']
    pf = log_map['pf']
    to = log_map['tov']
    log_string = f"**{date}** vs **{opp}**\n**MIN**: {mins} "\
                 f"\n**PTS**: {pts} ({fgm}/{fga}, {fgp} **FG%**, {tpm}/{tpa} **3P**, {ftm}/{fta} **FT**)" \
                 f"\n**REB**: {reb}\n**AST**: {ast}\n**STL**: {stl}\n**BLK**: {blk}\n**TO**: {to}\n**PF**: {pf}"
    if DEBUG:
        print(title)
        print(log_string)
    return discord.Embed(title=title, description=log_string)

