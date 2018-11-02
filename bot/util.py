from bs4 import BeautifulSoup
from difflib import SequenceMatcher
import urllib.request

blurb_search_url = 'http://www.rotoworld.com/content/playersearch.aspx?searchname={last},{first}&sport={sport}'


def get_blurb(first, last, sport, player_url=None):
    # for some weird reason its actually better to omit the first name in the search form
    soup = get_soup(player_url if player_url else blurb_search_url.format(first="", last=last, sport=sport))
    # did we land a result page?
    if not soup.findChild('div', class_='RW_pn'):
        name_map = {}
        results_table = soup.find('table', attrs={'id':'cp1_tblSearchResults'})
        # filter results, omitting duplicate "position" links that don't include the player's name
        filtered_results = results_table.findChildren(lambda tag: tag.name == 'a' and 'player' in tag['href'] and len(tag.text) > 3)
        if not filtered_results:
            raise NoResultsError("No results for %s %s" % (first, last))
        else:
            for result in filtered_results:
                name = " ".join(result.text.split())
                name_map[result] = SequenceMatcher(None, first + " " + last, name).ratio()
        # sort names by similarity to search criteria
        sorted_names = sorted(name_map, key=name_map.get, reverse=True)
        return get_blurb(first, last, sport, player_url='http://www.rotoworld.com' + sorted_names[0].get('href'))
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


def get_soup(url):
    response = urllib.request.urlopen(url)
    return BeautifulSoup(response.read().decode("ISO-8859-1"), 'html.parser')


class NoResultsError(Exception):
    # TODO just log a message in whatever channel
    message = None

    def __init__(self, message):
        super().__init__(message)
        self.message = message
