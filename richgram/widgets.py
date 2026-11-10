"""richgram.widgets: Bot API 10.4 HTML widgets.

Telegram's Bot API 10.4 guide (``core.telegram.org/bots/widgets``) adds
**widgets**: small, sandboxed HTML blocks a bot draws inside a message.
This module is an *additive* extension of richgram — nothing here changes
the behaviour of ``richgram.rich_ui`` or ``richgram.telethon`` (Bot API
10.3 rich messages), and it has no import-time dependency on them beyond
one shared helper (``_only_set``).

What this module is built against
----------------------------------
As of this module's writing (2026-11-10), ``core.telegram.org/bots/api``
(the full method/type reference) still tops out at **Bot API 10.3** and
does not list ``sendWidget`` or any widget type. The methods and fields
below come from the separate, already-published guide page
``core.telegram.org/bots/widgets``, which documents:

- ``sendWidget`` (``chat_id``, ``html``, ``allow_queries``, ``is_shared``,
  ``width``, ``height``, plus the usual send options)
- ``sendSharedWidget`` (re-send an existing shared widget by ``widget_id``)
- ``editMessageWidgetData`` (``chat_data`` / ``public_data`` on a static
  widget message, addressed by ``chat_id``+``message_id`` or
  ``inline_message_id``)
- ``editSharedWidgetData`` (``public_data`` / ``cache_time`` on a shared
  widget, by ``widget_id``)
- ``answerWidgetQuery`` (``widget_query_id``, optional ``data`` up to 1024
  bytes, within 15 seconds)
- the ``widget_query`` / ``shared_widget_query`` update types, including
  the TON-wallet-flavoured ``type: data | sent_transaction | sign_data``
  payloads carried inside ``widget_query``
- ``InputWidgetMessageContent`` / ``InputSharedWidgetMessageContent`` for
  ``answerInlineQuery``

Only names and shapes confirmed on that page are implemented here. Where
the guide page did not spell out a parameter's exact type/required-ness
(because it is a guide, not the full method reference table), this module
says so in the docstring rather than guessing — see "Known gaps" below.

Why this goes over the raw Bot HTTP API, not MTProto
------------------------------------------------------
richgram's existing rich-message support (``rich_ui.py``) rides on
Pyrogram/Kurigram's MTProto layer, which needs the *library* to carry
native support for a given Bot API feature (``InputRichMessage``,
``Client.send_rich_message``) before richgram can call it — that is what
``RICH_AVAILABLE`` detects. ``sendWidget`` is brand new; no known
Pyrogram/Kurigram release has added MTProto-level widget support yet, so
``WIDGET_NATIVE_AVAILABLE`` below is almost certainly ``False`` on every
installed build today.

Rather than block on that, every function in this module talks to the
plain Bot HTTP API directly (``https://api.telegram.org/bot<token>/...``),
the same escape hatch ``rich_ui._send_blocks_via_http`` already uses for
typed blocks. This works unconditionally, the moment Telegram turns the
feature on for your bot, independent of what your Pyrogram/Kurigram build
knows about. If ``WIDGET_NATIVE_AVAILABLE`` ever becomes true (a future
Kurigram release adds ``Client.send_widget`` and friends), each function
prefers the native client method and only falls back to raw HTTP on
failure or absence — the same pattern ``rich_send`` uses for
``RICH_AVAILABLE``.

This needs a bot token. Pass ``token=...`` explicitly, or set
``client.bot_token`` (Kurigram clients already expose this attribute for
bots) and it is picked up automatically.

Known gaps — read before relying on this in production
---------------------------------------------------------
- **Receiving** ``widget_query`` / ``shared_widget_query`` updates through
  Pyrogram/Kurigram's own event system is *not* implemented here, because
  no Pyrogram/Kurigram release is known to parse these updates into
  Python objects yet (same reasoning as above, in reverse). What *is*
  provided is :func:`parse_widget_query` / :func:`parse_shared_widget_query`
  / :func:`extract_widget_query`, which turn the raw Bot-API-JSON shape of
  an update (a ``dict``, exactly as ``getUpdates``/a webhook delivers it)
  into typed objects. If your bot runs over Kurigram/MTProto only, you
  will not receive these updates at all until the library adds support;
  running a small parallel Bot API poller/webhook (see the README) is the
  documented workaround.
- The guide page does not give a full parameter table (required vs.
  optional, exact types) the way the main API reference does for other
  methods. This module validates every field the guide page *does* pin
  down (HTML compressed-size limit, ``answerWidgetQuery`` data length and
  the 15-second window, ``cache_time`` bounds, 1–255 wallet messages,
  nanoton amount strings) and otherwise passes values through unchanged.
- **Test server vs. production**: Telegram's test environment
  (``api.telegram.org/bot<token>/test/...``) is a separate bot token
  namespace with separate chats; this module does not special-case it —
  pass a test-server token and it behaves the same way, but size/rate
  limits and feature availability on the test server are not guaranteed
  to match production, and this module cannot detect which one it is
  talking to. Nothing here was exercised against a live bot token; the
  unit tests mock the HTTP layer against the documented shapes above.
"""
from __future__ import annotations

