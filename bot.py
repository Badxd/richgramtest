import asyncio
import logging
import os
import random
import re

# Event loop must exist BEFORE the Clients are created
# (pyrogram's Client grabs the current loop in __init__).
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from pyrogram import Client, filters, idle
from pyrogram.types import (
    InlineQueryResultArticle,
    InputMediaPhoto,
    InputRichMessage,
    InputRichMessageContent,
    InputRichMessageMedia,
)

from richgram import (
    RICH_AVAILABLE,
    rich_button,
    rich_button_row,
    rich_details,
    rich_edit,
    rich_footer,
    rich_heading,
    rich_img,
    rich_kv_table,
    rich_list,
    rich_note,
    rich_pre,
    rich_reply,
    rich_table,
)
from richgram.rich_ui import _input_rich  # builds InputRichMessage from our HTML

logging.basicConfig(level=logging.INFO)
logging.getLogger("richgram").setLevel(logging.DEBUG)

# =========================
# Configuration
# =========================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STRING_SESSION = os.getenv("STRING_SESSION")  # optional (userbot)
EXTRA_OWNER_ID = os.getenv("OWNER_ID")        # optional
LOGO_URL = os.getenv("LOGO_URL", "https://files.catbox.moe/rbcz4j.jpg")  # image for help menu / start

if not (API_ID and API_HASH and BOT_TOKEN):
    raise SystemExit("API_ID, API_HASH and BOT_TOKEN are required.")

OWNER_IDS = set()          # filled at startup (userbot account + OWNER_ID)
BOT_USERNAME = None        # filled at startup
if EXTRA_OWNER_ID and EXTRA_OWNER_ID.lstrip("-").isdigit():
    OWNER_IDS.add(int(EXTRA_OWNER_ID))

# =========================
# Clients
# =========================

