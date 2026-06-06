"""
Telegram Channel Post Bot
Features:
  - Add/remove channels
  - Compose posts with rich text (HTML)
  - Add colored inline buttons (URLs or callbacks)
  - Use premium custom emojis in post text
  - Preview post before publishing
  - Publish to one or multiple connected channels
"""

import os
import json
import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MessageEntity,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("7878932594:AAE73-qSjp9AmostlZLDqHthBQUKiYuIsgQ", "7878932594:AAE73-qSjp9AmostlZLDqHthBQUKiYuIsgQ")
CHANNELS_FILE = "channels.json"

# ─── Conversation states ──────────────────────────────────────────────────────
(
    MAIN_MENU,
    ADD_CHANNEL,
    COMPOSE_TEXT,
    COMPOSE_BUTTONS,
    ADDING_BUTTON_TEXT,
    ADDING_BUTTON_URL,
    ADDING_BUTTON_ROW,
    SELECT_CHANNELS,
    CONFIRM_POST,
) = range(9)


# ─── Persistent channel store ─────────────────────────────────────────────────
def load_channels() -> dict:
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE) as f:
            return json.load(f)
    return {}


def save_channels(data: dict):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def build_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Add Channel", callback_data="add_channel")],
        [InlineKeyboardButton("✏️ Create Post", callback_data="create_post")],
        [InlineKeyboardButton("📋 My Channels", callback_data="list_channels")],
    ])


def build_post_keyboard(buttons: list[list[dict]]) -> InlineKeyboardMarkup | None:
    """Convert stored button dicts → InlineKeyboardMarkup."""
    if not buttons:
        return None
    keyboard = []
    for row in buttons:
        keyboard.append([
            InlineKeyboardButton(text=btn["text"], url=btn.get("url"))
            for btn in row
        ])
    return InlineKeyboardMarkup(keyboard)


def button_editor_keyboard(buttons: list[list[dict]]) -> InlineKeyboardMarkup:
    rows = []
    for ri, row in enumerate(buttons):
        rows.append([
            InlineKeyboardButton(f"❌ Row {ri+1}: {btn['text']}", callback_data=f"del_btn_{ri}_{bi}")
            for bi, btn in enumerate(row)
        ])
    rows.append([InlineKeyboardButton("➕ Add Button", callback_data="add_btn")])
    rows.append([
        InlineKeyboardButton("👁 Preview", callback_data="preview_post"),
        InlineKeyboardButton("✅ Done", callback_data="buttons_done"),
    ])
    return InlineKeyboardMarkup(rows)


def channel_select_keyboard(channels: dict, selected: set) -> InlineKeyboardMarkup:
    rows = []
    for ch_id, ch_info in channels.items():
        check = "✅" if ch_id in selected else "☑️"
        rows.append([InlineKeyboardButton(
            f"{check} {ch_info['title']}",
            callback_data=f"toggle_ch_{ch_id}",
        )])
    rows.append([
        InlineKeyboardButton("📤 Publish", callback_data="do_publish"),
        InlineKeyboardButton("❌ Cancel", callback_data="cancel_publish"),
    ])
    return InlineKeyboardMarkup(rows)


# ─── /start ───────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "👋 <b>Channel Post Bot</b>\n\nCompose beautiful posts with inline buttons and premium emojis, then publish to your channels.",
        parse_mode=ParseMode.HTML,
        reply_markup=build_main_menu(),
    )
    return MAIN_MENU