import logging
import time
import zlib
from dataclasses import dataclass, field
from typing import Any

from .rich_ui import _only_set

logger = logging.getLogger("richgram.widgets")

__all__ = [
    "WIDGET_NATIVE_AVAILABLE",
    "MAX_WIDGET_HTML_COMPRESSED_BYTES",
    "MAX_WIDGET_QUERY_REQUEST_BYTES",
    "MAX_WIDGET_ANSWER_DATA_BYTES",
    "MIN_WIDGET_CACHE_TIME",
    "MAX_WIDGET_CACHE_TIME",
    "MAX_WALLET_MESSAGES",
    "WidgetAPIError",
    "WalletCard",
    "WalletSentTransaction",
    "WalletSignDataResult",
    "WidgetQuery",
    "SharedWidgetQuery",
    "widget_html_compressed_size",
    "validate_widget_html",
    "validate_nanoton_amount",
    "parse_widget_query",
    "parse_shared_widget_query",
    "extract_widget_query",
    "build_wallet_transaction_answer",
    "send_widget",
    "send_shared_widget",
    "edit_message_widget_data",
    "edit_shared_widget_data",
    "answer_widget_query",
    "input_widget_message_content",
    "input_shared_widget_message_content",
]

try:
    from pyrogram import Client as _Client

    WIDGET_NATIVE_AVAILABLE = hasattr(_Client, "send_widget")
except Exception:
    WIDGET_NATIVE_AVAILABLE = False


_LIMITS_DOC = """Documented limits (core.telegram.org/bots/widgets):

MAX_WIDGET_HTML_COMPRESSED_BYTES: the zlib level-9 compressed size limit
for a widget's HTML source.

MAX_WIDGET_QUERY_REQUEST_BYTES: the widget JS side's
``TelegramWidget.request(data)`` sends 1-64 bytes; kept here for
documentation/validation of fixtures, since richgram (server side) never
constructs this payload itself.

MAX_WIDGET_ANSWER_DATA_BYTES: ``answerWidgetQuery``'s optional ``data`` is
at most 1024 bytes.

ANSWER_WIDGET_QUERY_WINDOW_SECONDS: ``answerWidgetQuery`` must be called
within this many seconds of receiving the query.

MIN_WIDGET_CACHE_TIME / MAX_WIDGET_CACHE_TIME: ``editSharedWidgetData``'s
``cache_time`` bounds, in seconds.

MAX_WALLET_MESSAGES: a wallet transaction answer carries 1-255 messages.
"""

MAX_WIDGET_HTML_COMPRESSED_BYTES = 4096
MAX_WIDGET_QUERY_REQUEST_BYTES = 64
MAX_WIDGET_ANSWER_DATA_BYTES = 1024
ANSWER_WIDGET_QUERY_WINDOW_SECONDS = 15
MIN_WIDGET_CACHE_TIME = 5
MAX_WIDGET_CACHE_TIME = 3600
MAX_WALLET_MESSAGES = 255

_DEFAULT_BOT_API_BASE = "https://api.telegram.org"