bot = Client("rich_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
user = (
    Client("rich_user", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)
    if STRING_SESSION
    else None
)

def random_style() -> str:
    """Random button colour - changes on every redraw."""
    return random.choice(["success", "danger", "primary"
])


def is_owner(user_id) -> bool:
    return (not OWNER_IDS) or (user_id in OWNER_IDS)


# =========================
# Inline helper
# A rich message can be returned as an inline result. Buttons live inside the
# HTML (<tg-button>), so no reply_markup is needed.
# =========================

def inline_rich_article(result_id: str, title: str, description: str, html: str, media=None) -> InlineQueryResultArticle:
    return InlineQueryResultArticle(
        id=result_id,
        title=title,
        description=description,
        input_message_content=InputRichMessageContent(rich_message=_input_rich(html, media=media)),
    )


# =========================
# Logo image inside rich messages
# html:   <img src="tg://photo?id=logo"/>   +   media=[InputRichMessageMedia(id="logo", ...)]
# LOGO_SOURCE starts as the URL; at startup it is replaced by a Telegram file_id
# (bot uploads it once to the owner and deletes that message). If nothing works,
# LOGO_OK becomes False and menus are sent without the image.
# =========================

LOGO_SOURCE = LOGO_URL
LOGO_OK = True


def logo_media():
    if not LOGO_OK:
        return None
    return [InputRichMessageMedia(id="logo", media=InputMediaPhoto(LOGO_SOURCE))]


def lg(html: str, logo: bool = True) -> str:
    """Put the logo on top of a rich message."""
    return (rich_img("tg://photo?id=logo") + html) if (logo and LOGO_OK) else html


async def prepare_logo():
    global LOGO_SOURCE, LOGO_OK
    for oid in list(OWNER_IDS):
        try:
            m = await bot.send_photo(oid, LOGO_URL)
            LOGO_SOURCE = m.photo.file_id
            await m.delete()
            print("Logo cached as file_id")
            return
        except Exception as e:
            print(f"Logo cache via owner {oid} failed: {type(e).__name__}: {e}")
    try:  # no owner chat available: try uploading straight from the URL
        await _input_rich(lg("x"), media=logo_media()).write(client=bot)
        print("Logo will be used from URL")
    except Exception as e:
        LOGO_OK = False
        print(f"Logo disabled: {type(e).__name__}: {e}")


# =========================
# TEST 1 - rich message (no buttons)
# =========================

def test1_text(who: str) -> str:
    return (
        rich_heading(f"Test 1 - Rich message ({who})", level=3)
        + rich_note("Heading, table te collapsible block dikh rahe han taan rich message chal reha hai.")
        + rich_kv_table([
            ("Sent by", who),
            ("RICH_AVAILABLE", "yes" if RICH_AVAILABLE else "no"),
        ])
        + rich_table(
            ["Block", "Status"],
            [["Heading", "ok"], ["Table", "ok"], ["List", "ok"], ["Code", "ok"]],
        )
        + rich_list(["pehli line", "dusri line", "tijji line"])
        + rich_pre('print("hello richgram")', language="python")
        + rich_details("Tap karo", "Eh collapsible (details) block hai.")
        + rich_footer("richgram test 1")
    )


# =========================
# TEST 2 - rich message + colored buttons
# =========================

def test2_text(who: str) -> str:
    return (
        rich_heading(f"Test 2 - Rich buttons ({who})", level=3)
        + rich_note("Har button nu dabao. Shuffle dabane te colours badal jande ne.")
    )


def test2_kb() -> str:
    return (
        rich_button_row(
            rich_button("Blue", callback_data="color_primary", style="primary"),
            rich_button("Green", callback_data="color_success", style="success"),
            rich_button("Red", callback_data="color_danger", style="danger"),
        )
        + rich_button_row(
            rich_button("Shuffle colours", callback_data="shuffle", style=random_style()),
            rich_button("Ping", callback_data="ping", style=random_style()),
        )
        + rich_button_row(rich_button("Support", url="https://t.me/BadmundaXd", style=random_style()))
        + rich_button_row(rich_button("Close", callback_data="close", style="danger"))
    )


# =========================
# HELP MENU (rich buttons, paginated, works inside inline messages)
# callback data: help_plugin(<key>)  help_prev(<n>)  help_next(<n>)  help_back  help_close
# =========================

PLUGINS = {
    "ping":   ("Ping",   "Bot/userbot di speed check karda hai.\n<code>.ping</code>"),
    "rich":   ("Rich",   "Rich message test.\n<code>.richtest</code>"),
    "button": ("Button", "Rich button test.\n<code>.btntest</code>"),
    "help":   ("Help",   "Eh menu kholda hai.\n<code>.help</code>"),
    "alive":  ("Alive",  "Userbot zinda hai ya nahi.\n<code>.alive</code>"),
    "sudo":   ("Sudo",   "Sudo users manage karo.\n<code>.addsudo</code> / <code>.delsudo</code>"),
    "tools":  ("Tools",  "Chhote tools (id, info, etc.)."),
}
PER_PAGE = 4  # plugin buttons per page (2 per row)


def help_top_text() -> str:
    return (
        rich_heading("Help Menu", level=3)
        + rich_note("Neeche de buttons te dabake plugin de commands dekho.")
        + rich_kv_table([("Plugins", str(len(PLUGINS))), ("Rich support", "yes" if RICH_AVAILABLE else "no")])
    )


def help_keyboard(page: int) -> str:
    keys = sorted(PLUGINS, key=lambda k: PLUGINS[k][0].lower())
    pages = max(1, -(-len(keys) // PER_PAGE))
    page %= pages
    chunk = keys[page * PER_PAGE:(page + 1) * PER_PAGE]
    buttons = [
        rich_button(PLUGINS[k][0], callback_data=f"help_plugin({k})", style=random_style()) for k in chunk
    ]
    kb = ""
    for i in range(0, len(buttons), 2):
        kb += rich_button_row(*buttons[i:i + 2])
    if pages > 1:
        kb += rich_button_row(
            rich_button("<<", callback_data=f"help_prev({page})", style=random_style()),
            rich_button(f"{page + 1}/{pages}", callback_data=f"help_page({page})"),
            rich_button(">>", callback_data=f"help_next({page})", style=random_style()),
        )
    kb += rich_button_row(rich_button("Close", callback_data="help_close", style="danger"))
    return kb


def help_plugin_text(key: str) -> str:
    name, body = PLUGINS[key]
    return rich_heading(f"Plugin: {name}", level=3) + rich_note(body)


def help_plugin_kb() -> str:
    return rich_button_row(rich_button("Back", callback_data="help_back", style=random_style()))


# =========================
# Menu texts for the bot's own /start
# =========================

def start_text() -> str:
    return (
        rich_heading("richgram test bot", level=3)
        + rich_kv_table([
            ("Rich support", "yes" if RICH_AVAILABLE else "no"),
            ("Userbot (string session)", "on" if user else "off"),
        ])
        + rich_list([
            "/help - help menu (rich buttons)",
            "/richtest - Test 1: rich message",
            "/btntest - Test 2: rich buttons",
            "Userbot: <code>.help</code> <code>.richtest</code> <code>.btntest</code>" if user
            else "Userbot off (STRING_SESSION nahi hai)",
        ])
    )


def start_kb() -> str:
    return rich_button_row(
        rich_button("Test 1", callback_data="run_t1", style=random_style()),
        rich_button("Test 2", callback_data="run_t2", style=random_style()),
        rich_button("Help", callback_data="run_help", style=random_style()),
    )


# =========================
# BOT: direct commands (in the bot's chat)
# =========================

@bot.on_message(filters.command("start"))
async def bot_start(_, message):
    await rich_reply(message, lg(start_text() + start_kb()), media=logo_media())


@bot.on_message(filters.command("richtest"))
async def bot_richtest(_, message):
    await rich_reply(message, test1_text("bot"))


@bot.on_message(filters.command("btntest"))
async def bot_btntest(_, message):
    await rich_reply(message, test2_text("bot") + test2_kb())


@bot.on_message(filters.command("help"))
async def bot_help(_, message):
    await rich_reply(message, lg(help_top_text() + help_keyboard(0)), media=logo_media())


# =========================
# BOT: callbacks. rich_edit(cbq, ...) edits BOTH normal and inline messages.
# =========================

@bot.on_callback_query(filters.regex(r"^run_t1$"))
async def cb_run_t1(_, cbq):
    await rich_reply(cbq, test1_text("bot"))
    await cbq.answer("Test 1 bhej ditta")


@bot.on_callback_query(filters.regex(r"^run_t2$"))
async def cb_run_t2(_, cbq):
    await rich_reply(cbq, test2_text("bot") + test2_kb())
    await cbq.answer("Test 2 bhej ditta")


@bot.on_callback_query(filters.regex(r"^run_help$"))
async def cb_run_help(_, cbq):
    await rich_reply(cbq, lg(help_top_text() + help_keyboard(0)), media=logo_media())
    await cbq.answer()


@bot.on_callback_query(filters.regex(r"^color_"))
async def cb_color(_, cbq):
    await cbq.answer(f"Tusi {cbq.data.split('_', 1)[1]} button dabaya")


@bot.on_callback_query(filters.regex(r"^shuffle$"))
async def cb_shuffle(_, cbq):
    await rich_edit(cbq, test2_text("bot") + test2_kb())  # new random colours
    await cbq.answer("Colours shuffled")


@bot.on_callback_query(filters.regex(r"^ping$"))
async def cb_ping(_, cbq):
    await cbq.answer("Pong!", show_alert=True)


@bot.on_callback_query(filters.regex(r"^close$"))
async def cb_close(_, cbq):
    if cbq.message:
        await cbq.message.delete()
    else:  # inline messages cannot be deleted by the bot, so we edit them
        await rich_edit(cbq, rich_note("Closed."))
        await cbq.answer()


@bot.on_callback_query(filters.regex(r"^help_"))
async def cb_help(_, cbq):
    if not is_owner(cbq.from_user.id):
        return await cbq.answer("Eh menu sirf owner layi hai.", show_alert=True)

    data = cbq.data
    if m := re.match(r"help_plugin\((.+?)\)$", data):
        key = m.group(1)
        if key not in PLUGINS:
            return await cbq.answer("Plugin nahi mila", show_alert=True)
        await rich_edit(cbq, lg(help_plugin_text(key) + help_plugin_kb()), media=logo_media())
    elif m := re.match(r"help_prev\((\d+)\)$", data):
        await rich_edit(cbq, lg(help_top_text() + help_keyboard(int(m.group(1)) - 1)), media=logo_media())
    elif m := re.match(r"help_next\((\d+)\)$", data):
        await rich_edit(cbq, lg(help_top_text() + help_keyboard(int(m.group(1)) + 1)), media=logo_media())
    elif data == "help_back":
        await rich_edit(cbq, lg(help_top_text() + help_keyboard(0)), media=logo_media())
    elif data == "help_close":
        if cbq.message:
            await cbq.message.delete()
        else:
            await rich_edit(cbq, rich_note("Help menu closed."))
    await cbq.answer()


# =========================
# BOT: inline query  ->  returns rich messages (with buttons) as inline results
# The userbot asks for these, then sends the chosen result into any chat.
#   "help"     -> help menu
#   "richtest" -> Test 1
#   "btntest"  -> Test 2
#   (empty)    -> all three (so you can also type @botusername in any chat)
# Needs inline mode ON in @BotFather:  /setinline
# =========================

@bot.on_inline_query()
async def on_inline(_, q):
    if not is_owner(q.from_user.id):
        return await q.answer([], cache_time=1)

    def build(logo: bool):
        media = logo_media() if logo else None
        return {
            "help": inline_rich_article(
                "help", "Help menu", "Rich buttons help menu",
                lg(help_top_text() + help_keyboard(0), logo), media,
            ),
            "richtest": inline_rich_article("richtest", "Test 1", "Rich message", test1_text("userbot via inline")),
            "btntest": inline_rich_article(
                "btntest", "Test 2", "Rich buttons", test2_text("userbot via inline") + test2_kb()
            ),
        }

    key = q.query.strip().lower()
    try:
        items = build(True)
        await q.answer(
            [items[key]] if key in items else list(items.values()), cache_time=0, is_personal=True
        )
    except Exception as e:  # image problem -> answer again without the logo
        print(f"inline answer with logo failed ({type(e).__name__}: {e}), retrying without logo")
        items = build(False)
        await q.answer(
            [items[key]] if key in items else list(items.values()), cache_time=0, is_personal=True
        )


# =========================
# USERBOT (STRING_SESSION)
# A user account cannot send rich messages or buttons directly
# (Telegram: RICH_MESSAGE_UNSUPPORTED), so it asks the bot through inline mode
# and sends the result.   Commands (send from your own account): .help .richtest .btntest
# =========================

async def send_via_inline(message, query: str):
    try:
        res = await user.get_inline_bot_results(f"@{BOT_USERNAME}", query)
        if not res.results:
            raise RuntimeError("bot ne koi inline result nahi ditta")
        await user.send_inline_bot_result(
            chat_id=message.chat.id,
            query_id=res.query_id,
            result_id=res.results[0].id,
        )
        try:
            await message.delete()
        except Exception:
            pass
    except Exception as e:
        await message.edit_text(
            f"Inline ton nahi gaya.\n{type(e).__name__}: {e}\n\n"
            f"Check karo: @BotFather -> /setinline -> @{BOT_USERNAME} te inline mode ON hai?"
        )


if user:

    @user.on_message(filters.me & filters.command(["help", "richtest", "btntest"], prefixes="."))
    async def user_cmds(_, message):
        await send_via_inline(message, message.command[0].lower())


# =========================
# Start
# =========================

async def main():
    global BOT_USERNAME
    await bot.start()
    BOT_USERNAME = (await bot.get_me()).username
    if user:
        await user.start()
        OWNER_IDS.add((await user.get_me()).id)
    await prepare_logo()
    print(
        f"Bot started: @{BOT_USERNAME} | userbot: {'on' if user else 'off'} "
        f"| RICH_AVAILABLE={RICH_AVAILABLE} | owners={sorted(OWNER_IDS)}"
    )
    await idle()
    if user:
        await user.stop()
    await bot.stop()


if __name__ == "__main__":
    loop.run_until_complete(main())
