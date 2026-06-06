import asyncio
import logging
from typing import Optional, Dict, List, Set, Tuple
from datetime import datetime
import json
import os
import re

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ParseMode, User, Chat, ChatMember
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, InlineQueryHandler
)
from telegram.inline.inlinequeryresultarticle import InlineQueryResultArticle
from telegram.inline.inputtextmessagecontent import InputTextMessageContent
from telegram.error import BadRequest

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Replace with your bot token
ADMIN_USER_ID = 123456789  # Replace with your Telegram user ID (Main Admin)

# File to store data
AUTH_FILE = "authorized_users.json"
CHANNELS_FILE = "connected_channels.json"

class UserManager:
    """Manage authorized users and admins"""
    
    def __init__(self, auth_file: str):
        self.auth_file = auth_file
        self.authorized_users: Dict[str, Dict] = {}
        self.load_users()
    
    def load_users(self):
        """Load authorized users from file"""
        if os.path.exists(self.auth_file):
            try:
                with open(self.auth_file, 'r') as f:
                    self.authorized_users = json.load(f)
            except:
                self.authorized_users = {}
        else:
            # Add main admin if file doesn't exist
            self.authorized_users = {
                str(ADMIN_USER_ID): {
                    "role": "super_admin",
                    "name": "Main Admin",
                    "added_by": "system",
                    "added_date": datetime.now().isoformat(),
                    "channels": []
                }
            }
            self.save_users()
    
    def save_users(self):
        """Save authorized users to file"""
        with open(self.auth_file, 'w') as f:
            json.dump(self.authorized_users, f, indent=2)
    
    def is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return str(user_id) in self.authorized_users
    
    def get_user_role(self, user_id: int) -> Optional[str]:
        """Get user's role"""
        user_data = self.authorized_users.get(str(user_id))
        return user_data.get("role") if user_data else None
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin or super admin"""
        role = self.get_user_role(user_id)
        return role in ["admin", "super_admin"]
    
    def is_super_admin(self, user_id: int) -> bool:
        """Check if user is super admin"""
        return self.get_user_role(user_id) == "super_admin"
    
    def add_user(self, user_id: int, name: str, added_by: int, role: str = "user") -> bool:
        """Add a new authorized user"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            return False
        
        self.authorized_users[user_id_str] = {
            "role": role,
            "name": name,
            "added_by": str(added_by),
            "added_date": datetime.now().isoformat(),
            "channels": []
        }
        self.save_users()
        return True
    
    def remove_user(self, user_id: int) -> bool:
        """Remove an authorized user"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            if self.authorized_users[user_id_str]["role"] == "super_admin":
                return False
            del self.authorized_users[user_id_str]
            self.save_users()
            return True
        return False
    
    def list_users(self) -> List[tuple]:
        """List all authorized users"""
        users = []
        for user_id, data in self.authorized_users.items():
            users.append((int(user_id), data["name"], data["role"], data["added_date"]))
        return users
    
    def update_role(self, user_id: int, new_role: str) -> bool:
        """Update user's role"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            if self.authorized_users[user_id_str]["role"] == "super_admin":
                return False
            self.authorized_users[user_id_str]["role"] = new_role
            self.save_users()
            return True
        return False
    
    def add_user_channel(self, user_id: int, channel_id: str, channel_info: dict) -> bool:
        """Add a channel to user's connected channels"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            if "channels" not in self.authorized_users[user_id_str]:
                self.authorized_users[user_id_str]["channels"] = []
            
            # Check if already connected
            for ch in self.authorized_users[user_id_str]["channels"]:
                if ch["channel_id"] == channel_id:
                    return False
            
            self.authorized_users[user_id_str]["channels"].append(channel_info)
            self.save_users()
            return True
        return False
    
    def get_user_channels(self, user_id: int) -> List[dict]:
        """Get all channels connected by user"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            return self.authorized_users[user_id_str].get("channels", [])
        return []
    
    def remove_user_channel(self, user_id: int, channel_id: str) -> bool:
        """Remove a channel from user's list"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            channels = self.authorized_users[user_id_str].get("channels", [])
            self.authorized_users[user_id_str]["channels"] = [
                ch for ch in channels if ch["channel_id"] != channel_id
            ]
            self.save_users()
            return True
        return False

class ColorfulButtonBot:
    """Main bot class with multi-channel support"""
    
    # Color schemes for buttons
    BUTTON_STYLES = {
        "primary": {"bg_color": "#0088cc", "text_color": "#ffffff"},
        "success": {"bg_color": "#00cc66", "text_color": "#ffffff"},
        "danger": {"bg_color": "#ff4444", "text_color": "#ffffff"},
        "warning": {"bg_color": "#ffaa00", "text_color": "#000000"},
        "info": {"bg_color": "#33b5e5", "text_color": "#ffffff"},
        "purple": {"bg_color": "#aa66cc", "text_color": "#ffffff"},
        "dark": {"bg_color": "#222222", "text_color": "#ffffff"},
        "light": {"bg_color": "#f0f0f0", "text_color": "#000000"},
    }
    
    def __init__(self, token: str):
        self.application = Application.builder().token(token).build()
        self.user_manager = UserManager(AUTH_FILE)
        self.user_sessions = {}  # Store user session data
        self.channel_pending_connection = {}  # Store users waiting to connect channel
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all command and callback handlers"""
        # Public command (only start and auth)
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("auth", self.auth_command))
        
        # Protected commands (require authorization)
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("newpost", self.new_post_command))
        self.application.add_handler(CommandHandler("postnow", self.post_now_command))
        self.application.add_handler(CommandHandler("templates", self.templates_command))
        self.application.add_handler(CommandHandler("channels", self.list_channels_command))
        self.application.add_handler(CommandHandler("connect", self.connect_channel_command))
        self.application.add_handler(CommandHandler("disconnect", self.disconnect_channel_command))
        self.application.add_handler(CommandHandler("setdefault", self.set_default_channel_command))
        
        # Admin commands
        self.application.add_handler(CommandHandler("users", self.list_users_command))
        self.application.add_handler(CommandHandler("adduser", self.add_user_command))
        self.application.add_handler(CommandHandler("removeuser", self.remove_user_command))
        self.application.add_handler(CommandHandler("setadmin", self.set_admin_command))
        
        # Inline mode handler
        self.application.add_handler(InlineQueryHandler(self.inline_query))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handler for forwarded messages (channel connection)
        self.application.add_handler(MessageHandler(
            filters.FORWARDED, self.handle_forwarded_message
        ))
        
        # Message handler for post creation
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, self.handle_post_content
        ))
    
    def check_auth(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return self.user_manager.is_authorized(user_id)
    
    def require_auth(func):
        """Decorator to require authorization"""
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
            user_id = update.effective_user.id
            if not self.check_auth(user_id):
                await update.message.reply_text(
                    "⛔ **Access Denied**\n\n"
                    "You are not authorized to use this bot.\n\n"
                    "Please contact the bot administrator to request access.\n\n"
                    "If you have an authorization code, use:\n"
                    "`/auth YOUR_CODE`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return
            return await func(self, update, context)
        return wrapper
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - Public access"""
        user = update.effective_user
        user_id = user.id
        
        if self.check_auth(user_id):
            # Authorized user
            role = self.user_manager.get_user_role(user_id)
            channels = self.user_manager.get_user_channels(user_id)
            
            welcome_text = f"""
🎨 **Welcome back, {user.first_name}!** 🎨
**Role:** {role.upper()}
**Connected Channels:** {len(channels)}

I can help you create amazing posts with:
• ✨ Colorful inline buttons (8 different colors!)
• 📝 Rich formatting (Markdown & HTML)
• 🖼️ Media support
• 🔄 Inline mode
• 📢 Multi-channel posting

**Commands:**
/newpost - Start creating a new post
/templates - View post templates
/channels - Manage your channels
/postnow - Post to channel
/help - Detailed help

**Channel Management:**
/connect - Connect a channel (forward a message)
/disconnect - Remove a channel
/setdefault - Set default channel

**Admin Commands** (Admins only):
/users - List authorized users
/adduser - Add new user
/removeuser - Remove user
/setadmin - Make user admin
            """
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
        else:
            # Unauthorized user
            await update.message.reply_text(
                f"🔐 **Welcome {user.first_name}** 🔐\n\n"
                "This bot is restricted to authorized users only.\n\n"
                "**How to get access:**\n"
                "1. Contact the bot administrator\n"
                "2. If you have an authorization code, use:\n"
                "   `/auth YOUR_CODE`\n\n"
                "**Administrator Contact:**\n"
                f"Main Admin ID: `{ADMIN_USER_ID}`\n\n"
                "*Note: Only the bot owner can grant access.*",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle authorization - Public access"""
        user = update.effective_user
        user_id = user.id
        
        if self.check_auth(user_id):
            await update.message.reply_text(
                "✅ You are already authorized!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ Please provide an authorization code.\n"
                "Usage: `/auth YOUR_CODE`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        auth_code = args[0]
        
        # Example authorization code (you can make this dynamic per user)
        VALID_CODE = "COOLPOST2024"
        
        if auth_code == VALID_CODE:
            success = self.user_manager.add_user(
                user_id, 
                user.full_name, 
                ADMIN_USER_ID, 
                "user"
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ **Authorization Successful!**\n\n"
                    f"Welcome {user.first_name}! You now have access to the bot.\n\n"
                    "**Next Steps:**\n"
                    "1. Add this bot as admin to your channel\n"
                    "2. Use `/connect` and forward a message from your channel\n"
                    "3. Start creating amazing posts!\n\n"
                    "Use /help to get started.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ Error adding user. Please contact administrator."
                )
        else:
            await update.message.reply_text(
                "❌ **Invalid Authorization Code**\n\n"
                "Please check your code and try again.\n"
                "Contact administrator if you need access.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def connect_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Connect a channel by forwarding a message"""
        user_id = update.effective_user.id
        
        if not self.check_auth(user_id):
            return
        
        await update.message.reply_text(
            "🔗 **Connect a Channel** 🔗\n\n"
            "To connect your channel to this bot:\n\n"
            "1. **Add this bot as admin** to your channel\n"
            "2. **Forward any message** from that channel to this chat\n"
            "3. The bot will automatically detect and connect the channel\n\n"
            "**Important:**\n"
            "• Bot needs 'Post Messages' permission\n"
            "• You can connect multiple channels\n"
            "• Each user can manage their own channels\n\n"
            "*Forward a message from your channel now...*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        self.channel_pending_connection[user_id] = True
    
    async def handle_forwarded_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle forwarded messages for channel connection"""
        user_id = update.effective_user.id
        
        if not self.check_auth(user_id):
            await update.message.reply_text("⛔ You are not authorized!")
            return
        
        # Check if user is trying to connect a channel
        if user_id not in self.channel_pending_connection:
            return
        
        forwarded_msg = update.message.forward_from_chat
        
        if not forwarded_msg:
            await update.message.reply_text(
                "❌ Please forward a message from the channel, not from a user!"
            )
            return
        
        channel_id = forwarded_msg.id
        channel_title = forwarded_msg.title or f"Channel_{channel_id}"
        channel_username = forwarded_msg.username
        
        # Try to get more channel info
        try:
            chat = await context.bot.get_chat(channel_id)
            channel_title = chat.title
            channel_username = chat.username
        except:
            pass
        
        # Check if bot is admin in the channel
        try:
            bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
            if bot_member.status not in ['administrator', 'creator']:
                await update.message.reply_text(
                    "❌ **Bot is not an admin in this channel!**\n\n"
                    "Please add this bot as an admin to your channel first.\n\n"
                    "**Required permissions:**\n"
                    "• Post Messages\n"
                    "• Edit Messages (optional)\n"
                    "• Delete Messages (optional)",
                    parse_mode=ParseMode.MARKDOWN
                )
                del self.channel_pending_connection[user_id]
                return
        except BadRequest as e:
            await update.message.reply_text(
                f"❌ **Cannot verify bot permissions!**\n\n"
                f"Error: {str(e)}\n\n"
                f"Make sure:\n"
                f"• Bot is added as admin to the channel\n"
                f"• Channel is not private/super-private\n"
                f"• You forwarded a message from the correct channel",
                parse_mode=ParseMode.MARKDOWN
            )
            del self.channel_pending_connection[user_id]
            return
        
        # Save channel to user's connected channels
        channel_info = {
            "channel_id": str(channel_id),
            "channel_title": channel_title,
            "channel_username": channel_username,
            "connected_date": datetime.now().isoformat(),
            "is_default": len(self.user_manager.get_user_channels(user_id)) == 0  # First channel becomes default
        }
        
        success = self.user_manager.add_user_channel(user_id, str(channel_id), channel_info)
        
        if success:
            default_text = " (Set as Default)" if channel_info["is_default"] else ""
            
            await update.message.reply_text(
                f"✅ **Channel Connected Successfully!**{default_text}\n\n"
                f"**Channel:** {channel_title}\n"
                f"**ID:** `{channel_id}`\n"
                f"**Username:** @{channel_username if channel_username else 'N/A'}\n\n"
                f"**What's Next?**\n"
                f"• Use `/postnow` to post to this channel\n"
                f"• Use `/channels` to manage all your channels\n"
                f"• Use `/setdefault` to change default channel\n"
                f"• Use `/disconnect` to remove this channel\n\n"
                f"*You can connect multiple channels to the bot!*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "⚠️ **Channel already connected!**\n\n"
                "Use `/channels` to see your connected channels.",
                parse_mode=ParseMode.MARKDOWN
            )
        
        # Clear pending connection
        del self.channel_pending_connection[user_id]
    
    async def list_channels_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all connected channels for the user"""
        user_id = update.effective_user.id
        
        if not self.check_auth(user_id):
            return
        
        channels = self.user_manager.get_user_channels(user_id)
        
        if not channels:
            await update.message.reply_text(
                "📢 **No Channels Connected** 📢\n\n"
                "You haven't connected any channels yet.\n\n"
                "**To connect a channel:**\n"
                "1. Add this bot as admin to your channel\n"
                "2. Use `/connect` command\n"
                "3. Forward a message from your channel\n\n"
                "The bot will automatically detect and connect it!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        channel_list = "📢 **Your Connected Channels** 📢\n\n"
        
        for i, channel in enumerate(channels, 1):
            default_mark = " ⭐ (Default)" if channel.get("is_default", False) else ""
            channel_list += f"{i}. **{channel['channel_title']}**{default_mark}\n"
            channel_list += f"   ID: `{channel['channel_id']}`\n"
            if channel.get('channel_username'):
                channel_list += f"   Username: @{channel['channel_username']}\n"
            channel_list += f"   Connected: {channel['connected_date'][:10]}\n\n"
        
        keyboard = []
        for channel in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"📤 Post to {channel['channel_title'][:20]}",
                    callback_data=f"post_to_{channel['channel_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("➕ Connect New Channel", callback_data="connect_channel")])
        
        await update.message.reply_text(
            channel_list,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def disconnect_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Disconnect a channel"""
        user_id = update.effective_user.id
        
        if not self.check_auth(user_id):
            return
        
        channels = self.user_manager.get_user_channels(user_id)
        
        if not channels:
            await update.message.reply_text("❌ You don't have any connected channels!")
            return
        
        keyboard = []
        for channel in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {channel['channel_title'][:30]}",
                    callback_data=f"disconnect_{channel['channel_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel_disconnect")])
        
        await update.message.reply_text(
            "🗑️ **Select channel to disconnect:**\n\n"
            "This will remove the channel from your bot access.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def set_default_channel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Set default channel for posting"""
        user_id = update.effective_user.id
        
        if not self.check_auth(user_id):
            return
        
        channels = self.user_manager.get_user_channels(user_id)
        
        if not channels:
            await update.message.reply_text("❌ You don't have any connected channels!")
            return
        
        keyboard = []
        for channel in channels:
            default_mark = " ⭐" if channel.get("is_default", False) else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 {channel['channel_title'][:30]}{default_mark}",
                    callback_data=f"setdefault_{channel['channel_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel_default")])
        
        await update.message.reply_text(
            "⭐ **Set Default Channel** ⭐\n\n"
            "Select which channel should be your default for posting.\n"
            "The default channel will be used when you don't specify one.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @require_auth
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        is_admin = self.user_manager.is_admin(user_id)
        
        help_text = """
📚 **Detailed Help Guide**

**Channel Management:**
/connect - Connect a new channel (forward a message)
/channels - List your connected channels
/disconnect - Remove a connected channel
/setdefault - Set default channel for posting

**Creating Posts:**
1. Use `/newpost` and follow the wizard
2. Choose post type (text, media, or mixed)
3. Add your content with formatting
4. Add colorful buttons using HTML tags
5. Post to channel or copy the message

**Colorful Buttons - Use HTML tags:**
- `<button primary>Click Me</button>` - Blue button
- `<button success>Success</button>` - Green button  
- `<button danger>Delete</button>` - Red button
- `<button warning>Warning</button>` - Yellow button
- `<button info>Info</button>` - Light blue
- `<button purple>Special</button>` - Purple button
- `<button dark>Dark Mode</button>` - Dark button
- `<button light>Light Mode</button>` - White button

**URL Buttons:**
`<url primary>https://example.com|Visit Site</url>`

**Post Templates:**
• Announcement template
• Poll with voting buttons
• Product showcase
• Countdown timer

**Examples:**