class WidgetAPIError(RuntimeError):
    """Raised when the Bot HTTP API rejects a widget call (``ok: false``).

    Carries the parsed error body so callers can branch on
    ``error_code``/``description`` instead of parsing a message string.
    """

    def __init__(self, method: str, status_code: int, payload: dict):
        self.method = method
        self.status_code = status_code
        self.payload = payload or {}
        self.error_code = self.payload.get("error_code")
        self.description = self.payload.get("description", "")
        super().__init__(
            f"{method} failed ({status_code}"
            + (f", error_code={self.error_code}" if self.error_code else "")
            + f"): {self.description or payload}"
        )




def widget_html_compressed_size(html_text: str) -> int:
    """The size the widgets guide checks the 4096-byte limit against.

    "Count compressed HTML size with zlib level 9" — ``zlib.compress``
    defaults to level 6, so the level is passed explicitly.
    """
    return len(zlib.compress(str(html_text).encode("utf-8"), level=9))


def validate_widget_html(html_text: str) -> str:
    if not isinstance(html_text, str) or not html_text.strip():
        raise ValueError("a widget needs non-empty HTML source")
    size = widget_html_compressed_size(html_text)
    if size > MAX_WIDGET_HTML_COMPRESSED_BYTES:
        raise ValueError(
            f"widget HTML is {size} bytes compressed (zlib level 9), "
            f"over the {MAX_WIDGET_HTML_COMPRESSED_BYTES}-byte limit"
        )
    return html_text


def _validate_answer_data(data) -> str | None:
    """Validate and normalize ``answerWidgetQuery``'s ``data`` to ``str``.

    Bot API JSON has no byte-string type, so this (like ``callback_data``
    elsewhere in the Bot API) is necessarily UTF-8 text on the wire. A
    ``str`` is accepted as-is; ``bytes``/``bytearray`` is accepted only if
    it *is* valid UTF-8 — anything else is rejected with a clear error
    instead of being silently mangled into something Telegram would
    receive differently than intended.
    """
    if data is None:
        return None
    if isinstance(data, (bytes, bytearray)):
        try:
            data = bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "answerWidgetQuery data must be UTF-8 text (Bot API JSON has "
                "no raw-byte field); encode non-UTF-8 payloads yourself "
                "(e.g. base64) before passing them as a str"
            ) from exc
    if not isinstance(data, str):
        raise ValueError("answerWidgetQuery data must be str or UTF-8 bytes")
    size = len(data.encode("utf-8"))
    if size > MAX_WIDGET_ANSWER_DATA_BYTES:
        raise ValueError(
            f"answerWidgetQuery data is {size} bytes, over the "
            f"{MAX_WIDGET_ANSWER_DATA_BYTES}-byte limit"
        )
    return data


def _validate_cache_time(cache_time) -> int | None:
    if cache_time is None:
        return None
    if isinstance(cache_time, bool) or not isinstance(cache_time, int):
        raise ValueError("cache_time must be an integer number of seconds")
    if not (MIN_WIDGET_CACHE_TIME <= cache_time <= MAX_WIDGET_CACHE_TIME):
        raise ValueError(
            f"cache_time must be {MIN_WIDGET_CACHE_TIME}-"
            f"{MAX_WIDGET_CACHE_TIME} seconds, got {cache_time}"
        )
    return cache_time


def validate_nanoton_amount(amount) -> str:
    """Validate a wallet message's ``amount``: a decimal nanoton string.

    The guide gives the shape as a decimal string ("amount is in nanotons
    as a decimal string"), so an int is accepted for convenience and
    rendered as one, but a non-digit string is rejected rather than sent
    on to Telegram to fail opaquely.
    """
    if isinstance(amount, bool):
        raise ValueError("a wallet message amount must be a non-negative integer or digit string")
    if isinstance(amount, int):
        if amount < 0:
            raise ValueError("a wallet message amount must be non-negative")
        return str(amount)
    if isinstance(amount, str) and amount.isdigit():
        return amount
    raise ValueError(
        f"invalid nanoton amount {amount!r}: expected a non-negative integer "
        "or a decimal digit string"
    )




