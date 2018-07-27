import asyncio
import discord
import os

from baseball_wrapper import get_log, get_highlight, get_blurb
from help_commands import get_help_text


class SportsClient(discord.Client):

    @asyncio.coroutine
    def on_message(self, message):
        if message.channel.name in ["sportsbot-testing", "baseball"]:
            # /help
            contentLower = message.content.lower();
            if contentLower.startswith('/help'):
                try:
                    help_map = discord.Embed(title="Commands List", description=get_help_text())
                    yield from self.send_message(message.channel, embed=help_map)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))

            # /blurb [firstname]* [lastname]*
            if contentLower.startswith('/blurb'):
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
            if contentLower.startswith('/last'):
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
            if contentLower.startswith('/log'):
                try:
                    search = " ".join(message.content.split()[1:])
                    embedded_stats = get_log(search)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            # /season [year] [player]*
            if contentLower.startswith('/season'):
                msg = message.content.split()[1:]
                try:
                    if msg[0].isdigit():
                        embedded_stats = get_log(" ".join(msg[1:]), season=True, season_year=msg[0])
                    else:
                        embedded_stats = get_log(" ".join(msg), season=True)
                    yield from self.send_message(message.channel, embed=embedded_stats)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))
            # /highlight [player]* [index]
            if contentLower.startswith('/highlight'):
                msg = message.content.split()[1:]
                response = "\n%s\n%s"
                try:
                    if msg[0] == 'index':
                        search = '%2B'.join(msg[1:])
                        highlights = get_highlight(search, list_index=True)
                        yield from self.send_message(message.channel, embed=highlights)
                    elif msg[-1].isdigit():
                        index = msg[-1]
                        search = '%2B'.join(msg[:-1])
                        highlight = get_highlight(search, int(index) - 1)
                        yield from self.send_message(message.channel, content=response % highlight)
                    else:
                        highlight = get_highlight('%2B'.join(msg))
                        yield from self.send_message(message.channel, content=response % highlight)
                except Exception as ex:
                    yield from self.send_message(message.channel, content=str(ex))


if __name__ == "__main__":
    # token = json.loads(open('token.json', 'r').read())["APP_TOKEN"]
    token = os.environ.get('TOKEN', '')
    client = SportsClient()
    client.run(token)