# ─── Main menu dispatcher ─────────────────────────────────────────────────────
async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_channel":
        await query.edit_message_text(
            "📢 <b>Add a Channel</b>\n\n"
            "1. Add me as an <b>Admin</b> to your channel (with <i>Post Messages</i> permission).\n"
            "2. Forward any message from that channel here, or send the channel username (e.g. <code>@mychannel</code>).",
            parse_mode=ParseMode.HTML,
        )
        return ADD_CHANNEL

    elif data == "create_post":
        context.user_data["post"] = {"text": "", "entities": [], "buttons": []}
        await query.edit_message_text(
            "✏️ <b>Compose your post</b>\n\n"
            "Send your post text now. You can use Telegram formatting:\n"
            "• <b>bold</b>, <i>italic</i>, <code>code</code>, etc.\n"
            "• Premium custom emojis will be preserved automatically.",
            parse_mode=ParseMode.HTML,
        )
        return COMPOSE_TEXT

    elif data == "list_channels":
        channels = load_channels()
        if not channels:
            await query.edit_message_text(
                "No channels added yet.\n\nUse <b>Add Channel</b> to get started.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_main")]
                ]),
            )
        else:
            lines = [f"• <b>{v['title']}</b> (<code>{k}</code>)" for k, v in channels.items()]
            await query.edit_message_text(
                "📋 <b>Connected Channels</b>\n\n" + "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🗑 Remove a Channel", callback_data="remove_channel_menu")],
                    [InlineKeyboardButton("⬅️ Back", callback_data="back_main")],
                ]),
            )
        return MAIN_MENU

    elif data == "back_main":
        await query.edit_message_text(
            "👋 <b>Channel Post Bot</b>\n\nWhat would you like to do?",
            parse_mode=ParseMode.HTML,
            reply_markup=build_main_menu(),
        )
        return MAIN_MENU

    elif data == "remove_channel_menu":
        channels = load_channels()
        rows = [[InlineKeyboardButton(f"🗑 {v['title']}", callback_data=f"rm_ch_{k}")] for k, v in channels.items()]
        rows.append([InlineKeyboardButton("⬅️ Back", callback_data="back_main")])
        await query.edit_message_text(
            "Select a channel to remove:",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return MAIN_MENU

    elif data.startswith("rm_ch_"):
        ch_id = data[len("rm_ch_"):]
        channels = load_channels()
        title = channels.pop(ch_id, {}).get("title", ch_id)
        save_channels(channels)
        await query.edit_message_text(
            f"✅ Removed <b>{title}</b>.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="back_main")]]),
        )
        return MAIN_MENU

    return MAIN_MENU


# ─── Add channel ──────────────────────────────────────────────────────────────
async def receive_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message

    # Forwarded message from channel
    if msg.forward_origin and hasattr(msg.forward_origin, "chat"):
        chat = msg.forward_origin.chat
        ch_id = str(chat.id)
        title = chat.title or ch_id
    elif msg.text and msg.text.startswith("@"):
        try:
            chat = await context.bot.get_chat(msg.text.strip())
            ch_id = str(chat.id)
            title = chat.title or msg.text
        except Exception as e:
            await msg.reply_text(f"❌ Could not find channel: {e}")
            return ADD_CHANNEL
    else:
        await msg.reply_text("Please forward a message from the channel or send its @username.")
        return ADD_CHANNEL

    # Verify bot is admin
    try:
        member = await context.bot.get_chat_member(ch_id, context.bot.id)
        if member.status not in ("administrator", "creator"):
            await msg.reply_text("❌ I'm not an admin in that channel. Please add me as admin first.")
            return ADD_CHANNEL
    except Exception as e:
        await msg.reply_text(f"❌ Could not verify admin status: {e}")
        return ADD_CHANNEL

    channels = load_channels()
    channels[ch_id] = {"title": title}
    save_channels(channels)

    await msg.reply_text(
        f"✅ Channel <b>{title}</b> added successfully!",
        parse_mode=ParseMode.HTML,
        reply_markup=build_main_menu(),
    )
    return MAIN_MENU


# ─── Compose post text ────────────────────────────────────────────────────────
async def receive_post_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message

    # Store text + all entities (preserves custom emoji, bold, italic, etc.)
    context.user_data["post"]["text"] = msg.text or msg.caption or ""
    context.user_data["post"]["entities"] = [
        e.to_dict() for e in (msg.entities or msg.caption_entities or [])
    ]

    await msg.reply_text(
        "✅ Text saved!\n\nNow add <b>inline buttons</b> to your post (optional).\n"
        "Each button can have a label and a URL.",
        parse_mode=ParseMode.HTML,
        reply_markup=button_editor_keyboard(context.user_data["post"]["buttons"]),
    )
    return COMPOSE_BUTTONS


# ─── Button editor ────────────────────────────────────────────────────────────
async def button_editor_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    post = context.user_data["post"]

    if data == "add_btn":
        await query.edit_message_text(
            "Enter the <b>button label</b> (text shown on the button):",
            parse_mode=ParseMode.HTML,
        )
        context.user_data["adding_btn"] = {}
        return ADDING_BUTTON_TEXT

    elif data.startswith("del_btn_"):
        _, _, ri, bi = data.split("_")
        ri, bi = int(ri), int(bi)
        if 0 <= ri < len(post["buttons"]) and 0 <= bi < len(post["buttons"][ri]):
            post["buttons"][ri].pop(bi)
            if not post["buttons"][ri]:
                post["buttons"].pop(ri)
        await query.edit_message_text(
            "Button removed. Current buttons:",
            reply_markup=button_editor_keyboard(post["buttons"]),
        )
        return COMPOSE_BUTTONS

    elif data == "preview_post":
        await send_preview(query, context)
        return COMPOSE_BUTTONS

    elif data == "buttons_done":
        channels = load_channels()
        if not channels:
            await query.edit_message_text(
                "⚠️ No channels connected. Add a channel first.",
                reply_markup=build_main_menu(),
            )
            return MAIN_MENU

        context.user_data["selected_channels"] = set()
        await query.edit_message_text(
            "📤 <b>Select channels to publish to:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=channel_select_keyboard(channels, set()),
        )
        return SELECT_CHANNELS

    return COMPOSE_BUTTONS


async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["adding_btn"]["text"] = update.message.text.strip()
    await update.message.reply_text("Now send the <b>URL</b> for this button:", parse_mode=ParseMode.HTML)
    return ADDING_BUTTON_URL


async def receive_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    url = update.message.text.strip()
    if not url.startswith(("http://", "https://", "tg://")):
        await update.message.reply_text("❌ Invalid URL. Must start with http://, https://, or tg://")
        return ADDING_BUTTON_URL

    btn = {**context.user_data["adding_btn"], "url": url}
    post = context.user_data["post"]

    await update.message.reply_text(
        "Add this button to a <b>new row</b> or the <b>last row</b>?",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Same row as last", callback_data="btn_same_row"),
                InlineKeyboardButton("New row", callback_data="btn_new_row"),
            ]
        ]),
    )
    context.user_data["pending_btn"] = btn
    return ADDING_BUTTON_ROW


