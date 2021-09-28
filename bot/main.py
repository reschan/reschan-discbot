# bot.py
"""
TODO: Error handlers, maybe improve else.
"""
from discord.ext import commands, tasks
import discord
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from threading import Thread
import asyncio
import youtube_dl
from dotenv import load_dotenv
import signal
import os
from youtube_search import YoutubeSearch

load_dotenv()

ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'  # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='res ', help_command=None, intents=intents)

handler = SimpleHTTPRequestHandler

signal.signal(signal.SIGTERM, lambda *_: bot.loop.create_task(bot.close()))


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.event
async def on_message(ctx):
    if ctx.author.id == bot.user.id:
        return None
    if isinstance(ctx.channel, discord.DMChannel):
        return None
    await bot.process_commands(ctx)


@bot.command(name='help')
async def help_cmd(ctx):
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
    embed.set_footer(text="To wake reschan, please click the link under 'About Me' section of reschan. But if you see this message, reschan is already awake.")
    return await ctx.send(embed=embed)


@bot.command()
async def kyosmile(ctx):
    return await ctx.send('<:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036><:kyoSmile:878070485592703036><:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036>⬛<:kyoSmile:878070485592703036>\n<:kyoSmile:878070485592703036>⬛<:kyoSmile:878070485592703036>')


@bot.command(name='test')
async def dumbstuff(ctx, *args):
    for i in range(len(args)):
        await ctx.send(args[i])
    print(ctx.message)
    return await ctx.send('probably alive')


def parse_playlist_link(url):
    """Extract a youtube playlist link from a video-in-a-playlist link"""
    # url =  https://www.youtube.com/watch?v=Atp5xTJS3gU&list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    # res =  https://www.youtube.com/playlist?list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    res = url[:url.find('watch?v=')] + 'playlist?' + url[url.find('&list=') + 1:]
    return res


async def get_videoinfo(url, author):
    """
    Extract video information for queues

    res = [{vid0},{vid1}]
    """
    res = []
    if '&list=' in url and 'watch?v=' in url:
        url = parse_playlist_link(url)
    if 'list=' not in url and 'watch?v=' not in url:
        url = YoutubeSearch(url, max_results=1).to_dict()[0]['id']

    data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    if 'entries' in data:
        for i in range(len(data['entries'])):
            res.append({})
            res[i]['url'] = data['entries'][i].get('webpage_url')
            res[i]['title'] = data['entries'][i].get('title')
            res[i]['thumbnail'] = data['entries'][i].get('thumbnail')
            res[i]['author'] = author
        playlist_info = {'url': data.get('webpage_url'),
                         'thumbnail': data['entries'][0].get('thumbnail'),
                         'title': data.get('title'),
                         'author': author}
        return res, playlist_info
    else:
        res.append({})
        res[0]['url'] = data.get('webpage_url')
        res[0]['title'] = data.get('title')
        res[0]['thumbnail'] = data.get('thumbnail')
        res[0]['author'] = author
    return res, None


def status_user_join():
    """Command checks for user vc join status"""
    async def predicate(ctx):
        if not ctx.author.voice:
            await ctx.send('ERROR: You are not in a Voice Channel!', delete_after=5)
            return False
        return True
    return commands.check(predicate)


def status_bot_join():
    """Command checks for bot vc join status"""
    async def predicate(ctx):
        if not ctx.voice_client:
            await ctx.send('ERROR: Not in a Voice Channel!', delete_after=5)
            return False
        return True
    return commands.check(predicate)


