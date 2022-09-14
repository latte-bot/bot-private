from __future__ import annotations

import asyncio
import enum
from io import BytesIO
from typing import TYPE_CHECKING, Optional, TypeAlias, Union

import chardet
import discord
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from valorant import Collection, SkinChromaLoadout, SkinLevelLoadout, SkinLoadout
from valorant.utils import MISSING

from utils.useful import LatteFonts, LatteImages

if TYPE_CHECKING:
    SkinL: TypeAlias = Union[SkinLoadout, SkinLevelLoadout, SkinChromaLoadout]


class Colors(enum.Enum):
    username = "#252627"
    tagline = "#64666a"
    title = "#64666a"
    level = "#e8e1cd"

    def __str__(self) -> str:
        return str(self.value)


class StatusColor(enum.Enum):
    available = "#63c0b5"
    away = "#de997d"
    offline = "#8a8b8f"
    in_match = "#4e98cc"

    def __str__(self) -> str:
        return str(self.value)


async def profile_card(loadout: Collection) -> discord.File:

    # ascii font
    font_username = ImageFont.truetype(font=str(LatteFonts.dinnextw1g_bold), size=19)
    font_tagline = ImageFont.truetype(font=str(LatteFonts.dinnextw1g_regular), size=13)
    font_rank = ImageFont.truetype(font=str(LatteFonts.beni_bold), size=36)
    font_title = ImageFont.truetype(font=str(LatteFonts.dinnextw1g_regular), size=13)

    # open image
    background = Image.open(str(LatteImages.profile_card_available_2))

    # # rank icon
    # r = session.get(player.rank_icon)
    # rank_icon = Image.open(BytesIO(r.content)).convert('RGBA')

    tasks = [
        asyncio.ensure_future(loadout.identity.player_card.small_icon.read()),
        asyncio.ensure_future(loadout.identity.level_border.small_player_card_appearance.read()),
        asyncio.ensure_future(loadout.identity.level_border.level_number_appearance.read()),
        # asyncio.ensure_future(loadout.user.rank),
    ]

    card = None
    level_border = None
    level_border_number = None
    rank_icon = None

    reads_task = await asyncio.gather(*tasks)
    for index, read in enumerate(reads_task):
        if index == 0:
            card = Image.open(BytesIO(read)).resize((62, 62), Image.ANTIALIAS).convert('RGBA')
        elif index == 1:
            level_border = Image.open(BytesIO(read)).convert('RGBA')
        elif index == 2:
            level_border_number = Image.open(BytesIO(read)).convert('RGBA')

    # draw
    draw = ImageDraw.Draw(background)

    # paste image
    background.paste(card, (234, 10), card)
    background.paste(level_border, (225, 3), level_border)
    background.paste(level_border_number, (226, 62), level_border_number)  # 63
    # background.paste(rank_icon, (19, 121), rank_icon)

    # tagline position
    tagline_y = 44

    # username detection utf-8
    if chardet.detect(loadout.user.name.encode('utf-8'))['encoding'] == 'utf-8':
        font_username = ImageFont.truetype(font=str(LatteFonts.serif_712), size=30)

    # tagline detection utf-8
    if chardet.detect(loadout.user.tagline.encode('utf-8'))['encoding'] == 'utf-8':
        font_tagline = ImageFont.truetype(font=str(LatteFonts.serif_712), size=20)
        tagline_y += 1

    # username
    text_size = draw.textsize(loadout.user.name, font=font_username)
    draw.text((26, 39), loadout.user.name, font=font_username, fill=str(Colors.username))

    # tagline
    tagline_x = 30 + text_size[0]
    draw.text((tagline_x, tagline_y), f"#{loadout.user.tagline}", font=font_tagline, fill=str(Colors.tagline))

    # player tile
    if loadout.identity.player_title is not None:
        draw.text((26, 63), loadout.identity.player_title.text, font=font_title, fill=str(Colors.title))

    # current tier
    # draw.text((92, 141), player.rank, font=font_rank, fill=f"#{player.rank_color}")

    # level
    draw.text(
        (264, 82),
        str(loadout.identity.account_level),
        font=font_title,
        fill=str(Colors.level),
        align='center',
        anchor='ms',
    )

    # buffering
    buffer = BytesIO()
    background.save(buffer, format='PNG')
    buffer.seek(0)

    return discord.File(fp=buffer, filename='profile.png')


