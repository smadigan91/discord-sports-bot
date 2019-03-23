from bs4 import BeautifulSoup
from difflib import SequenceMatcher
from urllib import request, parse
from requests_html import AsyncHTMLSession
import asyncio
import json

base_url = 'https://www.rotoworld.com'
blurb_search_url = "https://search.rotoworld.com/players?query={search}&league={sport}"
asession = AsyncHTMLSession()
# blurb_search_url = 'http://www.rotoworld.com/content/playersearch.aspx?searchname={last},{first}&sport={sport}'


def get_blurb(search, sport):
    # for some weird reason its actually better to omit the first name in the search form
    req = request.Request(blurb_search_url.format(search=parse.quote(search), sport=sport))
    req.add_header('x-api-key', 'vWahHcUV5n6xPc9GAnzpX55O0ny1CR5Z2vOFoht0')
    response = get_soup(req)
    json_response = json.loads(response.text)["responses"]
    if not json_response:
        raise NoResultsError(f"No recent player news for {search}")
    name_map = {}
    for result in json_response:
        total = result['hits']['total']
        if total == 0:
            continue
        player = result['hits']['hits'][0]['_source']
        player_name = player['full_name']
        name_map[(player['profile_url'], player_name)] = SequenceMatcher(None, search, player_name).ratio()
    sorted_names = sorted(name_map, key=name_map.get, reverse=True)
    profile_url = sorted_names[0][0]
    player_name = sorted_names[0][1]
    html = asyncio.ensure_future(get_blurb_html(f'{base_url}{profile_url}'))
    html.render()
    player_block = html.find('div[id=block-mainpagecontent-2]')[0]
    title = player_block.find('div[class=player-news-article__title]')[0].find('h1')[0]
    summary = player_block.find('div[class=player-news-article__summary]')[0].find('p')[0]
    timestamp = player_block.find('div[class=player-news-article__timestamp]')[0]
    if not title:
        raise NoResultsError(f"No recent player news for {search}")
    blurb = title.text + '\n\n' + summary.text + '\n' + timestamp.text
    # print(player_name + '\n\n' + blurb)
    return blurb, player_name


async def get_blurb_html(url):
    r = await asession.get(url)
    return r


def get_soup(url):
    response = request.urlopen(url)
    return BeautifulSoup(response.read().decode("ISO-8859-1"), 'html.parser')


class NoResultsError(Exception):
    # TODO just log a message in whatever channel
    message = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message
