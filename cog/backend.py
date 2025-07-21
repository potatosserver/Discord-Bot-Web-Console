import discord
from discord.ext import commands
from flask import Flask, render_template_string, request, jsonify
import threading
import asyncio
import re
from datetime import datetime, timedelta
from flask_cors import CORS # 將 flask_cors 導入移到檔案頂部

bot = discord.Bot(intents=discord.Intents.all())

# HTML 模板 - 這些將由後端渲染並傳遞給前端
# 前端會透過 AJAX 請求這些內容，並將其插入到 .main-inner 和 .sidebar 中
HTML_GUILDS = """
<h2>伺服器列表</h2>
<ul>
{% for guild in guilds %}
  <li>{{ guild.name }} ({{ guild.id }})</li>
{% endfor %}
</ul>
"""

HTML_CHANNELS = """
<h2>伺服器: {{ guild.name }}</h2>
<ul>
{% for channel in channels %}
  <li># {{ channel.name }} ({{ channel.id }})</li>
{% endfor %}
</ul>
"""

# 修改 HTML_MESSAGES 模板，直接輸出 ISO 格式的時間戳
# 新增 data-channel-id 到 channel-data 元素
HTML_MESSAGES = """
<div id="channel-data" data-channel-name="{{ channel.name }}" data-channel-id="{{ channel.id }}" style="display:none;"></div>
<div id="msg-list" class="msg-list">
{% for msg in messages %}
  <div class="msg" data-msgid="{{ msg.id }}">
    <img class="msg-avatar" src="{{ msg.avatar_url }}" alt="avatar" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
    <div class="msg-content">
      <div style="display:flex; align-items: center;"> {# 將 align-items 從 baseline 改為 center #}
        <span class="msg-author">{{ msg.author }}</span>
        {% if msg.is_bot %}<span class="bot-tag">應用</span>{% endif %} {# 新增的機器人標籤 #}
        {# 直接輸出 ISO 字串，讓 JavaScript 處理 #}
        <span class="msg-timestamp" style="margin-left: 8px;">{{ msg.created_at }}</span>
      </div>
      <span class="msg-text">{{ msg.content | safe }}</span>
      {% if msg.attachments %}
        <div class="attachments-grid">
        {% for att in msg.attachments %}
          {% if att.is_image %}
            <a href="{{ att.url }}" target="_blank" class="attachment-card image-preview">
              <img src="{{ att.url }}" class="image-preview-img" alt="{{ att.filename }}" onerror="this.src='https://placehold.co/100x100?text=Error'">
            </a>
          {% else %}
            {% set file_ext = att.filename.split('.')[-1] | lower %}
            {% set file_type_text = file_ext.upper() %}
            {% set file_type_class = 'file-type-other' %}
            {% if file_ext == 'pdf' %}{% set file_type_class = 'file-type-pdf' %}
            {% elif file_ext in ['png', 'jpg', 'jpeg', 'gif'] %}{% set file_type_class = 'file-type-image' %}
            {% elif file_ext in ['doc', 'docx'] %}{% set file_type_class = 'file-type-doc' %}
            {% elif file_ext in ['xls', 'xlsx'] %}{% set file_type_class = 'file-type-xls' %}
            {% elif file_ext in ['zip', 'rar', '7z'] %}{% set file_type_class = 'file-type-archive' %}
            {% elif file_ext == 'txt' %}{% set file_type_class = 'file-type-txt' %}
            {% elif file_ext in ['mp3', 'wav', 'ogg'] %}{% set file_type_class = 'file-type-audio' %}
            {% elif file_ext in ['mp4', 'mov', 'avi'] %}{% set file_type_class = 'file-type-video' %}
            {% elif file_ext in ['ppt', 'pptx'] %}{% set file_type_class = 'file-type-ppt' %}
            {% elif file_ext == 'py' %}{% set file_type_class = 'file-type-py' %}
            {% elif file_ext == 'js' %}{% set file_type_class = 'file-type-js' %}
            {% elif file_ext == 'html' %}{% set file_type_class = 'file-type-html' %}
            {% elif file_ext == 'css' %}{% set file_type_class = 'file-type-css' %}
            {% elif file_ext == 'json' %}{% set file_type_class = 'file-type-json' %}
            {% elif file_ext == 'xml' %}{% set file_type_class = 'file-type-xml' %}
            {% elif file_ext == 'csv' %}{% set file_type_class = 'file-type-csv' %}
            {% elif file_ext == 'exe' %}{% set file_type_class = 'file-type-exe' %}
            {% else %}{% set file_type_text = 'FILE' %}{% endif %}

            <a href="{{ att.url }}" target="_blank" class="attachment-card">
              <div class="attachment-icon {{ file_type_class }}">{{ file_type_text }}</div>
              <div class="attachment-filename" title="{{ att.filename }}">{{ att.filename }}</div>
            </a>
          {% endif %}
        {% endfor %}
        </div>
      {% endif %}
      {% if msg.embeds %}
        <div style="margin-top:6px;">
        {% for embed in msg.embeds %}
          {% if embed.image_url %}
            <a href="{{ embed.image_url }}" target="_blank"><img src="{{ embed.image_url }}" style="max-width:320px;max-height:240px;border-radius:6px;margin:2px 0;"></a>
          {% endif %}
          {% if embed.title %}
            <div style="color:#fff;font-weight:bold;">{{ embed.title }}</div>
          {% endif %}
          {% if embed.description %}
            <div style="color:#b9bbbe;">{{ embed.description }}</div>
          {% endif %}
        {% endfor %}
        </div>
      {% endif %}
    </div>
  </div>
{% endfor %}
</div>
<form id="send-form" enctype="multipart/form-data">
  <div id="selected-files-preview" style="display:none;"></div> {# 新增的檔案預覽區塊 #}
  <div class="input-area">
    <button type="button" id="file-btn" style="margin-right:8px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;background:#23272a;border:none;border-radius:50%;width:38px;height:38px;transition:background 0.15s;padding:0;">
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="11" stroke="#b9bbbe" stroke-width="2" fill="none"/>
        <path d="M12 7v10M7 12h10" stroke="#b9bbbe" stroke-width="2" stroke-linecap="round"/>
      </svg>
      <input type="file" name="file" id="msg-file" multiple style="display:none;">
    </button>
    {# 移除 file-label-text，因為現在有 selected-files-preview #}
    <textarea name="content" id="msg-content" placeholder="輸入訊息..." rows="1"></textarea>
    <button type="submit" class="button" id="send-btn" style="margin-left:8px;border-radius:50%;height:38px;width:38px;min-width:38px;display:flex;align-items:center;justify-content:center;padding:0;">
      <svg id="send-btn-icon" width="22" height="22" viewBox="0 0 24 24" fill="none">
        <path d="M3 20L21 12L3 4V10L17 12L3 14V20Z" fill="#fff"/>
      </svg>
    </button>
  </div>
</form>
"""