@dataclass(frozen=True)
class WalletCard:
    """``widget_query`` payload of ``type: "data"`` — a wallet info share."""

    raw: dict = field(default_factory=dict)

    @property
    def address(self):
        return self.raw.get("address")

    @property
    def balance(self):
        return self.raw.get("balance")


@dataclass(frozen=True)
class WalletSentTransaction:
    """``widget_query`` payload of ``type: "sent_transaction"``."""

    wallet: Any
    msg_hash: str
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class WalletSignDataResult:
    """``widget_query`` payload of ``type: "sign_data"``."""

    raw: dict = field(default_factory=dict)


def _parse_wallet_payload(type_data: dict | None):
    if not type_data:
        return None
    kind = type_data.get("type")
    if kind == "data":
        return WalletCard(raw=dict(type_data.get("wallet_card") or {}))
    if kind == "sent_transaction":
        return WalletSentTransaction(
            wallet=type_data.get("wallet"),
            msg_hash=type_data.get("msg_hash"),
            raw=dict(type_data),
        )
    if kind == "sign_data":
        return WalletSignDataResult(raw=dict(type_data))
    return None


@dataclass(frozen=True)
class WidgetQuery:
    """A ``widget_query`` update: a request from a widget's own (non-shared)
    message, parsed from the raw Bot-API-JSON ``dict`` Telegram sends.

    ``chat``/``message_id`` are present for a widget on a normal message;
    ``inline_message_id`` is present instead for a widget sent via the bot
    inline. Exactly one of the two addressing forms is set, mirroring the
    guide's "Requests from messages sent via the bot carry
    inline_message_id instead of chat and message_id".
    """

    id: str
    from_user: dict
    chat_instance: str
    widget_id: str
    data: bytes | None
    chat: dict | None = None
    message_id: int | None = None
    inline_message_id: str | None = None
    wallet: WalletCard | WalletSentTransaction | WalletSignDataResult | None = None
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SharedWidgetQuery:
    """A ``shared_widget_query`` update: a request from a forward of a
    shared widget. Carries only ``id``, ``from``, ``data`` and
    ``widget_id`` per the guide — no ``chat``/``message_id`` to reply
    into, since the forward may be anywhere.
    """

    id: str
    from_user: dict
    widget_id: str
    data: bytes | None
    raw: dict = field(default_factory=dict)


def _decode_query_data(value):
    """Normalize an incoming query's ``data`` field to ``bytes``.

    Bot API JSON cannot carry raw bytes, so a ``str`` value (the only
    shape Telegram ever sends here) is handed back encoded as UTF-8 bytes
    — the most useful default for a caller that wants to inspect it as
    either text or bytes.
    """
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    raise ValueError(f"unexpected widget query data type: {type(value).__name__}")


def parse_widget_query(data: dict) -> WidgetQuery:
    """Parse one raw ``widget_query`` update dict into a :class:`WidgetQuery`.

    ``data`` is the ``dict`` exactly as it appears under
    ``update["widget_query"]`` in Bot API JSON (from ``getUpdates`` or a
    webhook body) — not an already-wrapped ``Update``.
    """
    if not isinstance(data, dict):
        raise ValueError("parse_widget_query needs a dict (the widget_query object)")
    required = ("id", "from", "chat_instance", "widget_id")
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"widget_query is missing required field(s): {missing}")
    chat = data.get("chat")
    message_id = data.get("message_id")
    inline_message_id = data.get("inline_message_id")
    if bool(chat and message_id is not None) == bool(inline_message_id):
        raise ValueError(
            "widget_query must carry exactly one of (chat + message_id) or "
            "inline_message_id"
        )
    return WidgetQuery(
        id=data["id"],
        from_user=dict(data["from"]),
        chat_instance=data["chat_instance"],
        widget_id=data["widget_id"],
        data=_decode_query_data(data.get("data")),
        chat=dict(chat) if chat else None,
        message_id=message_id,
        inline_message_id=inline_message_id,
        wallet=_parse_wallet_payload(
            data.get("type") if isinstance(data.get("type"), dict) else None
        ),
        raw=dict(data),
    )


