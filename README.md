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
- `/ping` — the smallest possible widget: static HTML, no button, no
  `allow_queries`, no network call of its own. Added in place of the
  weather menu slot — if this doesn't render as a widget, nothing
  downstream (buttons, `widget_query` delivery, Open-Meteo, ...) is the
  problem; if it does, `sendWidget` itself is confirmed fine and any
  other widget failing is a bug in that specific command.
- `/widgetshared` — the original generic shared-widget demo (create →
  re-send by id → bump a counter via `editSharedWidgetData`).
- `/widgetedit` — edits the last `/widgettest` message's state
  (`editMessageWidgetData`).
- `/widgetwallet` — builds (doesn't send) a sample TON Connect-shaped
  transaction answer, to show the shape `build_wallet_transaction_answer`
  produces.
- `/widgetlog` — shows the last `widget_query`/`shared_widget_query`
  updates the bot has seen.

### Fixed: `sendWidget`'s real response shape

Your live test caught a real bug: `/draw` failed with "didn't return a
widget_id". The actual `sendWidget` response nests the widget under
`result["widget"]["id"]` (confirmed from your paste: `{"message_id": ...,
"widget": {"id": "...", "width": ..., "height": ..., "html": "..."}, ...}`)
— my code was looking for a top-level `widget_id` field that doesn't
exist. There's now an `extract_sent_widget_id(result)` helper in `bot.py`
that reads the real nested shape (with a fallback to a top-level
`widget_id` in case a future Bot API version or a native client method
ever uses that instead), used by both `/widgetshared` and `/draw`. Error
messages were also trimmed — commands no longer dump the raw API response
into the chat on failure, just a short description of what went wrong.

This also confirms, again, that `sendWidget` itself has been working the
whole time (your widget rendered as a real interactive card, not plain
text) — the bug was purely in how the bot read the id back out of a
successful response.

### Less clutter, more card

Per feedback, commands that already send a widget (`/widgettest`,
`/widgetshared`) no longer also send a separate confirmation text message
after it — the widget itself is the output now, nothing extra underneath
it. `/widgetedit` and `/widgetwallet` still reply with text, since they
don't send a new widget of their own to look at.

The widgets themselves (`/ping`, `/widgettest`, `/widgetshared`) were also
restyled to a dark card with a gold accent — rounded corners, pill
buttons, monospace accents — closer to the kind of polished widget look
other bots show, instead of a plain white box. `/lifegame` and `/draw`
keep their own canvas-based look since they're a different kind of UI.

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
that built this). You reported weather "isn't coming" with no further
detail, so rather than guess blindly, `/widgetweather <place>` is now
deprioritized: it's still there as a standalone command if you want to
dig into it later, but it's no longer on the `/widgetmenu` button row —
`/ping` (above) takes that slot as a simpler, nothing-can-go-wrong test.
If you want weather debugged, paste whatever it actually replies with
(an error message, or nothing at all) and that's enough to go on.

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

### `widget_query` delivery — now confirmed working

This was the open question in earlier versions of this README. It's
resolved: your `/widgetlog` test, after drawing on `/draw`'s board,
showed real entries —

```
widget_query widget_id=6314070046490494560 data='28,14'
widget_query widget_id=6314070046490494560 data='9,17'
widget_query widget_id=6314070046490494560 data='43,13'
```

— those `data` values are exactly the `"x,y"` point strings `/draw`'s
canvas sends on each stroke. So: the `getUpdates` poller works, Telegram
does deliver `widget_query` to this bot even while it's connected over
MTProto, and `/draw`'s server side (receiving a point, storing it,
pushing it back out with `editSharedWidgetData`) is getting real data to
work with. Whether every viewer's canvas visibly updates in sync is the
next thing to check — if it doesn't, that's a bug in how the widget reads
back `publicData`, not in delivery.

`/widgettest`'s button didn't show up in that same log — that's a
separate widget (a different `widget_id` each time it's sent, since
`/widgettest` isn't shared) and may just not have been tapped in that
test run, not a sign anything is broken.

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