# 渲染佈局的輔助函數，現在只返回內容，不包含完整的 HTML 結構
def render_layout_content(content, guilds, current_guild=None, channels=None, current_channel=None, sidebar_only=False):
    sidebar_content = """
    <div class="guild-list-scroll">
        <ul class="guild-list">
    """
    for g in guilds:
        active = "active" if current_guild and g.id == current_guild.id else ""
        icon_url = g.icon.url if hasattr(g, "icon") and g.icon else None
        if icon_url:
            icon_html = f'<img src="{icon_url}" alt="{g.name}" />'
        else:
            icon_html = f'<span style="font-size:1.3em;font-weight:bold;color:#fff;display:flex;align-items:center;justify-content:center;height:40px;">{g.name[0]}</span>'
        sidebar_content += (
            f'<li>'
            f'<a class="guild-link {active}" href="/guild/{g.id}" '
            f'title="{g.name}">'
            f'{icon_html}'
            f'</a></li>'
        )
    sidebar_content += "</ul></div>"

    sidebar_content += '<div class="channel-list-scroll">'
    if current_guild and channels:
        sidebar_content += (
            f'<div class="channel-list-header">{current_guild.name}</div>'
        )
        sidebar_content += '<ul class="channel-list">'
        # Determine the channel to be active in the sidebar
        active_channel_id_for_sidebar = None
        if current_channel:
            active_channel_id_for_sidebar = current_channel.id
        elif current_guild and channels:
            # If a guild is selected and channels exist, the first channel is implicitly active
            if channels:
                active_channel_id_for_sidebar = channels[0].id

        for c in channels:
            active = "active" if active_channel_id_for_sidebar and c.id == active_channel_id_for_sidebar else ""
            sidebar_content += (
                f'<li>'
                f'<a class="channel-link {active}" href="/guild/{current_guild.id}/channel/{c.id}">'
                f'# {c.name}'
                f'</a></li>'
            )
        sidebar_content += "</ul>"
    sidebar_content += "</div>"

    if sidebar_only:
        return sidebar_content
    
    # 這裡只返回主內容，前端會負責將其插入到正確的位置
    return content

