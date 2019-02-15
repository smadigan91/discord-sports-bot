import urllib
import re
import discord
from util import NoResultsError, get_blurb, get_soup
from datetime import datetime
from difflib import SequenceMatcher

bbref_url = 'https://www.basketball-reference.com'
search_url = bbref_url + '/search/search.fcgi?search={search}'
last_url = bbref_url + '/play-index/span_stats.cgi?html=1&page_id={page_id}&table_id=pgl_basic&range={last}-{career}'
espn_search_url = 'http://www.espn.com/nba/players/_/search/{search}'
top_url = bbref_url + '/friv/dailyleaders.fcgi'
letters = re.compile('[^a-zA-Z]')
DEBUG = False


def get_basketball_blurb(search):
    return get_blurb(search, 'nba')


def get_log(search):
    log_map = get_log_map(search)
    embed = format_log(log_map)
    return embed


def get_last(search, last):
    avg_log_map = get_avg_map(search, last)
    title = "Average stats for **{player}** over his last " + f"{last} games"
    embed = format_log(avg_log_map, title=title, add_date_header=False)
    return embed


def get_live_log(search):
    live_log_map = get_live_log_map(search)
    title = "Live(ish) stats for **{player}** vs **{opp}** @ **{date}**"
    embed = format_log(live_log_map, title=title, name_only=False, add_date_header=False)
    return embed


def get_highlight():
    highlight_map = get_highlight_lowlight_map(highlight=True)
    embed = None
    if highlight_map:
        title = "Stat line of the day for **{date}**: **{player}** vs **{opp}**"
        embed = format_log(highlight_map, title=title, name_only=False, add_date_header=False)
    return embed


def get_lowlight():
    lowlight_map = get_highlight_lowlight_map(highlight=False)
    embed = None
    if lowlight_map:
        title = "Lowlight of the day for **{date}**: **{player}** vs **{opp}**"
        embed = format_log(lowlight_map, title=title, name_only=False, add_date_header=False)
    return embed


def get_log_map(search):
    name, table = get_player_log_table(search=search)
    row = table.find_all(lambda tag: tag.name == 'tr' and 'pgl_basic' in tag.get('id', '')).pop()
    stat_map = index_row(row)
    stat_map['name'] = name
    return stat_map


def get_avg_map(search, last):
    name, table = get_avg_log_table(search=search, last=last)
    row = table.findChild('tr')
    stat_map = index_row(row)
    stat_map['name'] = name
    return stat_map


def get_live_log_map(search, url=None):
    full_search = ' '.join(search)
    if url:
        soup = get_soup(url)
    else:
        last_name = format_live_search(search)
        soup = get_soup(espn_search_url.format(search=last_name))
    profile = soup.findChild('td', class_='profile-overview')
    if profile:
        try:
            name = soup.find('div', class_='main-headshot').find_next('h1').text
            qtr = soup.find('li', class_='game-clock')
            if qtr:
                log_map = {}
                time_left = qtr.find_next('span').text
                log_header = profile.find_next(lambda tag: tag.name == 'h4' and tag.text == 'GAME LOG')
                stats = log_header.find_next('table', class_='tablehead').findChildren('td')
                end_qtr = 'Halftime' in qtr.text or 'End' in qtr.text
                log_map['date_game'] = qtr.text.rstrip() if end_qtr else '{}, {}'.format(qtr.text.replace('"', '').replace(time_left, ''), time_left)
                log_map['opp_id'] = stats[1].find_next('a').find_next('a').text
                log_map['mp'] = stats[3].text
                fgm_fga = stats[4].text.split('-')
                log_map['fg'] = fgm_fga[0]
                log_map['fga'] = fgm_fga[1]
                log_map['fg_pct'] = stats[5].text
                tpm_tpa = stats[6].text.split('-')
                log_map['fg3'] = tpm_tpa[0]
                log_map['fg3a'] = tpm_tpa[1]
                ftm_fta = stats[8].text.split('-')
                log_map['ft'] = ftm_fta[0]
                log_map['fta'] = ftm_fta[1]
                log_map['trb'] = stats[10].text
                log_map['ast'] = stats[11].text
                log_map['blk'] = stats[12].text
                log_map['stl'] = stats[13].text
                log_map['pf'] = stats[14].text
                log_map['tov'] = stats[15].text
                log_map['pts'] = stats[16].text
                log_map['name'] = name
                return log_map
            else:
                raise NoResultsError(f"{name} isn't currently playing")
        except Exception as ex:
            raise ex
    else:
        results_table = soup.find('div', attrs={'id': 'my-players-table'}).find_next('table')
        col_header = results_table.findChild('tr', class_='colhead')
        if col_header:
            player_results = results_table.findChildren(lambda tag: tag.name == 'tr' and tag.get('class') not in ['stathead', 'colhead'])
            result_map = {}
            for result in player_results:
                a = result.find_next('a')
                name = a.text.split(', ')
                name = f'{name[1]} {name[0]}'
                match = SequenceMatcher(None, full_search, name).ratio()
                result_map[a.get('href')] = match
            player_href = sorted(result_map, key=result_map.get, reverse=True)[0]
            return get_live_log_map(search, player_href)
        else:
            raise NoResultsError(f"No results for '{full_search}'")


