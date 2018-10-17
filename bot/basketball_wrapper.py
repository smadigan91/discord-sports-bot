import urllib
import discord
from util import NoResultsError, get_blurb, get_soup

bbref_url = 'https://www.basketball-reference.com'
search_url = bbref_url + '/search/search.fcgi?search={search}'


def get_basketball_blurb(first, last):
    return get_blurb(first, last, 'nba')


def get_log(search):
    log_map = get_log_map(search)
    embed = format_log(log_map)
    return embed


def get_log_map(search):
    name, table = get_player_log_table(search)
    row = table.find_all('tr').pop()
    stat_map = {'name': name}
    for cell in row.findChildren('td'):
        stat = cell.get('data-stat', default=None)
        if stat:
            stat_map[stat] = cell.text
    return stat_map


def get_player_log_table(search):
    soup = get_soup(search_url.format(search=urllib.parse.quote(search)))
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
            href = nba_players.find_next('div', class_='search-item-url').text
            return get_player_log_table(bbref_url + href)
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


def format_log(log_map):
    name = log_map['name']
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
    # **2018 - 04 - 11 * vs * MIL *
    title = f"**{name}**'s most recent game"
    log_string = f"**{date}** vs **{opp}**\n**MIN**: {mins} "\
                 f"\n**PTS**: {pts} ({fgm}/{fga}, {fgp} **FG%**, {tpm}/{tpa} **3P**, {ftm}/{fta} **FT**)" \
                 f"\n**REB**: {reb}\n**AST**: {ast}\n**STL**: {stl}\n**BLK**: {blk}\n**PF**: {pf}\n**TO**: {to}"
    return discord.Embed(title=title, description=log_string)