def linkify(text):
    url_pattern = re.compile(r'(https?://[^\s]+)')
    return url_pattern.sub(r'<a href="\1" target="_blank" style="color:#00b0f4;">\1</a>', text)

# Helper function to format message objects for JSON response
def _format_message_for_json(m):
    atts = []
    for a in getattr(m, "attachments", []):
        atts.append({
            "url": a.url,
            "filename": a.filename,
            "is_image": a.content_type and a.content_type.startswith("image"),
        })
    embeds = []
    for e in getattr(m, "embeds", []): # Changed m to e
        embeds.append({
            "image_url": e.image.url if getattr(e, "image", None) and e.image.url else None,
            "title": getattr(e, "title", None),
            "description": getattr(e, "description", None),
        })
    return {
        "id": m.id,
        "author": str(m.author),
        "avatar_url": m.author.display_avatar.url if hasattr(m.author, "display_avatar") else (m.author.avatar_url if hasattr(m.author, "avatar_url") else ""),
        "content": linkify(m.content),
        "attachments": atts,
        "embeds": embeds,
        "is_bot": m.author.bot, # 新增 is_bot 屬性
        # 只傳送 ISO 格式字串，讓前端處理時區轉換
        "created_at": m.created_at.isoformat(),
    }

# Helper function to format member objects for JSON response
def _format_member_for_json(member):
    # Determine highest role for display and sorting
    highest_role_position = 0
    display_role_name = "線上" # Default for members with no roles and online

    # If the member is offline, always set their display role name to "離線"
    if str(member.status) == 'offline':
        display_role_name = "離線"
    else:
        # Find the highest role that is not @everyone
        found_higher_role = False
        for role in member.roles:
            if role.position > highest_role_position:
                highest_role_position = role.position
                display_role_name = role.name
                found_higher_role = True

        # If no roles other than @everyone, and not offline, then "線上"
        if not found_higher_role or display_role_name == "@everyone":
            display_role_name = "線上"


    return {
        "id": member.id,
        "name": member.name,
        "display_name": member.display_name or member.name, # Ensure display_name is always present
        "avatar_url": member.display_avatar.url if hasattr(member, "display_avatar") else "https://cdn.discordapp.com/embed/avatars/0.png",
        "is_bot": member.bot,
        "status": str(member.status), # 新增成員狀態
        "highest_role_name": display_role_name,        # For frontend display
        "highest_role_position": highest_role_position, # For backend sorting
    }


