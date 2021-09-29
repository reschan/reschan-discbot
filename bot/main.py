from discord.ext import commands, tasks
import discord
import requests
import asyncio
from dotenv import load_dotenv
import signal
import os
import lavalink
import re
import datetime

load_dotenv()

url_rx = re.compile(r'https?://(?:www\.)?.+')


def parse_playlist_link(url):
    """Extract a youtube playlist link from a video-in-a-playlist link"""
    # url =  https://www.youtube.com/watch?v=Atp5xTJS3gU&list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    # res =  https://www.youtube.com/playlist?list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    if 'watch?v=' not in url:
        return url
    return url[:url.find('watch?v=')] + 'playlist?' + url[url.find('&list=') + 1:]


def np_bar(current: int, end: int) -> str:
    res = '--------------------'
    perc = round(20 * (current / end))
    return res[:perc] + '\u25B6' + res[perc + 1:]


class MainBot(commands.Bot):
    def __init__(self, intents):
        super().__init__(command_prefix='res ', help_command=None, intents=intents)
        self.bot = self

    async def on_ready(self):
        print(f'{self.user.name} has connected to Discord!')
        self.add_cog(Music(self))
        self.add_cog(Diagnostic(self))

    async def on_message(self, ctx):
        if ctx.author.id == self.user.id:
            return None
        if isinstance(ctx.channel, discord.DMChannel):
            return None
        await self.process_commands(ctx)


