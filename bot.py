import asyncio
import json
import logging
import os
import random
import re
import time
from datetime import datetime

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

# Bot API 10.4 widgets (separate module, additive — see richgram/widgets.py).
# Vendored under ./richgram in this project so the widget code is available
# even before it lands in the upstream richgram release.
from richgram.widgets import (
    SharedWidgetQuery,
    WidgetAPIError,
    WidgetQuery,
    answer_widget_query,
    build_wallet_transaction_answer,
    edit_message_widget_data,
    edit_shared_widget_data,
    extract_widget_query,
    send_shared_widget,
    send_widget,
    validate_widget_html,
    widget_html_compressed_size,
)

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
            "--- Bot API 10.4 widgets ---",
            "/widgetmenu - widget picker (buttons)",
            "/widgettest - send a basic HTML widget",
            "/widgetshared - send + re-send + edit a shared widget",
            "/widgetedit - edit the last widget's state",
            "/widgetwallet - build a sample TON wallet answer (no send)",
            "/widgetlog - last widget_query/shared_widget_query received",
            "/lifegame - Conway's Game of Life widget",
            "/widgetweather &lt;place&gt; - live weather widget (Open-Meteo)",
            "/draw - shared drawing board widget",
            "/drawclear - clear this chat's drawing board",
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
# WIDGET TESTS (Bot API 10.4) — separate from the richgram rich-message
# tests above. Everything here goes through richgram.widgets, which talks
# to the plain Bot HTTP API directly (api.telegram.org/bot<token>/...),
# since no Pyrogram/Kurigram release has native MTProto widget support
# yet. See richgram/widgets.py's module docstring for exactly what is and
# isn't confirmed against Telegram's widgets guide.
# =========================

# Per-chat memory of the last widget sent, so /widgetedit has something to
# edit without you having to paste ids back in by hand.
LAST_WIDGET = {}          # chat_id -> {"message_id": int, "clicks": int}
LAST_SHARED_WIDGET = {}   # chat_id -> {"widget_id": str, "clicks": int}

# A short ring buffer of the last widget_query/shared_widget_query updates
# seen by the poller below, for /widgetlog to show.
WIDGET_QUERY_LOG = []
WIDGET_QUERY_LOG_MAX = 20


