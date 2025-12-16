import discord
from discord.ext import commands
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO
import threading
import asyncio
import re
from datetime import datetime

bot = discord.Bot(intents=discord.Intents.all())

# -------------------------------------------------------------------
# HTML 模板
# -------------------------------------------------------------------
HTML_MESSAGES = """
<div id="channel-data" data-channel-name="{{ channel.name }}" data-channel-id="{{ channel.id }}" data-guild-id="{{ guild.id }}" style="display:none;"></div>

<div class="chat-header">
    <div class="mobile-menu-btn" id="mobile-menu-trigger">
        <svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"></path></svg>
    </div>
    
    <div class="chat-header-left">
        <span class="hashtag-symbol">#</span>
        <span class="chat-header-title">{{ channel.name }}</span>
        {% if channel.topic %}
        <span class="chat-header-divider">|</span>
        <span class="chat-header-topic">{{ channel.topic }}</span>
        {% endif %}
    </div>
    
    <div class="chat-header-right">
        <div class="icon-item" id="member-toggle-btn" title="切換成員名單">
            <svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" fill-rule="evenodd" clip-rule="evenodd" d="M14 8.00598C14 10.211 12.206 12.006 10 12.006C7.795 12.006 6 10.211 6 8.00598C6 5.80098 7.795 4.00598 10 4.00598C12.206 4.00598 14 5.80098 14 8.00598ZM2 19.006C2 15.473 5.29 13.006 10 13.006C14.711 13.006 18 15.473 18 19.006V20.006H2V19.006Z"></path><path fill="currentColor" fill-rule="evenodd" clip-rule="evenodd" d="M14 8.00598C14 10.211 12.206 12.006 10 12.006C7.795 12.006 6 10.211 6 8.00598C6 5.80098 7.795 4.00598 10 4.00598C12.206 4.00598 14 5.80098 14 8.00598ZM2 19.006C2 15.473 5.29 13.006 10 13.006C14.711 13.006 18 15.473 18 19.006V20.006H2V19.006Z" opacity="0.5"></path><path fill="currentColor" fill-rule="evenodd" clip-rule="evenodd" d="M20.0001 20.006H22.0001V19.006C22.0001 16.4433 20.2697 14.4415 17.5213 13.5352C19.0621 14.9127 20.0001 16.8059 20.0001 19.006V20.006Z"></path><path fill="currentColor" fill-rule="evenodd" clip-rule="evenodd" d="M14.8834 11.9077C16.6657 11.5044 18.0001 9.9077 18.0001 8.00598C18.0001 5.96916 16.4693 4.28218 14.4971 4.0367C15.4322 5.09334 16.0001 6.48524 16.0001 8.00598C16.0001 9.44888 15.4889 10.7742 14.6378 11.8102C14.7203 11.8418 14.8022 11.8743 14.8834 11.9077Z"></path></svg>
        </div>
    </div>
</div>

<div class="chat-body fade-in-animation">
    <div class="messages-wrapper">
        <div id="msg-list" class="msg-list scroller">
        {% for msg in messages %}
          <div class="msg-container" data-msgid="{{ msg.id }}">
            <div class="msg-avatar-wrapper">
                <img class="msg-avatar" src="{{ msg.avatar_url }}" alt="avatar" loading="lazy" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
            </div>
            <div class="msg-content">
              <div class="msg-header">
                <span class="msg-author">{{ msg.author }}</span>
                {% if msg.is_bot %}<span class="bot-tag">應用</span>{% endif %}
                <span class="msg-timestamp" data-iso="{{ msg.created_at }}">{{ msg.created_at }}</span>
              </div>
              <div class="msg-text markdown-content">{{ msg.content }}</div>
              
              {% if msg.attachments %}
                <div class="attachments-grid">
                {% for att in msg.attachments %}
                  {% if att.is_image %}
                    <a href="{{ att.url }}" target="_blank" class="attachment-card image-preview">
                      <img src="{{ att.url }}" alt="{{ att.filename }}" loading="lazy" onerror="this.src='https://placehold.co/100x100?text=Error'">
                    </a>
                  {% else %}
                    {% set ext = att.filename.split('.')[-1] | lower %}
                    {% set cls = 'file-type-other' %}
                    {% if ext in ['pdf'] %}{% set cls = 'file-type-pdf' %}
                    {% elif ext in ['zip', 'rar', '7z'] %}{% set cls = 'file-type-archive' %}
                    {% elif ext in ['doc', 'docx'] %}{% set cls = 'file-type-doc' %}
                    {% elif ext in ['xls', 'xlsx'] %}{% set cls = 'file-type-xls' %}
                    {% elif ext in ['txt'] %}{% set cls = 'file-type-txt' %}
                    {% elif ext in ['mp3', 'wav'] %}{% set cls = 'file-type-audio' %}
                    {% elif ext in ['mp4', 'mov'] %}{% set cls = 'file-type-video' %}
                    {% elif ext in ['py', 'js', 'html', 'css', 'json', 'c', 'cpp', 'java'] %}{% set cls = 'file-type-code' %}
                    {% endif %}
                    
                    <a href="{{ att.url }}" target="_blank" class="attachment-card file-card">
                      <div class="file-icon {{ cls }}">{{ ext | upper }}</div>
                      <div class="file-info">
                          <div class="file-name" title="{{ att.filename }}">{{ att.filename }}</div>
                      </div>
                    </a>
                  {% endif %}
                {% endfor %}
                </div>
              {% endif %}

              {% if msg.embeds %}
                <div class="embeds-container">
                {% for embed in msg.embeds %}
                   <div class="embed-wrapper">
                      <div class="embed-sidebar"></div>
                      <div class="embed-content">
                          {% if embed.title %}<div class="embed-title">{{ embed.title }}</div>{% endif %}
                          {% if embed.description %}<div class="embed-desc">{{ embed.description }}</div>{% endif %}
                          {% if embed.image_url %}<a href="{{ embed.image_url }}" target="_blank"><img class="embed-image" src="{{ embed.image_url }}" loading="lazy"></a>{% endif %}
                      </div>
                   </div>
                {% endfor %}
                </div>
              {% endif %}
            </div>
          </div>
        {% endfor %}
        </div>

        <form id="send-form" enctype="multipart/form-data">
          <div id="selected-files-preview" style="display:none;"></div>
          <div class="channel-textarea">
              <div class="channel-textarea-inner">
                  <button type="button" id="file-btn" class="attach-button">
                    <span style="font-size: 24px; line-height: 1; font-weight: 300;">+</span>
                    <input type="file" name="file" id="msg-file" multiple style="display:none;">
                  </button>
                  <textarea name="content" id="msg-content" placeholder="傳送訊息到 #{{ channel.name }}" rows="1"></textarea>
                  <div class="textarea-buttons"></div>
              </div>
          </div>
          <button type="submit" id="send-btn" style="display:none;"></button>
        </form>
    </div>

    <div id="members-sidebar-location"></div>
</div>
"""