class Diagnostic(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def kyosmile(self, ctx):
        return await ctx.send(
            '<:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036><:kyoSmile:878070485592703036><:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036>⬛<:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036>⬛<:kyoSmile:878070485592703036>')

    @commands.command(name='test')
    async def dumbstuff(self, ctx, *args):
        for i in range(len(args)):
            await ctx.send(args[i])
        print(ctx.message)
        return await ctx.send('probably alive')

    @commands.command(name='help')
    async def help_cmd(self, ctx):
        embed = discord.Embed(title="Commands for reschan:", color=0x2ff4ff)
        embed.add_field(name="MusicPlayer", value="Commands for MusicPlayer module", inline=False)
        embed.add_field(name="play", value="Join queue and play", inline=True)
        embed.add_field(name="pause", value="Pauses player", inline=True)
        embed.add_field(name="stop", value="Stops the player", inline=True)
        embed.add_field(name="resume", value="Resumes the player", inline=True)
        embed.add_field(name="skip", value="Skip a song", inline=True)
        embed.add_field(name="queue [pos]", value="Shows queue", inline=True)
        embed.add_field(name="np", value="Shows now playing", inline=True)
        embed.add_field(name="dc", value="Disconnects the bot", inline=True)
        embed.add_field(name="join", value="Deprecated, use play", inline=True)
        embed.add_field(name="misc.", value="Commands for uncategorized stuff.", inline=False)
        embed.add_field(name="kyosmile", value="Most precious creature", inline=True)
        embed.add_field(name="help", value="Shows this message", inline=True)
        embed.add_field(name="test", value="<:kyoSmile:878070485592703036>", inline=True)
        embed.set_footer(
            text="To wake reschan, please click the link under 'About Me' section of reschan. But if you see this message, reschan is already awake.")
        return await ctx.send(embed=embed)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        if not hasattr(bot, 'lavalink'):  # This ensures the client isn't overwritten during cog reloads.
            bot.lavalink = lavalink.Client(self.bot.user.id)
            bot.lavalink.add_node('127.0.0.1', os.getenv('PORT', 8000), os.getenv('PASS', 'youshallnotpass'), 'us',
                                  'default-node')  # Host, Port, Password, Region, Name
            bot.add_listener(bot.lavalink.voice_update_handler, 'on_socket_response')

        lavalink.add_event_hook(self.track_hook)

    @tasks.loop(minutes=10)
    async def ping_heroku(self) -> None:
        requests.get('https://reschan-discbot.herokuapp.com/')

    @commands.command()
    async def ping(self, ctx):
        requests.get('https://reschan-discbot.herokuapp.com/')

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()

    async def cog_before_invoke(self, ctx):
        """ Command before-invoke handler. """
        guild_check = ctx.guild is not None

        if guild_check:
            await self.ensure_voice(ctx)

        return guild_check

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))

        should_connect = ctx.command.name in ('play', 'ping')

        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandInvokeError('You are not in a voice channel.')

        if not player.is_connected:
            if not should_connect:
                raise commands.CommandInvokeError('reschan is not connected.')

            permissions = ctx.author.voice.channel.permissions_for(ctx.me)

            if not permissions.connect or not permissions.speak:
                raise commands.CommandInvokeError(f'Permission missing: CONNECT and/or SPEAK')

            player.store('channel', ctx.channel.id)
            await ctx.guild.change_voice_state(channel=ctx.author.voice.channel)
        else:
            if int(player.channel_id) != ctx.author.voice.channel.id:
                raise commands.CommandInvokeError('You are not in reschan\'s voice channel.')

    async def track_hook(self, event):
        if isinstance(event, lavalink.events.QueueEndEvent):
            guild_id = int(event.player.guild_id)
            guild = self.bot.get_guild(guild_id)
            await guild.change_voice_state(channel=None)
            self.ping_heroku.stop()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel is None:
            player = self.bot.lavalink.player_manager.get(before.channel.guild.id)
            player.queue.clear()
            await player.stop()
            self.ping_heroku.stop()

    @commands.command(aliases=['p'])
    @commands.cooldown(1, 2)
    async def play(self, ctx, *, query: str):
        """ Searches and plays a song from a given query. """

        def check(author):
            def msg_check(message):
                return message.author == author and message.content in ['0', '1', '2', '3', '4', '5', '6', '7', '8',
                                                                        '9']

            return msg_check

        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        query = query.strip('<>')

        if not url_rx.match(query):
            query = f'ytsearch:{query}'

        # ex: {'playlistInfo': {}, 'loadType': 'TRACK_LOADED', 'tracks': [{'track': 'QAAAgAIAHVBTTzJOR1MgLS0gVkVSU1VTIFBldHRhcyBWZXJhAAlBbmRyZXcgUC4AAAAAAAVTSAALQXRwNXhUSlMzZ1UAAQAraHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1BdHA1eFRKUzNnVQAHeW91dHViZQAAAAAAAAAA', 'info': {'identifier': 'Atp5xTJS3gU', 'isSeekable': True, 'author': 'Andrew P.', 'length': 349000, 'isStream': False, 'position': 0, 'title': 'PSO2NGS -- VERSUS Pettas Vera', 'uri': 'https://www.youtube.com/watch?v=Atp5xTJS3gU'}}]}
        results = await player.node.get_tracks(query)

        if not results or not results['tracks']:
            raise commands.CommandInvokeError('Nothing found!')

        # embed = discord.Embed(color=discord.Color.blurple())
        embed = discord.Embed()
        embed.set_author(name="Added to queue:", icon_url=self.bot.user.avatar_url)
        embed.set_footer(text=f'Requested by {ctx.author}')

        # Valid loadTypes are:
        #   TRACK_LOADED    - single video/direct URL)
        #   PLAYLIST_LOADED - direct URL to playlist)
        #   SEARCH_RESULT   - query prefixed with either ytsearch: or scsearch:.
        #   NO_MATCHES      - query yielded no results
        #   LOAD_FAILED     - most likely, the video encountered an exception during loading.
        if results['loadType'] == 'PLAYLIST_LOADED':
            tracks = results['tracks']
            results['playlistInfo']['totalLength'] = 0

            for track in tracks:
                # Add all of the tracks from the playlist to the queue.
                results['playlistInfo']['totalLength'] += track['info']['length']
                track = lavalink.models.AudioTrack(track, ctx.author.id, uri=track['info']['uri'], duration=track['info']['length'])
                player.add(requester=ctx.author.id, track=track)

            embed.title = results["playlistInfo"]["name"]
            embed.url = parse_playlist_link(query)
            embed.add_field(name='Duration',
                            value=f"`{datetime.timedelta(milliseconds=results['playlistInfo']['totalLength'])}`")
            embed.add_field(name='Tracks', value=f"`{len(tracks)}`")

            # embed.description = f'{results["playlistInfo"]["name"]} - {len(tracks)} tracks'
        elif results['loadType'] == 'TRACK_LOADED':
            track = results['tracks'][0]
            embed.title = track['info']['title']
            embed.url = track['info']['uri']
            embed.add_field(name='Duration', value=f"`{datetime.timedelta(milliseconds=track['info']['length'])}`")
            embed.add_field(name='Uploader', value=f"`{track['info']['author']}`")

            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True, uri=track['info']['uri'], duration=track['info']['length'])
            player.add(requester=ctx.author.id, track=track)
        elif results['loadType'] == 'SEARCH_RESULT':
            print(results)

            searches = results['tracks'][:10]

            s_embed = discord.Embed(title=f'Search results:')
            s_embed.set_footer(text='Please select from 0-9 in 15 second.')
            for i in range(len(searches)):
                s_embed.add_field(name=f'{i}. {searches[i]["info"]["title"][:60]}...',
                                  value=f'Chn. Name: {searches[i]["info"]["author"]} || '
                                        f'Duration: {datetime.timedelta(milliseconds=searches[i]["info"]["length"])}',
                                  inline=False)
            s_embed = await ctx.send(embed=s_embed, delete_after=15)

            try:
                msg = await self.bot.wait_for("message", check=check, timeout=15)
            except asyncio.exceptions.TimeoutError:
                await ctx.send('ERROR: No selection', delete_after=5)
                return False

            track = searches[int(msg.content)]

            await msg.delete()
            await s_embed.delete()

            embed.title = track['info']['title']
            embed.url = track['info']['uri']
            embed.add_field(name='Duration', value=f"`{datetime.timedelta(milliseconds=track['info']['length'])}`")
            embed.add_field(name='Uploader', value=f"`{track['info']['author']}`")

            track = lavalink.models.AudioTrack(track, ctx.author.id, uri=track['info']['uri'], duration=track['info']['length'])
            player.add(requester=ctx.author.id, track=track)

        await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()
            self.ping_heroku.start()

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            raise commands.CommandInvokeError('reschan is not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            raise commands.CommandInvokeError('You are not in reschan\'s voice channel.')

        self.ping_heroku.stop()
        player.queue.clear()
        await player.stop()
        await ctx.guild.change_voice_state(channel=None)
        await ctx.send('Disconnected', delete_after=5)

    @commands.command()
    async def shuffle(self, ctx, opt: bool = None):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.shuffle = opt if opt is not None else not player.shuffle
        await ctx.send(f'Shuffle is set to {player.shuffle}', delete_after=10)

    @commands.command()
    async def repeat(self, ctx, opt: bool = None):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.repeat = opt if opt is not None else not player.repeat
        await ctx.send(f'Repeat is set to {player.repeat}', delete_after=10)

    @commands.command()
    async def pause(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        await player.set_pause(pause=True)
        await ctx.send('Paused')

    @commands.command()
    async def resume(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        await player.set_pause(pause=False)
        await ctx.send('Resumed')

    @commands.command()
    async def stop(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        player.queue.clear()
        await player.stop()
        await ctx.send('Stopped')

    @commands.command(aliases=['q'])
    async def queue(self, ctx, entry=0):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        embed = discord.Embed(title=f"{ctx.me.voice.channel}'s queue:", color=0x9a3eae)

        for i in range(entry, entry + 10):
            if player.current and i == 0:
                embed.add_field(name=f"Requested by **{self.bot.get_user(player.current.requester)}**",
                                value=f"Now playing: [{player.current.title}]({player.current.uri})",
                                inline=False)
            elif i < len(player.queue):
                embed.add_field(name=f"Requested by **{self.bot.get_user(player.queue[i].requester)}**",
                                value=f"**{i}.** [{player.queue[i].title}]({player.queue[i].uri})",
                                inline=False)
        return await ctx.send(embed=embed)

    @commands.command()
    async def skip(self, ctx, pos: int = 0):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        if pos == 0:
            await player.skip()
        else:
            return player.queue.pop(pos) if len(player.queue) + 1 > pos else await ctx.send('ERROR: No position found',
                                                                                            delete_after=5)

    @commands.command(name='np')
    async def now_playing(self, ctx):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        embed = discord.Embed()
        embed.set_author(name='Now playing:', icon_url=self.bot.user.avatar_url)
        embed.title = player.current.title
        embed.url = player.current.uri
        embed.description = f'`0:00:00|{np_bar(player.position, player.current.duration)}|' \
                            f'{str(datetime.timedelta(milliseconds=player.position)).split(".")[0]}/' \
                            f'{datetime.timedelta(milliseconds=player.current.duration)}`'
        embed.add_field(name='Repeat', value=f'`{player.repeat}`')
        embed.add_field(name='Shuffle', value=f'`{player.shuffle}`')

        await ctx.send(embed=embed)


if __name__ == '__main__':
    intents = discord.Intents.default()
    intents.members = True

    bot = MainBot(intents)
    signal.signal(signal.SIGTERM, lambda *_: bot.loop.create_task(bot.close()))
    bot.run(os.getenv('TOKEN'))
