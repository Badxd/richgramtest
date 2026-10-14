
import asyncio
import logging
import os

from pyrogram import Client, filters, idle
from pyrogram.errors import FloodWait, RPCError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("badbrother")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
BOT_TOKEN = os.environ["BOT_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])

app = Client(
    "approve_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


async def approve_requests(client, chat_id, status):
    approved = failed = 0

    try:
        async for request in client.get_chat_join_requests(chat_id):
            try:
                await client.approve_chat_join_request(
                    chat_id, request.user.id
                )
                approved += 1

            except FloodWait as exc:
                await asyncio.sleep(exc.value + 1)
                try:
                    await client.approve_chat_join_request(
                        chat_id, request.user.id
                    )
                    approved += 1
                except RPCError:
                    failed += 1

            except RPCError:
                failed += 1

            if (approved + failed) % 10 == 0:
                await status.edit_text(
                    f"Processing...\nApproved: {approved}\nFailed: {failed}"
                )

            await asyncio.sleep(0.5)

    except (RPCError, AttributeError) as exc:
        logger.exception("Request processing failed")
        await status.edit_text(
            f"Stopped: {type(exc).__name__}\n"
            f"Approved: {approved}\nFailed: {failed}"
        )
        return

    await status.edit_text(
        f"Finished!\nApproved: {approved}\nFailed: {failed}"
    )


pending = {}


@app.on_message(filters.private & filters.command("start"))
async def start(_, message):
    if message.from_user.id != OWNER_ID:
        return
    await message.reply_text(
        "Approve Bot ready.\n"
        "Usage: /approveall CHAT_ID"
    )


@app.on_message(filters.private & filters.command("approveall"))
async def approveall(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("Owner only.")

    if len(message.command) != 2:
        return await message.reply_text(
            "Usage: /approveall CHAT_ID"
        )

    try:
        chat_id = int(message.command[1])
        chat = await app.get_chat(chat_id)
        member = await app.get_chat_member(chat.id, "me")

        if member.status not in ("administrator", "owner"):
            return await message.reply_text(
                "Bot needs admin permission in that chat."
            )

    except (ValueError, RPCError):
        return await message.reply_text(
            "Invalid chat ID or missing access."
        )

    pending[message.from_user.id] = chat.id

    await message.reply_text(
        f"Target: {chat.title or chat.id}\n"
        "Approve ALL pending requests?\n"
        "Send /confirmapprove to continue."
    )


@app.on_message(filters.private & filters.command("confirmapprove"))
async def confirmapprove(_, message):
    if message.from_user.id != OWNER_ID:
        return await message.reply_text("Owner only.")

    chat_id = pending.pop(OWNER_ID, None)
    if chat_id is None:
        return await message.reply_text(
            "No pending operation. Run /approveall first."
        )

    status = await message.reply_text("Processing requests...")
    await approve_requests(app, chat_id, status)


async def main():
    await app.start()
    me = await app.get_me()
    logger.info("Bot started: @%s", me.username)

    try:
        await idle()
    finally:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
    