HTML_COMING_SOON = """
<div class="chat-header">
    <div class="mobile-menu-btn" id="mobile-menu-trigger">
        <svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"></path></svg>
    </div>
</div>
<div class="fade-in-animation" style="display:flex;align-items:center;justify-content:center;height:100%;flex-direction:column;color:#8e9297;background:#36393f;">
    <svg width="100" height="100" viewBox="0 0 24 24"><path fill="currentColor" d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"></path></svg>
    <h3 style="color:#fff; margin-bottom: 8px; margin-top: 20px;">私人訊息</h3>
    <div style="font-size: 14px;">這裡是你所有私人對話的家，但我們還在裝修中。</div>
</div>
"""

HTML_HOME = """
<div class="chat-header">
    <div class="mobile-menu-btn" id="mobile-menu-trigger">
        <svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"></path></svg>
    </div>
</div>
<div class="fade-in-animation" style="display:flex;align-items:center;justify-content:center;height:100%;flex-direction:column;color:#8e9297;background:#36393f;">
    <svg width="100" height="100" viewBox="0 0 24 24"><path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-5.5-2.5l7.51-3.49L17.5 6.5 9.99 9.99 6.5 17.5zm5.5-6.6c.61 0 1.1.49 1.1 1.1s-.49 1.1-1.1 1.1-1.1-.49-1.1-1.1.49-1.1 1.1-1.1z"></path></svg>
    <h3 style="color:#fff;">請從左側選擇伺服器</h3>
</div>
"""

