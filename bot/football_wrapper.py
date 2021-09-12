import urllib.request
import re
import discord
import json
from util import NoResultsError, get_blurb
from bs4 import BeautifulSoup

search_url = 'https://www.fantasypros.com/nfl/start/{p1}-{p2}.php?scoring={scoring}'
player_search_url = 'https://www.fantasypros.com/ajax/players.php?callback=searchcb&q={name}&index=nfl_players&sport=NFL'
DEBUG = False


def get_football_blurb(first, last):
    return get_blurb(first, last, 'nfl')


# will need to actually do the search to get the most likely results for players who arent uniquely named
def start_or_sit(msg):
    if 'ppr' in msg:
        scoring = 'PPR'
        msg.remove('ppr')
    elif 'half' in msg:
        scoring = 'HALF'
        msg.remove('half')
    elif 'standard' in msg:
        scoring = 'Standard'
        msg.remove('standard')
    else:
        scoring = 'Standard'
    players = ' '.join(msg).split(' or ')
    return get_start_sit_advice(players, scoring)


def get_start_sit_advice(players, scoring='Standard'):
    # print(search_url.format(p1_first=p1[0], p1_second=p1[1], p2_first=p2[0], p2_second=p2[1], scoring=scoring))
    try:
        p1_valid_name = search_dropdown(players[0])
        p2_valid_name = search_dropdown(players[1])
    except NoResultsError:
        raise
    except Exception:
        raise ValueError("Request phrase must be of format \"[player_1] or [player_2] [ppr|half|standard*]\"")
    response = urllib.request.urlopen(search_url.format(p1=p1_valid_name, p2=p2_valid_name, scoring=scoring))
    soup = BeautifulSoup(response.read().decode('utf-8'), 'html.parser')
    title = soup.find('title').text
    pcts = soup.select('div[class=pick-percent]')
    more = pcts[0]
    more_experts = more.find_previous().text.split('by')[1]
    less = pcts[1]
    less_experts = less.find_previous().text.split('by')[1]
    start = soup.find(lambda tag: tag.name == 'a' and 'fp-player-name' in tag.attrs)
    sit = start.find_next(lambda tag: tag.name == 'a' and 'fp-player-name' in tag.attrs and tag['fp-player-name'] != start['fp-player-name'])

    ecr_tag = soup.find(lambda tag: tag.text == 'ECR')
    ecr_start_tag = ecr_tag.find_next(lambda tag: tag.name == 'td')
    ecr_start = int(ecr_start_tag.text.split()[1])
    ecr_sit_tag = ecr_start_tag.find_next(lambda tag: tag.name == 'td')
    ecr_sit = int(ecr_sit_tag.text.split()[1])

    best_rank_tag = soup.find(lambda tag: tag.text == 'Best Rank')
    best_rank_start_tag = best_rank_tag.find_next(lambda tag: tag.name == 'td')
    best_rank_start = int(best_rank_start_tag.text.split()[1])
    best_rank_sit_tag = best_rank_start_tag.find_next(lambda tag: tag.name == 'td')
    best_rank_sit = int(best_rank_sit_tag.text.split()[1])

    worst_rank_tag = soup.find(lambda tag: tag.text == 'Worst Rank')
    worst_rank_start_tag = worst_rank_tag.find_next(lambda tag: tag.name == 'td')
    worst_rank_start = int(worst_rank_start_tag.text.split()[1])
    worst_rank_sit_tag = worst_rank_start_tag.find_next(lambda tag: tag.name == 'td')
    worst_rank_sit = int(worst_rank_sit_tag.text.split()[1])
    title = "**"+title+"**\n"

    body = "{} {}\n{}\n".format('**Start:**', start['fp-player-name'], f"**{more.text}** ({more_experts})")
    body = body + "{} {}\n".format('**ECR:**', f"**{ecr_start}**" if ecr_start < ecr_sit else ecr_start)
    body = body + "{} {}\n".format('**Best Rank:**', f"**{best_rank_start}**" if best_rank_start < best_rank_sit else best_rank_start)
    body = body + "{} {}\n\n".format('**Worst Rank:**', f"**{worst_rank_start}**" if worst_rank_start < worst_rank_sit else worst_rank_start)

    body = body + "{} {}\n{}\n".format('**Sit:**', sit['fp-player-name'], f"**{less.text}** ({less_experts})")
    body = body + "{} {}\n".format('**ECR:**', f"**{ecr_sit}**" if ecr_sit < ecr_start else ecr_sit)
    body = body + "{} {}\n".format('**Best Rank:**', f"**{best_rank_sit}**" if best_rank_sit < best_rank_start else best_rank_sit)
    body = body + "{} {}\n\n".format('**Worst Rank:**', f"**{worst_rank_sit}**" if worst_rank_sit < worst_rank_start else worst_rank_sit)
    if DEBUG:
        print(title)
        print(body)
    return discord.Embed(title=title, description=body)


def search_dropdown(player_name):
    player_name = player_name.split()
    response = urllib.request.urlopen(player_search_url.format(name="+".join(player_name)))
    response = response.read().decode('utf-8')
    # print(response)
    json_results = json.loads(re.search(r'searchcb\((.*?)\);', response).group(1))['results']
    try:
        search_name = re.search(r'players\/(.*?).php', json_results[0]['link']).group(1)
    except IndexError:
        raise NoResultsError(f'No results for {player_name[0]} {player_name[1]}')
    return search_name

# DEBUG = True
# msg = '/start mostert or aiyuk ppr'
# start_or_sit(msg.split()[1:])
