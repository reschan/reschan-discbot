# bot.py
from discord.ext import commands, tasks
import discord
import asyncio
import youtube_dl
from dotenv import load_dotenv
import os

load_dotenv()

ffmpeg_options = {
    'options': '-vn'
}

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

bot = commands.Bot(command_prefix='res ')


@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')


@bot.command(name='test')
async def dumbstuff(ctx, *args):
    for i in args:
        await ctx.send(i)
    print(ctx.message.content)


"""
        @self.bot.command(name='timer')
        async def test(ctx, t):
            timerins = Timer(tx, int(t))
            timerins.remindchest.start()

        @self.bot.command(name='gamble')
        async def gambler(ctx, minroll=0, maxroll=100):
            return await ctx.send(f"You've rolled {random.randint(minroll, maxroll)}!")

        


class Timer:
    def __init__(self, ctx, minute, note=None):
        self.minute = minute
        self.ctx = ctx
        self.note = note

    @tasks.loop(minutes=1)
    async def remindchest(self):
        self.minute -= 1
        if self.minute == 0:
            self.remindchest.stop()
        print(f'remaining {self.minute}')

    @remindchest.before_loop
    async def before_timer(self):
        await self.ctx.send(f'I will remind you in {self.minute} minute(s), master!')

    @remindchest.after_loop
    async def after_timer(self):
        await self.ctx.send(f'Timer ended, master {self.ctx.author.mention}!')
        if self.note is not None:
            await self.ctx.send(f'Timer note: {self.note}')
"""


# class HelloWorld(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot

#     @commands.command()
#     async def hello(self, ctx):
#         await ctx.send(f'Hello, {ctx.author.mention}')


class MusicPlayer(commands.Cog):
    def __init__(self, botuser):
        self.bot = botuser
        self.queue = []
        self.is_vc = False

    def vc_status():
        async def predicate(ctx):
            if not ctx.voice_client:
                await ctx.send('ERROR: Not in a Voice Channel!')
                return False
            return ctx.voice_client
        return commands.check(predicate)

    async def playqueue(self, ctx):
        while not ctx.voice_client.is_playing() and self.queue:
            if ctx.voice_client.is_playing():
                await asyncio.sleep(1)
                continue
            ctx.voice_client.stop()
            player = await self.YTDLSource.from_url(self.queue[0], loop=self.bot.loop, stream=True)
            await ctx.send(f'Playing: {player.title}')
            ctx.voice_client.play(player, after=lambda d: self.queue.pop(0))
            print('loaded')

    @commands.command()
    async def join(self, ctx):
        if not ctx.author.voice:
            await ctx.send('ERROR: The user is not connected to a Voice Channel.')
            print('author vc not found')
            return None
        channel = ctx.author.voice.channel
        await channel.connect()
        self.is_vc = True
        await ctx.send(f'Successfully connected to: {ctx.author.voice.channel}')

    @commands.command(name='dc')
    @vc_status()
    async def leave(self, ctx):
        self.is_vc = False
        await ctx.voice_client.disconnect()

    @commands.command()
    @vc_status()
    async def play(self, ctx, url):
        self.queue.append(url)
        await ctx.send('Added url to queue!')
        if not ctx.voice_client.is_playing():
            await self.playqueue(ctx)

    @commands.command()
    @vc_status()
    async def pause(self, ctx):
        ctx.voice_client.pause()
        await ctx.send('Paused')

    @commands.command()
    @vc_status()
    async def resume(self, ctx):
        ctx.voice_client.resume()
        await ctx.send('Resumed')

    @commands.command()
    @vc_status()
    async def stop(self, ctx):
        self.queue = []
        ctx.voice_client.stop()
        await ctx.send('Queue cleared and stopped')

    @commands.command()
    @vc_status()
    async def skip(self, ctx):
        ctx.voice_client.stop()
        await ctx.send('Skipped')

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
