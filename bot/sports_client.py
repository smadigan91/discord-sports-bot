import asyncio
import datetime
import os

import discord
from discord.ext import tasks, commands

from baseball_wrapper import get_highlight, get_baseball_blurb, get_log as get_baseball_log
from basketball_wrapper import get_basketball_blurb, get_log as get_basketball_log, get_lowlight, \
    get_highlight as get_bball_highlight, get_live_log, get_last, get_season, get_career
from football_wrapper import get_football_blurb, start_or_sit
from help_commands import get_help_text

bot_test_id = 955175071637463051
main_basketball_channel_id = 428207200230440961
baseball_channel_ids = [428207176436154368]
football_channel_ids = [428207410424053761, 499342819069132820]
basketball_channel_ids = [bot_test_id, 428207200230440961, 428207239010975745, 812000767321309195, 897231880347324446]


class SportsClient(commands.Bot):

    intents = discord.Intents.default()

    def __init__(self):
        intents = discord.Intents(messages=True, message_content=True)
        super().__init__(intents=intents, command_prefix="/")
        self.highlight_lowlight = HighlightLowlightCog(self)
        asyncio.run(self.add_cog(self.highlight_lowlight))

    async def on_ready(self):
        await self.highlight_lowlight.start_loop()

    async def on_message(self, message):
        if message.content:
            channel = message.channel
            print(channel.id)
            if channel.id in baseball_channel_ids:
                command, message_content = extract_message(message)
                await self.handle_baseball_request(command, message_content, channel)
            elif channel.id in football_channel_ids:
                command, message_content = extract_message(message)
                await self.handle_football_request(command, message_content, channel)
            elif channel.id in basketball_channel_ids:
                print('handling message')
                command, message_content = extract_message(message)
                await self.handle_basketball_request(command, message_content, channel)

    async def handle_football_request(self, command, message_content, channel):
        if command.startswith('/start'):
            try:
                embed = start_or_sit(message_content)
                await channel.send(embed=embed)
            except Exception as ex:
                await channel.send(content=str(ex))

    async def handle_basketball_request(self, command, message_content, channel):
        msg_str = " ".join(message_content)
        print("handling basketball message " + msg_str)
        if command.startswith('/log'):
            try:
                embedded_stats = get_basketball_log(msg_str)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        # /season [year] [player]*
        elif command.startswith('/season'):
            try:
                if message_content[0].isdigit():
                    embedded_stats = get_season(" ".join(message_content[1:]), year=message_content[0])
                else:
                    embedded_stats = get_season(" ".join(message_content), year=None)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        # /career [player]*
        elif command.startswith('/career'):
            try:
                embedded_stats = get_career(" ".join(message_content))
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        elif command.startswith('/live'):
            try:
                embedded_stats = get_live_log(message_content)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        elif command.startswith('/last'):
            try:
                games = int(message_content[0])
                if not games:
                    raise ValueError('A number of last games must be provided')
                if len(message_content) < 2:
                    raise ValueError('Must provide both a number of games and a name')
                embedded_stats = get_last(' '.join(message_content[1:]), last=games)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        elif command.startswith('/highlight'):
            try:
                await self.do_bball_highlight(channel=channel)
            except Exception as ex:
                await channel.send(content=str(ex))
        elif command.startswith('/lowlight'):
            try:
                await self.do_bball_lowlight(channel=channel)
            except Exception as ex:
                await channel.send(content=str(ex))

    async def handle_baseball_request(self, command, message_content, channel):
        # /help
        msg_str = " ".join(message_content)
        if command.startswith('/help'):
            try:
                help_map = discord.Embed(title="Commands List", description=get_help_text())
                await channel.send(embed=help_map)
            except Exception as ex:
                await channel.send(content=str(ex))
        # /last [num days]* [player]*
        elif command.startswith('/last'):
            try:
                days = int(message_content[0])
                if not days:
                    raise ValueError('A number of last days must be provided')
                if len(message_content) < 2:
                    raise ValueError('Must provide both a number of days and a name')
                embedded_stats = get_baseball_log(" ".join(message_content[1:]), last_days=days)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        # /log [player]*
        elif command.startswith('/log'):
            try:
                embedded_stats = get_baseball_log(msg_str)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        # /season [year] [player]*
        elif command.startswith('/season'):
            try:
                if message_content[0].isdigit():
                    embedded_stats = get_baseball_log(" ".join(message_content[1:]), season=True,
                                                      season_year=message_content[0])
                else:
                    embedded_stats = get_baseball_log(" ".join(message_content), season=True)
                await channel.send(embed=embedded_stats)
            except Exception as ex:
                await channel.send(content=str(ex))
        # /highlight [player]* [index]
        elif command.startswith('/highlight'):
            response = "\n%s\n%s"
            try:
                if message_content[0] == 'index':
                    search = '%2B'.join(message_content[1:])
                    highlights = get_highlight(search, list_index=True)
                    await channel.send(embed=highlights)
                elif message_content[-1].isdigit():
                    index = message_content[-1]
                    search = '%2B'.join(message_content[:-1])
                    highlight = get_highlight(search, int(index) - 1)
                    await channel.send(content=response % highlight)
                else:
                    highlight = get_highlight('%2B'.join(message_content))
                    await channel.send(content=response % highlight)
            except Exception as ex:
                await channel.send(content=str(ex))

    async def handle_blurb(self, message_content, channel, sport):
        try:
            first = message_content[0]
            last = " ".join(message_content[1:])  # hopefully handles the Jrs
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
            await channel.send(embed=embedded_blurb)
        except Exception as ex:
            await channel.send(content=str(ex))

    def get_channel_from_name(self, channel_name):
        return discord.utils.get(self.get_all_channels(), name=channel_name)

    async def do_bball_highlight(self, channel=None):
        embed = get_bball_highlight()
        if embed:
            await channel.send(embed=embed)
        else:
            await channel.send(content="No highlight of the day yesterday")

    async def do_bball_lowlight(self, channel=None):
        embed = get_lowlight()
        if embed:
            await channel.send(embed=embed)
        else:
            await channel.send(content="No lowlight of the day yesterday")


class HighlightLowlightCog(commands.Cog):

    def __init__(self, bot: SportsClient):
        self.bot = bot

    @tasks.loop(minutes=1.0)
    async def highlight_lowlight(self):
        basketball_channel = self.bot.get_channel(main_basketball_channel_id)
        now = datetime.datetime.now()
        if now.hour == 14 and now.minute == 00:
            embed = get_bball_highlight()
            if embed:
                await basketball_channel.send(embed=embed)
            else:
                await basketball_channel.send(content="No highlight of the day yesterday")
        elif now.hour == 14 and now.minute == 15:
            embed = get_lowlight()
            if embed:
                await basketball_channel.send(embed=embed)
            else:
                await basketball_channel.send(content="No lowlight of the day yesterday")

    async def start_loop(self):
        await self.highlight_lowlight.start()


# given a message return "/command", "Rest of message"
def extract_message(message):
    lower_content = message.content.split()
    return lower_content[0].lower(), lower_content[1:]


if __name__ == "__main__":
    client = SportsClient()
    client.run(os.environ.get('TOKEN', ''))