def format_live_search(search):
    if len(search) == 2 or len(search) == 3:
        return search[1]
    elif len(search) == 1:
        return search[0]
    else:
        raise ValueError('Malformed search string or something?')


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


def get_highlight_lowlight_map(highlight=True):
    top_soup = get_soup(top_url)
    table = top_soup.find('table', attrs={'id': 'stats'})
    if not table:
        return None
    else:
        rows = table.find('tbody').findChildren(lambda tag: tag.name == 'tr' and not 'thead' == tag.get('class')
                                                and tag.findChild(lambda child: child.name == 'td'
                                                                  and child.get('data-stat') == 'mp'
                                                                  and int(child.text.split(':')[0]) >= 25))
    if highlight:
        return index_row(rows[0])
    else:
        return index_row(rows[-1])


def get_player_log_table(search):
    player_soup = get_player_page(search)
    log_holder = player_soup.find('span', text="Game Logs")
    name_node = player_soup.find('h1', attrs={'itemprop': 'name'})
    name = name_node.text
    href = log_holder.find_next('div').find('ul').findChildren('a').pop().get('href')
    log_soup = get_soup(bbref_url + href)
    table = log_soup.find('table', attrs={'id': 'pgl_basic'}).find('tbody')
    return name, table


def get_avg_log_table(search, last):
    player_soup = get_player_page(search)
    career_games = int(player_soup.find('h4', class_='poptip', attrs={'data-tip': 'Games'}).find_next('p').find_next('p').text)
    name_node = player_soup.find('h1', attrs={'itemprop': 'name'})
    name = name_node.text
    if last > career_games:
        raise ValueError(f'{name} has only played {career_games} career games')
    page_id = player_soup.find('link', attrs={'rel': 'canonical'}).get('href').split('/')[-1].split('.')[0]
    log_soup = get_soup(last_url.format(page_id=page_id, last=career_games - last + 1, career=career_games))
    table = log_soup.find('table', attrs={'id': 'pgl_basic_span'}).find('tbody')
    return name, table


def get_player_page(search=None, url=None):
    soup = get_soup(url if url else search_url.format(search=urllib.parse.quote(search)))
    log_holder = soup.find('span', text="Game Logs")
    if log_holder:
        return soup
    elif soup.findChild('div', class_='search-results'):
        nba_players = soup.find('div', attrs={"id": "players"})
        if nba_players:
            results = nba_players.findChildren('div', class_='search-item')
            if len(results) == 1:
                href = nba_players.find_next('div', class_='search-item-url').text
                return get_player_page(url=bbref_url + href)
            else:
                result_map = {}
                for result in results:
                    a = result.find_next('div', class_='search-item-name').find_next('a')
                    name = letters.sub('', a.text)
                    match = SequenceMatcher(None, search, name).ratio()
                    result_map[a.get('href')] = match
                href = sorted(result_map, key=result_map.get, reverse=True)[0]
                return get_player_page(url=bbref_url + href)
        else:
            raise NoResultsError("No NBA results for %s" % search)
    else:
        raise NoResultsError("No results for %s" % search)


def format_log(log_map, title="**{player}**'s most recent game", name_only=True, add_date_header=True):
    date = log_map.get('date_game', None)
    opp = log_map.get('opp_id', None)
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
    name = log_map['name']
    if name_only:
        title = title.format(player=name)
    else:
        title = title.format(player=name, date=date, opp=opp)
    date_header = f"**{date}** vs **{opp}**\n"
    log_string = (date_header if add_date_header else "") + \
                 f"**MIN**: {mins}\n**PTS**: {pts} ({fgm}/{fga}, {fgp} **FG%**, {tpm}/{tpa} **3P**, {ftm}/{fta} **FT**)" \
                 f"\n**REB**: {reb}\n**AST**: {ast}\n**STL**: {stl}\n**BLK**: {blk}\n**TO**: {to}\n**PF**: {pf}"
    if DEBUG:
        print(title)
        print(log_string)
    return discord.Embed(title=title, description=log_string)