def basic_widget_html(label: str = "richgram") -> str:
    """A small widget that calls back to the bot via TelegramWidget.request().

    Kept deliberately tiny — well under the 4096-byte (zlib level 9)
    compressed limit richgram.widgets.validate_widget_html enforces before
    any network call is made.
    """
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{font-family:sans-serif;margin:0;padding:14px;
background:var(--tg-theme-bg-color,#fff);color:var(--tg-theme-text-color,#000)}}
button{{padding:8px 16px;border:0;border-radius:10px;font-size:14px;
background:var(--tg-theme-button-color,#2ea6ff);
color:var(--tg-theme-button-text-color,#fff)}}
#out{{margin-top:10px;font-size:13px;opacity:.8}}
</style></head><body>
<p><b>{label}</b> &mdash; Bot API 10.4 widget</p>
<button onclick="ping()">Ping the bot</button>
<p id="out">(not pinged yet)</p>
<script>
function ping() {{
  var out = document.getElementById('out');
  try {{
    window.TelegramWidget.request('ping').then(function(r) {{
      out.textContent = 'bot replied: ' + JSON.stringify(r);
    }}).catch(function(e) {{
      out.textContent = 'request failed: ' + (e && e.code ? e.code : e);
    }});
  }} catch (e) {{
    out.textContent = 'TelegramWidget API not available in this client: ' + e;
  }}
}}
if (window.TelegramWidget && window.TelegramWidget.ready) {{
  window.TelegramWidget.ready();
}}
</script></body></html>"""


def shared_widget_html(count: int) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>body{{font-family:sans-serif;padding:14px;
background:var(--tg-theme-bg-color,#fff);color:var(--tg-theme-text-color,#000)}}
</style></head><body>
<p>Shared widget test</p>
<p>public_data count: <b>{count}</b></p>
<p style="opacity:.7;font-size:12px">Everyone who sees this (re)sent widget
sees the same count — editSharedWidgetData updates it for all of them at
once.</p>
</body></html>"""


@bot.on_message(filters.command("widgettest") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgettest(_, message):
    html = basic_widget_html()
    try:
        result = await send_widget(bot, message.chat.id, html, allow_queries=True)
    except WidgetAPIError as e:
        return await message.reply_text(
            f"sendWidget rejected by Telegram: {e}\n\n"
            "Common causes: widgets not yet enabled for this bot/account, "
            "or the Bot API server this token talks to doesn't support "
            "sendWidget yet."
        )
    except Exception as e:
        return await message.reply_text(f"sendWidget failed: {type(e).__name__}: {e}")
    message_id = result.get("message_id") if isinstance(result, dict) else getattr(result, "message_id", None)
    LAST_WIDGET[message.chat.id] = {"message_id": message_id, "clicks": 0}
    await message.reply_text(
        f"Widget sent (message_id={message_id}, "
        f"{widget_html_compressed_size(html)} bytes compressed).\n"
        "Tap the button inside it, then check /widgetlog — if your "
        "Telegram client supports widgets and this bot account has them "
        "enabled, a widget_query should show up there within a second or "
        "two of the tap."
    )


@bot.on_message(filters.command("widgetshared") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgetshared(_, message):
    state = LAST_SHARED_WIDGET.get(message.chat.id)
    try:
        if state is None:
            result = await send_widget(
                bot, message.chat.id, shared_widget_html(0), is_shared=True, allow_queries=True
            )
            widget_id = result.get("widget_id") if isinstance(result, dict) else getattr(result, "widget_id", None)
            if not widget_id:
                return await message.reply_text(
                    f"sendWidget (is_shared=True) didn't return a widget_id: {result!r}"
                )
            LAST_SHARED_WIDGET[message.chat.id] = {"widget_id": widget_id, "clicks": 0}
            return await message.reply_text(
                f"Shared widget created (widget_id={widget_id}). Run /widgetshared "
                "again to re-send it by id and bump its shared count."
            )

        widget_id = state["widget_id"]
        state["clicks"] += 1
        await send_shared_widget(bot, message.chat.id, widget_id)
        await edit_shared_widget_data(
            bot, widget_id, public_data={"count": state["clicks"]}, cache_time=5
        )
        await message.reply_text(
            f"Re-sent shared widget {widget_id} and bumped its public_data "
            f"count to {state['clicks']} via editSharedWidgetData — every "
            "copy of this shared widget should update."
        )
    except WidgetAPIError as e:
        await message.reply_text(f"Widget API call rejected: {e}")
    except Exception as e:
        await message.reply_text(f"Shared widget test failed: {type(e).__name__}: {e}")


@bot.on_message(filters.command("widgetedit") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgetedit(_, message):
    state = LAST_WIDGET.get(message.chat.id)
    if state is None or not state.get("message_id"):
        return await message.reply_text("No widget sent yet in this chat — run /widgettest first.")
    state["clicks"] += 1
    try:
        await edit_message_widget_data(
            bot,
            chat_id=message.chat.id,
            message_id=state["message_id"],
            public_data={"edits": state["clicks"]},
        )
        await message.reply_text(
            f"editMessageWidgetData sent for message_id={state['message_id']} "
            f"(public_data.edits={state['clicks']})."
        )
    except WidgetAPIError as e:
        await message.reply_text(f"editMessageWidgetData rejected: {e}")
    except Exception as e:
        await message.reply_text(f"Edit failed: {type(e).__name__}: {e}")


@bot.on_message(filters.command("widgetwallet") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgetwallet(_, message):
    """Builds (but does not send — there's nothing server-initiated to send
    here) a sample TON Connect-shaped transaction answer, to show
    build_wallet_transaction_answer's output against the shape the guide
    documents. A real transaction answer is only ever a *reply* to a
    widget_query whose .wallet is a WalletSentTransaction/sign_data
    request — see handle_widget_query below.
    """
    try:
        answer = build_wallet_transaction_answer(
            valid_until=int(time.time()) + 300,
            messages=[{"address": "EQExampleAddressNotReal000000000000000000000", "amount": 1_000_000_000}],
        )
    except Exception as e:
        return await message.reply_text(f"build_wallet_transaction_answer failed: {type(e).__name__}: {e}")
    await rich_reply(
        message,
        rich_heading("Sample wallet transaction answer", level=3)
        + rich_note("This is the shape richgram builds; it isn't sent anywhere by this command.")
        + rich_pre(json.dumps(answer, indent=2), language="json"),
    )


@bot.on_message(filters.command("widgetlog") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgetlog(_, message):
    if not WIDGET_QUERY_LOG:
        return await message.reply_text(
            "No widget_query/shared_widget_query seen yet. Tap a button inside "
            "a widget sent by /widgettest or /widgetshared, then check again — "
            "if nothing ever shows up here, this bot account/Telegram client "
            "pair likely doesn't have widgets enabled yet."
        )
    lines = [
        f"{entry['at']} {entry['kind']} widget_id={entry['widget_id']} data={entry['data']!r}"
        for entry in WIDGET_QUERY_LOG[-10:]
    ]
    await rich_reply(
        message,
        rich_heading("Last widget queries", level=3) + rich_pre("\n".join(lines)),
    )


# --- widget menu -----------------------------------------------------

def widget_menu_text() -> str:
    return (
        rich_heading("Widgets", level=3)
        + rich_list([
            "<b>Ping test</b> - a tiny widget with a button (sendWidget)",
            "<b>Game of Life</b> - Conway's cellular automaton, runs client-side",
            "<b>Weather</b> - live forecast card (ask for a place after tapping)",
            "<b>Shared board</b> - draw together, synced via a shared widget",
        ])
    )


def widget_menu_kb() -> str:
    return rich_button_row(
        rich_button("Ping test", callback_data="wmenu_ping"),
        rich_button("Game of Life", callback_data="wmenu_life"),
    ) + rich_button_row(
        rich_button("Weather", callback_data="wmenu_weather"),
        rich_button("Shared board", callback_data="wmenu_draw"),
    )


@bot.on_message(filters.command("widgetmenu") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgetmenu(_, message):
    await rich_reply(message, widget_menu_text() + widget_menu_kb())


@bot.on_callback_query(filters.regex(r"^wmenu_") & filters.create(lambda _, __, cbq: is_owner(cbq.from_user.id)))
async def cb_widget_menu(_, cbq):
    action = cbq.data.split("_", 1)[1]
    chat_id = cbq.message.chat.id
    await cbq.answer()
    if action == "ping":
        await bot_widgettest(_, cbq.message)
    elif action == "life":
        await run_lifegame(chat_id)
    elif action == "weather":
        await cbq.message.reply_text("Which place? Send: /widgetweather <place>")
    elif action == "draw":
        await run_draw(chat_id)


# --- Game of Life (self-contained, no widget_query round trip needed) ---

GAME_OF_LIFE_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>
body{margin:0;padding:10px;font-family:sans-serif;
background:var(--tg-theme-bg-color,#0e1e17);color:var(--tg-theme-text-color,#fff)}
#hd{display:flex;justify-content:space-between;font-size:12px;opacity:.8;margin-bottom:6px}
canvas{width:100%;display:block;background:#123;border-radius:6px}
#row{display:flex;gap:6px;margin-top:8px;flex-wrap:wrap}
button{flex:1;min-width:70px;padding:8px 4px;border:0;border-radius:8px;font-size:12px;
background:var(--tg-theme-button-color,#2ea6ff);color:var(--tg-theme-button-text-color,#fff)}
button.off{opacity:.55}
</style></head><body>
<div id="hd"><span>Game of Life</span><span id="st">gen 0 - alive 0</span></div>
<canvas id="c" width="360" height="234"></canvas>
<div id="row">
<button id="bp">Pause</button>
<button id="bs">Step</button>
<button id="bx">x1</button>
<button id="bd">Dice</button>
<button id="bg">Gosper gun</button>
</div>
<script>
(function(){
var COLS=40,ROWS=26,cell=9;
var cv=document.getElementById('c'),ctx=cv.getContext('2d');
var grid=new Uint8Array(COLS*ROWS);
var gen=0,running=true,speed=1,acc=0,last=0;
function idx(x,y){return ((y+ROWS)%ROWS)*COLS+((x+COLS)%COLS);}
function randomize(){
  for(var i=0;i<grid.length;i++) grid[i]=Math.random()<0.25?1:0;
  gen=0; draw();
}
function clearGrid(){ grid.fill(0); gen=0; }
function placeGosperGun(){
  clearGrid();
  var cells=[[0,4],[0,5],[1,4],[1,5],[10,4],[10,5],[10,6],[11,3],[11,7],
  [12,2],[12,8],[13,2],[13,8],[14,5],[15,3],[15,7],[16,4],[16,5],[16,6],
  [17,5],[20,2],[20,3],[20,4],[21,2],[21,3],[21,4],[22,1],[22,5],
  [24,0],[24,1],[24,5],[24,6],[34,2],[34,3],[35,2],[35,3]];
  for(var i=0;i<cells.length;i++) grid[idx(cells[i][0]+2,cells[i][1]+2)]=1;
  draw();
}
function step(){
  var next=new Uint8Array(COLS*ROWS);
  for(var y=0;y<ROWS;y++) for(var x=0;x<COLS;x++){
    var n=grid[idx(x-1,y-1)]+grid[idx(x,y-1)]+grid[idx(x+1,y-1)]
         +grid[idx(x-1,y)]              +grid[idx(x+1,y)]
         +grid[idx(x-1,y+1)]+grid[idx(x,y+1)]+grid[idx(x+1,y+1)];
    var alive=grid[idx(x,y)];
    next[idx(x,y)]=(alive&&(n===2||n===3))||(!alive&&n===3)?1:0;
  }
  grid=next; gen++; draw();
}
function draw(){
  ctx.fillStyle='#123'; ctx.fillRect(0,0,cv.width,cv.height);
  ctx.fillStyle='#bff';
  var alive=0;
  for(var y=0;y<ROWS;y++) for(var x=0;x<COLS;x++) if(grid[idx(x,y)]){
    ctx.fillRect(x*cell,y*cell,cell-1,cell-1); alive++;
  }
  document.getElementById('st').textContent='gen '+gen+' - alive '+alive;
}
function loop(ts){
  if(running){
    if(!last) last=ts;
    acc+=ts-last; last=ts;
    var interval=220/speed;
    if(acc>interval){ acc=0; step(); }
  } else { last=0; }
  requestAnimationFrame(loop);
}
document.getElementById('bp').onclick=function(e){
  running=!running; e.target.textContent=running?'Pause':'Resume';
  e.target.classList.toggle('off', !running);
};
document.getElementById('bs').onclick=function(){ running=false;
  document.getElementById('bp').textContent='Resume';
  document.getElementById('bp').classList.add('off'); step(); };
document.getElementById('bx').onclick=function(e){
  speed = speed>=8?1:speed*2; e.target.textContent='x'+speed; };
document.getElementById('bd').onclick=randomize;
document.getElementById('bg').onclick=placeGosperGun;
randomize();
requestAnimationFrame(loop);
if (window.TelegramWidget && window.TelegramWidget.ready) window.TelegramWidget.ready();
})();
</script></body></html>"""


async def run_lifegame(chat_id):
    try:
        await send_widget(bot, chat_id, GAME_OF_LIFE_HTML, width=380, height=330)
    except WidgetAPIError as e:
        await bot.send_message(chat_id, f"sendWidget rejected: {e}")
    except Exception as e:
        await bot.send_message(chat_id, f"Game of Life widget failed: {type(e).__name__}: {e}")


@bot.on_message(filters.command("lifegame") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_lifegame(_, message):
    await run_lifegame(message.chat.id)


# --- Weather (static, server-rendered; no widget_query needed) ---------

_WMO = {
    0: ("clear sky", "+"), 1: ("mainly clear", "+"), 2: ("partly cloudy", "~"),
    3: ("overcast", "="), 45: ("fog", "="), 48: ("depositing rime fog", "="),
    51: ("light drizzle", "."), 53: ("drizzle", "."), 55: ("dense drizzle", "."),
    56: ("freezing drizzle", "."), 57: ("dense freezing drizzle", "."),
    61: ("slight rain", "/"), 63: ("rain", "/"), 65: ("heavy rain", "/"),
    66: ("freezing rain", "/"), 67: ("heavy freezing rain", "/"),
    71: ("slight snow", "*"), 73: ("snow", "*"), 75: ("heavy snow", "*"),
    77: ("snow grains", "*"), 80: ("slight rain showers", "/"),
    81: ("rain showers", "/"), 82: ("violent rain showers", "/"),
    85: ("slight snow showers", "*"), 86: ("heavy snow showers", "*"),
    95: ("thunderstorm", "!"), 96: ("thunderstorm, slight hail", "!"),
    99: ("thunderstorm, heavy hail", "!"),
}


def _wmo_desc(code):
    return _WMO.get(code, ("unknown", "?"))[0]


async def fetch_weather_card_html(place: str):
    """Geocode `place` and build a static weather widget via Open-Meteo
    (free, no API key). Returns (html, resolved_label).

    Not exercised against the live Open-Meteo API from the environment
    that wrote this code — its outbound network is allowlisted to package
    registries only, so api.open-meteo.com was unreachable from there.
    The request/response shapes follow Open-Meteo's documented API as of
    this writing; if the shape has drifted, the exception raised here
    carries whatever Open-Meteo's own response said, rather than a
    swallowed/generic failure.
    """
    import httpx

    async with httpx.AsyncClient(timeout=15.0) as http:
        geo_resp = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": place, "count": 1, "language": "en", "format": "json"},
        )
        geo = geo_resp.json()
        results = geo.get("results") or []
        if not results:
            raise RuntimeError(f"Open-Meteo couldn't find a place named {place!r}")
        loc = results[0]
        lat, lon = loc["latitude"], loc["longitude"]
        label = loc.get("name", place)
        if loc.get("admin1") and loc["admin1"] != label:
            label += f", {loc['admin1']}"

        fc_resp = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                           "weather_code,wind_speed_10m,surface_pressure",
                "hourly": "temperature_2m,weather_code",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunset",
                "wind_speed_unit": "ms",
                "timezone": "auto",
                "forecast_days": 8,
            },
        )
        fc = fc_resp.json()
        if "current" not in fc:
            raise RuntimeError(f"Open-Meteo forecast error: {fc.get('reason', fc)}")

    cur = fc["current"]
    daily = fc["daily"]
    hourly = fc["hourly"]

    temp = round(cur["temperature_2m"])
    feels = round(cur["apparent_temperature"])
    desc = _wmo_desc(cur["weather_code"])
    wind = cur["wind_speed_10m"]
    humidity = cur["relative_humidity_2m"]
    pressure_mmhg = round(cur["surface_pressure"] * 0.750062)
    sunset_today = daily["sunset"][0][-5:] if daily.get("sunset") else "?"

    hourly_times = hourly.get("time", [])
    now_iso = cur.get("time", "")
    start = 0
    for i, t in enumerate(hourly_times):
        if t >= now_iso:
            start = i
            break
    strip = []
    for i in range(start, min(start + 24, len(hourly_times)), 3):
        hh = hourly_times[i][11:13]
        strip.append(
            f'<div class="hcol"><span>{hh}</span>'
            f'<b>{round(hourly["temperature_2m"][i])}</b></div>'
        )

    day_rows = []
    day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i in range(min(7, len(daily.get("time", [])))):
        d = daily["time"][i]
        try:
            wd = day_names[datetime.fromisoformat(d).weekday()]
        except Exception:
            wd = d[5:]
        wd = "Today" if i == 0 else wd
        lo = round(daily["temperature_2m_min"][i])
        hi = round(daily["temperature_2m_max"][i])
        day_rows.append(
            f'<div class="drow"><span class="dname">{wd}</span>'
            f'<span class="dlo">{lo}</span>'
            f'<span class="dbar"></span>'
            f'<span class="dhi">{hi}</span></div>'
        )

    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>
body{{margin:0;padding:12px;font-family:sans-serif;
background:linear-gradient(#1b4a7a,#123);color:#fff}}
#top{{display:flex;justify-content:space-between;font-size:13px;opacity:.85}}
#temp{{font-size:42px;font-weight:700;margin:4px 0}}
#desc{{font-size:13px;opacity:.9}}
#tiles{{display:flex;gap:6px;margin:10px 0}}
.tile{{flex:1;background:rgba(255,255,255,.08);border-radius:8px;padding:6px;
text-align:center;font-size:11px}}
.tile b{{display:block;font-size:14px}}
#strip{{display:flex;gap:4px;overflow-x:auto;margin:10px 0;padding-bottom:4px}}
.hcol{{flex:0 0 auto;text-align:center;font-size:11px;opacity:.9;min-width:28px}}
.drow{{display:flex;align-items:center;gap:8px;font-size:12px;padding:3px 0}}
.dname{{flex:0 0 42px}}
.dlo{{flex:0 0 22px;opacity:.7;text-align:right}}
.dbar{{flex:1;height:4px;border-radius:2px;
background:linear-gradient(90deg,#9fe,#fc6)}}
.dhi{{flex:0 0 22px;text-align:right}}
</style></head><body>
<div id="top"><b>{label}</b><span>via Open-Meteo</span></div>
<div id="temp">{temp}&deg;</div>
<div id="desc">{desc} - feels like {feels}&deg;</div>
<div id="tiles">
<div class="tile">Wind<b>{wind:.1f} m/s</b></div>
<div class="tile">Humidity<b>{humidity}%</b></div>
<div class="tile">Pressure<b>{pressure_mmhg} mmHg</b></div>
<div class="tile">Sunset<b>{sunset_today}</b></div>
</div>
<div id="strip">{''.join(strip)}</div>
<div id="days">{''.join(day_rows)}</div>
</body></html>"""
    return html, label


@bot.on_message(filters.command("widgetweather") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_widgetweather(_, message):
    place = message.text.split(None, 1)[1].strip() if len(message.text.split(None, 1)) > 1 else None
    if not place:
        return await message.reply_text("Usage: /widgetweather <place>")
    status = await message.reply_text(f"Fetching weather for {place} from Open-Meteo...")
    try:
        html, label = await fetch_weather_card_html(place)
        validate_widget_html(html)
    except Exception as e:
        return await status.edit_text(f"Weather widget failed: {type(e).__name__}: {e}")
    try:
        await send_widget(bot, message.chat.id, html)
        await status.delete()
    except WidgetAPIError as e:
        await status.edit_text(f"sendWidget rejected by Telegram: {e}")
    except Exception as e:
        await status.edit_text(f"sendWidget failed: {type(e).__name__}: {e}")


# --- Shared drawing board (needs widget_query delivery to work live) ----

DRAW_COLS, DRAW_ROWS, DRAW_CELL = 48, 32, 7
DRAW_MAX_POINTS = 600
DRAW_BOARDS = {}         # widget_id -> [[x, y], ...]
DRAW_WIDGET_BY_CHAT = {}  # chat_id -> widget_id

DRAW_WIDGET_HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>
body{margin:0;padding:8px;font-family:sans-serif;
background:var(--tg-theme-bg-color,#123);color:var(--tg-theme-text-color,#fff)}
#hd{font-size:12px;opacity:.8;margin-bottom:6px}
canvas{width:100%;display:block;background:#1a3b2c;border-radius:6px;touch-action:none}
</style></head><body>
<div id="hd">Shared board - draw, everyone watching sees it</div>
<canvas id="c" width="336" height="224"></canvas>
<script>
(function(){
var COLS=48,ROWS=32,cell=7;
var cv=document.getElementById('c'),ctx=cv.getContext('2d');
var have={};
function key(x,y){return x+','+y;}
function plot(x,y){
  if(x<0||y<0||x>=COLS||y>=ROWS) return;
  var k=key(x,y);
  if(have[k]) return;
  have[k]=1;
  ctx.fillStyle='#fff';
  ctx.fillRect(x*cell,y*cell,cell-1,cell-1);
}
function renderAll(points){
  ctx.fillStyle='#1a3b2c'; ctx.fillRect(0,0,cv.width,cv.height);
  have={};
  (points||[]).forEach(function(p){ plot(p[0],p[1]); });
}
function pointFromEvent(e){
  var r=cv.getBoundingClientRect();
  var cx=(e.touches?e.touches[0].clientX:e.clientX)-r.left;
  var cy=(e.touches?e.touches[0].clientY:e.clientY)-r.top;
  var sx=cv.width/r.width, sy=cv.height/r.height;
  return [Math.floor(cx*sx/cell), Math.floor(cy*sy/cell)];
}
var drawing=false;
function onDown(e){ drawing=true; onMove(e); }
function onUp(){ drawing=false; }
function onMove(e){
  if(!drawing) return;
  e.preventDefault();
  var p=pointFromEvent(e);
  plot(p[0],p[1]);
  try{
    window.TelegramWidget.request(p[0]+','+p[1]).catch(function(){});
  }catch(err){}
}
cv.addEventListener('mousedown', onDown);
cv.addEventListener('mousemove', onMove);
window.addEventListener('mouseup', onUp);
cv.addEventListener('touchstart', onDown, {passive:false});
cv.addEventListener('touchmove', onMove, {passive:false});
cv.addEventListener('touchend', onUp);

var lastSerialized='';
function poll(){
  try{
    var pd=window.TelegramWidget.publicData;
    if(pd && pd.points){
      var s=JSON.stringify(pd.points);
      if(s!==lastSerialized){ lastSerialized=s; renderAll(pd.points); }
    }
  }catch(err){}
}
setInterval(poll, 1500);
poll();
if (window.TelegramWidget && window.TelegramWidget.ready) window.TelegramWidget.ready();
})();
</script></body></html>"""


async def run_draw(chat_id):
    existing_widget_id = DRAW_WIDGET_BY_CHAT.get(chat_id)
    try:
        if existing_widget_id is None:
            result = await send_widget(
                bot, chat_id, DRAW_WIDGET_HTML, is_shared=True, allow_queries=True,
                width=350, height=260,
            )
            widget_id = result.get("widget_id") if isinstance(result, dict) else getattr(result, "widget_id", None)
            if not widget_id:
                return await bot.send_message(chat_id, f"sendWidget didn't return a widget_id: {result!r}")
            DRAW_WIDGET_BY_CHAT[chat_id] = widget_id
            DRAW_BOARDS[widget_id] = []
            await edit_shared_widget_data(bot, widget_id, public_data={"points": []}, cache_time=5)
        else:
            await send_shared_widget(bot, chat_id, existing_widget_id)
    except WidgetAPIError as e:
        await bot.send_message(chat_id, f"Draw widget failed: {e}")
    except Exception as e:
        await bot.send_message(chat_id, f"Draw widget failed: {type(e).__name__}: {e}")


@bot.on_message(filters.command("draw") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_draw(_, message):
    await run_draw(message.chat.id)


@bot.on_message(filters.command("drawclear") & filters.create(lambda _, __, m: is_owner(m.from_user.id)))
async def bot_drawclear(_, message):
    widget_id = DRAW_WIDGET_BY_CHAT.get(message.chat.id)
    if not widget_id:
        return await message.reply_text("No drawing board in this chat yet - run /draw first.")
    DRAW_BOARDS[widget_id] = []
    try:
        await edit_shared_widget_data(bot, widget_id, public_data={"points": []}, cache_time=5)
        await message.reply_text("Board cleared.")
    except Exception as e:
        await message.reply_text(f"Clear failed: {type(e).__name__}: {e}")


async def handle_draw_query(query) -> bool:
    """If `query` is a point tapped/dragged on a known drawing board, apply
    it and push the updated board to every viewer. Returns True if it was
    handled (so the generic ping-pong reply below is skipped for it).
    """
    if query.widget_id not in DRAW_BOARDS or not query.data:
        return False
    try:
        cx_s, cy_s = query.data.decode("utf-8").split(",")
        cx, cy = int(cx_s), int(cy_s)
    except Exception:
        return False
    if not (0 <= cx < DRAW_COLS and 0 <= cy < DRAW_ROWS):
        return True

    points = DRAW_BOARDS[query.widget_id]
    points.append([cx, cy])
    del points[:-DRAW_MAX_POINTS]

    if isinstance(query, WidgetQuery):
        try:
            await answer_widget_query(bot, query.id, data="ok")
        except Exception as e:
            print(f"[draw] answer failed: {type(e).__name__}: {e}")
    try:
        await edit_shared_widget_data(bot, query.widget_id, public_data={"points": points}, cache_time=5)
    except Exception as e:
        print(f"[draw] edit_shared_widget_data failed: {type(e).__name__}: {e}")
    return True


async def handle_widget_query(query):
    """Called by widget_query_poller() for every parsed widget_query /
    shared_widget_query. Logs it for /widgetlog, routes drawing-board
    points to handle_draw_query, and otherwise answers a plain
    (non-wallet) WidgetQuery so the widget's own
    TelegramWidget.request(...) promise resolves — this is what
    basic_widget_html()'s "Ping the bot" button is waiting on.
    """
    entry = {
        "at": time.strftime("%H:%M:%S"),
        "kind": "widget_query" if isinstance(query, WidgetQuery) else "shared_widget_query",
        "widget_id": query.widget_id,
        "data": query.data.decode("utf-8", "replace") if query.data else None,
    }
    WIDGET_QUERY_LOG.append(entry)
    del WIDGET_QUERY_LOG[:-WIDGET_QUERY_LOG_MAX]
    print(f"[widget_query] {entry}")

    if await handle_draw_query(query):
        return

    if isinstance(query, WidgetQuery) and query.wallet is None:
        try:
            await answer_widget_query(bot, query.id, data=f"pong:{entry['data']}"[:1024])
        except Exception as e:
            print(f"[widget_query] answer failed: {type(e).__name__}: {e}")


async def widget_query_poller():
    """A small, separate long-poll loop for widget_query/shared_widget_query,
    talking to the plain Bot HTTP API directly.

    This runs alongside Pyrogram's own MTProto connection, not instead of
    it: Pyrogram never calls Bot API getUpdates itself (it receives
    updates over its own MTProto session), so this poller and Pyrogram's
    update handling don't race or conflict with each other. It asks only
    for widget_query/shared_widget_query via allowed_updates, so it never
    sees (and never needs to handle) ordinary messages/callbacks — those
    stay on Pyrogram's handlers above, unchanged.

    This is a best-effort addition: no Pyrogram/Kurigram release is known
    to deliver these updates itself yet (see richgram/widgets.py), so this
    poller is the only way this test bot can receive them at all. It has
    not been exercised against a live bot token — richgram.widgets.extract_widget_query
    does the actual parsing/validation, this function is just the transport loop.
    """
    import httpx

    offset = 0
    backoff = 2
    async with httpx.AsyncClient(timeout=40.0) as http:
        while True:
            try:
                resp = await http.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
                    params={
                        "timeout": 30,
                        "offset": offset,
                        "allowed_updates": json.dumps(["widget_query", "shared_widget_query"]),
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    print(f"[widget_query_poller] getUpdates not ok: {data}")
                    await asyncio.sleep(backoff)
                    continue
                backoff = 2
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        query = extract_widget_query(update)
                    except Exception as e:
                        print(f"[widget_query_poller] parse failed: {type(e).__name__}: {e}")
                        continue
                    if query is not None:
                        await handle_widget_query(query)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[widget_query_poller] transport error: {type(e).__name__}: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)


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
    poller_task = asyncio.create_task(widget_query_poller())
    print(
        f"Bot started: @{BOT_USERNAME} | userbot: {'on' if user else 'off'} "
        f"| RICH_AVAILABLE={RICH_AVAILABLE} | owners={sorted(OWNER_IDS)} "
        f"| widget_query_poller: running"
    )
    await idle()
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass
    if user:
        await user.stop()
    await bot.stop()


if __name__ == "__main__":
    loop.run_until_complete(main())
