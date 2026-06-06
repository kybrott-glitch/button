# Telegram Channel Post Bot

A bot that lets you compose rich posts with:
- **Formatted text** (bold, italic, code, etc.)
- **Premium custom emojis** (preserved from your input message)
- **Colored inline buttons** with custom labels and URLs
- **Multi-channel publishing** — connect multiple channels and choose where to post

---

## Setup

### 1. Create your bot
1. Message [@BotFather](https://t.me/BotFather) → `/newbot`
2. Copy the token you receive

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set your token
Either edit `bot.py` directly:
```python
BOT_TOKEN = "YOUR_TOKEN_HERE"
```
Or set it as an environment variable:
```bash
export BOT_TOKEN="YOUR_TOKEN_HERE"
```

### 4. Run
```bash
python bot.py
```

---

## Usage

### Add a channel
1. Add the bot as **Admin** to your channel (needs *Post Messages* permission)
2. Start the bot → **Add Channel**
3. Either forward any message from the channel, or send `@yourchannel`

### Create a post
1. **Create Post** → send your message text
   - Use Telegram formatting (bold, italic, etc.)
   - Send a message that contains **premium custom emojis** — they're automatically preserved
2. Add **inline buttons**: enter button text + URL, arrange into rows
3. **Preview** your post
4. Select target channels and **Publish**

---

## Premium Emoji Support

When you send text containing Telegram premium custom emojis to the bot, it reads the `MessageEntity` objects of type `custom_emoji` and stores them. When publishing to your channel, the bot re-sends the text with those exact entities, so the premium emojis appear correctly in the channel post.

> **Requirement**: The publishing bot account must be allowed to use custom emojis (works fine with regular bots — Telegram forwards the entities as-is).

---

## Button Colors

Telegram's inline buttons don't support custom background colors natively in regular inline keyboards. However, you can achieve visual variety by:

- Using emoji at the start of button labels (🔴 🟢 🔵 🟡)
- Using Unicode symbols or decorative characters in labels
- Structuring rows to create visual grouping

For **true colored buttons**, this would require a Telegram Mini App (WebApp button) — see the `webapp_url` parameter in `InlineKeyboardButton`.

---

## File structure
```
tg_post_bot/
├── bot.py          # Main bot code
├── channels.json   # Saved channels (auto-created)
└── requirements.txt
```

---

## Running on a VPS (systemd)

Create `/etc/systemd/system/postbot.service`:
```ini
[Unit]
Description=Telegram Post Bot
After=network.target

[Service]
WorkingDirectory=/path/to/tg_post_bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
Environment=BOT_TOKEN=YOUR_TOKEN_HERE

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable postbot
sudo systemctl start postbot
```
