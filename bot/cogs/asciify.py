import requests
from PIL import Image, ImageFont, ImageDraw
from discord.ext import commands
from discord import File, Emoji
import requests
import io


def emote_url(emote):
    return f"https://cdn.discordapp.com/emojis/{emote.id}.png"


class ImgManipulation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='asciify')
    async def asciify(self, ctx, img_url, max_width: int = 200, charset: str = " .:-=+*#%@"):
        if img_url == "file":
            img_url = ctx.message.attachments[0].url
        image = io.BytesIO(requests.get(img_url, stream=True).content)
        image = asciify(image, max_width, charset)
        with io.BytesIO() as image_binary:
            image.save(image_binary, 'PNG')
            image_binary.seek(0)
            await ctx.send(file=File(fp=image_binary, filename='image.png'))


def asciify(image, max_width: int = 200, charset: str = " .:-=+*#%@"):
    """
    Converts an image to ASCII art.
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
    print(image.size)

    for y in range(image.size[1]):
        for x in range(image.size[0]):
            gray = image.getpixel((x, y))
            res += charset[int(gray / 255 * (len(charset) - 1))]
        res += '\n'

    res_img = Image.new("RGB", (image.size[0]*6, image.size[1]*6), (54, 57, 63))
    fnt = ImageFont.truetype("../bot/cogs/CourierPrime-Regular.ttf", 10)

    d = ImageDraw.Draw(res_img)
    d.multiline_text((0, 0), res, font=fnt, spacing=-2)

    return res_img


def braillify():
    pass


# asciify("test4.jpg").show()

