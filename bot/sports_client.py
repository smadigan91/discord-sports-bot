import asyncio
import discord
import os
import datetime

from baseball_wrapper import get_highlight, get_baseball_blurb, get_log as get_baseball_log
from football_wrapper import get_football_blurb, start_or_sit
from basketball_wrapper import get_basketball_blurb, get_log as get_basketball_log, get_lowlight, \
    get_highlight as get_bball_highlight, get_live_log, get_last
from help_commands import get_help_text


class SportsClient(discord.Client):

    @asyncio.coroutine
    def on_message(self, message):
        if message.channel.name in ["sportsbot-testing", "baseball"]:
            yield from self.handle_baseball_request(message)
        elif message.channel.name in ["american-football"]:
            yield from self.handle_football_request(message)
        elif message.channel.name in ["basketball", "better-late-than-never", "fuck-kevin-durant",
                                      "in-memory-of-sankalp"]:
            yield from self.handle_basketball_request(message)

    def handle_football_request(self, message):
        sport = 'nfl'
        cmd, msg = extract_message(message)
        # /blurb [firstname]* [lastname]*
        if cmd.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        elif cmd.startswith('/start'):
            try:
                embed = start_or_sit(msg)
                yield from self.send_message(message.channel, embed=embed)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))

    def handle_basketball_request(self, message):
        sport = 'nba'
        cmd, msg = extract_message(message)
        msg_str = " ".join(msg)
        # /blurb [firstname]* [lastname]*
        if cmd.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        # /log [player]*
        elif cmd.startswith('/log'):
            try:
                embedded_stats = get_basketball_log(msg_str)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        elif cmd.startswith('/live'):
            try:
                embedded_stats = get_live_log(msg)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        elif cmd.startswith('/last'):
            try:
                games = int(msg[0])
                if not games:
                    raise ValueError('A number of last games must be provided')
                if len(msg) < 2:
                    raise ValueError('Must provide both a number of games and a name')
                embedded_stats = get_last(msg_str, last=games)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        elif cmd.startswith('/highlight'):
            try:
                yield from self.do_bball_highlight(channel=message.channel)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        elif cmd.startswith('/lowlight'):
            try:
                yield from self.do_bball_lowlight(channel=message.channel)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))

    def handle_baseball_request(self, message):
        sport = 'mlb'
        # /help
        cmd, msg = extract_message(message)
        msg_str = " ".join(msg)
        if cmd.startswith('/help'):
            try:
                help_map = discord.Embed(title="Commands List", description=get_help_text())
                yield from self.send_message(message.channel, embed=help_map)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        # /blurb [firstname]* [lastname]*
        if cmd.startswith('/blurb'):
            yield from self.handle_blurb(message, sport)
        # /last [num days]* [player]*
        if cmd.startswith('/last'):
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
        if cmd.startswith('/log'):
            try:
                embedded_stats = get_baseball_log(msg_str)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        # /season [year] [player]*
        if cmd.startswith('/season'):
            try:
                if msg[0].isdigit():
                    embedded_stats = get_baseball_log(" ".join(msg[1:]), season=True, season_year=msg[0])
                else:
                    embedded_stats = get_baseball_log(" ".join(msg), season=True)
                yield from self.send_message(message.channel, embed=embedded_stats)
            except Exception as ex:
                yield from self.send_message(message.channel, content=str(ex))
        # /highlight [player]* [index]
        if cmd.startswith('/highlight'):
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
        _, msg = extract_message(message)
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

    async def highlight_lowlight_loop(self):
        await self.wait_until_ready()
        channel = self.get_channel_from_name("basketball")
        while not self.is_closed:
            # check time every minute
            now = datetime.datetime.now()
            if now.hour == 14 and now.minute == 30:
                embed = get_bball_highlight()
                if embed:
                    await self.send_message(channel, embed=embed)
                else:
                    await self.send_message(channel, content="No highlight of the day yesterday")
            elif now.hour == 15 and now.minute == 0:
                embed = get_lowlight()
                if embed:
                    await self.send_message(channel, embed=embed)
                else:
                    await self.send_message(channel, content="No lowlight of the day yesterday")
            await asyncio.sleep(60)

    def do_bball_highlight(self, channel=None):
        embed = get_bball_highlight()
        if embed:
            yield from self.send_message(channel, embed=embed)
        else:
            yield from self.send_message(channel, content="No highlight of the day yesterday")

    def do_bball_lowlight(self, channel=None):
        embed = get_lowlight()
        if embed:
            yield from self.send_message(channel, embed=embed)
        else:
            yield from self.send_message(channel, content="No lowlight of the day yesterday")


# given a message return "/command", "Rest of message"
def extract_message(message):
    lower_content = message.content.lower()
    return lower_content[0], lower_content.split()[1:]


if __name__ == "__main__":
    # token = json.loads(open('token.json', 'r').read())["APP_TOKEN"]
    client = SportsClient()
    token = os.environ.get('TOKEN', '')
    client.loop.create_task(client.highlight_lowlight_loop())
    client.run(token)