def parse_shared_widget_query(data: dict) -> SharedWidgetQuery:
    """Parse one raw ``shared_widget_query`` update dict."""
    if not isinstance(data, dict):
        raise ValueError("parse_shared_widget_query needs a dict (the shared_widget_query object)")
    required = ("id", "from", "widget_id")
    missing = [k for k in required if k not in data]
    if missing:
        raise ValueError(f"shared_widget_query is missing required field(s): {missing}")
    return SharedWidgetQuery(
        id=data["id"],
        from_user=dict(data["from"]),
        widget_id=data["widget_id"],
        data=_decode_query_data(data.get("data")),
        raw=dict(data),
    )


def extract_widget_query(update):
    """Duck-type an incoming update into a parsed widget query, or ``None``.

    Accepts, in order:

    - a raw Bot-API-JSON ``dict`` (the whole ``Update`` object, or just its
      ``widget_query``/``shared_widget_query`` value)
    - any object exposing ``.widget_query`` / ``.shared_widget_query``
      attributes carrying such a dict (forward-compatible with a future
      Pyrogram/Kurigram ``Update`` that adds these attributes)

    Returns a :class:`WidgetQuery`, a :class:`SharedWidgetQuery`, or
    ``None`` when the update carries neither.
    """
    if isinstance(update, dict):
        if "widget_query" in update:
            return parse_widget_query(update["widget_query"])
        if "shared_widget_query" in update:
            return parse_shared_widget_query(update["shared_widget_query"])
        if {"id", "from", "widget_id"} <= set(update):
            if "chat_instance" in update:
                return parse_widget_query(update)
            return parse_shared_widget_query(update)
        return None

    wq = getattr(update, "widget_query", None)
    if wq is not None:
        return parse_widget_query(wq if isinstance(wq, dict) else vars(wq))
    swq = getattr(update, "shared_widget_query", None)
    if swq is not None:
        return parse_shared_widget_query(swq if isinstance(swq, dict) else vars(swq))
    return None


def build_wallet_transaction_answer(valid_until, messages) -> dict:
    """Build the bot's TON Connect-shaped transaction answer.

    ``messages`` is an iterable of ``{"address": ..., "amount": ...,
    "payload": ..., "stateInit": ...}`` dicts (``payload``/``stateInit``
    optional); 1-255 of them, per the guide. ``amount`` is validated and
    normalised to a decimal nanoton string with
    :func:`validate_nanoton_amount`.
    """
    messages = list(messages or ())
    if not (1 <= len(messages) <= MAX_WALLET_MESSAGES):
        raise ValueError(
            f"a wallet transaction answer needs 1-{MAX_WALLET_MESSAGES} messages, "
            f"got {len(messages)}"
        )
    built = []
    for i, msg in enumerate(messages):
        if not isinstance(msg, dict) or "address" not in msg or "amount" not in msg:
            raise ValueError(f"wallet message #{i} needs at least 'address' and 'amount'")
        built.append(
            _only_set(
                address=msg["address"],
                amount=validate_nanoton_amount(msg["amount"]),
                payload=msg.get("payload"),
                stateInit=msg.get("stateInit"),
            )
        )
    return {"valid_until": int(valid_until), "messages": built}




def input_widget_message_content(html_text: str, *, allow_queries=None, is_shared=None,
                                  width=None, height=None) -> dict:
    """An ``InputWidgetMessageContent`` dict for ``answerInlineQuery``."""
    validate_widget_html(html_text)
    return _only_set(
        html=html_text,
        allow_queries=allow_queries,
        is_shared=is_shared,
        width=width,
        height=height,
    )


def input_shared_widget_message_content(widget_id: str) -> dict:
    """An ``InputSharedWidgetMessageContent`` dict for ``answerInlineQuery``."""
    if not widget_id:
        raise ValueError("input_shared_widget_message_content needs widget_id")
    return {"widget_id": widget_id}




def _resolve_token(client, token):
    token = token or getattr(client, "bot_token", None)
    if not token:
        raise RuntimeError(
            "widget methods need a bot token: pass token=..., or use a "
            "client with a .bot_token attribute"
        )
    return token