def render_layout_content(content, guilds, current_guild=None, channels=None, current_channel=None, sidebar_only=False, bot_user=None):
    # 1. 伺服器列表 (保持不變)
    servers_html = """<nav class="guilds-nav"><div class="scroller"><ul class="guilds-tree">"""
    servers_html += """
    <li class="guild-list-item">
        <div class="guild-blob-item">
            <a href="/dms" class="guild-icon-wrapper home-icon" title="私人訊息">
                <svg width="28" height="20" viewBox="0 0 28 20"><path fill="currentColor" d="M20.6644 2.15556C19.1467 1.44444 17.5244 0.928889 15.8222 0.666667C15.8089 0.657778 15.7911 0.675556 15.7822 0.688889C15.5822 1.05333 15.3644 1.53333 15.2133 1.90222C13.4044 1.63556 11.6044 1.63556 9.81333 1.90222C9.66222 1.52889 9.44 1.05333 9.24 0.684444C9.23111 0.675556 9.21333 0.657778 9.2 0.666667C7.49778 0.924444 5.87556 1.44 4.35556 2.15556C4.34222 2.16 4.33333 2.17333 4.32889 2.18667C1.24889 6.78222 0.404444 11.2667 0.817778 15.7111C0.822222 15.7289 0.835556 15.7422 0.853333 15.7556C2.88 17.24 4.84 18.1422 6.77333 18.7378C6.79556 18.7467 6.81778 18.7333 6.83111 18.7111C7.28889 18.0844 7.70222 17.4267 8.06667 16.7422C8.08 16.7156 8.06667 16.6844 8.04 16.6756C7.32444 16.4089 6.64 16.0889 5.98667 15.7289C5.93333 15.6978 5.92889 15.6222 5.98222 15.5822C6.12444 15.4756 6.26222 15.3644 6.39556 15.2533C6.41333 15.2356 6.44 15.2311 6.46222 15.24C10.2933 17 14.7333 17 18.5422 15.24C18.5644 15.2267 18.5867 15.2356 18.6089 15.2533C18.7467 15.3644 18.8844 15.4756 19.0267 15.5822C19.08 15.6222 19.0756 15.6978 19.0222 15.7289C18.3689 16.0844 17.6844 16.7156 16.9644 16.7378C16.9378 16.68 16.9244 16.7111 16.9378 16.7378C17.3022 17.4222 17.7156 18.08 18.1733 18.7067C18.1867 18.7333 18.2089 18.7422 18.2311 18.7333C20.1644 18.1378 22.1244 17.2356 24.1511 15.7511C24.1689 15.7378 24.1822 15.7244 24.1867 15.7067C24.6978 10.48 22.9556 6.04 20.6756 2.18222C20.6667 2.16889 20.6578 2.15556 20.6644 2.15556ZM8.68 12.8711C7.54667 12.8711 6.61333 11.8311 6.61333 10.5511C6.61333 9.27111 7.52889 8.23111 8.68 8.23111C9.84 8.23111 10.7733 9.27111 10.7556 10.5511C10.7556 11.8311 9.84 12.8711 8.68 12.8711ZM16.3244 12.8711C15.1911 12.8711 14.2578 11.8311 14.2578 10.5511C14.2578 9.27111 15.1733 8.23111 16.3244 8.23111C17.4844 8.23111 18.4178 9.27111 18.4 10.5511C18.4 11.8311 17.4844 12.8711 16.3244 12.8711Z"></path></svg>
            </a>
        </div>
    </li>
    <li class="guild-separator"></li>
    """
    for g in guilds:
        active_class = "active" if current_guild and g.id == current_guild.id else ""
        icon_url = g.icon.url if hasattr(g, "icon") and g.icon else None
        servers_html += f'<li class="guild-list-item"><div class="guild-blob-item {active_class}"><div class="guild-pill"></div><a href="/guild/{g.id}" class="guild-icon-wrapper" title="{g.name}">'
        if icon_url:
            servers_html += f'<img src="{icon_url}" alt="{g.name}" class="guild-icon-img" />'
        else:
            servers_html += f'<span class="guild-text-icon">{g.name[:2]}</span>'
        servers_html += '</a></div></li>'
    servers_html += "</ul></div></nav>"

    # 2. 中間側邊欄 (結構優化：Header (Top), Scroller (Middle), UserBar (Bottom))
    channels_html = f"""<div class="sidebar-channels">"""
    
    if current_guild:
        # Header
        channels_html += f"""
            <div class="sidebar-header">
                <h1 class="guild-header-name">{current_guild.name}</h1>
            </div>
            <div class="channels-scroller scroller">
                <div class="category-header">
                    <span style="font-size:10px; margin-right:4px;">&#9660;</span>
                    <span>文字頻道</span>
                </div>
                <ul class="channel-list-tree">
        """
        if channels:
            for c in channels:
                active_class = "active" if current_channel and c.id == current_channel.id else ""
                channels_html += f"""
                <li class="channel-item {active_class}">
                    <a href="/guild/{current_guild.id}/channel/{c.id}" class="channel-link">
                        <span class="channel-symbol">#</span>
                        <span class="channel-name">{c.name}</span>
                    </a>
                </li>
                """
        channels_html += "</ul></div>"
    else:
        channels_html += f"""
            <div class="sidebar-header">
                <button style="width:100%;text-align:left;background:#202225;color:#96989d;border:none;border-radius:4px;padding:6px;cursor:pointer;">尋找或開始對話</button>
            </div>
            <div class="channels-scroller scroller">
                <div class="category-header" style="padding: 16px 8px 8px 16px;">
                    <span>私人訊息 (即將開放)</span>
                </div>
            </div>
        """

    # User Bar (絕對獨立，不被 Scroller 包裹)
    if bot_user:
        avatar_url = bot_user.display_avatar.url if hasattr(bot_user, "display_avatar") else "https://cdn.discordapp.com/embed/avatars/0.png"
        username = bot_user.name
        discriminator = f"#{bot_user.discriminator}" if bot_user.discriminator != "0" else ""
        
        channels_html += f"""
        <section class="user-bar">
            <div class="user-avatar-wrapper">
               <img class="user-avatar-img" src="{avatar_url}" alt="avatar">
               <div class="status-indicator status-online"></div>
            </div>
            <div class="user-info-text">
                <div class="user-username">{username}</div>
                <div class="user-discriminator">{discriminator}</div>
            </div>
            <div class="user-settings-btn icon-item" id="view-mode-btn" title="切換檢視模式" style="margin-left:auto;cursor:pointer;">
                <svg width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" d="M4 6h18V4H4c-1.1 0-2 .9-2 2v11H0v3h14v-3H4V6zm19 2h-6c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h6c.55 0 1-.45 1-1V9c0-.55-.45-1-1-1zm-1 9h-4v-7h4v7z"></path></svg>
            </div>
        </section>
        """
    channels_html += "</div>"
    
    combined_sidebar = f"{servers_html}{channels_html}"
    
    if sidebar_only:
        return combined_sidebar
    return content