async def player_collection(loadout: Collection) -> discord.File:  # TODO: Object

    # local assets
    background = Image.open(str(LatteImages.pre_collection))
    draw = ImageDraw.Draw(background)

    # font
    font_path = str(LatteFonts.dinnextw1g_regular)
    font_title = ImageFont.truetype(font=font_path, size=12)
    font_level = ImageFont.truetype(font=font_path, size=13)
    font_display_name = ImageFont.truetype(font=font_path, size=17)

    # player loadout
    skins = loadout.skins

    # TODO: ถ้ามีไฟล์ในเครื่องไม่ต้อง add เข้าไปใน task

    # this way to fasten the process
    tasks = [
        asyncio.ensure_future(skins.classic.display_icon.read()),
        asyncio.ensure_future(skins.shorty.display_icon.read()),
        asyncio.ensure_future(skins.frenzy.display_icon.read()),
        asyncio.ensure_future(skins.ghost.display_icon.read()),
        asyncio.ensure_future(skins.sheriff.display_icon.read()),
        asyncio.ensure_future(skins.stinger.display_icon.read()),
        asyncio.ensure_future(skins.spectre.display_icon.read()),
        asyncio.ensure_future(skins.bucky.display_icon.read()),
        asyncio.ensure_future(skins.judge.display_icon.read()),
        asyncio.ensure_future(skins.bulldog.display_icon.read()),
        asyncio.ensure_future(skins.guardian.display_icon.read()),
        asyncio.ensure_future(skins.phantom.display_icon.read()),
        asyncio.ensure_future(skins.vandal.display_icon.read()),
        asyncio.ensure_future(skins.marshal.display_icon.read()),
        asyncio.ensure_future(skins.operator.display_icon.read()),
        asyncio.ensure_future(skins.ares.display_icon.read()),
        asyncio.ensure_future(skins.odin.display_icon.read()),
        asyncio.ensure_future(skins.melee.display_icon.read()),
        asyncio.ensure_future(loadout.sprays.slot_1.display_icon.read()),
        asyncio.ensure_future(loadout.sprays.slot_2.display_icon.read()),
        asyncio.ensure_future(loadout.sprays.slot_3.display_icon.read()),
        asyncio.ensure_future(loadout.identity.level_border.level_number_appearance.read()),
        asyncio.ensure_future(loadout.identity.player_card.large_icon.read()),
    ]

    skin_tasks = await asyncio.gather(*tasks)
    for index, image in enumerate(skin_tasks):
        if index == 0:
            classic = Image.open(BytesIO(image)).convert('RGBA')
            classic = classic.resize((int(classic.size[0] / 3.55), int(classic.size[1] / 3.55)), Image.ANTIALIAS)
        elif index == 1:
            shorty = Image.open(BytesIO(image)).convert('RGBA')
            shorty = shorty.resize((int(shorty.size[0] / 3.32), int(shorty.size[1] / 3.25)), Image.ANTIALIAS)
        elif index == 2:
            frenzy = Image.open(BytesIO(image)).convert('RGBA')
            frenzy = frenzy.resize((int(frenzy.size[0] / 3.45), int(frenzy.size[1] / 3.4)), Image.ANTIALIAS)
        elif index == 3:
            ghost = Image.open(BytesIO(image)).convert('RGBA')
            ghost = ghost.resize((int(ghost.size[0] / 3.12), int(ghost.size[1] / 3.12)), Image.ANTIALIAS)
        elif index == 4:
            sheriff = Image.open(BytesIO(image)).convert('RGBA')
            sheriff = sheriff.resize((int(sheriff.size[0] / 3.12), int(sheriff.size[1] / 3.1)), Image.ANTIALIAS)
        elif index == 5:
            stinger = Image.open(BytesIO(image)).convert('RGBA')
            stinger = stinger.resize((int(stinger.size[0] / 2.09), int(stinger.size[1] / 2.09)), Image.ANTIALIAS)
        elif index == 6:
            spectre = Image.open(BytesIO(image)).convert('RGBA')
            spectre = spectre.resize((int(spectre.size[0] / 1.96), int(spectre.size[1] / 1.97)), Image.ANTIALIAS)
        elif index == 7:
            bucky = Image.open(BytesIO(image)).convert('RGBA')
            bucky = bucky.resize((int(bucky.size[0] / 1.69), int(bucky.size[1] / 1.71)), Image.ANTIALIAS)
        elif index == 8:
            judge = Image.open(BytesIO(image)).convert('RGBA')
            judge = judge.resize((int(judge.size[0] / 1.66), int(judge.size[1] / 1.67)), Image.ANTIALIAS)
        elif index == 9:
            bulldog = Image.open(BytesIO(image)).convert('RGBA')
            bulldog = bulldog.resize((int(bulldog.size[0] / 1.75), int(bulldog.size[1] / 1.75)), Image.ANTIALIAS)
        elif index == 10:
            guardian = Image.open(BytesIO(image)).convert('RGBA')
            guardian = guardian.resize((int(guardian.size[0] / 1.75), int(guardian.size[1] / 1.74)), Image.ANTIALIAS)
        elif index == 11:
            phantom = Image.open(BytesIO(image)).convert('RGBA')
            phantom = phantom.resize((int(phantom.size[0] / 1.75), int(phantom.size[1] / 1.75)), Image.ANTIALIAS)
        elif index == 12:
            vandal = Image.open(BytesIO(image)).convert('RGBA')
            vandal = vandal.resize((int(vandal.size[0] / 1.75), int(vandal.size[1] / 1.76)), Image.ANTIALIAS)
        elif index == 13:
            marshal = Image.open(BytesIO(image)).convert('RGBA')
            marshal = marshal.resize((int(marshal.size[0] / 1.37), int(marshal.size[1] / 1.37)), Image.ANTIALIAS)
        elif index == 14:
            operator = Image.open(BytesIO(image)).convert('RGBA')
            operator = operator.resize((int(operator.size[0] / 1.37), int(operator.size[1] / 1.36)), Image.ANTIALIAS)
        elif index == 15:
            ares = Image.open(BytesIO(image)).convert('RGBA')
            ares = ares.resize((int(ares.size[0] / 1.37), int(ares.size[1] / 1.5)), Image.ANTIALIAS)
        elif index == 16:
            odin = Image.open(BytesIO(image)).convert('RGBA')
            odin = odin.resize((int(odin.size[0] / 1.37), int(odin.size[1] / 1.37)), Image.ANTIALIAS)
        elif index == 17:
            melee = Image.open(BytesIO(image)).convert('RGBA')
        elif index == 18:
            slot_1 = Image.open(BytesIO(image)).convert('RGBA')
            slot_1 = slot_1.resize((78, 78), Image.ANTIALIAS)
        elif index == 19:
            slot_2 = Image.open(BytesIO(image)).convert('RGBA')
            slot_2 = slot_2.resize((78, 78), Image.ANTIALIAS)
        elif index == 20:
            slot_3 = Image.open(BytesIO(image)).convert('RGBA')
            slot_3 = slot_3.resize((78, 78), Image.ANTIALIAS)
        elif index == 21:
            level_border = Image.open(BytesIO(image)).convert('RGBA')
            level_border = level_border.resize((61, 25), Image.ANTIALIAS)
        elif index == 22:
            player_card = Image.open(BytesIO(image)).convert('RGBA')

    # blur
    box = (0, 410, 268, 473)
    ic = player_card.crop(box)
    ic = ic.filter(ImageFilter.GaussianBlur(radius=2))
    player_card.paste(ic, box)

    # skin paste
    background.paste(classic, (389, 191), classic)
    background.paste(shorty, (385, 388), shorty)
    background.paste(frenzy, (388, 529), frenzy)
    background.paste(ghost, (379, 725), ghost)
    background.paste(sheriff, (379, 882), sheriff)
    background.paste(stinger, (632, 195), stinger)
    background.paste(spectre, (625, 367), spectre)
    background.paste(bucky, (605, 552), bucky)
    background.paste(judge, (602, 708), judge)
    background.paste(bulldog, (984, 199), bulldog)
    background.paste(guardian, (984, 380), guardian)
    background.paste(phantom, (984, 547), phantom)
    background.paste(vandal, (984, 709), vandal)
    background.paste(marshal, (1352, 205), marshal)
    background.paste(operator, (1353, 372), operator)
    background.paste(ares, (1353, 545), ares)
    background.paste(odin, (1353, 708), odin)

    # malee paste
    width, height = melee.size
    if height > 400:
        width = int(width // 4.5)
        height = int(height // 4.5)
        position = (1482, 867)
    elif height > 300:
        width = int(width // 3.5)
        height = int(height // 3.5)
        position = (1452, 867)
    else:
        position = (1400, 867)
        width = width / 2
        height = height / 2
    melee = melee.resize((int(width), int(height)))
    background.paste(melee, position, melee)

    # spray paste
    background.paste(slot_1, (190, 691), slot_1)
    background.paste(slot_2, (190, 797), slot_2)
    background.paste(slot_3, (190, 903), slot_3)

    # player card paste
    player_card = player_card.resize((203, 486))
    width, height = player_card.size
    pixels = player_card.load()
    for y in range(203, 486):
        alpha = 255 - int((y - height * 0.55) / height / 0.35 * 255)
        for x in range(width):
            pixels[x, y] = pixels[x, y][:3] + (alpha,)
    background.paste(player_card, (127, 176), player_card)

    # draw yellow bar
    yellow_bar = Image.new('RGBA', (203, 24), (234, 237, 177, 255))
    background.paste(yellow_bar, (127, 486), yellow_bar)

    # level paste
    background.paste(level_border, (199, 164), level_border)

    # level text paste
    draw.text(
        (230, 181), str(loadout.identity.account_level), font=font_level, fill='#e8e1cd', align='center', anchor='ms'
    )

    # display name
    # draw.text((230, 504), str(loadout.identity.name), font=font_display_name, fill='#252627', align='center', anchor='ms')

    if loadout.identity.player_title is not None:
        # filter blur
        blur_bar = Image.new('RGBA', (203, 24), color='white')
        blur_bar.putalpha(30)
        background.paste(blur_bar, (127, 510), blur_bar)

        # player title
        draw.text(
            (231, 526),
            str(loadout.identity.player_title.text),
            font=font_title,
            fill='#000',
            align='center',
            anchor='ms',
        )
        draw.text(
            (230, 525),
            str(loadout.identity.player_title.text),
            font=font_title,
            fill='#fff',
            align='center',
            anchor='ms',
        )

    # convert to rgb * remove alpha
    background = background.convert('RGB')

    # save
    buffer = BytesIO()
    background.save(buffer, 'png')
    buffer.seek(0)

    return discord.File(buffer, filename='collection.png')


class PlayerCollectionPillow:
    def __init__(self, collection: Collection):
        self.classic: Optional[bytes] = None
        self.shorty: Optional[bytes] = None
        self.frenzy: Optional[bytes] = None
        self.ghost: Optional[bytes] = None
        self.sheriff: Optional[bytes] = None
        self.stinger: Optional[bytes] = None
        self.spectre: Optional[bytes] = None
        self.bucky: Optional[bytes] = None
        self.judge: Optional[bytes] = None
        self.bulldog: Optional[bytes] = None
        self.guardian: Optional[bytes] = None
        self.phantom: Optional[bytes] = None
        self.vandal: Optional[bytes] = None
        self.marshal: Optional[bytes] = None
        self.operator: Optional[bytes] = None
        self.ares: Optional[bytes] = None
        self.odin: Optional[bytes] = None
        self.melee: Optional[bytes] = None
        self.slot_1: Optional[bytes] = None
        self.slot_2: Optional[bytes] = None
        self.slot_3: Optional[bytes] = None
        self.level_border: Optional[bytes] = None
        self.player_card: Optional[bytes] = None

    async def to_files(self) -> None:
        ...
