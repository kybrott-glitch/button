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
BOT_TOKEN = "8651990559:AAHk3DToBDJCgz57OJf88AtqcLLiS-S2myk"  # Replace with your bot token
ADMIN_USER_ID = 1899208318  # Replace with your Telegram user ID (Main Admin)

# File to store data
AUTH_FILE = "authorized_users.json"

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
    
    def set_default_channel(self, user_id: int, channel_id: str) -> bool:
        """Set a channel as default for user"""
        user_id_str = str(user_id)
        if user_id_str in self.authorized_users:
            channels = self.authorized_users[user_id_str].get("channels", [])
            for ch in channels:
                ch["is_default"] = (ch["channel_id"] == channel_id)
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
        self.user_sessions = {}
        self.channel_pending_connection = {}
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
            role = self.user_manager.get_user_role(user_id)
            channels = self.user_manager.get_user_channels(user_id)
            
            welcome_text = (
                f"🎨 **Welcome back, {user.first_name}!** 🎨\n"
                f"**Role:** {role.upper()}\n"
                f"**Connected Channels:** {len(channels)}\n\n"
                "I can help you create amazing posts with:\n"
                "• ✨ Colorful inline buttons (8 different colors!)\n"
                "• 📝 Rich formatting (Markdown & HTML)\n"
                "• 🖼️ Media support\n"
                "• 🔄 Inline mode\n"
                "• 📢 Multi-channel posting\n\n"
                "**Commands:**\n"
                "/newpost - Start creating a new post\n"
                "/templates - View post templates\n"
                "/channels - Manage your channels\n"
                "/postnow - Post to channel\n"
                "/help - Detailed help\n\n"
                "**Channel Management:**\n"
                "/connect - Connect a channel (forward a message)\n"
                "/disconnect - Remove a channel\n"
                "/setdefault - Set default channel\n\n"
                "**Admin Commands** (Admins only):\n"
                "/users - List authorized users\n"
                "/adduser - Add new user\n"
                "/removeuser - Remove user\n"
                "/setadmin - Make user admin"
            )
            await update.message.reply_text(
                welcome_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
        else:
            await update.message.reply_text(
                f"🔐 **Welcome {user.first_name}** 🔐\n\n"
                "This bot is restricted to authorized users only.\n\n"
                "**How to get access:**\n"
                "1. Contact the bot administrator\n"
                "2. If you have an authorization code, use:\n"
                "   `/auth YOUR_CODE`\n\n"
                f"**Administrator Contact:**\nMain Admin ID: `{ADMIN_USER_ID}`\n\n"
                "*Note: Only the bot owner can grant access.*",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def auth_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle authorization - Public access"""
        user = update.effective_user
        user_id = user.id
        
        if self.check_auth(user_id):
            await update.message.reply_text("✅ You are already authorized!")
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
                await update.message.reply_text("❌ Error adding user. Please contact administrator.")
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
        
        if user_id not in self.channel_pending_connection:
            return
        
        forwarded_msg = update.message.forward_from_chat
        
        if not forwarded_msg:
            await update.message.reply_text("❌ Please forward a message from the channel, not from a user!")
            return
        
        channel_id = forwarded_msg.id
        channel_title = forwarded_msg.title or f"Channel_{channel_id}"
        channel_username = forwarded_msg.username
        
        try:
            chat = await context.bot.get_chat(channel_id)
            channel_title = chat.title
            channel_username = chat.username
        except:
            pass
        
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
                f"• Channel is not private\n"
                f"• You forwarded a message from the correct channel",
                parse_mode=ParseMode.MARKDOWN
            )
            del self.channel_pending_connection[user_id]
            return
        
        channel_info = {
            "channel_id": str(channel_id),
            "channel_title": channel_title,
            "channel_username": channel_username,
            "connected_date": datetime.now().isoformat(),
            "is_default": len(self.user_manager.get_user_channels(user_id)) == 0
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
                f"• Use `/disconnect` to remove this channel",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                "⚠️ **Channel already connected!**\n\n"
                "Use `/channels` to see your connected channels.",
                parse_mode=ParseMode.MARKDOWN
            )
        
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
        
        await update.message.reply_text(
            channel_list,
            parse_mode=ParseMode.MARKDOWN
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
        
        help_text = (
            "📚 **Detailed Help Guide**\n\n"
            "**Channel Management:**\n"
            "/connect - Connect a new channel (forward a message)\n"
            "/channels - List your connected channels\n"
            "/disconnect - Remove a connected channel\n"
            "/setdefault - Set default channel for posting\n\n"
            "**Creating Posts:**\n"
            "1. Use `/newpost` and follow the wizard\n"
            "2. Choose post type (text, media, or mixed)\n"
            "3. Add your content with formatting\n"
            "4. Add colorful buttons using HTML tags\n"
            "5. Post to channel or copy the message\n\n"
            "**Colorful Buttons - Use HTML tags:**\n"
            "- `<button primary>Click Me</button>` - Blue button\n"
            "- `<button success>Success</button>` - Green button\n"
            "- `<button danger>Delete</button>` - Red button\n"
            "- `<button warning>Warning</button>` - Yellow button\n"
            "- `<button info>Info</button>` - Light blue\n"
            "- `<button purple>Special</button>` - Purple button\n"
            "- `<button dark>Dark Mode</button>` - Dark button\n"
            "- `<button light>Light Mode</button>` - White button\n\n"
            "**URL Buttons:**\n"
            "`<url primary>https://example.com|Visit Site</url>`\n\n"
            "**Post Templates:**\n"
            "• Announcement template\n"
            "• Poll with voting buttons\n"
            "• Product showcase\n"
            "• Countdown timer\n\n"
            "**Examples:**\n"
            "Check out this amazing deal!\n"
            "<button success>Buy Now</button>\n"
            "<button info>Learn More</button>"
        )
        
        if is_admin:
            help_text += (
                "\n\n**Admin Commands:**\n"
                "/users - List all authorized users\n"
                "/adduser - Add new user (by ID)\n"
                "/removeuser - Remove user (by ID)\n"
                "/setadmin - Make user admin"
            )
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    
    def get_main_keyboard(self):
        """Create main keyboard with colorful buttons"""
        keyboard = [
            [
                InlineKeyboardButton("📝 New Post", callback_data="new_post"),
                InlineKeyboardButton("📋 Templates", callback_data="templates")
            ],
            [
                InlineKeyboardButton("📢 My Channels", callback_data="list_channels"),
                InlineKeyboardButton("🔗 Connect Channel", callback_data="connect_channel")
            ],
            [
                InlineKeyboardButton("🎨 Color Guide", callback_data="color_guide"),
                InlineKeyboardButton("💡 Examples", callback_data="examples")
            ],
            [
                InlineKeyboardButton("🚀 Post Now", callback_data="post_to_channel"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @require_auth
    async def new_post_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start new post creation process"""
        keyboard = [
            [
                InlineKeyboardButton("📝 Text Only", callback_data="post_text"),
                InlineKeyboardButton("🖼️ With Photo", callback_data="post_photo")
            ],
            [
                InlineKeyboardButton("🎥 With Video", callback_data="post_video"),
                InlineKeyboardButton("📊 Poll Style", callback_data="post_poll")
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")
            ]
        ]
        
        await update.message.reply_text(
            "🎨 **Choose Post Type**\n\n"
            "What kind of post would you like to create?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['post_type'] = None
        context.user_data['post_content'] = None
    
    @require_auth
    async def templates_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show post templates"""
        templates = (
            "📋 **Available Post Templates**\n\n"
            "**1. Announcement Template:**\n"
            "```\n"
            "📢 **ANNOUNCEMENT** 📢\n\n"
            "{message}\n\n"
            "<button primary>Learn More</button>\n"
            "<button success>Register</button>\n"
            "```\n\n"
            "**2. Poll/Voting Template:**\n"
            "```\n"
            "🗳️ **Community Vote** 🗳️\n\n"
            "Topic: {topic}\n\n"
            "<button success>✅ Yes</button>\n"
            "<button danger>❌ No</button>\n"
            "<button info>🤔 Maybe</button>\n"
            "```\n\n"
            "**3. Product Showcase:**\n"
            "```\n"
            "✨ **New Product Alert** ✨\n\n"
            "{product_name}\n"
            "{description}\n\n"
            "<button primary>🛒 Buy Now</button>\n"
            "<button info>ℹ️ Details</button>\n"
            "```\n\n"
            "**4. Countdown/Event:**\n"
            "```\n"
            "⏰ **Event Countdown** ⏰\n\n"
            "Event: {event_name}\n"
            "Time: {time}\n\n"
            "<button primary>📅 Add to Calendar</button>\n"
            "<button info>🔔 Remind Me</button>\n"
            "```"
        )
        
        await update.message.reply_text(
            templates,
            parse_mode=ParseMode.MARKDOWN
        )
    
    def parse_button_markup(self, text: str) -> tuple:
        """Parse custom button markup and return (clean_text, buttons)"""
        buttons = []
        clean_text = text
        
        button_pattern = r'<button\s+(\w+)>(.*?)</button>'
        url_pattern = r'<url\s+(\w+)>(.*?)\|(.*?)</url>'
        
        for match in re.finditer(url_pattern, text):
            color = match.group(1)
            url = match.group(2)
            button_text = match.group(3)
            
            if color in self.BUTTON_STYLES:
                buttons.append(InlineKeyboardButton(button_text, url=url))
                clean_text = clean_text.replace(match.group(0), '')
        
        for match in re.finditer(button_pattern, text):
            color = match.group(1)
            button_text = match.group(2)
            
            if color in self.BUTTON_STYLES:
                callback_data = f"btn_{color}_{button_text[:20]}"
                buttons.append(InlineKeyboardButton(button_text, callback_data=callback_data))
                clean_text = clean_text.replace(match.group(0), '')
        
        clean_text = re.sub(r'\n\s*\n', '\n\n', clean_text).strip()
        button_rows = [buttons[i:i+3] for i in range(0, len(buttons), 3)]
        
        return clean_text, button_rows
    
    async def post_to_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE, 
                              channel_id: str = None, user_id: int = None):
        """Post content to specified channel"""
        if user_id is None:
            user_id = update.effective_user.id
        
        if not context.user_data.get('post_content'):
            await update.message.reply_text("❌ No post created yet!\nUse /newpost first.")
            return False
        
        channels = self.user_manager.get_user_channels(user_id)
        
        if not channels:
            await update.message.reply_text(
                "❌ **No channels connected!**\n\n"
                "Please connect a channel first using `/connect`",
                parse_mode=ParseMode.MARKDOWN
            )
            return False
        
        target_channel = None
        
        if channel_id:
            for channel in channels:
                if channel["channel_id"] == channel_id:
                    target_channel = channel
                    break
        else:
            for channel in channels:
                if channel.get("is_default", False):
                    target_channel = channel
                    break
            if not target_channel and channels:
                target_channel = channels[0]
        
        if not target_channel:
            await update.message.reply_text("❌ No valid channel found!")
            return False
        
        try:
            content = context.user_data['post_content']
            clean_text, button_rows = self.parse_button_markup(content)
            reply_markup = InlineKeyboardMarkup(button_rows) if button_rows else None
            
            result = await context.bot.send_message(
                chat_id=target_channel["channel_id"],
                text=clean_text,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
            
            if update.message:
                await update.message.reply_text(
                    f"✅ **Post published successfully!**\n\n"
                    f"**Channel:** {target_channel['channel_title']}\n"
                    f"**Message ID:** {result.message_id}",
                    parse_mode=ParseMode.MARKDOWN
                )
            return True
            
        except Exception as e:
            error_msg = f"❌ Error posting to channel: {str(e)}"
            if update.message:
                await update.message.reply_text(error_msg)
            return False
    
    @require_auth
    async def post_now_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post to channel with channel selection"""
        user_id = update.effective_user.id
        channels = self.user_manager.get_user_channels(user_id)
        
        if not channels:
            await update.message.reply_text(
                "❌ **No channels connected!**\n\n"
                "Please connect a channel first using `/connect`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        if not context.user_data.get('post_content'):
            await update.message.reply_text("❌ No post created yet!\nUse /newpost first.")
            return
        
        keyboard = []
        for channel in channels:
            default_mark = " ⭐" if channel.get("is_default", False) else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 {channel['channel_title'][:30]}{default_mark}",
                    callback_data=f"post_to_{channel['channel_id']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="cancel_post")])
        
        await update.message.reply_text(
            "📢 **Select Channel to Post** 📢\n\n"
            "Choose which channel you want to post to:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    @require_auth
    async def handle_post_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user's post content input"""
        content = update.message.text
        
        if '<button' in content or '<url' in content:
            context.user_data['post_content'] = content
            await self.create_colored_post(update, content)
            
            keyboard = [
                [
                    InlineKeyboardButton("📢 Post to Channel", callback_data="post_to_channel"),
                    InlineKeyboardButton("📋 Copy Message", callback_data="copy_message")
                ],
                [InlineKeyboardButton("🔄 Edit Post", callback_data="edit_post")]
            ]
            
            await update.message.reply_text(
                "✨ **Post Created!** ✨\n\n"
                "What would you like to do next?",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text(
                "⚠️ Please use button markup!\n\n"
                "Example:\n"
                "`<button primary>Click Me</button>`\n\n"
                "Use /help to see all options.",
                parse_mode=ParseMode.MARKDOWN
            )
    
    @require_auth
    async def create_colored_post(self, update: Update, content: str, 
                                  media_url: str = None, media_type: str = None):
        """Create and send a post with colored buttons"""
        clean_text, button_rows = self.parse_button_markup(content)
        reply_markup = InlineKeyboardMarkup(button_rows) if button_rows else None
        
        await update.message.reply_text(
            clean_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup,
            disable_web_page_preview=False
        )
    
    @require_auth
    async def inline_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline queries"""
        user_id = update.effective_user.id
        
        if not self.check_auth(user_id):
            await update.inline_query.answer([], cache_time=0)
            return
        
        query = update.inline_query.query
        results = []
        
        if not query:
            templates = [
                ("simple", "Simple text with button", 
                 "Hello World!\n\n<button primary>Click Me</button>"),
                ("announcement", "Announcement template",
                 "📢 **Announcement**\n\nImportant message here!\n\n<button primary>Read More</button>"),
                ("poll", "Quick poll",
                 "🗳️ **Quick Poll**\n\nDo you agree?\n\n<button success>✅ Yes</button>\n<button danger>❌ No</button>"),
            ]
            
            for template_id, title, content in templates:
                clean_text, button_rows = self.parse_button_markup(content)
                reply_markup = InlineKeyboardMarkup(button_rows) if button_rows else None
                
                results.append(
                    InlineQueryResultArticle(
                        id=template_id,
                        title=title,
                        input_message_content=InputTextMessageContent(
                            clean_text,
                            parse_mode=ParseMode.MARKDOWN
                        ),
                        reply_markup=reply_markup,
                        description=f"Template: {title}"
                    )
                )
        else:
            clean_text, button_rows = self.parse_button_markup(query)
            reply_markup = InlineKeyboardMarkup(button_rows) if button_rows else None
            
            results.append(
                InlineQueryResultArticle(
                    id="colored_post",
                    title="🎨 Colored Post",
                    input_message_content=InputTextMessageContent(
                        clean_text,
                        parse_mode=ParseMode.MARKDOWN
                    ),
                    reply_markup=reply_markup,
                    description=query[:50]
                )
            )
        
        await update.inline_query.answer(results, cache_time=5)
    
    # Admin Commands
    
    @require_auth
    async def list_users_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all authorized users (Admin only)"""
        user_id = update.effective_user.id
        
        if not self.user_manager.is_admin(user_id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        users = self.user_manager.list_users()
        
        if not users:
            await update.message.reply_text("No authorized users found.")
            return
        
        user_list = "👥 **Authorized Users**\n\n"
        for uid, name, role, date in users:
            user_list += f"**ID:** `{uid}`\n"
            user_list += f"**Name:** {name}\n"
            user_list += f"**Role:** {role.upper()}\n"
            user_list += f"**Added:** {date[:10]}\n"
            user_list += "───────────\n"
        
        await update.message.reply_text(user_list, parse_mode=ParseMode.MARKDOWN)
    
    @require_auth
    async def add_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Add a new user (Admin only)"""
        user_id = update.effective_user.id
        
        if not self.user_manager.is_admin(user_id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Usage: `/adduser USER_ID USER_NAME`\n"
                "Example: `/adduser 123456789 John Doe`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            new_user_id = int(args[0])
            new_user_name = ' '.join(args[1:])
            
            success = self.user_manager.add_user(
                new_user_id,
                new_user_name,
                user_id,
                "user"
            )
            
            if success:
                await update.message.reply_text(
                    f"✅ **User Added Successfully!**\n\n"
                    f"ID: `{new_user_id}`\n"
                    f"Name: {new_user_name}\n"
                    f"Role: USER\n\n"
                    f"They can now use the bot.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ User already exists or invalid data.")
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID! Must be a number.")
    
    @require_auth
    async def remove_user_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Remove a user (Admin only)"""
        user_id = update.effective_user.id
        
        if not self.user_manager.is_admin(user_id):
            await update.message.reply_text("⛔ Admin access required!")
            return
        
        args = context.args
        if not args:
            await update.message.reply_text(
                "❌ Usage: `/removeuser USER_ID`\n"
                "Example: `/removeuser 123456789`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            remove_user_id = int(args[0])
            success = self.user_manager.remove_user(remove_user_id)
            
            if success:
                await update.message.reply_text(
                    f"✅ **User Removed Successfully!**\n\n"
                    f"ID: `{remove_user_id}`\n\n"
                    f"This user can no longer access the bot.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ User not found or cannot remove super admin.")
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID! Must be a number.")
    
    @require_auth
    async def set_admin_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Make a user admin (Super Admin only)"""
        user_id = update.effective_user.id
        
        if not self.user_manager.is_super_admin(user_id):
            await update.message.reply_text("⛔ Super Admin access required!")
            return
        
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Usage: `/setadmin USER_ID ROLE`\n"
                "Roles: `admin`, `user`\n"
                "Example: `/setadmin 123456789 admin`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        try:
            target_user_id = int(args[0])
            new_role = args[1].lower()
            
            if new_role not in ["admin", "user"]:
                await update.message.reply_text("❌ Invalid role! Use 'admin' or 'user'.")
                return
            
            success = self.user_manager.update_role(target_user_id, new_role)
            
            if success:
                await update.message.reply_text(
                    f"✅ **User Role Updated!**\n\n"
                    f"ID: `{target_user_id}`\n"
                    f"New Role: {new_role.upper()}\n\n"
                    f"The user's permissions have been updated.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text("❌ Cannot update role. User not found or is super admin.")
        except ValueError:
            await update.message.reply_text("❌ Invalid User ID! Must be a number.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self.check_auth(user_id):
            await query.answer("⛔ You are not authorized to use this bot!", show_alert=True)
            return
        
        await query.answer()
        data = query.data
        
        if data.startswith("btn_"):
            parts = data.split('_', 2)
            if len(parts) >= 2:
                color = parts[1]
                await query.edit_message_text(
                    text=f"You clicked the {color} button!\n\nOriginal message:\n{query.message.text}",
                    parse_mode=ParseMode.MARKDOWN
                )
        
        elif data == "new_post":
            await self.new_post_command(update, context)
        
        elif data == "templates":
            await self.templates_command(update, context)
        
        elif data == "list_channels":
            await self.list_channels_command(update, context)
        
        elif data == "connect_channel":
            await self.connect_channel_command(update, context)
        
        elif data == "post_to_channel":
            await self.post_now_command(update, context)
        
        elif data.startswith("post_to_"):
            channel_id = data[8:]
            context.user_data['post_content'] = context.user_data.get('post_content', 'Test post with buttons!\n\n<button primary>Click Me</button>')
            await self.post_to_channel(update, context, channel_id, user_id)
        
        elif data.startswith("disconnect_"):
            channel_id = data[11:]
            success = self.user_manager.remove_user_channel(user_id, channel_id)
            if success:
                await query.message.reply_text(f"✅ Channel disconnected successfully!")
            else:
                await query.message.reply_text(f"❌ Failed to disconnect channel.")
        
        elif data.startswith("setdefault_"):
            channel_id = data[11:]
            success = self.user_manager.set_default_channel(user_id, channel_id)
            if success:
                await query.message.reply_text(f"⭐ Default channel updated successfully!")
            else:
                await query.message.reply_text(f"❌ Failed to update default channel.")
        
        elif data == "copy_message":
            content = context.user_data.get('post_content', 'No content')
            await query.message.reply_text(
                f"📋 **Copy this message:**\n\n"
                f"```\n{content}\n```",
                parse_mode=ParseMode.MARKDOWN
            )
        
        elif data == "color_guide":
            guide = "🎨 **Color Guide** 🎨\n\n"
            for color in self.BUTTON_STYLES.keys():
                guide += f"• `{color}` - {color.upper()} button\n"
            guide += "\n**Usage:**\n`<button color>Your Text</button>`"
            await query.message.reply_text(guide, parse_mode=ParseMode.MARKDOWN)
        
        elif data == "examples":
            await self.templates_command(update, context)
        
        elif data == "help":
            await self.help_command(update, context)
        
        elif data in ["cancel_post", "cancel_disconnect", "cancel_default", "edit_post", "back_to_menu"]:
            await query.message.reply_text("Operation cancelled.")
    
    async def run(self):
        """Start the bot"""
        logger.info("Bot is starting...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Bot is running!")
        await asyncio.Event().wait()

def main():
    """Main function to run the bot"""
    bot = ColorfulButtonBot(BOT_TOKEN)
    asyncio.run(bot.run())

if __name__ == '__main__':
    main()
