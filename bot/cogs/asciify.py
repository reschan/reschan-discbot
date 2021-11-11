import requests
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
from discord.ext import commands
from discord import File
import requests
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor

braille_table = {'00000000': chr(10241)}

for chrid in range(10241, 10496):
    braille_table[bin(chrid)[8:]] = chr(chrid)


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

    @commands.command(name='braillify', aliases=['brify'])
    async def braillify(self, ctx, img_url, *args):
        config = {'width': '40', 'bias': '1'}
        for i in range(len(args)):
            arg = args[i].split('=')
            config[arg[0]] = arg[1]

        max_width = int(config['width']) if config['width'].isdigit() else 40
        bias = float(config['bias']) if config['bias'].replace('.', '', 1).isdigit() else 1

        if img_url == "f":
            img_url = ctx.message.attachments[0].url
        image = io.BytesIO(requests.get(img_url, stream=True).content)
        loop = asyncio.get_event_loop()
        image = await loop.run_in_executor(ThreadPoolExecutor(), braillify, image, max_width, bias)
        if isinstance(image, str):
            await ctx.send(image)
        else:
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


def braillify(image, max_width: int = 40, bias: float = 1):
    image = Image.open(image).convert("L")
    image = image.resize((max_width, int(image.size[1] * max_width / image.size[0])))

    pxlst = []
    pxall = []

    for y in range(image.size[1] // 4):
        for x in range(image.size[0] // 2):
            grp = []
            for ix in range(2):
                for iy in range(3):
                    grp.append(image.getpixel((x * 2 + ix, y * 4 + iy)))
            grp.append(image.getpixel((x * 2, y * 4 + 3)))
            grp.append(image.getpixel((x * 2 + 1, y * 4 + 3)))
            pxlst.append(grp)
            pxall.extend(grp)
        pxlst.append('nl')

    res = ''
    avg = int(sum(pxall) / len(pxall) * bias)

    for chrs in pxlst:
        if chrs == 'nl':
            res += '\n'
            continue
        bincode = ''
        for c in chrs:
            if c > avg:
                bincode += '1'
            else:
                bincode += '0'
        res += braille_table[bincode[::-1]]

    if len(res) > 2000:
        res_img = Image.new("RGB", (int(image.size[0] * 3.5), int(image.size[1] * 3.5)))
        fnt = ImageFont.truetype("dejavu.ttf", 10)
        d = ImageDraw.Draw(res_img)
        d.multiline_text((0, 0), res, font=fnt)

        return res_img
    return res


if __name__ == "__main__":
    braillify('testimg/3.jpg', 1200).save('brify.png')