async def _call_bot_api(client, method: str, payload: dict, *, token=None, api_base=None):
    """POST one Bot HTTP API method and return its ``result``.

    Raises :class:`WidgetAPIError` on a non-``ok`` response, and lets any
    transport exception (connection error, timeout) propagate — callers
    that want a fallback instead of an exception should catch around this.
    """
    import httpx

    resolved_token = _resolve_token(client, token)
    base = api_base or _DEFAULT_BOT_API_BASE
    endpoint = f"{base}/bot{resolved_token}/{method}"
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        resp = await http_client.post(endpoint, json=payload)
    try:
        body = resp.json()
    except Exception:
        body = {}
    if resp.status_code != 200 or not body.get("ok"):
        raise WidgetAPIError(method, resp.status_code, body)
    return body.get("result")


async def _try_native(client, method_name, kwargs) -> tuple[bool, Any]:
    """Call ``client.<method_name>(**kwargs)`` if the client has it natively.

    Returns ``(True, result)`` on success, ``(False, None)`` if the method
    is absent or native calling failed (logged, not raised) so the caller
    falls through to the HTTP path.
    """
    method = getattr(client, method_name, None) if WIDGET_NATIVE_AVAILABLE else None
    if method is None:
        return False, None
    try:
        return True, await method(**kwargs)
    except Exception as e:
        logger.debug(f"[widgets] native {method_name} failed, falling back to HTTP: {e}")
        return False, None




async def send_widget(
    client,
    chat_id,
    html_text: str,
    *,
    allow_queries: bool = None,
    is_shared: bool = None,
    width: int = None,
    height: int = None,
    reply_markup=None,
    reply_parameters=None,
    message_thread_id=None,
    business_connection_id=None,
    disable_notification=None,
    protect_content=None,
    token=None,
    api_base=None,
):
    """Send a new widget (``sendWidget``).

    ``html_text`` is the widget's full HTML source; it is checked against
    the documented 4096-byte (zlib level 9 compressed) limit before
    anything is sent. ``allow_queries=True`` lets the widget call
    ``TelegramWidget.request(...)`` back to the bot (as a ``widget_query``
    update); ``is_shared=True`` makes it a shared widget other chats can
    re-send by id (``send_shared_widget``) and whose state is edited for
    everyone at once (``edit_shared_widget_data``). ``width``/``height``
    are logical pixels; ``0`` (or omitted) means automatic.

    Returns the Bot API ``result`` (a dict with at least ``message_id``)
    on success, or raises :class:`WidgetAPIError` / ``ValueError`` /
    whatever the transport raises on failure — unlike ``rich_send``, this
    does not swallow errors into ``None``, since a widget silently not
    sent is a worse surprise than an exception.
    """
    validate_widget_html(html_text)
    kwargs = _only_set(
        chat_id=chat_id,
        html=html_text,
        allow_queries=allow_queries,
        is_shared=is_shared,
        width=width,
        height=height,
        reply_markup=reply_markup,
        reply_parameters=reply_parameters,
        message_thread_id=message_thread_id,
        business_connection_id=business_connection_id,
        disable_notification=disable_notification,
        protect_content=protect_content,
    )
    ok, result = await _try_native(client, "send_widget", kwargs)
    if ok:
        return result
    return await _call_bot_api(client, "sendWidget", kwargs, token=token, api_base=api_base)


async def send_shared_widget(
    client,
    chat_id,
    widget_id: str,
    *,
    reply_markup=None,
    reply_parameters=None,
    message_thread_id=None,
    business_connection_id=None,
    disable_notification=None,
    protect_content=None,
    token=None,
    api_base=None,
):
    """Re-send an existing shared widget by id (``sendSharedWidget``) —
    "the way a photo is sent again by its file_id", per the guide.
    """
    if not widget_id:
        raise ValueError("send_shared_widget needs a widget_id")
    kwargs = _only_set(
        chat_id=chat_id,
        widget_id=widget_id,
        reply_markup=reply_markup,
        reply_parameters=reply_parameters,
        message_thread_id=message_thread_id,
        business_connection_id=business_connection_id,
        disable_notification=disable_notification,
        protect_content=protect_content,
    )
    ok, result = await _try_native(client, "send_shared_widget", kwargs)
    if ok:
        return result
    return await _call_bot_api(client, "sendSharedWidget", kwargs, token=token, api_base=api_base)


