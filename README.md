### ☁️ Heroku

[![Deploy on Heroku](https://img.shields.io/badge/Deploy%20On%20Heroku-430098?style=for-the-badge&logo=heroku&logoColor=white)](https://dashboard.heroku.com/new?template=https://github.com/Badmundaxd/deep)

## Widget tests (Bot API 10.4)

This bot now also vendors `richgram.widgets` (copied into `./richgram/`,
next to `bot.py`) and adds five owner-only commands alongside the
existing rich-message ones:

- `/widgettest` — sends a small HTML widget with a "Ping the bot" button
  (`sendWidget`).
- `/widgetshared` — first run creates a **shared** widget
  (`sendWidget` with `is_shared=True`); every run after that re-sends it
  by id (`sendSharedWidget`) and bumps a counter in its state for every
  viewer at once (`editSharedWidgetData`).
- `/widgetedit` — edits the last `/widgettest` message's state
  (`editMessageWidgetData`).
- `/widgetwallet` — builds (doesn't send) a sample TON Connect-shaped
  transaction answer, to show the shape `build_wallet_transaction_answer`
  produces.
- `/widgetlog` — shows the last `widget_query`/`shared_widget_query`
  updates the bot has seen.

### Why there's a second update loop

No Pyrogram/Kurigram release is known to deliver `widget_query`/
`shared_widget_query` updates as Python objects yet (this is a
same-day-new Bot API feature). So `bot.py` runs a small extra
`widget_query_poller()` task, in parallel with Pyrogram's own MTProto
connection, that long-polls the plain Bot HTTP API
(`getUpdates`) with `allowed_updates` restricted to exactly those two
update types. It doesn't touch, duplicate, or race with anything
Pyrogram's own handlers already do — Pyrogram never calls `getUpdates`
itself, so the two update deliveries are on separate channels.

### Testing it

1. `pip install -r requirements.txt`
2. Set `API_ID` / `API_HASH` / `BOT_TOKEN` (and optionally
   `STRING_SESSION`) and run `python bot.py`.
3. In the bot's chat (as the owner), send `/widgettest`. If your Telegram
   client and bot account both support widgets, you'll see an HTML widget
   with a button; tapping it should make `/widgetlog` show a
   `widget_query` within a second or two, and the widget's own "bot
   replied: ..." line should update in place.
4. If `/widgettest` replies with a `sendWidget rejected by Telegram`
   message instead of a widget, that's Telegram telling you widgets
   aren't available yet for this bot/account/client combination (or the
   HTTP call shape needs adjusting) — the error text from Telegram is
   shown as-is so you can tell which.

**This was built and unit-tested offline (see the `richgram` project's
own test suite) but has not been run against a live bot token in the
environment that built it** — that sandbox's network allowlist blocks
`api.telegram.org` outbound entirely, so no live Telegram call was
possible from there. Please run the steps above yourself and report back
whatever `/widgettest` actually says — that's the real test.