def _format_message_for_json(m):
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
        "id": m.id,
        "author": str(m.author),
        "avatar_url": m.author.display_avatar.url if hasattr(m.author, "display_avatar") else (m.author.avatar_url if hasattr(m.author, "avatar_url") else ""),
        "content": m.content, 
        "attachments": atts,
        "embeds": embeds,
        "is_bot": m.author.bot,
        "created_at": m.created_at.isoformat(),
        "channel_id": m.channel.id,
        "guild_id": m.guild.id if m.guild else None
    }

def _format_member_for_json(member):
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
        "id": member.id,
        "name": member.name,
        "display_name": member.display_name or member.name,
        "avatar_url": member.display_avatar.url if hasattr(member, "display_avatar") else "https://cdn.discordapp.com/embed/avatars/0.png",
        "is_bot": member.bot,
        "status": str(member.status),
        "highest_role_name": display_role_name,
        "color": str(member.color) if member.color.value != 0 else "",
    }

class backend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = Flask("discord_backend")
        self.loop = bot.loop
        CORS(self.app)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')

        @self.app.route("/")
        def index():
            guilds = list(bot.guilds)
            return render_layout_content(HTML_HOME, guilds, bot_user=self.bot.user)

        @self.app.route("/dms")
        def dms():
            guilds = list(bot.guilds)
            return render_layout_content(HTML_COMING_SOON, guilds, bot_user=self.bot.user)

        @self.app.route("/guild/<int:guild_id>")
        def guild(guild_id):
            guilds = list(bot.guilds)
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return "找不到伺服器"
            channels = [c for c in guild.text_channels]

            if channels:
                first_channel = channels[0]
                async def fetch_messages():
                    return [m async for m in first_channel.history(limit=50)]
                fut = asyncio.run_coroutine_threadsafe(fetch_messages(), self.loop)
                try:
                    messages = fut.result(timeout=10)
                except Exception:
                    messages = []
                
                messages = [_format_message_for_json(m) for m in reversed(messages)]
                
                content = render_template_string(
                    HTML_MESSAGES,
                    guild=guild,
                    channel=first_channel,
                    messages=messages,
                )
                return render_layout_content(content, guilds, current_guild=guild, channels=channels, current_channel=first_channel, bot_user=self.bot.user)
            else:
                content = "<div style='padding:20px;color:#fff;background:#36393f;height:100%;'>此伺服器沒有可用的文字頻道。</div>"
                return render_layout_content(content, guilds, current_guild=guild, channels=channels, bot_user=self.bot.user)

        @self.app.route("/guild_channels_sidebar/")
        @self.app.route("/guild_channels_sidebar/<int:guild_id>")
        def guild_channels_sidebar(guild_id=None):
            guilds = list(bot.guilds)
            current_guild = None
            channels = None
            if guild_id:
                current_guild = discord.utils.get(bot.guilds, id=guild_id)
                if current_guild:
                    channels = [c for c in current_guild.text_channels]
            return render_layout_content("", guilds, current_guild=current_guild, channels=channels, sidebar_only=True, bot_user=self.bot.user)

        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>")
        def channel(guild_id, channel_id):
            guilds = list(bot.guilds)
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return "找不到伺服器"
            channels = [c for c in guild.text_channels]
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return "找不到頻道"

            async def fetch_messages():
                return [m async for m in channel.history(limit=50)]
            fut = asyncio.run_coroutine_threadsafe(fetch_messages(), self.loop)
            try:
                messages = fut.result(timeout=10)
            except Exception:
                messages = []

            messages = [_format_message_for_json(m) for m in reversed(messages)]
            
            content = render_template_string(
                HTML_MESSAGES,
                guild=guild,
                channel=channel,
                messages=messages,
            )
            return render_layout_content(content, guilds, current_guild=guild, channels=channels, current_channel=channel, bot_user=self.bot.user)

        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>/messages")
        def channel_messages(guild_id, channel_id):
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return jsonify({"messages": []})
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return jsonify({"messages": []})

            before = request.args.get("before", type=int)
            limit = 100 
            async def fetch_messages():
                kwargs = {"limit": limit}
                if before:
                    kwargs["before"] = discord.Object(id=before)
                return [m async for m in channel.history(**kwargs)]
            fut = asyncio.run_coroutine_threadsafe(fetch_messages(), self.loop)
            try:
                messages = fut.result(timeout=10)
            except Exception:
                messages = []

            messages = [_format_message_for_json(m) for m in reversed(messages)]
            return jsonify({"messages": messages})

        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>/members")
        def channel_members(guild_id, channel_id):
            try:
                guild = discord.utils.get(bot.guilds, id=guild_id)
                if not guild: return jsonify({"members": [], "error": "Not found"}), 404
                channel = discord.utils.get(guild.text_channels, id=channel_id)
                if not channel: return jsonify({"members": [], "error": "Not found"}), 404

                readable_members = [
                    member for member in guild.members
                    if channel.permissions_for(member).read_messages
                ]
                formatted_members = [_format_member_for_json(m) for m in readable_members]
                return jsonify({"members": formatted_members})
            except Exception as e:
                return jsonify({"members": [], "error": str(e)}), 500

        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>/send", methods=["POST"])
        def send_message(guild_id, channel_id):
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
                    return jsonify({"ok": True, "message": _format_message_for_json(sent_message)})
                else:
                    return jsonify({"ok": False, "error": "Empty or failed"}), 400
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500

        threading.Thread(target=lambda: self.socketio.run(self.app, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True), daemon=True).start()
        
        @self.bot.event
        async def on_message(message):
            if message.guild:
                formatted_msg = _format_message_for_json(message)
                self.socketio.emit('new_message', formatted_msg)

def setup(bot):
    bot.add_cog(backend(bot))