class MusicPlayer(commands.Cog):
    """Main class for music cog."""

    def __init__(self, botuser):
        self.bot = botuser
        self.queue = []
        self.is_vc = False

        self.play_lock = asyncio.Lock()
        self.queue_lock = asyncio.Lock()
        self.sleep_lock = asyncio.Lock()

    def nowplaying_embed(self, video):
        embed = discord.Embed(title=video['title'],
                              url=video['url'])
        embed.set_author(name="Now playing:", icon_url=self.bot.user.avatar_url)
        embed.set_thumbnail(url=video['thumbnail'])
        embed.set_footer(text=f'Requested by {video["author"]}')
        return embed

    @tasks.loop(seconds=5)
    async def playqueue(self, ctx):
        if not ctx.voice_client:
            self.playqueue.cancel()
        elif ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            return True
        elif not self.queue:
            return await self.leave(ctx)
        else:
            ctx.voice_client.stop()
            player = await self.YTDLSource.from_url(self.queue[0]['url'], loop=self.bot.loop, stream=True)
            await ctx.send(embed=self.nowplaying_embed(self.queue[0]))
            ctx.voice_client.play(player, after=lambda d: self.queue.pop(0) if self.queue else None)

    @commands.command()
    async def join(self, ctx):
        if ctx.voice_client:
            ctx.voice_client.stop()
        channel = ctx.author.voice.channel
        self.is_vc = True
        print(f'Successfully connected to: {ctx.author.voice.channel}')
        return await channel.connect()

    @commands.command(name='dc')
    @status_user_join()
    @status_bot_join()
    async def leave(self, ctx):
        self.is_vc = False
        self.queue = []
        return await ctx.voice_client.disconnect()

    @commands.command()
    @commands.cooldown(1, 2)
    @status_user_join()
    async def play(self, ctx, url):
        def play_embed():
            embed = discord.Embed(title=pl_info['title'] if pl_info else video_info[0]['title'],
                                  url=pl_info['url'] if pl_info else video_info[0]['url'])
            embed.set_author(name="Added URL to queue!", icon_url=self.bot.user.avatar_url)
            embed.set_footer(text=f"Requested by {pl_info['author'] if pl_info else video_info[0]['author']}")
            embed.set_thumbnail(url=pl_info['thumbnail'] if pl_info else video_info[0]['thumbnail'])
            return embed

        video_info, pl_info = await get_videoinfo(url, ctx.message.author)
        self.queue = [*self.queue, *video_info]
        await ctx.send(embed=play_embed())

        async with self.play_lock:
            if not self.is_vc:
                await self.join(ctx)
            if not ctx.voice_client.is_playing():
                self.playqueue.start(ctx) if not self.playqueue.is_running() else None
        return True

    @commands.command()
    @status_user_join()
    async def search(self, ctx, *terms):
        if not terms:
            return await ctx.send('ERROR: No search terms provided.', delete_after=5)

        def search_embed(search_res):
            embed = discord.Embed(title=f'Search results:')
            embed.set_author(name='YouTube search', icon_url=self.bot.user.avatar_url)
            embed.set_footer(text='Please select from 0-9 in 15 second.')
            for i in range(len(search_res)):
                embed.add_field(name=f'{i}. {search_res[i]["title"][:60]}...',
                                value=f'Chn. Name: {search_res[i]["channel"]} || Duration: {search_res[i]["duration"]}',
                                inline=False)
            return embed

        def check(author):
            def msg_check(message):
                return message.author == author and message.content in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
            return msg_check

        query = ' '.join(terms)
        res = YoutubeSearch(query, max_results=10).to_dict()
        search_msg = await ctx.send(embed=search_embed(res), delete_after=15)

        try:
            msg = await self.bot.wait_for("message", check=check(ctx.author), timeout=15)
            await self.play(ctx=ctx, url=res[int(msg.content)]['id'])
            await msg.delete()
            await search_msg.delete()
        except asyncio.exceptions.TimeoutError:
            await ctx.send('ERROR: No selection', delete_after=5)
            return False

    @commands.command()
    @status_user_join()
    @status_bot_join()
    async def pause(self, ctx):
        await ctx.send('Paused')
        return ctx.voice_client.pause()

    @commands.command()
    @status_user_join()
    @status_bot_join()
    async def resume(self, ctx):
        await ctx.send('Resumed')
        return ctx.voice_client.resume()

    @commands.command()
    @status_user_join()
    @status_bot_join()
    async def stop(self, ctx):
        await ctx.send('Queue cleared and stopped')
        self.queue = []
        return ctx.voice_client.stop()

    @commands.command()
    @status_user_join()
    @status_bot_join()
    async def skip(self, ctx, pos=0):
        if pos == 0:
            return ctx.voice_client.stop()
        else:
            if self.queue[pos]:
                await ctx.send('pass')
            return self.queue.pop(pos) if self.queue[pos] else await ctx.send('ERROR: No position found', delete_after=5)

    @commands.command()
    @status_user_join()
    @status_bot_join()
    async def queue(self, ctx, entry=0):
        embed = discord.Embed(title=f"{ctx.voice_client.channel}'s queue:", color=0x9a3eae)
        for i in range(entry, entry + 10):
            if i < len(self.queue):
                embed.add_field(name=f"Requested by **{self.queue[i]['author']}**", value=f"{'**Now playing:**' if i == 0 else f'**{i}.**'} [{self.queue[i]['title']}]({self.queue[i]['url']})", inline=False)
        return await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel is None and self.is_vc:
            return await self.leave(before.channel.guild)

    @commands.command(aliases=['np'])
    async def isplaying(self, ctx):
        await ctx.send(embed=self.nowplaying_embed(self.queue[0]))

    class YTDLSource(discord.PCMVolumeTransformer):
        def __init__(self, source, *, data, volume=0.5):
            super().__init__(source, volume)

            self.data = data

            self.title = data.get('title')
            self.url = data.get('url')

        @classmethod
        async def from_url(cls, url, *, loop=None, stream=False):
            loop = loop or asyncio.get_event_loop()
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

            if 'entries' in data:
                # take first item from a playlist
                data = data['entries'][0]

            filename = data['url'] if stream else ytdl.prepare_filename(data)
            return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


def start_server(port: int):
    print(f"Starting on port {port}")
    server = ThreadingHTTPServer(('', port), handler)
    serve_thread = Thread(group=None, target=server.serve_forever)
    serve_thread.start()


if __name__ == '__main__':
    start_server(int(os.getenv('PORT', 8000)))
    bot.add_cog(MusicPlayer(bot))
    bot.run(os.getenv('TOKEN'))