async def receive_button_row(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    post = context.user_data["post"]
    btn = context.user_data.pop("pending_btn")

    if query.data == "btn_same_row" and post["buttons"]:
        post["buttons"][-1].append(btn)
    else:
        post["buttons"].append([btn])

    await query.edit_message_text(
        "Button added! Continue adding buttons or click Done.",
        reply_markup=button_editor_keyboard(post["buttons"]),
    )
    return COMPOSE_BUTTONS


# ─── Channel selection & publish ─────────────────────────────────────────────
async def channel_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = query.data
    channels = load_channels()
    selected = context.user_data["selected_channels"]

    if data.startswith("toggle_ch_"):
        ch_id = data[len("toggle_ch_"):]
        if ch_id in selected:
            selected.discard(ch_id)
        else:
            selected.add(ch_id)
        await query.edit_message_reply_markup(channel_select_keyboard(channels, selected))
        return SELECT_CHANNELS

    elif data == "cancel_publish":
        await query.edit_message_text("Cancelled.", reply_markup=build_main_menu())
        return MAIN_MENU

    elif data == "do_publish":
        if not selected:
            await query.answer("Select at least one channel!", show_alert=True)
            return SELECT_CHANNELS

        post = context.user_data["post"]
        keyboard = build_post_keyboard(post["buttons"])
        entities = [MessageEntity.de_json(e, context.bot) for e in post["entities"]]

        results = []
        for ch_id in selected:
            title = channels[ch_id]["title"]
            try:
                await context.bot.send_message(
                    chat_id=int(ch_id),
                    text=post["text"],
                    entities=entities,
                    reply_markup=keyboard,
                )
                results.append(f"✅ {title}")
            except Exception as e:
                results.append(f"❌ {title}: {e}")

        await query.edit_message_text(
            "<b>Publish results:</b>\n\n" + "\n".join(results),
            parse_mode=ParseMode.HTML,
            reply_markup=build_main_menu(),
        )
        context.user_data.clear()
        return MAIN_MENU

    return SELECT_CHANNELS


# ─── Preview helper ───────────────────────────────────────────────────────────
async def send_preview(query, context: ContextTypes.DEFAULT_TYPE):
    post = context.user_data["post"]
    keyboard = build_post_keyboard(post["buttons"])
    entities = [MessageEntity.de_json(e, context.bot) for e in post["entities"]]

    await query.message.reply_text("👁 <b>Post preview:</b>", parse_mode=ParseMode.HTML)
    await query.message.reply_text(
        text=post["text"],
        entities=entities,
        reply_markup=keyboard,
    )
    await query.message.reply_text(
        "Preview sent above. Continue editing or click ✅ Done.",
        reply_markup=button_editor_keyboard(post["buttons"]),
    )


# ─── Cancel ───────────────────────────────────────────────────────────────────
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Cancelled.", reply_markup=build_main_menu())
    return MAIN_MENU


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(main_menu_callback),
            ],
            ADD_CHANNEL: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_channel),
                CallbackQueryHandler(main_menu_callback, pattern="^back_main$"),
            ],
            COMPOSE_TEXT: [
                MessageHandler(filters.ALL & ~filters.COMMAND, receive_post_text),
            ],
            COMPOSE_BUTTONS: [
                CallbackQueryHandler(button_editor_callback),
            ],
            ADDING_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_text),
            ],
            ADDING_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_url),
            ],
            ADDING_BUTTON_ROW: [
                CallbackQueryHandler(receive_button_row, pattern="^btn_(same|new)_row$"),
            ],
            SELECT_CHANNELS: [
                CallbackQueryHandler(channel_select_callback),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)

    print("Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
