import discord
from discord.ext import commands
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_socketio import SocketIO
import threading
import asyncio
import os

# 設定機器人
bot = discord.Bot(intents=discord.Intents.all())

# 輔助函數：格式化數據為 JSON
def _format_user(user):
    if not user: return None
    return {
        "id": user.id,
        "username": user.name,
        "discriminator": f"#{user.discriminator}" if user.discriminator != "0" else "",
        "avatar_url": user.display_avatar.url if hasattr(user, "display_avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"
    }

def _format_guild(guild):
    return {
        "id": str(guild.id),
        "name": guild.name,
        "icon_url": guild.icon.url if guild.icon else None
    }

def _format_channel(channel):
    return {
        "id": str(channel.id),
        "name": channel.name,
        "topic": channel.topic or ""
    }

def _format_message(m):
    atts = []
    for a in getattr(m, "attachments", []):
        atts.append({
            "url": a.url,
            "filename": a.filename,
            "is_image": a.content_type and a.content_type.startswith("image"),
        })
    embeds = []
    for e in getattr(m, "embeds", []):
        embeds.append({
            "image_url": e.image.url if getattr(e, "image", None) and e.image.url else None,
            "title": getattr(e, "title", None),
            "description": getattr(e, "description", None),
        })
    return {
        "id": str(m.id),
        "author": str(m.author),
        "avatar_url": m.author.display_avatar.url if hasattr(m.author, "display_avatar") else (m.author.avatar_url if hasattr(m.author, "avatar_url") else ""),
        "content": m.content, 
        "attachments": atts,
        "embeds": embeds,
        "is_bot": m.author.bot,
        "created_at": m.created_at.isoformat(),
        "channel_id": str(m.channel.id),
        "guild_id": str(m.guild.id) if m.guild else None
    }

def _format_member(member):
    highest_role_position = 0
    display_role_name = "線上"
    if str(member.status) == 'offline':
        display_role_name = "離線"
    else:
        found_higher_role = False
        for role in member.roles:
            if role.position > highest_role_position:
                highest_role_position = role.position
                display_role_name = role.name
                found_higher_role = True
        if not found_higher_role or display_role_name == "@everyone":
            display_role_name = "線上"

    return {
        "id": str(member.id),
        "name": member.name,
        "display_name": member.display_name or member.name,
        "avatar_url": member.display_avatar.url if hasattr(member, "display_avatar") else "https://cdn.discordapp.com/embed/avatars/0.png",
        "is_bot": member.bot,
        "status": str(member.status),
        "highest_role_name": display_role_name,
        "color": str(member.color) if member.color.value != 0 else "",
    }

class Backend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = Flask("discord_backend")
        self.loop = bot.loop
        CORS(self.app)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')

        # --- 路由 ---

        @self.app.route("/")
        @self.app.route("/guild/<path:subpath>") # 支援前端路由刷新
        def index(subpath=None):
            # 讀取 index.html 檔案內容並回傳
            try:
                with open("index.html", "r", encoding="utf-8") as f:
                    return f.read()
            except FileNotFoundError:
                return "index.html not found. Please ensure the file is in the same directory."

        # API: 初始化 (取得使用者資訊與伺服器列表)
        @self.app.route("/api/init")
        def api_init():
            guilds = [_format_guild(g) for g in bot.guilds]
            return jsonify({
                "user": _format_user(self.bot.user),
                "guilds": guilds
            })

        # API: 取得特定伺服器資訊與頻道列表
        @self.app.route("/api/guild/<int:guild_id>")
        def api_guild(guild_id):
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return jsonify({"error": "Guild not found"}), 404
            
            channels = [c for c in guild.text_channels]
            return jsonify({
                "guild": _format_guild(guild),
                "channels": [_format_channel(c) for c in channels]
            })

        # API: 取得訊息
        @self.app.route("/api/guild/<int:guild_id>/channel/<int:channel_id>/messages")
        def api_messages(guild_id, channel_id):
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return jsonify({"messages": []})
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return jsonify({"messages": []})

            before = request.args.get("before", type=int)
            limit = 50
            
            async def fetch():
                kwargs = {"limit": limit}
                if before: kwargs["before"] = discord.Object(id=before)
                return [m async for m in channel.history(**kwargs)]
            
            fut = asyncio.run_coroutine_threadsafe(fetch(), self.loop)
            try:
                messages = fut.result(timeout=10)
            except Exception:
                messages = []

            return jsonify({"messages": [_format_message(m) for m in reversed(messages)]})

        # API: 取得成員列表
        @self.app.route("/api/guild/<int:guild_id>/channel/<int:channel_id>/members")
        def api_members(guild_id, channel_id):
            try:
                guild = discord.utils.get(bot.guilds, id=guild_id)
                if not guild: return jsonify({"members": []}), 404
                channel = discord.utils.get(guild.text_channels, id=channel_id)
                if not channel: return jsonify({"members": []}), 404

                # 簡單過濾：只顯示能看見該頻道的成員
                readable_members = [
                    member for member in guild.members
                    if channel.permissions_for(member).read_messages
                ]
                return jsonify({"members": [_format_member(m) for m in readable_members]})
            except Exception as e:
                return jsonify({"members": [], "error": str(e)}), 500

        # API: 發送訊息
        @self.app.route("/api/guild/<int:guild_id>/channel/<int:channel_id>/send", methods=["POST"])
        def api_send(guild_id, channel_id):
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return jsonify({"ok": False}), 404
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return jsonify({"ok": False}), 404

            content = request.form.get("content", "")
            files = request.files.getlist("file")
            sent_message = None

            async def send():
                nonlocal sent_message
                discord_files = [discord.File(f.stream, filename=f.filename) for f in files if f.filename]
                if discord_files:
                    sent_message = await channel.send(content=content, files=discord_files)
                elif content:
                    sent_message = await channel.send(content=content)

            fut = asyncio.run_coroutine_threadsafe(send(), self.loop)
            try:
                fut.result(timeout=10)
                if sent_message:
                    return jsonify({"ok": True, "message": _format_message(sent_message)})
                else:
                    return jsonify({"ok": False}), 400
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500

        # 啟動 Flask
        threading.Thread(target=lambda: self.socketio.run(self.app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True), daemon=True).start()
        
        # Discord 事件監聽
        @self.bot.event
        async def on_message(message):
            if message.guild:
                formatted_msg = _format_message(message)
                self.socketio.emit('new_message', formatted_msg)

def setup(bot):
    bot.add_cog(Backend(bot))
