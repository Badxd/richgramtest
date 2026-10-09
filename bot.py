import os
import random

from pyrogram import Client, filters

from richgram import (
    RICH_AVAILABLE,
    rich_details,
    rich_edit,
    rich_heading,
    rich_kv_table,
    rich_note,
    rich_reply,
)

# =========================
# Telegram Configuration
# =========================

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# =========================
# Pyrogram Client
# =========================

app = Client(
    "rich_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)



# Premium / custom emoji used in the start message
START_EMOJI = '<tg-emoji emoji-id="6334598469746952256">🌸</tg-emoji>'


# Custom emoji shown inside the buttons
BTN_EMOJI = '<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>'


def style() -> str:
    return random.choice(["primary", "success", "danger"])


def btn(text: str, data: str, st: str = "") -> str:
    st = f' style="{st}"' if st else ""
    return f'<tg-button type="callback_data"{st} data="{data}">{text}</tg-button>'


def url_btn(text: str, url: str, st: str = "") -> str:
    st = f' style="{st}"' if st else ""
    return f'<tg-button type="url"{st} url="{url}">{text}</tg-button>'


def row(*buttons: str) -> str:
    return "<tg-button-row>" + "".join(buttons) + "</tg-button-row>"


def home_text() -> str:
    return (
        rich_heading(f"{START_EMOJI} richgram demo", level=3)
        + rich_note("Buttons change colour every time you tap Shuffle.")
        + rich_kv_table([
            ("Library", "richgram"),
            ("Rich support", "yes" if RICH_AVAILABLE else "no"),
        ])
        + rich_details("What is this?", "A test bot for the richgram package.")
    )


def home_kb() -> str:
    return (
        row(btn(f"{BTN_EMOJI} Shuffle colours", "shuffle", style()),
            btn(f"{BTN_EMOJI} Ping", "ping", style()))
        + row(url_btn(f"{BTN_EMOJI} Support", "https://t.me/BadmundaXd", style()))
        + row(btn(f"{BTN_EMOJI} Close", "close", "danger"))
    )



@app.on_message(filters.command("start"))
async def start(_, message):
    await rich_reply(
        message,
        home_text() + home_kb(),
    )

@app.on_callback_query(filters.regex("^shuffle$"))
async def shuffle(_, cbq):
    await rich_edit(cbq.message, home_text() + home_kb())   # new random colours
    await cbq.answer("Colours shuffled")


@app.on_callback_query(filters.regex("^ping$"))
async def ping(_, cbq):
    await cbq.answer("Pong!", show_alert=True)


@app.on_callback_query(filters.regex("^close$"))
async def close(_, cbq):
    await cbq.message.delete()


# =========================
# Start Bot
# =========================

print("🤖 Groq Pyrogram Bot Started!")

app.run()
  
