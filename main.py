import disnake
from disnake.ext import commands, tasks
import asyncio
import datetime
import random
import json
import aiosqlite
import os
import aiohttp
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ DISCORD_BOT_TOKEN not found in environment variables")

intents = disnake.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

OWNER_ID = 1207251344029786164


class EconomyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)
        self.db = None
        self.cooldowns = {}
        self.blacklisted_words = [
            "nigger",
            "fuck",
            "shit",
            "asshole",
            "bitch",
        ]
        self.exchange_rate = 100
        self.log_channels = {
            "economy": 1456677466092605665,
            "user": 1456677242498191665,
            "server": 1456677364443512832,
            "channel": 1456677533650128980,
            "moderation": 1456677598884266173,
        }
        self.withdraw_channel = 1456677723022950533
        self.cleanup.start()

    async def on_connect(self):
        os.makedirs("data", exist_ok=True)
        self.db = await aiosqlite.connect("data/economy.db")
        await self.init_db()

    async def init_db(self):
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS economy (
                user_id INTEGER PRIMARY KEY,
                cash INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                last_daily TIMESTAMP,
                last_work TIMESTAMP
            )
        """
        )
        await self.db.commit()

    @tasks.loop(minutes=30)
    async def cleanup(self):
        current_time = datetime.datetime.now()
        expired = [key for key, value in self.cooldowns.items() if value < current_time]
        for key in expired:
            del self.cooldowns[key]

    async def add_cash(self, user_id: int, amount: int, admin: bool = False):
        async with self.db.execute(
            "SELECT cash FROM economy WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            new_cash = row[0] + amount
            await self.db.execute(
                "UPDATE economy SET cash = ? WHERE user_id = ?", (new_cash, user_id)
            )
        else:
            await self.db.execute(
                "INSERT INTO economy (user_id, cash) VALUES (?, ?)", (user_id, amount)
            )
            new_cash = amount

        await self.db.commit()

        if admin:
            channel = self.get_channel(self.log_channels["economy"])
            if channel:
                embed = disnake.Embed(
                    description=f"💰 Admin action: `{amount}` cash added to <@{user_id}>",
                    color=disnake.Color.green(),
                    timestamp=datetime.datetime.now(),
                )
                embed.set_footer(text=f"User ID: {user_id}")
                await channel.send(embed=embed)

    async def remove_cash(self, user_id: int, amount: int, admin: bool = False):
        async with self.db.execute(
            "SELECT cash FROM economy WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return False

        current_cash = row[0]
        new_cash = max(0, current_cash - amount)
        await self.db.execute(
            "UPDATE economy SET cash = ? WHERE user_id = ?", (new_cash, user_id)
        )
        await self.db.commit()

        if admin:
            channel = self.get_channel(self.log_channels["economy"])
            if channel:
                embed = disnake.Embed(
                    description=f"💰 Admin action: `{amount}` cash removed from <@{user_id}>",
                    color=disnake.Color.red(),
                    timestamp=datetime.datetime.now(),
                )
                embed.set_footer(text=f"User ID: {user_id}")
                await channel.send(embed=embed)

        return True

    async def get_cash(self, user_id: int) -> int:
        async with self.db.execute(
            "SELECT cash FROM economy WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()

        return row[0] if row else 0

    async def log_economy(self, message: str):
        channel = self.get_channel(self.log_channels["economy"])
        if channel:
            embed = disnake.Embed(
                description=message,
                color=disnake.Color.green(),
                timestamp=datetime.datetime.now(),
            )
            await channel.send(embed=embed)

    async def log_user(self, message: str):
        channel = self.get_channel(self.log_channels["user"])
        if channel:
            embed = disnake.Embed(
                description=message,
                color=disnake.Color.blue(),
                timestamp=datetime.datetime.now(),
            )
            await channel.send(embed=embed)

    async def log_moderation(self, message: str):
        channel = self.get_channel(self.log_channels["moderation"])
        if channel:
            embed = disnake.Embed(
                description=message,
                color=disnake.Color.orange(),
                timestamp=datetime.datetime.now(),
            )
            await channel.send(embed=embed)

    async def check_cooldown(self, user_id: int, command: str, cooldown: int) -> bool:
        key = f"{user_id}_{command}"
        now = datetime.datetime.now()

        if key in self.cooldowns:
            if self.cooldowns[key] > now:
                return False

        self.cooldowns[key] = now + datetime.timedelta(seconds=cooldown)
        return True


bot = EconomyBot()


@bot.slash_command(
    name="check_blinx_community", description="Check community info from Blinx system"
)
async def check_blinx_community(inter, community_id: str):
    API_URL = "http://localhost/app/api/communities/"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{API_URL}?id={community_id}", timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if not data.get("success"):
                        embed = disnake.Embed(
                            description=f"❌ Error: {data.get('error', 'Unknown error')}",
                            color=disnake.Color.red(),
                        )
                        await inter.response.send_message(embed=embed, ephemeral=True)
                        return

                    community = data["data"]

                    embed = disnake.Embed(
                        title=f"🏘️ {community['name']}",
                        url=community["urls"]["profile"],
                        color=disnake.Color.green(),
                        timestamp=datetime.datetime.now(),
                    )

                    if community["description"]:
                        embed.description = community["description"][:200] + (
                            "..." if len(community["description"]) > 200 else ""
                        )

                    embed.add_field(
                        name="📊 STATS",
                        value=f"**Members:** `{community['stats']['members']:,}`\n**Posts:** `{community['stats']['posts']:,}`",
                        inline=True,
                    )

                    status_text = []
                    if community["status"]["is_verified"]:
                        status_text.append("✅ Verified")

                    if community["visibility"]["is_private"]:
                        status_text.append("🔒 Private")
                    else:
                        status_text.append("🔓 Public")

                    if community["visibility"]["is_public_feed"]:
                        status_text.append("📢 Public Feed")

                    embed.add_field(
                        name="🔍 STATUS",
                        value="\n".join(status_text) if status_text else "Standard",
                        inline=True,
                    )

                    embed.add_field(
                        name="👑 CREATOR",
                        value=f"**{community['creator']['display_name']}**\n`@{community['creator']['username']}`",
                        inline=False,
                    )

                    if community["admins"]:
                        admins_text = []
                        for admin in community["admins"][:5]:
                            admins_text.append(
                                f"• **{admin['display_name']}** (`@{admin['username']}`)"
                            )

                        if len(community["admins"]) > 5:
                            admins_text.append(
                                f"... and {len(community['admins']) - 5} more"
                            )

                        embed.add_field(
                            name=f"🛡️ ADMIN TEAM ({len(community['admins'])})",
                            value="\n".join(admins_text),
                            inline=False,
                        )

                    if community["recent_posts"]:
                        posts_text = []
                        for post in community["recent_posts"][:3]:
                            posts_text.append(f"• {post['content_preview']}")

                        embed.add_field(
                            name="📝 RECENT POSTS",
                            value="\n".join(posts_text),
                            inline=False,
                        )

                    created_date = datetime.datetime.fromisoformat(
                        community["dates"]["created_at"].replace("Z", "+00:00")
                    )
                    age_days = (datetime.datetime.now() - created_date).days

                    embed.add_field(
                        name="📅 CREATED",
                        value=f"`{created_date.strftime('%Y-%m-%d')}`\n({age_days} days ago)",
                        inline=True,
                    )

                    embed.add_field(
                        name="🔗 PROFILE",
                        value=f"[Open on Blinx]({community['urls']['profile']})",
                        inline=True,
                    )

                    if community["avatar_url"]:
                        embed.set_thumbnail(url=community["avatar_url"])

                    embed.set_footer(text=f"Community ID: {community_id}")
                    await inter.response.send_message(embed=embed)

                else:
                    embed = disnake.Embed(
                        description="❌ Failed to fetch community data",
                        color=disnake.Color.red(),
                    )
                    await inter.response.send_message(embed=embed, ephemeral=True)

        except asyncio.TimeoutError:
            embed = disnake.Embed(
                description="⏱️ Request timeout", color=disnake.Color.orange()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            embed = disnake.Embed(
                description=f"❌ Error: {str(e)[:200]}", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="help", description="Show all available commands")
async def help_command(inter):
    embed = disnake.Embed(
        title="🔧 BLINX BOT COMMANDS",
        description="**Economy & Finance**",
        color=disnake.Color.blue(),
        timestamp=datetime.datetime.now(),
    )

    economy_commands = """
    **💳 Balance**
    `/balance` - Check your cash balance

    **🎁 Daily Reward**
    `/daily` - Claim daily cash reward

    **💼 Work**
    `/work` - Work to earn cash (1h cooldown)

    **🔄 Withdraw**
    `/withdraw <amount> <blinx_id>` - Convert cash to Blinks
    *Rate: 1 Blink = 100 cash*

    **🏆 Leaderboard**
    `/leaderboard` - Top 10 richest users
    """

    embed.add_field(name="💰 ECONOMY SYSTEM", value=economy_commands, inline=False)

    private_rooms = """
    **🔒 Create Private Room**
    `/create_pr <channel_name> <user_limit>`
    *Prices:*
    • ≤2 users: 1,500 cash
    • ≤8 users: 2,500 cash
    • ≤15 users: 5,000 cash
    • Unlimited: 10,000 cash

    **🗑️ Delete Private Room**
    `/delete_pr <channel_id>` - Delete your private channel

    **🔑 Transfer Ownership**
    `/transfer_pr <channel_id> <new_owner>` - Transfer channel ownership
    """

    embed.add_field(name="🎙️ PRIVATE VOICE CHANNELS", value=private_rooms, inline=False)

    admin_commands = """
    **➕ Add Cash**
    `/addcash <user> <amount>` - Admin only

    **➖ Remove Cash**
    `/removecash <user> <amount>` - Admin only

    **⚙️ Set Exchange Rate**
    `/setrate <rate>` - Owner only

    **🔄 Reset Cooldown**
    `/resetcooldown <user>` - Owner only

    **📊 Economy Stats**
    `/economystats` - Owner only
    """

    embed.add_field(name="👑 ADMIN COMMANDS", value=admin_commands, inline=False)

    blinx_system = """
    **👤 Check User**
    `/blinx_check <user_id>` - Get user info from BlinX

    **🏘️ Check Community**
    `/check_blinx_community <community_id>` - Get community info

    **🌐 System Status**
    `/blinx_status` - Check BlinX website status
    """

    embed.add_field(
        name="🔗 BLINX SYSTEM INTEGRATION", value=blinx_system, inline=False
    )

    features = """
    **🛡️ Auto-Moderation**
    • Automatic blacklisted word filtering
    • Message deletion & warnings
    • Logging to moderation channel

    **📊 Logging System**
    • Economy transactions
    • User joins/leaves/bans
    • Channel & role changes
    • Moderation actions

    **⚙️ Settings**
    • Exchange rate: 1 Blink = 100 cash
    • Daily cooldown: 24 hours
    • Work cooldown: 1 hour
    """

    embed.add_field(name="⚡ FEATURES", value=features, inline=False)

    embed.set_footer(
        text=f"Requested by {inter.author.name}",
        icon_url=inter.author.display_avatar.url,
    )

    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="blinx_status", description="Check BlinX website status")
async def blinx_status(inter):
    API_URL = "https://blin-x.space/"

    async with aiohttp.ClientSession() as session:
        try:
            start_time = datetime.datetime.now()

            async with session.get(API_URL, timeout=10) as response:
                end_time = datetime.datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000

                status_emoji = "✅" if response.status == 200 else "❌"
                status_text = "ONLINE" if response.status == 200 else "OFFLINE"
                color = (
                    disnake.Color.green()
                    if response.status == 200
                    else disnake.Color.red()
                )

                embed = disnake.Embed(
                    title=f"{status_emoji} BLINX STATUS - {status_text}",
                    color=color,
                    timestamp=datetime.datetime.now(),
                )

                embed.add_field(
                    name="🌐 WEBSITE", value=f"[blin-x.space]({API_URL})", inline=True
                )

                embed.add_field(
                    name="📊 STATUS CODE", value=f"`{response.status}`", inline=True
                )

                embed.add_field(
                    name="⚡ RESPONSE TIME",
                    value=f"`{response_time:.0f}ms`",
                    inline=True,
                )

                if response.status != 200:
                    embed.add_field(
                        name="⚠️ ALERT",
                        value="Website is experiencing issues",
                        inline=False,
                    )

                embed.set_footer(text=f"Checked at {end_time.strftime('%H:%M:%S')}")

                await inter.response.send_message(embed=embed)

        except asyncio.TimeoutError:
            embed = disnake.Embed(
                title="⏱️ BLINX STATUS - TIMEOUT",
                description="Website took too long to respond",
                color=disnake.Color.orange(),
                timestamp=datetime.datetime.now(),
            )
            embed.add_field(
                name="🌐 WEBSITE", value="[blin-x.space](https://blin-x.space/)"
            )
            embed.add_field(name="⚡ RESPONSE TIME", value="> 10 seconds")
            embed.set_footer(text="Connection timeout")
            await inter.response.send_message(embed=embed)

        except Exception as e:
            embed = disnake.Embed(
                title="❌ BLINX STATUS - ERROR",
                description="Could not check website status",
                color=disnake.Color.red(),
                timestamp=datetime.datetime.now(),
            )
            embed.add_field(
                name="🌐 WEBSITE", value="[blin-x.space](https://blin-x.space/)"
            )
            embed.add_field(name="❓ ERROR", value=str(e)[:100])
            await inter.response.send_message(embed=embed)


@tasks.loop(minutes=3)
async def update_presence():
    API_URL = "http://localhost/app/api/ulpc"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, timeout=8) as response:
                if response.status == 200:
                    data = await response.json()

                    if data.get("success"):
                        stats = data["data"]["raw"]
                        users_count = stats["activeUsers"]
                        posts_count = stats["posts"]

                        statuses = [
                            f"👥 {users_count:,} users",
                            f"📝 {posts_count:,} posts",
                            "/help • BlinX",
                            f"🪙 1:100 rate",
                        ]

                        current_status = statuses[
                            int(datetime.datetime.now().timestamp()) % len(statuses)
                        ]

                        activity_type = disnake.ActivityType.watching
                        if "users" in current_status:
                            activity_type = disnake.ActivityType.watching
                        elif "posts" in current_status:
                            activity_type = disnake.ActivityType.watching
                        elif "rate" in current_status:
                            activity_type = disnake.ActivityType.watching
                        else:
                            activity_type = disnake.ActivityType.playing

                        activity = disnake.Activity(
                            name=current_status, type=activity_type
                        )

                        await bot.change_presence(
                            activity=activity, status=disnake.Status.online
                        )

                        print(f"Presence updated: {current_status}")

    except Exception as e:
        fallback_statuses = [
            "BlinX Economy",
            "/withdraw • 1:100",
            "💎 Premium Features",
            "🎮 BlinX Gaming",
        ]

        current_fallback = fallback_statuses[
            int(datetime.datetime.now().timestamp()) % len(fallback_statuses)
        ]

        await bot.change_presence(
            activity=disnake.Activity(
                name=current_fallback, type=disnake.ActivityType.playing
            ),
            status=disnake.Status.online,
        )


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    print(f"🔗 Connected to {len(bot.guilds)} guilds")
    print(f"👥 Serving {len(bot.users)} users")

    await update_presence.start()


@bot.event
async def on_member_join(member):
    await bot.log_user(f"👤 Member joined: {member.mention}")

    welcome_channel = bot.get_channel(1456676376630395025)
    if welcome_channel:
        welcome_embed = disnake.Embed(
            description=f"🎉 {member.mention} joined the server!",
            color=disnake.Color.green(),
            timestamp=datetime.datetime.now(),
        )

        welcome_embed.set_thumbnail(url=member.display_avatar.url)
        welcome_embed.set_footer(text=f"ID: {member.id}")

        await welcome_channel.send(embed=welcome_embed)


@bot.event
async def on_member_remove(member):
    await bot.log_user(f"👤 Member left: {member.name}#{member.discriminator}")

    welcome_channel = bot.get_channel(1456676376630395025)
    if welcome_channel:
        goodbye_embed = disnake.Embed(
            description=f"👋 {member.name} left the server",
            color=disnake.Color.red(),
            timestamp=datetime.datetime.now(),
        )

        await welcome_channel.send(embed=goodbye_embed)


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content_lower = message.content.lower()
    for word in bot.blacklisted_words:
        if word in content_lower:
            await message.delete()
            warning = await message.channel.send(
                f"{message.author.mention} Watch your language!", delete_after=3
            )
            await bot.log_moderation(
                f"🚫 Auto-mod: {message.author.mention} used blacklisted word in {message.channel.mention}"
            )
            break

    await bot.process_commands(message)


@bot.slash_command(name="create_pr", description="Create private voice channel")
async def create_pr(inter, channel_name: str, user_limit: int = 0):
    user_id = inter.author.id
    cash = await bot.get_cash(user_id)

    if user_limit == 0:
        price = 10000
    elif user_limit <= 2:
        price = 1500
    elif user_limit <= 8:
        price = 2500
    elif user_limit <= 15:
        price = 5000
    else:
        price = 10000

    if cash < price:
        embed = disnake.Embed(
            description=f"❌ Insufficient funds. Required: **{price}** cash",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if len(channel_name) > 32:
        embed = disnake.Embed(
            description="❌ Channel name too long (max 32 characters)",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if len(channel_name) < 3:
        embed = disnake.Embed(
            description="❌ Channel name too short (min 3 characters)",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    await bot.remove_cash(user_id, price)

    try:
        overwrites = {
            inter.guild.default_role: disnake.PermissionOverwrite(connect=False),
            inter.author: disnake.PermissionOverwrite(
                connect=True, manage_channels=True, manage_roles=True
            ),
        }

        category = None
        for cat in inter.guild.categories:
            if "PRIVATE" in cat.name.upper():
                category = cat
                break

        channel = await inter.guild.create_voice_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            user_limit=user_limit if user_limit > 0 else 0,
        )

        await bot.db.execute(
            "INSERT INTO private_channels (channel_id, owner_id, created_at) VALUES (?, ?, ?)",
            (channel.id, user_id, datetime.datetime.now().isoformat()),
        )
        await bot.db.commit()

        limit_text = f"{user_limit} users" if user_limit > 0 else "Unlimited"

        embed = disnake.Embed(
            title="✅ PRIVATE CHANNEL CREATED",
            description=f"**Channel:** {channel.mention}\n**Price paid:** {price} cash",
            color=disnake.Color.green(),
        )
        embed.add_field(name="OWNER", value=inter.author.mention, inline=True)
        embed.add_field(name="USER LIMIT", value=limit_text, inline=True)
        embed.add_field(name="CHANNEL ID", value=f"`{channel.id}`", inline=True)
        embed.set_footer(
            text="Use /delete_pr to delete or /transfer_pr to transfer ownership"
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

        await bot.log_economy(
            f"🔒 Private channel created: {inter.author.mention} ({inter.author.id}) - {channel_name} - {price} cash"
        )

    except Exception as e:
        await bot.add_cash(user_id, price)
        embed = disnake.Embed(
            description="❌ Failed to create channel. Refund issued.",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="delete_pr", description="Delete your private voice channel")
async def delete_pr(inter, channel_id: str):
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            embed = disnake.Embed(
                description="❌ Channel not found", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        async with bot.db.execute(
            "SELECT owner_id FROM private_channels WHERE channel_id = ?", (channel.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            embed = disnake.Embed(
                description="❌ This is not a registered private channel",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if row[0] != inter.author.id:
            embed = disnake.Embed(
                description="❌ You are not the owner of this channel",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        await channel.delete()

        await bot.db.execute(
            "DELETE FROM private_channels WHERE channel_id = ?", (channel.id,)
        )
        await bot.db.commit()

        embed = disnake.Embed(
            title="✅ CHANNEL DELETED",
            description=f"Private channel **{channel.name}** has been deleted",
            color=disnake.Color.green(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

        await bot.log_economy(
            f"🗑️ Private channel deleted: {inter.author.mention} - {channel.name}"
        )

    except ValueError:
        embed = disnake.Embed(
            description="❌ Invalid channel ID", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        embed = disnake.Embed(
            description="❌ Failed to delete channel", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="transfer_pr", description="Transfer private channel ownership")
async def transfer_pr(inter, channel_id: str, new_owner: disnake.Member):
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            embed = disnake.Embed(
                description="❌ Channel not found", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        async with bot.db.execute(
            "SELECT owner_id FROM private_channels WHERE channel_id = ?", (channel.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            embed = disnake.Embed(
                description="❌ This is not a registered private channel",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if row[0] != inter.author.id:
            embed = disnake.Embed(
                description="❌ You are not the owner of this channel",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if new_owner.bot:
            embed = disnake.Embed(
                description="❌ Cannot transfer to bot", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        overwrites = channel.overwrites

        if inter.author in overwrites:
            del overwrites[inter.author]

        overwrites[new_owner] = disnake.PermissionOverwrite(
            connect=True,
            manage_channels=True,
            manage_roles=True,
            move_members=True,
            mute_members=True,
            deafen_members=True,
        )

        await channel.edit(overwrites=overwrites)

        await bot.db.execute(
            "UPDATE private_channels SET owner_id = ? WHERE channel_id = ?",
            (new_owner.id, channel.id),
        )
        await bot.db.commit()

        embed = disnake.Embed(
            title="✅ OWNERSHIP TRANSFERRED",
            description=f"**Channel:** {channel.mention}\n**New owner:** {new_owner.mention}",
            color=disnake.Color.green(),
        )
        embed.set_footer(text=f"Transferred by {inter.author.name}")
        await inter.response.send_message(embed=embed, ephemeral=True)

        try:
            notify_embed = disnake.Embed(
                title="🔑 PRIVATE CHANNEL TRANSFERRED",
                description=f"You are now the owner of **{channel.name}**\n**Previous owner:** {inter.author.mention}\n**Channel ID:** `{channel.id}`",
                color=disnake.Color.blue(),
            )
            await new_owner.send(embed=notify_embed)
        except:
            pass

        await bot.log_economy(
            f"🔄 Ownership transferred: {channel.name} - {inter.author.mention} → {new_owner.mention}"
        )

    except ValueError:
        embed = disnake.Embed(
            description="❌ Invalid channel ID", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        embed = disnake.Embed(
            description="❌ Failed to transfer ownership", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


async def setup_db_tables():
    await bot.db.execute(
        """
        CREATE TABLE IF NOT EXISTS private_channels (
            channel_id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """
    )
    await bot.db.commit()


async def setup_db_tables():
    await bot.db.execute(
        """
        CREATE TABLE IF NOT EXISTS private_channels (
            channel_id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """
    )
    await bot.db.commit()


@bot.slash_command(name="blinx_check", description="Check user info from Blinx system")
async def blinx_check(inter, user_id: str):
    API_URL = "http://localhost/app/api/users"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_URL}?user={user_id}", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    if not data.get("success"):
                        embed = disnake.Embed(
                            description=f"❌ Error: {data.get('error', 'Unknown error')}",
                            color=disnake.Color.red(),
                        )
                        await inter.response.send_message(embed=embed, ephemeral=True)
                        return

                    user = data["data"]

                    embed = disnake.Embed(
                        title="🔍 BLINX USER INFO",
                        url=user["profile_url"],
                        color=disnake.Color.blue(),
                        timestamp=datetime.datetime.now(),
                    )

                    embed.add_field(
                        name="IDENTITY",
                        value=f"**ID:** `{user['id']}`\n**Username:** `{user['username']}`\n**Display:** {user['display_name']}",
                        inline=False,
                    )

                    status_text = []
                    if user["status"]["is_active"]:
                        status_text.append("🟢 Active")
                    else:
                        status_text.append("🔴 Inactive")

                    if user["status"]["is_verified"]:
                        status_text.append("✅ Verified")

                    if user["status"]["is_banned"]:
                        status_text.append("🔨 Banned")

                    if user["status"]["has_premium"]:
                        status_text.append("💎 Premium")

                    embed.add_field(
                        name="STATUS", value="\n".join(status_text), inline=True
                    )

                    roles_text = []
                    if user["status"]["is_moderator"]:
                        roles_text.append("🛡️ Moderator")
                    if user["status"]["is_admin"]:
                        roles_text.append("👑 Admin")
                    if user["status"]["is_employee"]:
                        roles_text.append("💼 Employee")

                    if roles_text:
                        embed.add_field(
                            name="ROLES", value="\n".join(roles_text), inline=True
                        )

                    embed.add_field(
                        name="ECONOMY",
                        value=f"**Blinks:** `{user['economy']['blinks']:,}`",
                        inline=False,
                    )

                    created_date = datetime.datetime.fromisoformat(
                        user["dates"]["created_at"].replace("Z", "+00:00")
                    ).strftime("%Y-%m-%d %H:%M")
                    last_login = (
                        datetime.datetime.fromisoformat(
                            user["dates"]["last_login"].replace("Z", "+00:00")
                        ).strftime("%Y-%m-%d %H:%M")
                        if user["dates"]["last_login"]
                        else "Never"
                    )

                    embed.add_field(
                        name="DATES",
                        value=f"**Created:** `{created_date}`\n**Last login:** `{last_login}`",
                        inline=False,
                    )

                    if user["status"]["is_banned"] and user["moderation"]["ban_reason"]:
                        embed.add_field(
                            name="BAN INFO",
                            value=f"**Reason:** {user['moderation']['ban_reason']}\n**Until:** {user['dates']['banned_until']}",
                            inline=False,
                        )

                    if user["bio"]:
                        embed.add_field(
                            name="BIO",
                            value=user["bio"][:200]
                            + ("..." if len(user["bio"]) > 200 else ""),
                            inline=False,
                        )

                    embed.add_field(
                        name="PROFILE",
                        value=f"[View on Blinx]({user['profile_url']})",
                        inline=False,
                    )

                    embed.set_footer(text=f"Blinx ID: {user_id}")
                    await inter.response.send_message(embed=embed)

                else:
                    embed = disnake.Embed(
                        description="❌ API connection failed",
                        color=disnake.Color.red(),
                    )
                    await inter.response.send_message(embed=embed, ephemeral=True)

        except asyncio.TimeoutError:
            embed = disnake.Embed(
                description="❌ API request timeout", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            embed = disnake.Embed(
                description=f"❌ Error: {str(e)}", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_connect():
    os.makedirs("data", exist_ok=True)
    bot.db = await aiosqlite.connect("data/economy.db")
    await bot.init_db()
    await setup_db_tables()


@bot.event
async def on_member_join(member):
    await bot.log_user(f"👤 Member joined: {member.mention}")


@bot.event
async def on_member_remove(member):
    await bot.log_user(f"👤 Member left: {member.name}#{member.discriminator}")


@bot.event
async def on_member_ban(guild, user):
    await bot.log_user(f"🔨 Member banned: {user.name}#{user.discriminator}")


@bot.event
async def on_guild_channel_create(channel):
    await bot.log_moderation(f"📝 Channel created: {channel.name}")


@bot.event
async def on_guild_channel_delete(channel):
    await bot.log_moderation(f"📝 Channel deleted: {channel.name}")


@bot.event
async def on_guild_role_create(role):
    await bot.log_moderation(f"🎭 Role created: {role.name}")


@bot.event
async def on_guild_role_delete(role):
    await bot.log_moderation(f"🎭 Role deleted: {role.name}")


@bot.event
async def on_guild_role_update(before, after):
    if before.name != after.name:
        await bot.log_moderation(f"🎭 Role renamed: `{before.name}` → `{after.name}`")


@bot.slash_command(name="balance", description="Check your cash balance")
async def balance(inter):
    cash = await bot.get_cash(inter.author.id)
    embed = disnake.Embed(
        title="💳 Balance",
        description=f"You have **{cash}** cash",
        color=disnake.Color.purple(),
    )
    embed.set_thumbnail(url=inter.author.display_avatar.url)
    embed.set_footer(text=f"1 Blink = {bot.exchange_rate} cash")
    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="daily", description="Claim your daily reward")
async def daily(inter):
    user_id = inter.author.id

    if not await bot.check_cooldown(user_id, "daily", 86400):
        embed = disnake.Embed(
            description="Come back tomorrow for your daily reward!",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    reward = random.randint(500, 1500)
    await bot.add_cash(user_id, reward)

    embed = disnake.Embed(
        title="🎁 Daily Reward",
        description=f"Claimed **{reward}** cash",
        color=disnake.Color.gold(),
    )
    embed.set_footer(text="Available again in 24 hours")
    await inter.response.send_message(embed=embed)
    await bot.log_economy(f"🎁 Daily: {inter.author.mention} got {reward} cash")


@bot.slash_command(name="work", description="Work to earn cash")
async def work(inter):
    user_id = inter.author.id

    if not await bot.check_cooldown(user_id, "work", 3600):
        embed = disnake.Embed(
            description="Take a break! 1 hour cooldown remaining.",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    earnings = random.randint(100, 500)
    await bot.add_cash(user_id, earnings)

    embed = disnake.Embed(
        title="💼 Work Completed",
        description=f"Earned **{earnings}** cash",
        color=disnake.Color.dark_green(),
    )
    await inter.response.send_message(embed=embed)
    await bot.log_economy(f"💼 Work: {inter.author.mention} earned {earnings} cash")


@bot.slash_command(name="withdraw", description="Withdraw cash to Blinks")
async def withdraw(inter, amount: int, blinks_id: str):
    user_id = inter.author.id
    cash = await bot.get_cash(user_id)

    if cash < amount:
        embed = disnake.Embed(
            description="❌ Insufficient funds", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if amount < bot.exchange_rate:
        embed = disnake.Embed(
            description=f"❌ Minimum withdrawal: {bot.exchange_rate} cash",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    blinks = amount // bot.exchange_rate
    await bot.remove_cash(user_id, amount)

    channel = bot.get_channel(bot.withdraw_channel)
    if channel:
        embed = disnake.Embed(
            title="🔄 WITHDRAWAL REQUEST",
            color=disnake.Color.blue(),
            timestamp=datetime.datetime.now(),
        )
        embed.add_field(
            name="USER",
            value=f"{inter.author.mention}\n`{inter.author.id}`",
            inline=False,
        )
        embed.add_field(name="BLINX ID", value=f"`{blinks_id}`", inline=False)
        embed.add_field(
            name="AMOUNT", value=f"**{blinks}** Blinks\n`{amount}` cash", inline=False
        )
        embed.add_field(
            name="EXCHANGE RATE",
            value=f"1 Blink = {bot.exchange_rate} cash",
            inline=False,
        )
        embed.set_footer(text="Withdrawal request • Contact user within 12h")
        await channel.send(embed=embed)

    embed = disnake.Embed(
        title="✅ WITHDRAWAL INITIATED",
        description=f"**Amount:** {blinks} Blinks\n**Cash deducted:** {amount}",
        color=disnake.Color.green(),
    )
    embed.add_field(name="BLINX ID", value=f"`{blinks_id}`", inline=False)
    embed.add_field(
        name="PROCESSING TIME",
        value="Within **12 hours** funds will be credited to your Blinks account or admin will contact you via DM for clarification.",
        inline=False,
    )
    embed.set_footer(text="Do not submit duplicate requests")
    await inter.response.send_message(embed=embed, ephemeral=True)

    await bot.log_economy(
        f"🔄 Withdrawal: {inter.author.mention} ({inter.author.id}) → BlinX ID: `{blinks_id}` - {blinks} Blinks"
    )


@bot.slash_command(name="addcash", description="Add cash to user")
@commands.has_permissions(administrator=True)
async def addcash(inter, user: disnake.User, amount: int):
    await bot.add_cash(user.id, amount, admin=True)

    embed = disnake.Embed(
        title="✅ Cash Added",
        description=f"Added **{amount}** cash to {user.mention}",
        color=disnake.Color.green(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="removecash", description="Remove cash from user")
@commands.has_permissions(administrator=True)
async def removecash(inter, user: disnake.User, amount: int):
    success = await bot.remove_cash(user.id, amount, admin=True)

    if success:
        embed = disnake.Embed(
            title="✅ Cash Removed",
            description=f"Removed **{amount}** cash from {user.mention}",
            color=disnake.Color.red(),
        )
    else:
        embed = disnake.Embed(
            description="User not found in database", color=disnake.Color.red()
        )

    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="leaderboard", description="Top 10 richest users")
async def leaderboard(inter):
    async with bot.db.execute(
        "SELECT user_id, cash FROM economy ORDER BY cash DESC LIMIT 10"
    ) as cursor:
        rows = await cursor.fetchall()

    embed = disnake.Embed(title="🏆 Leaderboard", color=disnake.Color.dark_purple())

    description = ""
    for idx, (user_id, cash) in enumerate(rows, 1):
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"{idx}."
        description += f"{medal} {user.mention} - **{cash}** cash\n"

    if not description:
        description = "No users found"

    embed.description = description
    embed.set_footer(text="Total economy leaderboard")
    await inter.response.send_message(embed=embed)


@bot.slash_command(name="setrate", description="Set exchange rate (Owner only)")
async def setrate(inter, rate: int):
    if inter.author.id != OWNER_ID:
        embed = disnake.Embed(
            description="This command is restricted to the bot owner",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if rate < 1:
        embed = disnake.Embed(
            description="Rate must be at least 1", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    old_rate = bot.exchange_rate
    bot.exchange_rate = rate

    embed = disnake.Embed(
        title="✅ Exchange Rate Updated",
        description=f"Changed from `{old_rate}` to `{rate}`\n1 Blink = {rate} cash",
        color=disnake.Color.green(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)

    channel = bot.get_channel(bot.log_channels["economy"])
    if channel:
        log_embed = disnake.Embed(
            description=f"📊 Exchange rate changed: `{old_rate}` → `{rate}`",
            color=disnake.Color.gold(),
            timestamp=datetime.datetime.now(),
        )
        log_embed.set_footer(text=f"Changed by {inter.author.name}")
        await channel.send(embed=log_embed)


@bot.slash_command(name="resetcooldown", description="Reset user cooldown (Owner only)")
async def resetcooldown(inter, user: disnake.User):
    if inter.author.id != OWNER_ID:
        embed = disnake.Embed(
            description="This command is restricted to the bot owner",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    keys_to_remove = [
        key for key in bot.cooldowns.keys() if key.startswith(f"{user.id}_")
    ]
    for key in keys_to_remove:
        del bot.cooldowns[key]

    embed = disnake.Embed(
        title="✅ Cooldowns Reset",
        description=f"Reset all cooldowns for {user.mention}",
        color=disnake.Color.green(),
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(
    name="economystats", description="View economy statistics (Owner only)"
)
async def economystats(inter):
    if inter.author.id != OWNER_ID:
        embed = disnake.Embed(
            description="This command is restricted to the bot owner",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    async with bot.db.execute("SELECT COUNT(*), SUM(cash) FROM economy") as cursor:
        row = await cursor.fetchone()

    total_users = row[0] if row else 0
    total_cash = row[1] if row and row[1] else 0

    embed = disnake.Embed(title="📊 Economy Statistics", color=disnake.Color.blue())
    embed.add_field(name="Total Users", value=f"`{total_users}`", inline=True)
    embed.add_field(name="Total Cash", value=f"`{total_cash}`", inline=True)
    embed.add_field(
        name="Exchange Rate", value=f"1 Blink = `{bot.exchange_rate}` cash", inline=True
    )
    embed.add_field(
        name="Active Cooldowns", value=f"`{len(bot.cooldowns)}`", inline=True
    )
    embed.add_field(
        name="Blacklisted Words", value=f"`{len(bot.blacklisted_words)}`", inline=True
    )

    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(
    name="pr_guides", description="Post PR guides in channel (Admin only)"
)
@commands.has_permissions(administrator=True)
async def pr_guides(inter):
    try:
        if not inter.channel.permissions_for(inter.guild.me).send_messages:
            error_embed = disnake.Embed(
                description="❌ Bot doesn't have permission to send messages here",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=error_embed, ephemeral=True)
            return

        guide_embed = disnake.Embed(
            title="🎙️ PRIVATE VOICE CHANNELS - OFFICIAL GUIDE",
            description="Complete guide to creating and managing private voice channels",
            color=disnake.Color.gold(),
            timestamp=datetime.datetime.now(),
        )

        guide_embed.add_field(
            name="💰 PRICING SYSTEM",
            value="```\n• 1-2 users: 1,500 cash\n• 3-8 users: 2,500 cash\n• 9-15 users: 5,000 cash\n• Unlimited: 10,000 cash\n```",
            inline=False,
        )

        guide_embed.add_field(
            name="🔧 CREATING A PRIVATE ROOM",
            value="```/create_pr channel_name user_limit```\n**Examples:**\n• `/create_pr Gaming 5` → 5 users (2,500 cash)\n• `/create_pr Chill 0` → Unlimited users (10,000 cash)\n• `/create_pr Meeting 2` → 2 users (1,500 cash)",
            inline=False,
        )

        guide_embed.add_field(
            name="🆔 HOW TO GET CHANNEL ID",
            value="```\n1. Enable Developer Mode:\n   Settings → Advanced → Developer Mode\n\n2. Right-click voice channel\n3. Click 'Copy ID'\n```\n**Save your Channel ID!**",
            inline=False,
        )

        guide_embed.add_field(
            name="⚙️ MANAGEMENT COMMANDS",
            value="```\n• /delete_pr 123456789012345678\n   → Delete your channel (owner only)\n\n• /transfer_pr 123456789012345678 @User\n   → Transfer ownership to another user\n```",
            inline=False,
        )

        guide_embed.add_field(
            name="📝 IMPORTANT NOTES",
            value="```\n✓ Check balance: /balance\n✓ Unlimited = user_limit: 0\n✓ Channel ID is required for management\n✓ No refunds after creation\n✓ Technical issues → Contact admins\n```",
            inline=False,
        )

        guide_embed.add_field(
            name="💡 PRO TIPS",
            value="```\n• Choose name wisely (no spaces)\n• Backup your Channel ID\n• Consider user needs when setting limit\n• Transfer to trusted users only\n```",
            inline=False,
        )

        guide_embed.set_footer(
            text=f"Posted by {inter.author.name}",
            icon_url=inter.author.display_avatar.url,
        )

        await inter.response.send_message("📖 Sending guide...", ephemeral=True)
        await inter.channel.send(embed=guide_embed)

        await bot.log_moderation(
            f"📖 PR guide posted by {inter.author.mention} in #{inter.channel.name}"
        )

    except Exception as e:
        error_embed = disnake.Embed(
            description=f"❌ Error: {str(e)}", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=error_embed, ephemeral=True)


@pr_guides.error
async def pr_guides_error(inter, error):
    if isinstance(error, commands.MissingPermissions):
        embed = disnake.Embed(
            description="❌ Administrator permission required",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = disnake.Embed(
            description=f"❌ Unexpected error: {error}", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


class SupportTicketModal(disnake.ui.Modal):
    def __init__(self, problem_type):
        self.problem_type = problem_type
        components = [
            disnake.ui.TextInput(
                label="Describe your problem",
                placeholder="Please describe the issue in detail...",
                custom_id="problem_description",
                style=disnake.TextInputStyle.paragraph,
                min_length=20,
                max_length=1000,
                required=True,
            ),
            disnake.ui.TextInput(
                label="What have you tried?",
                placeholder="Steps you've already taken to solve the issue...",
                custom_id="tried_solutions",
                style=disnake.TextInputStyle.paragraph,
                max_length=500,
                required=False,
            ),
        ]

        if problem_type == "blinx":
            components.insert(
                0,
                disnake.ui.TextInput(
                    label="BlinX User ID",
                    placeholder="Enter your BlinX user ID...",
                    custom_id="blinx_id",
                    style=disnake.TextInputStyle.short,
                    required=True,
                ),
            )
            title = "BlinX Support Ticket"
        else:
            components.insert(
                0,
                disnake.ui.TextInput(
                    label="Discord Username",
                    placeholder="Enter your full Discord username (name#0000)...",
                    custom_id="discord_username",
                    style=disnake.TextInputStyle.short,
                    required=True,
                ),
            )
            title = "Discord Server Support Ticket"

        super().__init__(
            title=title,
            custom_id="support_ticket_modal",
            timeout=300,
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction):
        await inter.response.defer(ephemeral=True)

        user_id = inter.author.id
        key = f"{user_id}_support_ticket"
        now = datetime.datetime.now()

        if key in bot.cooldowns:
            if bot.cooldowns[key] > now:
                remaining = (bot.cooldowns[key] - now).total_seconds()
                embed = disnake.Embed(
                    description=f"❌ Please wait {int(remaining)} seconds before submitting another ticket",
                    color=disnake.Color.red(),
                )
                await inter.followup.send(embed=embed, ephemeral=True)
                return

        bot.cooldowns[key] = now + datetime.timedelta(hours=1)

        values = inter.text_values
        problem_desc = values.get("problem_description", "")
        tried_solutions = values.get("tried_solutions", "None mentioned")

        if self.problem_type == "blinx":
            blinx_id = values.get("blinx_id", "")
            identifier = f"BlinX ID: `{blinx_id}`"
        else:
            discord_username = values.get("discord_username", "")
            identifier = f"Discord: `{discord_username}`"

        ticket_id = str(inter.id)[:8]

        ticket_embed = disnake.Embed(
            title="🎫 NEW SUPPORT TICKET",
            color=disnake.Color.orange(),
            timestamp=datetime.datetime.now(),
        )

        ticket_embed.add_field(
            name="USER",
            value=f"{inter.author.mention}\n`{inter.author.id}`",
            inline=True,
        )
        ticket_embed.add_field(
            name="TYPE", value=f"**{self.problem_type.upper()}**", inline=True
        )
        ticket_embed.add_field(name="IDENTIFIER", value=identifier, inline=True)
        ticket_embed.add_field(
            name="PROBLEM",
            value=problem_desc[:500] + ("..." if len(problem_desc) > 500 else ""),
            inline=False,
        )
        ticket_embed.add_field(
            name="ATTEMPTS", value=tried_solutions[:200], inline=False
        )

        ticket_embed.set_footer(text=f"Ticket ID: {ticket_id}")

        support_channel = bot.get_channel(1456677723022950533)
        if support_channel:
            await support_channel.send(embed=ticket_embed)

        confirm_embed = disnake.Embed(
            title="✅ TICKET SUBMITTED",
            description="Your support ticket has been received. An admin will contact you soon.",
            color=disnake.Color.green(),
        )
        confirm_embed.add_field(
            name="Ticket Type", value=self.problem_type.capitalize(), inline=True
        )
        confirm_embed.add_field(name="Cooldown", value="1 hour", inline=True)
        confirm_embed.add_field(name="Ticket ID", value=f"`{ticket_id}`", inline=True)

        await inter.followup.send(embed=confirm_embed, ephemeral=True)

        await bot.log_moderation(
            f"🎫 Support ticket submitted by {inter.author.mention} ({self.problem_type}) | ID: {ticket_id}"
        )


class SupportButtonView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="BlinX Issue",
        style=disnake.ButtonStyle.blurple,
        emoji="🌐",
        custom_id="blinx_support",
    )
    async def blinx_support(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        await inter.response.send_modal(SupportTicketModal("blinx"))

    @disnake.ui.button(
        label="Discord Server Issue",
        style=disnake.ButtonStyle.green,
        emoji="🛡️",
        custom_id="discord_support",
    )
    async def discord_support(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        await inter.response.send_modal(SupportTicketModal("discord"))

    @disnake.ui.button(
        label="Private Room Help",
        style=disnake.ButtonStyle.red,
        emoji="🎙️",
        custom_id="pr_support",
    )
    async def pr_support(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        pr_guide_embed = disnake.Embed(
            title="🎙️ PRIVATE ROOM SUPPORT",
            description="Before submitting a ticket, please check these common issues:",
            color=disnake.Color.blue(),
        )

        pr_guide_embed.add_field(
            name="❓ Common Questions",
            value="```\n• Get Channel ID: Right-click → Copy ID\n• Not owner? Use /transfer_pr\n• Check balance: /balance\n• Pricing: /pr_guides\n```",
            inline=False,
        )

        pr_guide_embed.add_field(
            name="🚨 Urgent Issues",
            value="```\n• Channel disappeared → Admin abuse\n• Wrong money deducted → Technical error\n• Cannot delete → Check ownership\n```",
            inline=False,
        )

        pr_guide_embed.add_field(
            name="📞 Need More Help?",
            value="If your issue isn't listed above, click **Discord Server Issue** button",
            inline=False,
        )

        await inter.response.send_message(embed=pr_guide_embed, ephemeral=True)


@bot.slash_command(name="support", description="Setup support system (Admin only)")
@commands.has_permissions(administrator=True)
async def support_setup(inter):
    try:
        if not inter.channel.permissions_for(inter.guild.me).send_messages:
            error_embed = disnake.Embed(
                description="❌ Bot doesn't have permission to send messages here",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=error_embed, ephemeral=True)
            return

        support_embed = disnake.Embed(
            title="🛡️ BLINX SUPPORT SYSTEM",
            description="Need help? Choose the appropriate support option below:",
            color=disnake.Color.blurple(),
            timestamp=datetime.datetime.now(),
        )

        support_embed.add_field(
            name="🌐 BLINX PLATFORM ISSUES",
            value="• Account problems\n• Blinks transactions\n• Website access\n• Profile issues\n• Withdrawal problems",
            inline=True,
        )

        support_embed.add_field(
            name="🛡️ DISCORD SERVER ISSUES",
            value="• Bot commands\n• Cash system\n• Permissions\n• Rule violations\n• Moderation issues",
            inline=True,
        )

        support_embed.add_field(
            name="🎙️ PRIVATE ROOM HELP",
            value="• Creation problems\n• Ownership transfer\n• Deletion issues\n• Pricing questions\n• Access problems",
            inline=True,
        )

        support_embed.add_field(
            name="📝 TICKET GUIDELINES",
            value="```\n✓ Provide detailed description\n✓ Include relevant IDs\n✓ Mention what you've tried\n✓ One ticket per issue\n✓ 1 hour cooldown between tickets\n✓ Tickets sent to support channel\n```",
            inline=False,
        )

        support_embed.add_field(
            name="⏱️ RESPONSE TIME",
            value="• **Normal**: Within 24 hours\n• **Urgent**: Within 6 hours\n• **Critical**: Within 1 hour\n• **Location**: <#1456677723022950533>",
            inline=False,
        )

        support_embed.set_footer(
            text=f"Support system | Managed by {inter.author.name}",
            icon_url=inter.author.display_avatar.url,
        )

        view = SupportButtonView()

        await inter.response.send_message(
            "🛡️ Setting up support system...", ephemeral=True
        )
        await inter.channel.send(embed=support_embed, view=view)

        await bot.log_moderation(
            f"🛡️ Support system setup by {inter.author.mention} in #{inter.channel.name}"
        )

    except Exception as e:
        error_embed = disnake.Embed(
            description=f"❌ Error: {str(e)}", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=error_embed, ephemeral=True)


@support_setup.error
async def support_setup_error(inter, error):
    if isinstance(error, commands.MissingPermissions):
        embed = disnake.Embed(
            description="❌ Administrator permission required",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = disnake.Embed(
            description=f"❌ Unexpected error: {error}", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


@addcash.error
@removecash.error
async def admin_error(inter, error):
    if isinstance(error, commands.MissingPermissions):
        embed = disnake.Embed(
            description="Insufficient permissions", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


bot.run(TOKEN)
