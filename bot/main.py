# bot.py
from discord.ext import commands, tasks
import discord
import asyncio
import youtube_dl
from dotenv import load_dotenv
import os

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
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

bot = commands.Bot(command_prefix='res ', help_command=None)


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.event
async def on_message(ctx):
    if ctx.author.id == bot.user.id:
        return None
    await bot.process_commands(ctx)


@bot.command(name='test')
async def dumbstuff(ctx, m):
    for i in range(50):
        await ctx.send(m)
    print(ctx.message.content)


def parse_playlist_link(url):
    # url =  https://www.youtube.com/watch?v=Atp5xTJS3gU&list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    # res =  https://www.youtube.com/playlist?list=PLp4K2TWhRg0ANsGA7ENtr2ZjO2gvvXMJM&index=13
    res = url[:url.find('watch?v=')] + 'playlist?' + url[url.find('&list=') + 1:]
    return res


async def get_videoinfo(url, author):
    res = []
    if '&list=' in url and 'watch?v=' in url:
        url = parse_playlist_link(url)

    data = await bot.loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=False))
    if 'entries' in data:
        for i in range(len(data['entries'])):
            res.append({})
            res[i]['url'] = data['entries'][i].get('webpage_url')
            res[i]['title'] = data['entries'][i].get('title')
            res[i]['author'] = author
            pass
    else:
        res.append({})
        res[0]['url'] = url
        res[0]['title'] = data.get('title')
        res[0]['author'] = author
    return res


def vc_status():
    async def predicate(ctx):
        if not ctx.voice_client:
            await ctx.send('ERROR: Not in a Voice Channel!')
            return False
        if not ctx.author.voice:
            await ctx.send('ERROR: You are not in a Voice Channel!')
        return ctx.voice_client and ctx.author.voice
    return commands.check(predicate)


class MusicPlayer(commands.Cog):
    def __init__(self, botuser):
        self.bot = botuser
        self.queue = []
        self.is_vc = False

        self.play_lock = asyncio.Lock()
        self.queue_lock = asyncio.Lock()

    async def playqueue(self, ctx):
        async with self.queue_lock:
            while self.is_vc and self.queue:
                if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
                    await asyncio.sleep(1)
                    continue
                ctx.voice_client.stop()
                player = await self.YTDLSource.from_url(self.queue[0]['url'], loop=self.bot.loop, stream=True)
                await ctx.send(f'Playing: {player.title}')
                ctx.voice_client.play(player, after=lambda d: self.queue.pop(0))
            return True

    @commands.command()
    async def join(self, ctx):
        self.queue = []
        if ctx.voice_client:
            ctx.voice_client.stop()
        if not ctx.author.voice:
            await ctx.send('ERROR: The user is not connected to a Voice Channel.')
            print('author vc not found')
            return False
        channel = ctx.author.voice.channel
        self.is_vc = True
        await ctx.send(f'Successfully connected to: {ctx.author.voice.channel}')
        await channel.connect()
        return True

    @commands.command(name='dc')
    @vc_status()
    async def leave(self, ctx):
        self.is_vc = False
        self.queue = []
        return await ctx.voice_client.disconnect()

    @commands.command()
    async def play(self, ctx, url):
        async with self.play_lock:
            if not self.is_vc:
                await self.join(ctx)
            self.queue = [*self.queue, *await get_videoinfo(url, ctx.message.author)]
            await ctx.send('Added url to queue!')
        if not ctx.voice_client.is_playing():
            return await self.playqueue(ctx)
        return True

    @commands.command()
    @vc_status()
    async def pause(self, ctx):
        await ctx.send('Paused')
        return ctx.voice_client.pause()

    @commands.command()
    @vc_status()
    async def resume(self, ctx):
        await ctx.send('Resumed')
        return ctx.voice_client.resume()

    @commands.command()
    @vc_status()
    async def stop(self, ctx):
        await ctx.send('Queue cleared and stopped')
        self.queue = []
        return ctx.voice_client.stop()

    @commands.command()
    @vc_status()
    async def skip(self, ctx):
        await ctx.send('Skipped')
        return ctx.voice_client.stop()

    @commands.command()
    @vc_status()
    async def queue(self, ctx, entry=0):
        embed = discord.Embed(title=f"{ctx.voice_client.channel}'s queue:", color=0x9a3eae)
        for i in range(entry, entry + 10):
            if i < len(self.queue):
                embed.add_field(name=f"Requested by {self.queue[i]['author']}", value=f"{'Now playing:' if i == 0 else f'{i}.'} [{self.queue[i]['title']}]({self.queue[i]['url']})", inline=False)
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None:
            voice = after.channel.guild.voice_client
            time = 0
            while True:
                await asyncio.sleep(1)
                time = time + 1
                if voice.is_playing() and not voice.is_paused():
                    time = 0
                if time == 180:
                    await voice.disconnect()
                if not voice.is_connected():
                    break

    @commands.command()
    @vc_status()
    async def isplaying(self, ctx):
        await ctx.send(ctx.voice_client.is_playing())
        await ctx.send(self.queue)

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


bot.add_cog(MusicPlayer(bot))
bot.run(os.getenv('TOKEN'))
