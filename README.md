### ☁️ Heroku

[![Deploy on Heroku](https://img.shields.io/badge/Deploy%20On%20Heroku-430098?style=for-the-badge&logo=heroku&logoColor=white)](https://dashboard.heroku.com/new?template=https://github.com/Badmundaxd/deep)

## Widget tests (Bot API 10.4)

This bot now also vendors `richgram.widgets` (copied into `./richgram/`,
next to `bot.py`) and adds owner-only commands alongside the existing
rich-message ones:

- `/widgetmenu` — a button picker for the widgets below.
- `/widgettest` — sends a small HTML widget with a "Ping the bot" button
  (`sendWidget`).
- `/lifegame` — Conway's Game of Life as a widget: a canvas simulation
  that runs **entirely in the widget's own JS**, with Pause/Resume, Step,
  a speed cycle button, Dice (randomize) and a Gosper glider gun preset.
  This one needs no `widget_query` round trip at all — verified by
  rendering it in a real (headless) browser while building it: the
  simulation runs, the generation/alive counters update, and the Gosper
  gun preset places exactly the standard 36-cell pattern. The only thing
  not verified is Telegram's own widget sandbox specifically (see
  "What's actually confirmed" below).
- `/widgetweather <place>` — a live weather card (current conditions,
  next-24h strip, 7-day forecast) built server-side from the free
  [Open-Meteo](https://open-meteo.com) API (no key needed) and sent as a
  static widget — also no `widget_query` round trip needed.
- `/draw` — a **shared** drawing board: everyone who has the (re-sent)
  widget open draws on the same canvas. This one *does* need the
  `widget_query` round trip to work: each stroke point is sent to the bot
  via `TelegramWidget.request(...)`, the bot appends it to that board's
  state and pushes the update to every viewer with
  `editSharedWidgetData`. `/drawclear` empties a chat's board.
- `/widgetshared` — the original generic shared-widget demo (create →
  re-send by id → bump a counter via `editSharedWidgetData`).
- `/widgetedit` — edits the last `/widgettest` message's state
  (`editMessageWidgetData`).
- `/widgetwallet` — builds (doesn't send) a sample TON Connect-shaped
  transaction answer, to show the shape `build_wallet_transaction_answer`
  produces.
- `/widgetlog` — shows the last `widget_query`/`shared_widget_query`
  updates the bot has seen.

### What's actually confirmed vs. still open

Verified by rendering the widget HTML in a real headless browser while
building this (not a live Telegram client, but it rules out JS/syntax
bugs): `/lifegame`'s simulation runs correctly frame by frame, the Gosper
gun preset places exactly 36 live cells (the known count for that
pattern), and `/draw`'s canvas correctly plots a mouse-dragged stroke and
degrades gracefully (silently, via try/catch) when `window.TelegramWidget`
doesn't exist — which it won't outside an actual Telegram widget sandbox.
`/widgetweather`'s HTML builder was verified against a mocked Open-Meteo
response (its real network calls weren't reachable from the environment
that built this).

Still genuinely unverified, because none of it is possible without a real
bot token talking to real Telegram (your last test confirmed `sendWidget`
itself works — the message rendered as an interactive widget, not plain
text):

- Whether `window.TelegramWidget.request(...)` and `.publicData` exist
  and behave as the guide describes, inside Telegram's actual widget
  sandbox — `/lifegame` doesn't depend on this, but `/draw` does entirely.
- Whether `widget_query`/`shared_widget_query` updates ever reach this
  bot at all. Your last `/widgetlog` check (after tapping `/widgettest`'s
  button) still showed nothing — see the open question below.

### The open `widget_query` delivery question

`/widgetlog` showing nothing after a tap means one of two things, and I
can't tell which from here (no live Telegram access):

1. **The poller (`widget_query_poller` in `bot.py`) is erroring.** It
   prints `[widget_query_poller] ...` on every failure — check your
   terminal for that.
2. **Telegram isn't delivering these updates over `getUpdates` at all**
   for a bot that's also connected over MTProto (how Pyrogram/Kurigram
   connects). I flagged this as an unconfirmed assumption when I first
   wrote the poller — I don't actually know how Telegram routes a new
   update type like `widget_query` for an MTProto-connected bot, and
   there's no way for me to check that from where I'm running.

If your terminal shows the poller running cleanly (periodic `getUpdates`
calls succeeding, just with an empty `result`) and `/widgetlog` still
never shows anything even after tapping `/widgettest`'s button, that
points at (2) — and the fix would likely be running a webhook instead of
long-polling, or using whatever mechanism the official widgets guide
actually documents for receiving these (it describes the update types but
I did not find it saying which delivery mechanism — polling vs. webhook
vs. something MTProto-native — a bot should expect them through). Paste
me the terminal output and I'll dig further.

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
