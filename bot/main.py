from discord.ext import commands
import discord
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
import asyncio
from dotenv import load_dotenv
import signal
import os
import lavalink
import re
import datetime

load_dotenv()

handler = SimpleHTTPRequestHandler

url_rx = re.compile(r'https?://(?:www\.)?.+')


def parse_playlist_link(url):
    """Extract a youtube playlist link from a video-in-a-playlist link"""
    # url =  https://www.youtube.com/watch?v=Atp5xTJS3gU&list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    # res =  https://www.youtube.com/playlist?list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    if 'watch?v=' not in url:
        return url
    return url[:url.find('watch?v=')] + 'playlist?' + url[url.find('&list=') + 1:]


class MainBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='res ', help_command=None)
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

    def cog_unload(self):
        """ Cog unload handler. This removes any event hooks that were registered. """
        self.bot.lavalink._event_hooks.clear()

    async def cog_before_invoke(self, ctx):
        """ Command before-invoke handler. """
        guild_check = ctx.guild is not None

        if guild_check:
            await self.ensure_voice(ctx)

        return guild_check

    async def cog_command_error(self, ctx, error):

        if isinstance(error, commands.CommandInvokeError):
            await ctx.send(error.original, delete_after=5)

    async def ensure_voice(self, ctx):
        """ This check ensures that the bot and command author are in the same voicechannel. """
        player = self.bot.lavalink.player_manager.create(ctx.guild.id, endpoint=str(ctx.guild.region))

        should_connect = ctx.command.name in ('play',)

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

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel is None:
            player = self.bot.lavalink.player_manager.get(before.channel.guild.id)
            player.queue.clear()
            await player.stop()

    @commands.command(aliases=['p'])
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
        embed.set_author(name="Now playing:", icon_url=self.bot.user.avatar_url)
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
                track = lavalink.models.AudioTrack(track, ctx.author.id, uri=track['info']['uri'])
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

            track = lavalink.models.AudioTrack(track, ctx.author.id, recommended=True, uri=track['info']['uri'])
            player.add(requester=ctx.author.id, track=track)
        elif results['loadType'] == 'SEARCH_RESULT':
            # {'playlistInfo': {}, 'loadType': 'SEARCH_RESULT', 'tracks': [{'track': 'QAAApQIAPlRoZSBPZmZzcHJpbmcgLSBUaGUgS2lkcyBBcmVuJ3QgQWxyaWdodCAoT2ZmaWNpYWwgTXVzaWMgVmlkZW8pAA1UaGUgT2Zmc3ByaW5nAAAAAAACvyAACzdpTmJuaW5lVUNJAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9N2lOYm5pbmVVQ0kAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': '7iNbnineUCI', 'isSeekable': True, 'author': 'The Offspring', 'length': 180000, 'isStream': False, 'position': 0, 'title': "The Offspring - The Kids Aren't Alright (Official Music Video)", 'uri': 'https://www.youtube.com/watch?v=7iNbnineUCI'}}, {'track': 'QAAAnQIAMERpYW5hIGFuZCB0aGUgQ29sbGVjdGlvbiBvZiBOZXcgU3RvcmllcyBmb3IgS2lkcwAT4py/IEtpZHMgRGlhbmEgU2hvdwAAAAAADpZgAAt1eXlYcEZPNHlRMAABACtodHRwczovL3d3dy55b3V0dWJlLmNvbS93YXRjaD92PXV5eVhwRk80eVEwAAd5b3V0dWJlAAAAAAAAAAA=', 'info': {'identifier': 'uyyXpFO4yQ0', 'isSeekable': True, 'author': '✿ Kids Diana Show', 'length': 956000, 'isStream': False, 'position': 0, 'title': 'Diana and the Collection of New Stories for Kids', 'uri': 'https://www.youtube.com/watch?v=uyyXpFO4yQ0'}}, {'track': 'QAAAwQIAV0dvb2QgbW9ybmluZytNb3JlIEtpZHMgRGlhbG9ndWVzIHwgTGVhcm4gRW5nbGlzaCBmb3IgS2lkcyB8IENvbGxlY3Rpb24gb2YgRWFzeSBEaWFsb2d1ZQAQRW5nbGlzaCBTaW5nc2luZwAAAAAAIofYAAs4aXJTRnZveUxIUQABACtodHRwczovL3d3dy55b3V0dWJlLmNvbS93YXRjaD92PThpclNGdm95TEhRAAd5b3V0dWJlAAAAAAAAAAA=', 'info': {'identifier': '8irSFvoyLHQ', 'isSeekable': True, 'author': 'English Singsing', 'length': 2263000, 'isStream': False, 'position': 0, 'title': 'Good morning+More Kids Dialogues | Learn English for Kids | Collection of Easy Dialogue', 'uri': 'https://www.youtube.com/watch?v=8irSFvoyLHQ'}}, {'track': 'QAAAyQIAX0tpZHMgdm9jYWJ1bGFyeSAtIEJvZHkgLSBwYXJ0cyBvZiB0aGUgYm9keSAtIExlYXJuIEVuZ2xpc2ggZm9yIGtpZHMgLSBFbmdsaXNoIGVkdWNhdGlvbmFsIHZpZGVvABBFbmdsaXNoIFNpbmdzaW5nAAAAAAADZxgAC1NVdDhxMEVLYm1zAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9U1V0OHEwRUtibXMAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'SUt8q0EKbms', 'isSeekable': True, 'author': 'English Singsing', 'length': 223000, 'isStream': False, 'position': 0, 'title': 'Kids vocabulary - Body - parts of the body - Learn English for kids - English educational video', 'uri': 'https://www.youtube.com/watch?v=SUt8q0EKbms'}}, {'track': 'QAAArAIAS1RvbSAmIEplcnJ5IHwgSG93IHRvIENhdC1jaCBhIE1vdXNlIHwgQ2xhc3NpYyBDYXJ0b29uIENvbXBpbGF0aW9uIHwgV0IgS2lkcwAHV0IgS2lkcwAAAAAAEXioAAtfOEFfc3dHQ1NuSQABACtodHRwczovL3d3dy55b3V0dWJlLmNvbS93YXRjaD92PV84QV9zd0dDU25JAAd5b3V0dWJlAAAAAAAAAAA=', 'info': {'identifier': '_8A_swGCSnI', 'isSeekable': True, 'author': 'WB Kids', 'length': 1145000, 'isStream': False, 'position': 0, 'title': 'Tom & Jerry | How to Cat-ch a Mouse | Classic Cartoon Compilation | WB Kids', 'uri': 'https://www.youtube.com/watch?v=_8A_swGCSnI'}}, {'track': 'QAAAxgIASkhlbGxvIFNvbmcgfCBIZWxsbyBIZWxsbyBIb3cgQXJlIFlvdSB8IEhlbGxvIFNvbmcgZm9yIEtpZHMgfCBUaGUgS2lib29tZXJzACJUaGUgS2lib29tZXJzIC0gS2lkcyBNdXNpYyBDaGFubmVsAAAAAAABgrgAC3gyM3JURGw0QU1zAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9eDIzclREbDRBTXMAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'x23rTDl4AMs', 'isSeekable': True, 'author': 'The Kiboomers - Kids Music Channel', 'length': 99000, 'isStream': False, 'position': 0, 'title': 'Hello Song | Hello Hello How Are You | Hello Song for Kids | The Kiboomers', 'uri': 'https://www.youtube.com/watch?v=x23rTDl4AMs'}}, {'track': 'QAAAmgIAN2JsaW5rLTE4MiAtIFN0YXkgVG9nZXRoZXIgRm9yIFRoZSBLaWRzIChPZmZpY2lhbCBWaWRlbykACWJsaW5rLTE4MgAAAAAAA6GwAAtrMUJGSFl0WmxBVQABACtodHRwczovL3d3dy55b3V0dWJlLmNvbS93YXRjaD92PWsxQkZIWXRabEFVAAd5b3V0dWJlAAAAAAAAAAA=', 'info': {'identifier': 'k1BFHYtZlAU', 'isSeekable': True, 'author': 'blink-182', 'length': 238000, 'isStream': False, 'position': 0, 'title': 'blink-182 - Stay Together For The Kids (Official Video)', 'uri': 'https://www.youtube.com/watch?v=k1BFHYtZlAU'}}, {'track': 'QAAAsQIAPUljZSBDcmVhbSBTb25nICsgTW9yZSBOdXJzZXJ5IFJoeW1lcyAmIEtpZHMgU29uZ3MgLSBDb0NvbWVsb24AGkNvY29tZWxvbiAtIE51cnNlcnkgUmh5bWVzAAAAAAAiykAAC1hjZWJaV3loZlFBAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9WGNlYlpXeWhmUUEAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'XcebZWyhfQA', 'isSeekable': True, 'author': 'Cocomelon - Nursery Rhymes', 'length': 2280000, 'isStream': False, 'position': 0, 'title': 'Ice Cream Song + More Nursery Rhymes & Kids Songs - CoComelon', 'uri': 'https://www.youtube.com/watch?v=XcebZWyhfQA'}}, {'track': 'QAAAlwIAMlRPTkVTIEFORCBJIC0gVEhFIEtJRFMgQVJFIENPTUlORyAoT0ZGSUNJQUwgVklERU8pAAtUb25lcyBBbmQgSQAAAAAAAxzgAAtidVdBX3hzVF9JcwABACtodHRwczovL3d3dy55b3V0dWJlLmNvbS93YXRjaD92PWJ1V0FfeHNUX0lzAAd5b3V0dWJlAAAAAAAAAAA=', 'info': {'identifier': 'buWA_xsT_Is', 'isSeekable': True, 'author': 'Tones And I', 'length': 204000, 'isStream': False, 'position': 0, 'title': 'TONES AND I - THE KIDS ARE COMING (OFFICIAL VIDEO)', 'uri': 'https://www.youtube.com/watch?v=buWA_xsT_Is'}}, {'track': 'QAAAjgIAJVN1cmYgKyBUcmFpbCBhbmQgTGFtYXcgd2l0aCB0aGUga2lkcyEAD0hhcHB5IElzbGFuZGVycwAAAAAAE10IAAt3Q1lHeWRWSWp6UQABACtodHRwczovL3d3dy55b3V0dWJlLmNvbS93YXRjaD92PXdDWUd5ZFZJanpRAAd5b3V0dWJlAAAAAAAAAAA=', 'info': {'identifier': 'wCYGydVIjzQ', 'isSeekable': True, 'author': 'Happy Islanders', 'length': 1269000, 'isStream': False, 'position': 0, 'title': 'Surf + Trail and Lamaw with the kids!', 'uri': 'https://www.youtube.com/watch?v=wCYGydVIjzQ'}}, {'track': 'QAAAiQIAIkNoaWxkIFZsYWQgcGxheSBUb3kgQ2FmZSBvbiBXaGVlbHMADVZsYWQgYW5kIE5pa2kAAAAAAAmkwAALT1EtWFNyY28za3MAAQAraHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1PUS1YU3JjbzNrcwAHeW91dHViZQAAAAAAAAAA', 'info': {'identifier': 'OQ-XSrco3ks', 'isSeekable': True, 'author': 'Vlad and Niki', 'length': 632000, 'isStream': False, 'position': 0, 'title': 'Child Vlad play Toy Cafe on Wheels', 'uri': 'https://www.youtube.com/watch?v=OQ-XSrco3ks'}}, {'track': 'QAAAwgIASFRoZSBMaW9uIGFuZCB0aGUgTW91c2UgfCBCZWR0aW1lIFN0b3JpZXMgZm9yIEtpZHMgaW4gRW5nbGlzaCB8IFN0b3J5dGltZQAgRmFpcnkgVGFsZXMgYW5kIFN0b3JpZXMgZm9yIEtpZHMAAAAAAA2UkAALMjNfbUVTYXdFRWMAAQAraHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj0yM19tRVNhd0VFYwAHeW91dHViZQAAAAAAAAAA', 'info': {'identifier': '23_mESawEEc', 'isSeekable': True, 'author': 'Fairy Tales and Stories for Kids', 'length': 890000, 'isStream': False, 'position': 0, 'title': 'The Lion and the Mouse | Bedtime Stories for Kids in English | Storytime', 'uri': 'https://www.youtube.com/watch?v=23_mESawEEc'}}, {'track': 'QAAAwwIAWVNwZWFraW5nIENhcnRvb24gfCA0NSBtaW51dGVzIEtpZHMgRGlhbG9ndWVzIHwgRWFzeSBjb252ZXJzYXRpb24gfCBMZWFybiBFbmdsaXNoIGZvciBLaWRzABBFbmdsaXNoIFNpbmdzaW5nAAAAAAAnadgAC0ZkbExzeFI1QUUwAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9RmRsTHN4UjVBRTAAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'FdlLsxR5AE0', 'isSeekable': True, 'author': 'English Singsing', 'length': 2583000, 'isStream': False, 'position': 0, 'title': 'Speaking Cartoon | 45 minutes Kids Dialogues | Easy conversation | Learn English for Kids', 'uri': 'https://www.youtube.com/watch?v=FdlLsxR5AE0'}}, {'track': 'QAAAswIATkhvdyB0byB0ZWFjaCBLaWRzICB8IGZyb20gYSBQcmFndWUga2luZGVyZ2FydGVuLCBwYXJ0IDEgfCBFbmdsaXNoIGZvciBDaGlsZHJlbgALV09XIEVOR0xJU0gAAAAAABI0KAALTklrMS1jazRjNlEAAQAraHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1OSWsxLWNrNGM2UQAHeW91dHViZQAAAAAAAAAA', 'info': {'identifier': 'NIk1-ck4c6Q', 'isSeekable': True, 'author': 'WOW ENGLISH', 'length': 1193000, 'isStream': False, 'position': 0, 'title': 'How to teach Kids  | from a Prague kindergarten, part 1 | English for Children', 'uri': 'https://www.youtube.com/watch?v=NIk1-ck4c6Q'}}, {'track': 'QAAAqAIAQ1NoYW5nIENoaSBhbmQgU3BpZGVybWFuIFRlYW0gVXAgQWdhaW5zdCBWZW5vbSEgIFN1cGVyaGVybyBTaG93ZG93biEAC0tpZHMgRnVuIFRWAAAAAAAIEmgAC3lBQWY3MXNjZlNrAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9eUFBZjcxc2NmU2sAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'yAAf71scfSk', 'isSeekable': True, 'author': 'Kids Fun TV', 'length': 529000, 'isStream': False, 'position': 0, 'title': 'Shang Chi and Spiderman Team Up Against Venom!  Superhero Showdown!', 'uri': 'https://www.youtube.com/watch?v=yAAf71scfSk'}}, {'track': 'QAAAlgIAMFRvcCAxMCBLaWRzIFNpbmdpbmcgRElTTkVZIFNvbmdzIG9uIFRhbGVudCBTaG93cwAMVGFsZW50IFJlY2FwAAAAAAAct5AAC0lLbnJ1RTRGcHVFAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9SUtucnVFNEZwdUUAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'IKnruE4FpuE', 'isSeekable': True, 'author': 'Talent Recap', 'length': 1882000, 'isStream': False, 'position': 0, 'title': 'Top 10 Kids Singing DISNEY Songs on Talent Shows', 'uri': 'https://www.youtube.com/watch?v=IKnruE4FpuE'}}, {'track': 'QAAAvQIAP0JsaXBwaSBUb3VycyBhIENoaWxkcmVuJ3MgTXVzZXVtIHwgTGVhcm5pbmcgVmlkZW9zIGZvciBUb2RkbGVycwAkQmxpcHBpIC0gRWR1Y2F0aW9uYWwgVmlkZW9zIGZvciBLaWRzAAAAAAAliWAAC002WEFIRmxMdEZrAAEAK2h0dHBzOi8vd3d3LnlvdXR1YmUuY29tL3dhdGNoP3Y9TTZYQUhGbEx0RmsAB3lvdXR1YmUAAAAAAAAAAA==', 'info': {'identifier': 'M6XAHFlLtFk', 'isSeekable': True, 'author': 'Blippi - Educational Videos for Kids', 'length': 2460000, 'isStream': False, 'position': 0, 'title': "Blippi Tours a Children's Museum | Learning Videos for Toddlers", 'uri': 'https://www.youtube.com/watch?v=M6XAHFlLtFk'}}, {'track': 'QAAA1wIAWUJsaXBwaSBNYWtlcyBGcnVpdCBQaXp6YSEgfCBMZWFybiBTaWduIExhbmd1YWdlIFdpdGggQmxpcHBpIHwgRWR1Y2F0aW9uYWwgVmlkZW9zIEZvciBLaWRzACRCbGlwcGkgLSBFZHVjYXRpb25hbCBWaWRlb3MgZm9yIEtpZHMAAAAAAAoxYAALanVTVHg2elMwQ2sAAQAraHR0cHM6Ly93d3cueW91dHViZS5jb20vd2F0Y2g/dj1qdVNUeDZ6UzBDawAHeW91dHViZQAAAAAAAAAA', 'info': {'identifier': 'juSTx6zS0Ck', 'isSeekable': True, 'author': 'Blippi - Educational Videos for Kids', 'length': 668000, 'isStream': False, 'position': 0, 'title': 'Blippi Makes Fruit Pizza! | Learn Sign Language With Blippi | Educational Videos For Kids', 'uri': 'https://www.youtube.com/watch?v=juSTx6zS0Ck'}}]}
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

            track = lavalink.models.AudioTrack(track, ctx.author.id, uri=track['info']['uri'])
            player.add(requester=ctx.author.id, track=track)

        await ctx.send(embed=embed)

        if not player.is_playing:
            await player.play()
            player.loop = False
            player.shuffle = False

    @commands.command(aliases=['dc'])
    async def disconnect(self, ctx):
        """ Disconnects the player from the voice channel and clears its queue. """
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        if not player.is_connected:
            raise commands.CommandInvokeError('reschan is not connected.')

        if not ctx.author.voice or (player.is_connected and ctx.author.voice.channel.id != int(player.channel_id)):
            raise commands.CommandInvokeError('You are not in reschan\'s voice channel.')

        player.queue.clear()
        await player.stop()
        await ctx.guild.change_voice_state(channel=None)
        await ctx.send('Disconnected', delete_after=5)

    @commands.command()
    async def shuffle(self, ctx, opt: bool = None):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.shuffle = opt if opt is not None else not player.shuffle
        await ctx.send(f'Shuffle is set to {opt}', delete_after=10)

    @commands.command()
    async def loop(self, ctx, opt: bool = None):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)

        player.loop = opt if opt is not None else not player.loop
        await ctx.send(f'Loop is set to {player.loop}', delete_after=10)

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

    @commands.command()
    async def queue(self, ctx, entry=0):
        player = self.bot.lavalink.player_manager.get(ctx.guild.id)
        embed = discord.Embed(title=f"{ctx.me.voice.channel}'s queue:", color=0x9a3eae)

        for i in range(entry, entry + 10):
            if i < len(player.queue):
                embed.add_field(name=f"Requested by **{self.bot.get_user(player.queue[i].requester)}**",
                                value=f"{'**Now playing:**' if i == 0 else f'**{i}.**'} "
                                      f"[{player.current.title if i == 0 else player.queue[i].title}]"
                                      f"({player.current.uri if i == 0 else player.queue[i].uri})",
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


if __name__ == '__main__':
    bot = MainBot()
    signal.signal(signal.SIGTERM, lambda *_: bot.loop.create_task(bot.close()))
    bot.run(os.getenv('TOKEN'))
