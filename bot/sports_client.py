import asyncio
import discord
import os
import threading
import schedule

from baseball_wrapper import get_highlight, get_baseball_blurb, get_log as get_baseball_log
from football_wrapper import get_football_blurb, start_or_sit
from basketball_wrapper import get_basketball_blurb, get_log as get_basketball_log, get_lowlight, get_highlight as get_bball_highlight
from help_commands import get_help_text


class SportsClient(discord.Client):

    @asyncio.coroutine
    def on_message(self, message):
        if message.channel.name in ["sportsbot-testing", "baseball"]:
            yield from self.handle_baseball_request(message)
        elif message.channel.name in ["american-football"]:
            yield from self.handle_football_request(message)
        elif message.channel.name in ["basketball", "better-late-than-never", "fuck-kevin-durant",
                                      "people-order-our-patties"]:
            yield from self.handle_basketball_request(message)

    def handle_football_request(self, message):
        sport = 'nfl'
        content_lower = message.content.lower()
        # /blurb [firstname]* [lastname]*
        if content_lower.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        elif content_lower.startswith('/start'):
            msg = content_lower.split()[1:]
            try:
                embed = start_or_sit(msg)
                yield from self.send_message(message.channel, embed=embed)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))

    def handle_basketball_request(self, message):
        sport = 'nba'
        content_lower = message.content.lower()
        # /blurb [firstname]* [lastname]*
        if content_lower.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        # /log [player]*
        elif content_lower.startswith('/log'):
            try:
                search = " ".join(message.content.split()[1:])
                embedded_stats = get_basketball_log(search)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        elif content_lower.startswith('/highlight'):
            try:
                yield from self.do_bball_highlight(channel=message.channel, cached=True)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        elif content_lower.startswith('/lowlight'):
            try:
                yield from self.do_bball_lowlight(channel=message.channel)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))

    def handle_baseball_request(self, message):
        sport = 'mlb'
        # /help
        content_lower = message.content.lower()
        if content_lower.startswith('/help'):
            try:
                help_map = discord.Embed(title="Commands List", description=get_help_text())
                yield from self.send_message(message.channel, embed=help_map)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))

        # /blurb [firstname]* [lastname]*
        if content_lower.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        # /last [num days]* [player]*
        if content_lower.startswith('/last'):
            msg = message.content.split()[1:]
            try:
                days = int(msg[0])
                if not days:
                    raise ValueError('A number of last days must be provided')
                if len(msg) < 2:
                    raise ValueError('Must provide both a number of days and a name')
                embedded_stats = get_baseball_log(" ".join(msg[1:]), last_days=days)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        # /log [player]*
        if content_lower.startswith('/log'):
            try:
                search = " ".join(message.content.split()[1:])
                embedded_stats = get_baseball_log(search)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        # /season [year] [player]*
        if content_lower.startswith('/season'):
            msg = message.content.split()[1:]
            try:
                if msg[0].isdigit():
                    embedded_stats = get_baseball_log(" ".join(msg[1:]), season=True, season_year=msg[0])
                else:
                    embedded_stats = get_baseball_log(" ".join(msg), season=True)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        # /highlight [player]* [index]
        if content_lower.startswith('/highlight'):
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

    def handle_blurb(self, message, sport):
        msg = message.content.split()[1:]
        try:
            first = msg[0]
            last = " ".join(msg[1:])  # hopefully handles the Jrs
            if not first or not last:
                raise ValueError('A first and last name must be provided')
            if sport == 'mlb':
                blurb = get_baseball_blurb(first, last)
            elif sport == 'nfl':
                blurb = get_football_blurb(first, last)
            elif sport == 'nba':
                blurb = get_basketball_blurb(first, last)
            else:
                raise ValueError(f"Invalid value for 'sport': {sport}")
            embedded_blurb = discord.Embed(title=" ".join([first, last]).title(), description=blurb)
            yield from self.send_message(message.channel, embed=embedded_blurb)
        except Exception as ex:
            yield from self.send_message(message.channel, content=str(ex))

    def get_channel_from_name(self, channel_name):
        return discord.utils.get(client.get_all_channels(), name=channel_name)

    def do_bball_highlight(self, channel=None, cached=False):
        embed = get_bball_highlight(cached=cached)
        if embed:
            bball_channel = channel if channel else self.get_channel_from_name("basketball")
            yield from self.send_message(bball_channel, embed=embed)

    def do_bball_lowlight(self, channel=None):
        embed = get_lowlight()
        if embed:
            bball_channel = channel if channel else self.get_channel_from_name("basketball")
            yield from self.send_message(bball_channel, embed=embed)

    def highlight_lowlight_job(self):
        schedule.every().day.at("15:32").do(self.do_bball_highlight)
        schedule.every().day.at("15:33").do(self.do_bball_lowlight)
        while True:
            schedule.run_pending()


if __name__ == "__main__":
    # token = json.loads(open('token.json', 'r').read())["APP_TOKEN"]
    token = os.environ.get('TOKEN', '')
    client = SportsClient()
    threading.Thread(target=client.highlight_lowlight_job)
    client.run(token)
