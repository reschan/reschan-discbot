import requests
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands
from discord import File, Emoji
import requests
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
from unicodedata import lookup


class ImgManipulation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='asciify')
    async def asciify(self, ctx, img_url, *args):
        config = {'width': '200', 'charset': ' .:-=+*#%@', 'bgc': (0, 0, 0), 'fgc': (255, 255, 255)}
        for i in range(len(args)):
            arg = args[i].split('=')
            if arg[0] == 'bgc' or arg[0] == 'fgc':
                rgb = arg[1].split(',')
                if len(rgb) != 3 or not all(x.isdigit() for x in rgb):
                    rgb = (0, 0, 0)
                else:
                    rgb = tuple(int(x) for x in rgb)
                arg[1] = rgb
            config[arg[0]] = arg[1]

        max_width = int(config['width']) if config['width'].isdigit() else 200
        charset = config['charset']
        bgc = config['bgc']
        fgc = config['fgc']

        if img_url == "f":
            img_url = ctx.message.attachments[0].url

        image = io.BytesIO(requests.get(img_url, stream=True).content)
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(ThreadPoolExecutor(), asciify, image, max_width, charset, bgc, fgc)
        with io.BytesIO() as image_binary:
            image.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.send(file=File(fp=image_binary, filename='image.png'))


def asciify(image, max_width: int = 200, charset: str = " .:-=+*#%@", bgc: tuple = (0, 0, 0), fgc: tuple = (255, 255, 255)):
    """
    Converts an image to ASCII art.
    :param fgc:
    :param bgc:
    :param image:
    :param max_width:
    :param charset:
    :return:
    """
    charset = [c for c in charset]

    image = Image.open(image).convert("L")
    max_width = min(max_width, image.size[0])

    image = image.resize((max_width, int(image.size[1] * max_width / image.size[0])))

    res = ''

    for y in range(image.size[1] // 2):
        for x in range(image.size[0]):
            gray = image.getpixel((x, y * 2))
            res += charset[int(gray / 255 * (len(charset) - 1))]
        res += '\n'

    res_img = Image.new("RGB", (image.size[0]*6, image.size[1]*6), color=bgc)
    fnt = ImageFont.truetype("CourierPrime-Regular.ttf", 10)

    d = ImageDraw.Draw(res_img)
    d.multiline_text((0, 0), res, font=fnt, fill=fgc)

    return res_img


def braillify():
    pass


if __name__ == "__main__":
    # asciify('testimg/3.jpg', 2000).save('ascii.png')

    a = '2'
    print(int(a) if a.isdigit() else 1)