class backend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.app = Flask("discord_backend")
        self.loop = bot.loop

        # 允許來自任何來源的跨域請求
        CORS(self.app)

        @self.app.route("/")
        def index():
            guilds = list(bot.guilds)
            content = render_template_string(HTML_GUILDS, guilds=guilds)
            return render_layout_content(content, guilds)

        @self.app.route("/guild/<int:guild_id>")
        def guild(guild_id):
            guilds = list(bot.guilds)
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild:
                return "找不到伺服器"
            channels = [c for c in guild.text_channels]

            # NEW LOGIC: Automatically select the first channel if available
            if channels:
                first_channel = channels[0]
                # Fetch messages for the first channel
                async def fetch_messages():
                    return [m async for m in first_channel.history(limit=20)]
                fut = asyncio.run_coroutine_threadsafe(fetch_messages(), self.loop)
                try:
                    messages = fut.result(timeout=10)
                except Exception:
                    messages = []

                messages = [_format_message_for_json(m) for m in reversed(messages)]
                content = render_template_string(
                    HTML_MESSAGES,
                    guild=guild,
                    channel=first_channel, # Pass the first channel
                    messages=messages,
                )
                # Ensure current_channel is set for layout rendering
                return render_layout_content(content, guilds, current_guild=guild, channels=channels, current_channel=first_channel)
            else:
                # If no channels, show a message
                content = "<h2>此伺服器沒有可用的文字頻道。</h2>"
                return render_layout_content(content, guilds, current_guild=guild, channels=channels)

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
            return render_layout_content("", guilds, current_guild=current_guild, channels=channels, sidebar_only=True)


        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>")
        def channel(guild_id, channel_id):
            guilds = list(bot.guilds)
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return "找不到伺服器"
            channels = [c for c in guild.text_channels]
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return "找不到頻道"

            async def fetch_messages():
                return [m async for m in channel.history(limit=20)]
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
            return render_layout_content(content, guilds, current_guild=guild, channels=channels, current_channel=channel)

        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>/messages")
        def channel_messages(guild_id, channel_id):
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return jsonify({"messages": []})
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return jsonify({"messages": []})

            before = request.args.get("before", type=int)
            limit = 20
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
                if not guild: return jsonify({"members": [], "error": "找不到伺服器"}), 404
                channel = discord.utils.get(guild.text_channels, id=channel_id)
                if not channel: return jsonify({"members": [], "error": "找不到頻道"}), 404

                # Filter members who can read messages in this channel
                readable_members = [
                    member for member in guild.members
                    if channel.permissions_for(member).read_messages
                ]

                # Define status order for sorting
                status_order = {
                    "online": 0,
                    "streaming": 1,
                    "idle": 2,
                    "dnd": 3,
                    "offline": 4,
                }

                # Sort members based on role position (descending), then status (defined order), then display name (alphabetical)
                def get_sort_key(member):
                    # Get the highest role position for the member. If no roles, default to 0.
                    highest_role_position = 0
                    for role in member.roles:
                        if role.position > highest_role_position:
                            highest_role_position = role.position

                    # Get the status order value. Default to a high number if status is not in the map.
                    status_value = status_order.get(str(member.status), 99)

                    # For offline members, we want them at the very bottom.
                    # We can achieve this by giving them a very low (negative) role position
                    # and the highest status value in the status_order map.
                    if str(member.status) == 'offline':
                        # Use a very large negative number for role position to ensure offline members
                        # are always sorted after all online members, regardless of their roles.
                        # Use the 'offline' status value to keep them grouped at the bottom of the offline section.
                        return (-1000000000, status_order.get('offline', 99), (member.display_name or member.name).lower())

                    # For online members, sort by descending role position, then status, then display name.
                    # Multiply by -1 for role position to achieve descending order.
                    return (-highest_role_position, status_value, (member.display_name or member.name).lower())

                sorted_members = sorted(readable_members, key=get_sort_key)

                # Now format the sorted members for the JSON response
                formatted_members = [_format_member_for_json(m) for m in sorted_members]

                return jsonify({"members": formatted_members})
            except Exception as e:
                # 捕獲任何處理成員時的錯誤並返回 500 錯誤訊息
                print(f"Error fetching members: {e}")
                return jsonify({"members": [], "error": f"處理成員時發生錯誤: {str(e)}"}), 500


        @self.app.route("/guild/<int:guild_id>/channel/<int:channel_id>/send", methods=["POST"])
        def send_message(guild_id, channel_id):
            guild = discord.utils.get(bot.guilds, id=guild_id)
            if not guild: return jsonify({"ok": False, "error": "找不到伺服器"}), 404
            channel = discord.utils.get(guild.text_channels, id=channel_id)
            if not channel: return jsonify({"ok": False, "error": "找不到頻道"}), 404

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
                    return jsonify({"ok": False, "error": "訊息內容為空或傳送失敗"}), 400
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500

        threading.Thread(target=self.app.run, kwargs={"host": "0.0.0.0", "port": 5000}, daemon=True).start()

def setup(bot):
    bot.add_cog(backend(bot))
