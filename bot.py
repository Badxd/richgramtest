import asyncio
import logging
import os
import random

from pyrogram import Client, filters, idle

from richgram import (
    RICH_AVAILABLE,
    rich_button,
    rich_button_row,
    rich_details,
    rich_edit,
    rich_footer,
    rich_heading,
    rich_kv_table,
    rich_list,
    rich_note,
    rich_pre,
    rich_reply,
    rich_send,
    rich_table,
)
from richgram.rich_ui import _input_rich  # builds the InputRichMessage (used for the raw userbot test)

logging.basicConfig(level=logging.INFO)
logging.getLogger("richgram").setLevel(logging.DEBUG)  # shows why a rich message fell back to plain text

# =========================
# Configuration
# =========================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STRING_SESSION = os.getenv("STRING_SESSION")  # optional

if not (API_ID and API_HASH and BOT_TOKEN):
    raise SystemExit("API_ID, API_HASH and BOT_TOKEN are required.")

# =========================
# Event loop (must exist BEFORE the Clients are created,
# because pyrogram's Client grabs the current loop in __init__)
# =========================

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# =========================
# Clients
# =========================

bot = Client("rich_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

user = (
    Client("rich_user", api_id=API_ID, api_hash=API_HASH, session_string=STRING_SESSION, in_memory=True)
    if STRING_SESSION
    else None
)

STYLES = ("primary", "success", "danger")


def style() -> str:
    return random.choice(STYLES)


# =========================
# Test content
# =========================

def test1_text(who: str) -> str:
    """TEST 1: rich message (heading, table, list, details, code) with no buttons."""
    return (
        rich_heading(f"Test 1 - Rich message ({who})", level=3)
        + rich_note("Agar tuhanu heading, table te collapsible block dikh rahe han, rich message chal reha hai.")
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


def test2_text(who: str) -> str:
    """TEST 2: rich message + colored buttons."""
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
            rich_button("Shuffle colours", callback_data="shuffle", style=style()),
            rich_button("Ping", callback_data="ping", style=style()),
        )
        + rich_button_row(rich_button("Support", url="https://t.me/BadmundaXd", style=style()))
        + rich_button_row(rich_button("Close", callback_data="close", style="danger"))
    )


def menu_text() -> str:
    return (
        rich_heading("richgram test bot", level=3)
        + rich_kv_table([
            ("Rich support", "yes" if RICH_AVAILABLE else "no"),
            ("Userbot (string session)", "on" if user else "off"),
        ])
        + rich_list([
            "/richtest - Test 1: rich message",
            "/btntest - Test 2: rich buttons",
            "Userbot: <code>.richtest</code> and <code>.btntest</code>" if user else "Userbot off (STRING_SESSION nahi hai)",
        ])
    )


def menu_kb() -> str:
    return rich_button_row(
        rich_button("Test 1: Rich message", callback_data="run_t1", style="primary"),
        rich_button("Test 2: Rich buttons", callback_data="run_t2", style="success"),
    )


# =========================
# BOT handlers (BOT_TOKEN)
# =========================

@bot.on_message(filters.command("start"))
async def start(_, message):
    await rich_reply(message, menu_text() + menu_kb())


@bot.on_message(filters.command("richtest"))
async def bot_richtest(_, message):
    await rich_reply(message, test1_text("bot"))


@bot.on_message(filters.command("btntest"))
async def bot_btntest(_, message):
    await rich_reply(message, test2_text("bot") + test2_kb())


@bot.on_callback_query(filters.regex("^run_t1$"))
async def cb_run_t1(_, cbq):
    await rich_send(cbq._client, cbq.message.chat.id, test1_text("bot"))
    await cbq.answer("Test 1 bhej ditta")


@bot.on_callback_query(filters.regex("^run_t2$"))
async def cb_run_t2(_, cbq):
    await rich_send(cbq._client, cbq.message.chat.id, test2_text("bot") + test2_kb())
    await cbq.answer("Test 2 bhej ditta")


@bot.on_callback_query(filters.regex("^color_"))
async def cb_color(_, cbq):
    await cbq.answer(f"Tusi {cbq.data.split('_', 1)[1]} button dabaya", show_alert=False)


@bot.on_callback_query(filters.regex("^shuffle$"))
async def cb_shuffle(_, cbq):
    await rich_edit(cbq, test2_text("bot") + test2_kb())  # new random colours
    await cbq.answer("Colours shuffled")


@bot.on_callback_query(filters.regex("^ping$"))
async def cb_ping(_, cbq):
    await cbq.answer("Pong!", show_alert=True)


@bot.on_callback_query(filters.regex("^close$"))
async def cb_close(_, cbq):
    await cbq.message.delete()


# =========================
# USERBOT handlers (STRING_SESSION)
# Commands: .richtest  .btntest   (send them from the user account itself)
# A user account calls send_rich_message directly here, so the real
# Telegram result/error is shown instead of a silent fallback.
# =========================

async def _raw_rich_test(client, message, text: str, label: str):
    chat_id = message.chat.id
    try:
        await client.send_rich_message(chat_id=chat_id, rich_message=_input_rich(text))
        await message.edit_text(f"{label}: rich message SEND HO GAYA (user account ton).")
    except Exception as e:
        await message.edit_text(
            f"{label}: user account ton rich message NAHI gaya.\n"
            f"Error: {type(e).__name__}: {e}\n\n"
            "Plain-text fallback neeche bhej reha haan."
        )
        await rich_send(client, chat_id, text)  # richgram's plain-text fallback


if user:

    @user.on_message(filters.me & filters.command("richtest", prefixes="."))
    async def user_richtest(client, message):
        await _raw_rich_test(client, message, test1_text("userbot"), "Test 1")

    @user.on_message(filters.me & filters.command("btntest", prefixes="."))
    async def user_btntest(client, message):
        await _raw_rich_test(client, message, test2_text("userbot") + test2_kb(), "Test 2")


# =========================
# Start
# =========================

async def main():
    await bot.start()
    if user:
        await user.start()
    me = await bot.get_me()
    print(f"Bot started: @{me.username} | userbot: {'on' if user else 'off'} | RICH_AVAILABLE={RICH_AVAILABLE}")
    await idle()
    if user:
        await user.stop()
    await bot.stop()


if __name__ == "__main__":
    loop.run_until_complete(main())