async def edit_message_widget_data(
    client,
    *,
    chat_id=None,
    message_id=None,
    inline_message_id=None,
    chat_data=None,
    public_data=None,
    token=None,
    api_base=None,
):
    """Edit a static widget message's state (``editMessageWidgetData``).

    Addressed either by ``chat_id``+``message_id`` (a normal message) or
    by ``inline_message_id`` (one sent via the bot inline) — exactly one
    form, matching ``widget_query``'s own addressing. ``chat_data`` is
    private per-chat state; ``public_data`` is shared state visible to
    every viewer, mirroring the widget's own ``chatData``/``publicData``.
    At least one of ``chat_data``/``public_data`` must be given.
    """
    has_chat_addr = chat_id is not None and message_id is not None
    if bool(has_chat_addr) == bool(inline_message_id):
        raise ValueError(
            "edit_message_widget_data needs exactly one of "
            "(chat_id + message_id) or inline_message_id"
        )
    if chat_data is None and public_data is None:
        raise ValueError("edit_message_widget_data needs chat_data and/or public_data")
    kwargs = _only_set(
        chat_id=chat_id,
        message_id=message_id,
        inline_message_id=inline_message_id,
        chat_data=chat_data,
        public_data=public_data,
    )
    ok, result = await _try_native(client, "edit_message_widget_data", kwargs)
    if ok:
        return result
    return await _call_bot_api(
        client, "editMessageWidgetData", kwargs, token=token, api_base=api_base
    )


async def edit_shared_widget_data(
    client,
    widget_id: str,
    *,
    public_data=None,
    cache_time: int = None,
    token=None,
    api_base=None,
):
    """Edit a shared widget's state for every viewer (``editSharedWidgetData``).

    ``cache_time`` (5-3600 seconds, per the guide) sets how long clients
    may keep showing the previous state before refreshing.
    """
    if not widget_id:
        raise ValueError("edit_shared_widget_data needs a widget_id")
    cache_time = _validate_cache_time(cache_time)
    kwargs = _only_set(widget_id=widget_id, public_data=public_data, cache_time=cache_time)
    ok, result = await _try_native(client, "edit_shared_widget_data", kwargs)
    if ok:
        return result
    return await _call_bot_api(
        client, "editSharedWidgetData", kwargs, token=token, api_base=api_base
    )


async def answer_widget_query(
    client,
    widget_query_id: str,
    data=None,
    *,
    received_at: float = None,
    token=None,
    api_base=None,
):
    """Answer a ``widget_query`` (``answerWidgetQuery``).

    ``data`` (optional, up to 1024 bytes) is what
    ``TelegramWidget.request(...)``'s promise resolves with as
    ``{result}`` on the widget side. The guide requires this call within
    15 seconds of receiving the query; if ``received_at`` (a
    ``time.time()`` timestamp taken when the query arrived) is given and
    more than 15 seconds have passed, this raises ``ValueError``
    immediately instead of making a call Telegram will reject as stale —
    pass nothing to skip that check (e.g. if you track timing yourself).
    """
    if not widget_query_id:
        raise ValueError("answer_widget_query needs a widget_query_id")
    answer_data = _validate_answer_data(data)
    if received_at is not None:
        elapsed = time.time() - received_at
        if elapsed > ANSWER_WIDGET_QUERY_WINDOW_SECONDS:
            raise ValueError(
                f"answerWidgetQuery must be called within "
                f"{ANSWER_WIDGET_QUERY_WINDOW_SECONDS}s of receiving the query "
                f"({elapsed:.1f}s elapsed)"
            )
    kwargs = _only_set(widget_query_id=widget_query_id, data=answer_data)
    ok, result = await _try_native(client, "answer_widget_query", kwargs)
    if ok:
        return result
    return await _call_bot_api(client, "answerWidgetQuery", kwargs, token=token, api_base=api_base)
