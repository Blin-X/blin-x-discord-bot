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
    raise ValueError("Токен не найден")

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
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id TEXT PRIMARY KEY,
                user_id INTEGER,
                channel_id INTEGER,
                created_at TIMESTAMP,
                status TEXT DEFAULT 'open'
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
                    description=f"Админ действие: `{amount}` наличных добавлено <@{user_id}>",
                    color=0x6A0DAD,
                    timestamp=datetime.datetime.now(),
                )
                embed.set_footer(text=f"ID пользователя: {user_id}")
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
                    description=f"Админ действие: `{amount}` наличных удалено у <@{user_id}>",
                    color=0x6A0DAD,
                    timestamp=datetime.datetime.now(),
                )
                embed.set_footer(text=f"ID пользователя: {user_id}")
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
                color=0x6A0DAD,
                timestamp=datetime.datetime.now(),
            )
            await channel.send(embed=embed)

    async def log_user(self, message: str):
        channel = self.get_channel(self.log_channels["user"])
        if channel:
            embed = disnake.Embed(
                description=message,
                color=0x6A0DAD,
                timestamp=datetime.datetime.now(),
            )
            await channel.send(embed=embed)

    async def log_moderation(self, message: str):
        channel = self.get_channel(self.log_channels["moderation"])
        if channel:
            embed = disnake.Embed(
                description=message,
                color=0x6A0DAD,
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
    name="check_blinx_community",
    description="Проверить информацию о сообществе из системы Blinx",
)
async def check_blinx_community(inter, community_id: str):
    await inter.response.defer()  # ✅ ДОБАВЬТЕ ЭТО

    API_URL = "http://blinx-dev.online/app/api/communities/"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                f"{API_URL}?id={community_id}", timeout=10
            ) as response:
                if response.status == 200:
                    data = await response.json()

                    if not data.get("success"):
                        embed = disnake.Embed(
                            description=f"Ошибка: {data.get('error', 'Неизвестная ошибка')}",
                            color=disnake.Color.red(),
                        )
                        await inter.edit_original_response(
                            embed=embed
                        ) 
                        return

                    community = data["data"]

                    embed = disnake.Embed(
                        title=f"🏘️ {community['name']}",
                        url=community["urls"]["profile"],
                        color=0x6A0DAD,
                        timestamp=datetime.datetime.now(),
                    )

                    if community["description"]:
                        embed.description = community["description"][:200] + (
                            "..." if len(community["description"]) > 200 else ""
                        )

                    embed.add_field(
                        name="📊 СТАТИСТИКА",
                        value=f"**Участники:** `{community['stats']['members']:,}`\n**Посты:** `{community['stats']['posts']:,}`",
                        inline=True,
                    )

                    status_text = []
                    if community["status"]["is_verified"]:
                        status_text.append("✅ Проверено")

                    if community["visibility"]["is_private"]:
                        status_text.append("🔒 Приватное")
                    else:
                        status_text.append("🔓 Публичное")

                    if community["visibility"]["is_public_feed"]:
                        status_text.append("📢 Публичная лента")

                    embed.add_field(
                        name="🔍 СТАТУС",
                        value="\n".join(status_text) if status_text else "Стандартное",
                        inline=True,
                    )

                    embed.add_field(
                        name="👑 СОЗДАТЕЛЬ",
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
                                f"... и еще {len(community['admins']) - 5}"
                            )

                        embed.add_field(
                            name=f"🛡️ КОМАНДА АДМИНОВ ({len(community['admins'])})",
                            value="\n".join(admins_text),
                            inline=False,
                        )

                    if community["recent_posts"]:
                        posts_text = []
                        for post in community["recent_posts"][:3]:
                            posts_text.append(f"• {post['content_preview']}")

                        embed.add_field(
                            name="📝 ПОСЛЕДНИЕ ПОСТЫ",
                            value="\n".join(posts_text),
                            inline=False,
                        )

                    created_date = datetime.datetime.fromisoformat(
                        community["dates"]["created_at"].replace("Z", "+00:00")
                    )
                    age_days = (datetime.datetime.now() - created_date).days

                    embed.add_field(
                        name="📅 СОЗДАНО",
                        value=f"`{created_date.strftime('%Y-%m-%d')}`\n({age_days} дней назад)",
                        inline=True,
                    )

                    embed.add_field(
                        name="🔗 ПРОФИЛЬ",
                        value=f"[Открыть в Blinx]({community['urls']['profile']})",
                        inline=True,
                    )

                    if community["avatar_url"]:
                        embed.set_thumbnail(url=community["avatar_url"])

                    embed.set_footer(text=f"ID сообщества: {community_id}")
                    await inter.edit_original_response(
                        embed=embed
                    ) 

                else:
                    embed = disnake.Embed(
                        description="Не удалось получить данные сообщества",
                        color=disnake.Color.red(),
                    )
                    await inter.edit_original_response(
                        embed=embed
                    ) 

        except asyncio.TimeoutError:
            embed = disnake.Embed(
                description="Таймаут запроса", color=disnake.Color.orange()
            )
            await inter.edit_original_response(
                embed=embed
            ) 

        except Exception as e:
            embed = disnake.Embed(
                description=f"Ошибка: {str(e)[:200]}", color=disnake.Color.red()
            )
            await inter.edit_original_response(
                embed=embed
            ) 


@bot.slash_command(name="help", description="Показать все доступные команды")
async def help_command(inter):
    embed = disnake.Embed(
        title="🔧 КОМАНДЫ BLINX БОТА",
        description="**Экономика и финансы**",
        color=0x6A0DAD,
        timestamp=datetime.datetime.now(),
    )

    economy_commands = """
    **💳 Баланс**
    `/balance` - Проверить баланс наличных

    **🎁 Ежедневная награда**
    `/daily` - Получить ежедневную награду

    **💼 Работа**
    `/work` - Работать для заработка наличных (перезарядка 1 час)

    **🔄 Вывод**
    `/withdraw <amount> <blinx_id>` - Конвертировать наличные в Blinks
    *Курс: 1 Blink = 100 наличных*

    **🏆 Таблица лидеров**
    `/leaderboard` - Топ 10 самых богатых пользователей
    """

    embed.add_field(name="💰 СИСТЕМА ЭКОНОМИКИ", value=economy_commands, inline=False)

    private_rooms = """
    **🔒 Создать приватную комнату**
    `/create_pr <channel_name> <user_limit>`
    *Цены:*
    • ≤2 пользователей: 1,500 наличных
    • ≤8 пользователей: 2,500 наличных
    • ≤15 пользователей: 5,000 наличных
    • Без ограничений: 10,000 наличных

    **🗑️ Удалить приватную комнату**
    `/delete_pr <channel_id>` - Удалить ваш приватный канал

    **🔑 Передать владение**
    `/transfer_pr <channel_id> <new_owner>` - Передать владение каналом
    """

    embed.add_field(
        name="🎙️ ПРИВАТНЫЕ ГОЛОСОВЫЕ КАНАЛЫ", value=private_rooms, inline=False
    )

    admin_commands = """
    **➕ Добавить наличные**
    `/addcash <user> <amount>` - Только для админов

    **➖ Удалить наличные**
    `/removecash <user> <amount>` - Только для админов

    **⚙️ Установить курс обмена**
    `/setrate <rate>` - Только для владельца

    **🔄 Сбросить перезарядку**
    `/resetcooldown <user>` - Только для владельца

    **📊 Статистика экономики**
    `/economystats` - Только для владельца
    """

    embed.add_field(
        name="👑 КОМАНДЫ АДМИНИСТРАТОРА", value=admin_commands, inline=False
    )

    blinx_system = """
    **👤 Проверить пользователя**
    `/blinx_check <user_id>` - Получить информацию о пользователе из BlinX

    **🏘️ Проверить сообщество**
    `/check_blinx_community <community_id>` - Получить информацию о сообществе

    **🌐 Статус системы**
    `/blinx_status` - Проверить статус сайта BlinX
    """

    embed.add_field(
        name="🔗 ИНТЕГРАЦИЯ С СИСТЕМОЙ BLINX", value=blinx_system, inline=False
    )

    features = """
    **🛡️ Авто-модерация**
    • Автоматическая фильтрация запрещенных слов
    • Удаление сообщений и предупреждения
    • Логирование в канал модерации

    **📊 Система логирования**
    • Экономические транзакции
    • Вход/выход/бан пользователей
    • Изменения каналов и ролей
    • Действия модерации
    """

    embed.add_field(name="⚡ ФУНКЦИИ", value=features, inline=False)

    embed.set_footer(
        text=f"Запрошено {inter.author.name}",
        icon_url=inter.author.display_avatar.url,
    )

    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="blinx_status", description="Проверить статус сайта BlinX")
async def blinx_status(inter):
    API_URL = "https://blinx-dev.online/"

    async with aiohttp.ClientSession() as session:
        try:
            start_time = datetime.datetime.now()

            async with session.get(API_URL, timeout=10) as response:
                end_time = datetime.datetime.now()
                response_time = (end_time - start_time).total_seconds() * 1000

                status_emoji = "✅" if response.status == 200 else "❌"
                status_text = "ОНЛАЙН" if response.status == 200 else "ОФФЛАЙН"
                color = 0x6A0DAD if response.status == 200 else disnake.Color.red()

                embed = disnake.Embed(
                    title=f"{status_emoji} СТАТУС BLINX - {status_text}",
                    color=color,
                    timestamp=datetime.datetime.now(),
                )

                embed.add_field(
                    name="🌐 САЙТ", value=f"[blinx-dev.online]({API_URL})", inline=True
                )

                embed.add_field(
                    name="📊 КОД СТАТУСА", value=f"`{response.status}`", inline=True
                )

                embed.add_field(
                    name="⚡ ВРЕМЯ ОТВЕТА",
                    value=f"`{response_time:.0f}мс`",
                    inline=True,
                )

                if response.status != 200:
                    embed.add_field(
                        name="⚠️ ВНИМАНИЕ",
                        value="Сайт испытывает проблемы",
                        inline=False,
                    )

                embed.set_footer(text=f"Проверено в {end_time.strftime('%H:%M:%S')}")

                await inter.response.send_message(embed=embed)

        except asyncio.TimeoutError:
            embed = disnake.Embed(
                title="⏱️ СТАТУС BLINX - ТАЙМАУТ",
                description="Сайт слишком долго отвечал",
                color=disnake.Color.orange(),
                timestamp=datetime.datetime.now(),
            )
            embed.add_field(
                name="🌐 САЙТ", value="[blinx-dev.online](https://blinx-dev.online/)"
            )
            embed.add_field(name="⚡ ВРЕМЯ ОТВЕТА", value="> 10 секунд")
            embed.set_footer(text="Таймаут соединения")
            await inter.response.send_message(embed=embed)

        except Exception as e:
            embed = disnake.Embed(
                title="❌ СТАТУС BLINX - ОШИБКА",
                description="Не удалось проверить статус сайта",
                color=disnake.Color.red(),
                timestamp=datetime.datetime.now(),
            )
            embed.add_field(
                name="🌐 САЙТ", value="[blinx-dev.online](https://blinx-dev.online/)"
            )
            embed.add_field(name="❓ ОШИБКА", value=str(e)[:100])
            await inter.response.send_message(embed=embed)


@tasks.loop(minutes=3)
async def update_presence():
    API_URL = "http://blinx-dev.online/app/api/ulpc"

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
                            f"👥 {users_count:,} пользователей",
                            f"📝 {posts_count:,} постов",
                            "/help • BlinX",
                            f"🪙 1:100 курс",
                        ]

                        current_status = statuses[
                            int(datetime.datetime.now().timestamp()) % len(statuses)
                        ]

                        activity_type = disnake.ActivityType.watching
                        if "пользователей" in current_status:
                            activity_type = disnake.ActivityType.watching
                        elif "постов" in current_status:
                            activity_type = disnake.ActivityType.watching
                        elif "курс" in current_status:
                            activity_type = disnake.ActivityType.watching
                        else:
                            activity_type = disnake.ActivityType.playing

                        activity = disnake.Activity(
                            name=current_status, type=activity_type
                        )

                        await bot.change_presence(
                            activity=activity, status=disnake.Status.online
                        )

    except Exception as e:
        fallback_statuses = [
            "BlinX Экономика",
            "/withdraw • 1:100",
            "💎 Премиум функции",
            "🎮 BlinX Игры",
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
    print(f"Бот {bot.user} запущен")
    print(f"Подключен к {len(bot.guilds)} серверам")
    print(f"Обслуживает {len(bot.users)} пользователей")

    await update_presence.start()


@bot.event
async def on_member_join(member):
    await bot.log_user(f"Пользователь присоединился: {member.mention}")

    welcome_channel = bot.get_channel(1456676376630395025)
    if welcome_channel:
        welcome_embed = disnake.Embed(
            description=f"🎉 {member.mention} присоединился к серверу!",
            color=0x6A0DAD,
            timestamp=datetime.datetime.now(),
        )

        welcome_embed.set_thumbnail(url=member.display_avatar.url)
        welcome_embed.set_footer(text=f"ID: {member.id}")

        await welcome_channel.send(embed=welcome_embed)


@bot.event
async def on_member_remove(member):
    await bot.log_user(
        f"Пользователь покинул сервер: {member.name}#{member.discriminator}"
    )

    welcome_channel = bot.get_channel(1456676376630395025)
    if welcome_channel:
        goodbye_embed = disnake.Embed(
            description=f"👋 {member.name} покинул сервер",
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
                f"{message.author.mention} Следите за языком!", delete_after=3
            )
            await bot.log_moderation(
                f"Авто-мод: {message.author.mention} использовал запрещенное слово в {message.channel.mention}"
            )
            break

    await bot.process_commands(message)


@bot.slash_command(name="create_pr", description="Создать приватный голосовой канал")
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
            description=f"Недостаточно средств. Требуется: **{price}** наличных",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if len(channel_name) > 32:
        embed = disnake.Embed(
            description="Название канала слишком длинное (максимум 32 символа)",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if len(channel_name) < 3:
        embed = disnake.Embed(
            description="Название канала слишком короткое (минимум 3 символа)",
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

        limit_text = (
            f"{user_limit} пользователей" if user_limit > 0 else "Без ограничений"
        )

        embed = disnake.Embed(
            title="✅ ПРИВАТНЫЙ КАНАЛ СОЗДАН",
            description=f"**Канал:** {channel.mention}\n**Оплачено:** {price} наличных",
            color=0x6A0DAD,
        )
        embed.add_field(name="ВЛАДЕЛЕЦ", value=inter.author.mention, inline=True)
        embed.add_field(name="ЛИМИТ ПОЛЬЗОВАТЕЛЕЙ", value=limit_text, inline=True)
        embed.add_field(name="ID КАНАЛА", value=f"`{channel.id}`", inline=True)
        embed.set_footer(
            text="Используйте /delete_pr для удаления или /transfer_pr для передачи владения"
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

        await bot.log_economy(
            f"Приватный канал создан: {inter.author.mention} ({inter.author.id}) - {channel_name} - {price} наличных"
        )

    except Exception as e:
        await bot.add_cash(user_id, price)
        embed = disnake.Embed(
            description="Не удалось создать канал. Средства возвращены.",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(
    name="delete_pr", description="Удалить ваш приватный голосовой канал"
)
async def delete_pr(inter, channel_id: str):
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            embed = disnake.Embed(
                description="Канал не найден", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        async with bot.db.execute(
            "SELECT owner_id FROM private_channels WHERE channel_id = ?", (channel.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            embed = disnake.Embed(
                description="Это не зарегистрированный приватный канал",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if row[0] != inter.author.id:
            embed = disnake.Embed(
                description="Вы не владелец этого канала",
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
            title="✅ КАНАЛ УДАЛЕН",
            description=f"Приватный канал **{channel.name}** был удален",
            color=0x6A0DAD,
        )
        await inter.response.send_message(embed=embed, ephemeral=True)

        await bot.log_economy(
            f"Приватный канал удален: {inter.author.mention} - {channel.name}"
        )

    except ValueError:
        embed = disnake.Embed(
            description="Неверный ID канала", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        embed = disnake.Embed(
            description="Не удалось удалить канал", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(
    name="transfer_pr", description="Передать владение приватным каналом"
)
async def transfer_pr(inter, channel_id: str, new_owner: disnake.Member):
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            embed = disnake.Embed(
                description="Канал не найден", color=disnake.Color.red()
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        async with bot.db.execute(
            "SELECT owner_id FROM private_channels WHERE channel_id = ?", (channel.id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            embed = disnake.Embed(
                description="Это не зарегистрированный приватный канал",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if row[0] != inter.author.id:
            embed = disnake.Embed(
                description="Вы не владелец этого канала",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=embed, ephemeral=True)
            return

        if new_owner.bot:
            embed = disnake.Embed(
                description="Нельзя передать боту", color=disnake.Color.red()
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
            title="✅ ВЛАДЕНИЕ ПЕРЕДАНО",
            description=f"**Канал:** {channel.mention}\n**Новый владелец:** {new_owner.mention}",
            color=0x6A0DAD,
        )
        embed.set_footer(text=f"Передано {inter.author.name}")
        await inter.response.send_message(embed=embed, ephemeral=True)

        try:
            notify_embed = disnake.Embed(
                title="🔑 ВЛАДЕНИЕ ПРИВАТНЫМ КАНАЛОМ ПЕРЕДАНО",
                description=f"Теперь вы владелец **{channel.name}**\n**Предыдущий владелец:** {inter.author.mention}\n**ID канала:** `{channel.id}`",
                color=0x6A0DAD,
            )
            await new_owner.send(embed=notify_embed)
        except:
            pass

        await bot.log_economy(
            f"Владение передано: {channel.name} - {inter.author.mention} → {new_owner.mention}"
        )

    except ValueError:
        embed = disnake.Embed(
            description="Неверный ID канала", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        embed = disnake.Embed(
            description="Не удалось передать владение", color=disnake.Color.red()
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


@bot.slash_command(name="blinx_check", description="Проверить информацию о пользователе из системы Blinx")
async def blinx_check(inter, user_id: str):
    await inter.response.defer() 
    
    API_URL = "http://blinx-dev.online/app/api/users"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_URL}?user={user_id}", timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    if not data.get("success"):
                        embed = disnake.Embed(
                            description=f"Ошибка: {data.get('error', 'Неизвестная ошибка')}",
                            color=disnake.Color.red(),
                        )
                        await inter.edit_original_response(embed=embed)
                        return

                    user = data["data"]

                    embed = disnake.Embed(
                        title="🔍 ИНФОРМАЦИЯ О ПОЛЬЗОВАТЕЛЕ BLINX",
                        url=user["profile_url"],
                        color=0x6A0DAD,
                        timestamp=datetime.datetime.now(),
                    )

                    embed.add_field(
                        name="ИДЕНТИФИКАЦИЯ",
                        value=f"**ID:** `{user['id']}`\n**Имя пользователя:** `{user['username']}`\n**Отображаемое имя:** {user['display_name']}",
                        inline=False,
                    )

                    status_text = []
                    if user["status"]["is_active"]:
                        status_text.append("🟢 Активен")
                    else:
                        status_text.append("🔴 Неактивен")

                    if user["status"]["is_verified"]:
                        status_text.append("✅ Проверен")

                    if user["status"]["is_banned"]:
                        status_text.append("🔨 Забанен")

                    if user["status"]["has_premium"]:
                        status_text.append("💎 Премиум")

                    embed.add_field(
                        name="СТАТУС", value="\n".join(status_text), inline=True
                    )

                    roles_text = []
                    if user["status"]["is_moderator"]:
                        roles_text.append("🛡️ Модератор")
                    if user["status"]["is_admin"]:
                        roles_text.append("👑 Админ")
                    if user["status"]["is_employee"]:
                        roles_text.append("💼 Сотрудник")

                    if roles_text:
                        embed.add_field(
                            name="РОЛИ", value="\n".join(roles_text), inline=True
                        )

                    embed.add_field(
                        name="ЭКОНОМИКА",
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
                        else "Никогда"
                    )

                    embed.add_field(
                        name="ДАТЫ",
                        value=f"**Создан:** `{created_date}`\n**Последний вход:** `{last_login}`",
                        inline=False,
                    )

                    if user["status"]["is_banned"] and user["moderation"]["ban_reason"]:
                        embed.add_field(
                            name="ИНФОРМАЦИЯ О БАНЕ",
                            value=f"**Причина:** {user['moderation']['ban_reason']}\n**До:** {user['dates']['banned_until']}",
                            inline=False,
                        )

                    if user["bio"]:
                        embed.add_field(
                            name="БИО",
                            value=user["bio"][:200]
                            + ("..." if len(user["bio"]) > 200 else ""),
                            inline=False,
                        )

                    embed.add_field(
                        name="ПРОФИЛЬ",
                        value=f"[Посмотреть в Blinx]({user['profile_url']})",
                        inline=False,
                    )

                    embed.set_footer(text=f"Blinx ID: {user_id}")
                    await inter.edit_original_response(embed=embed) 

                else:
                    embed = disnake.Embed(
                        description="Не удалось подключиться к API",
                        color=disnake.Color.red(),
                    )
                    await inter.edit_original_response(embed=embed)

        except asyncio.TimeoutError:
            embed = disnake.Embed(
                description="Таймаут запроса API", color=disnake.Color.red()
            )
            await inter.edit_original_response(embed=embed)

        except Exception as e:
            embed = disnake.Embed(
                description=f"Ошибка: {str(e)}", color=disnake.Color.red()
            )
            await inter.edit_original_response(embed=embed) 


@bot.event
async def on_connect():
    os.makedirs("data", exist_ok=True)
    bot.db = await aiosqlite.connect("data/economy.db")
    await bot.init_db()
    await setup_db_tables()


@bot.event
async def on_member_join(member):
    await bot.log_user(f"Пользователь присоединился: {member.mention}")


@bot.event
async def on_member_remove(member):
    await bot.log_user(f"Пользователь покинул: {member.name}#{member.discriminator}")


@bot.event
async def on_member_ban(guild, user):
    await bot.log_user(f"Пользователь забанен: {user.name}#{user.discriminator}")


@bot.event
async def on_guild_channel_create(channel):
    await bot.log_moderation(f"Канал создан: {channel.name}")


@bot.event
async def on_guild_channel_delete(channel):
    await bot.log_moderation(f"Канал удален: {channel.name}")


@bot.event
async def on_guild_role_create(role):
    await bot.log_moderation(f"Роль создана: {role.name}")


@bot.event
async def on_guild_role_delete(role):
    await bot.log_moderation(f"Роль удалена: {role.name}")


@bot.event
async def on_guild_role_update(before, after):
    if before.name != after.name:
        await bot.log_moderation(
            f"Роль переименована: `{before.name}` → `{after.name}`"
        )


@bot.slash_command(name="balance", description="Проверить баланс наличных")
async def balance(inter):
    cash = await bot.get_cash(inter.author.id)
    embed = disnake.Embed(
        title="💳 Баланс",
        description=f"У вас **{cash}** наличных",
        color=0x6A0DAD,
    )
    embed.set_thumbnail(url=inter.author.display_avatar.url)
    embed.set_footer(text=f"1 Blink = {bot.exchange_rate} наличных")
    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="daily", description="Получить ежедневную награду")
async def daily(inter):
    user_id = inter.author.id

    if not await bot.check_cooldown(user_id, "daily", 86400):
        embed = disnake.Embed(
            description="Возвращайтесь завтра за ежедневной наградой!",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    reward = random.randint(500, 1500)
    await bot.add_cash(user_id, reward)

    embed = disnake.Embed(
        title="🎁 Ежедневная награда",
        description=f"Получено **{reward}** наличных",
        color=0x6A0DAD,
    )
    embed.set_footer(text="Доступно снова через 24 часа")
    await inter.response.send_message(embed=embed)
    await bot.log_economy(
        f"Ежедневная награда: {inter.author.mention} получил {reward} наличных"
    )


@bot.slash_command(name="work", description="Работать для заработка наличных")
async def work(inter):
    user_id = inter.author.id

    if not await bot.check_cooldown(user_id, "work", 3600):
        embed = disnake.Embed(
            description="Сделайте перерыв! Перезарядка 1 час.",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    earnings = random.randint(100, 500)
    await bot.add_cash(user_id, earnings)

    embed = disnake.Embed(
        title="💼 Работа завершена",
        description=f"Заработано **{earnings}** наличных",
        color=0x6A0DAD,
    )
    await inter.response.send_message(embed=embed)
    await bot.log_economy(
        f"Работа: {inter.author.mention} заработал {earnings} наличных"
    )


@bot.slash_command(name="withdraw", description="Вывести наличные в Blinks")
async def withdraw(inter, amount: int, blinks_id: str):
    user_id = inter.author.id
    cash = await bot.get_cash(user_id)

    if cash < amount:
        embed = disnake.Embed(
            description="Недостаточно средств", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if amount < bot.exchange_rate:
        embed = disnake.Embed(
            description=f"Минимальный вывод: {bot.exchange_rate} наличных",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    blinks = amount // bot.exchange_rate
    await bot.remove_cash(user_id, amount)

    channel = bot.get_channel(bot.withdraw_channel)
    if channel:
        embed = disnake.Embed(
            title="🔄 ЗАПРОС НА ВЫВОД",
            color=0x6A0DAD,
            timestamp=datetime.datetime.now(),
        )
        embed.add_field(
            name="ПОЛЬЗОВАТЕЛЬ",
            value=f"{inter.author.mention}\n`{inter.author.id}`",
            inline=False,
        )
        embed.add_field(name="BLINX ID", value=f"`{blinks_id}`", inline=False)
        embed.add_field(
            name="СУММА",
            value=f"**{blinks}** Blinks\n`{amount}` наличных",
            inline=False,
        )
        embed.add_field(
            name="КУРС ОБМЕНА",
            value=f"1 Blink = {bot.exchange_rate} наличных",
            inline=False,
        )
        embed.set_footer(
            text="Запрос на вывод • Свяжитесь с пользователем в течение 12ч"
        )
        await channel.send(embed=embed)

    embed = disnake.Embed(
        title="✅ ВЫВОД ИНИЦИИРОВАН",
        description=f"**Сумма:** {blinks} Blinks\n**Списано наличных:** {amount}",
        color=0x6A0DAD,
    )
    embed.add_field(name="BLINX ID", value=f"`{blinks_id}`", inline=False)
    embed.add_field(
        name="ВРЕМЯ ОБРАБОТКИ",
        value="В течение **12 часов** средства будут зачислены на ваш аккаунт Blinks или администратор свяжется с вами через ЛС для уточнения.",
        inline=False,
    )
    embed.set_footer(text="Не отправляйте повторные запросы")
    await inter.response.send_message(embed=embed, ephemeral=True)

    await bot.log_economy(
        f"Вывод: {inter.author.mention} ({inter.author.id}) → BlinX ID: `{blinks_id}` - {blinks} Blinks"
    )


@bot.slash_command(name="addcash", description="Добавить наличные пользователю")
@commands.has_permissions(administrator=True)
async def addcash(inter, user: disnake.User, amount: int):
    await bot.add_cash(user.id, amount, admin=True)

    embed = disnake.Embed(
        title="✅ Наличные добавлены",
        description=f"Добавлено **{amount}** наличных пользователю {user.mention}",
        color=0x6A0DAD,
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="removecash", description="Удалить наличные у пользователя")
@commands.has_permissions(administrator=True)
async def removecash(inter, user: disnake.User, amount: int):
    success = await bot.remove_cash(user.id, amount, admin=True)

    if success:
        embed = disnake.Embed(
            title="✅ Наличные удалены",
            description=f"Удалено **{amount}** наличных у пользователя {user.mention}",
            color=0x6A0DAD,
        )
    else:
        embed = disnake.Embed(
            description="Пользователь не найден в базе данных",
            color=disnake.Color.red(),
        )

    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(name="leaderboard", description="Топ 10 самых богатых пользователей")
async def leaderboard(inter):
    async with bot.db.execute(
        "SELECT user_id, cash FROM economy ORDER BY cash DESC LIMIT 10"
    ) as cursor:
        rows = await cursor.fetchall()

    embed = disnake.Embed(title="🏆 Таблица лидеров", color=0x6A0DAD)

    description = ""
    for idx, (user_id, cash) in enumerate(rows, 1):
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        medal = ["🥇", "🥈", "🥉"][idx - 1] if idx <= 3 else f"{idx}."
        description += f"{medal} {user.mention} - **{cash}** наличных\n"

    if not description:
        description = "Пользователи не найдены"

    embed.description = description
    embed.set_footer(text="Общая таблица лидеров экономики")
    await inter.response.send_message(embed=embed)


@bot.slash_command(
    name="setrate", description="Установить курс обмена (только для владельца)"
)
async def setrate(inter, rate: int):
    if inter.author.id != OWNER_ID:
        embed = disnake.Embed(
            description="Эта команда доступна только владельцу бота",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if rate < 1:
        embed = disnake.Embed(
            description="Курс должен быть не менее 1", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    old_rate = bot.exchange_rate
    bot.exchange_rate = rate

    embed = disnake.Embed(
        title="✅ Курс обмена обновлен",
        description=f"Изменено с `{old_rate}` на `{rate}`\n1 Blink = {rate} наличных",
        color=0x6A0DAD,
    )
    await inter.response.send_message(embed=embed, ephemeral=True)

    channel = bot.get_channel(bot.log_channels["economy"])
    if channel:
        log_embed = disnake.Embed(
            description=f"Курс обмена изменен: `{old_rate}` → `{rate}`",
            color=0x6A0DAD,
            timestamp=datetime.datetime.now(),
        )
        log_embed.set_footer(text=f"Изменено {inter.author.name}")
        await channel.send(embed=log_embed)


@bot.slash_command(
    name="resetcooldown",
    description="Сбросить перезарядку пользователя (только для владельца)",
)
async def resetcooldown(inter, user: disnake.User):
    if inter.author.id != OWNER_ID:
        embed = disnake.Embed(
            description="Эта команда доступна только владельцу бота",
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
        title="✅ Перезарядки сброшены",
        description=f"Сброшены все перезарядки для {user.mention}",
        color=0x6A0DAD,
    )
    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(
    name="economystats",
    description="Просмотреть статистику экономики (только для владельца)",
)
async def economystats(inter):
    if inter.author.id != OWNER_ID:
        embed = disnake.Embed(
            description="Эта команда доступна только владельцу бота",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    async with bot.db.execute("SELECT COUNT(*), SUM(cash) FROM economy") as cursor:
        row = await cursor.fetchone()

    total_users = row[0] if row else 0
    total_cash = row[1] if row and row[1] else 0

    embed = disnake.Embed(title="📊 Статистика экономики", color=0x6A0DAD)
    embed.add_field(name="Всего пользователей", value=f"`{total_users}`", inline=True)
    embed.add_field(name="Всего наличных", value=f"`{total_cash}`", inline=True)
    embed.add_field(
        name="Курс обмена",
        value=f"1 Blink = `{bot.exchange_rate}` наличных",
        inline=True,
    )
    embed.add_field(
        name="Активные перезарядки", value=f"`{len(bot.cooldowns)}`", inline=True
    )
    embed.add_field(
        name="Запрещенные слова", value=f"`{len(bot.blacklisted_words)}`", inline=True
    )

    await inter.response.send_message(embed=embed, ephemeral=True)


@bot.slash_command(
    name="pr_guides",
    description="Опубликовать руководства по PR в канале (только для админов)",
)
@commands.has_permissions(administrator=True)
async def pr_guides(inter):
    try:
        if not inter.channel.permissions_for(inter.guild.me).send_messages:
            error_embed = disnake.Embed(
                description="У бота нет разрешения отправлять сообщения здесь",
                color=disnake.Color.red(),
            )
            await inter.response.send_message(embed=error_embed, ephemeral=True)
            return

        guide_embed = disnake.Embed(
            title="🎙️ ПРИВАТНЫЕ ГОЛОСОВЫЕ КАНАЛЫ - ОФИЦИАЛЬНОЕ РУКОВОДСТВО",
            description="Полное руководство по созданию и управлению приватными голосовыми каналами",
            color=0x6A0DAD,
            timestamp=datetime.datetime.now(),
        )

        guide_embed.add_field(
            name="💰 СИСТЕМА ЦЕНООБРАЗОВАНИЯ",
            value="```\n• 1-2 пользователя: 1,500 наличных\n• 3-8 пользователей: 2,500 наличных\n• 9-15 пользователей: 5,000 наличных\n• Без ограничений: 10,000 наличных\n```",
            inline=False,
        )

        guide_embed.add_field(
            name="🔧 СОЗДАНИЕ ПРИВАТНОЙ КОМНАТЫ",
            value="```/create_pr название_канала лимит_пользователей```\n**Примеры:**\n• `/create_pr Игры 5` → 5 пользователей (2,500 наличных)\n• `/create_pr Отдых 0` → Без ограничений (10,000 наличных)\n• `/create_pr Встреча 2` → 2 пользователя (1,500 наличных)",
            inline=False,
        )

        guide_embed.add_field(
            name="🆔 КАК ПОЛУЧИТЬ ID КАНАЛА",
            value="```\n1. Включите режим разработчика:\n   Настройки → Дополнительно → Режим разработчика\n\n2. Щелкните правой кнопкой по голосовому каналу\n3. Нажмите 'Копировать ID'\n```\n**Сохраните ваш ID канала!**",
            inline=False,
        )

        guide_embed.add_field(
            name="⚙️ КОМАНДЫ УПРАВЛЕНИЯ",
            value="```\n• /delete_pr 123456789012345678\n   → Удалить ваш канал (только владелец)\n\n• /transfer_pr 123456789012345678 @Пользователь\n   → Передать владение другому пользователю\n```",
            inline=False,
        )

        guide_embed.add_field(
            name="📝 ВАЖНЫЕ ЗАМЕЧАНИЯ",
            value="```\n✓ Проверьте баланс: /balance\n✓ Без ограничений = лимит: 0\n✓ ID канала требуется для управления\n✓ Возврата средств после создания нет\n✓ Технические проблемы → Свяжитесь с админами\n```",
            inline=False,
        )

        guide_embed.add_field(
            name="💡 ПРОФЕССИОНАЛЬНЫЕ СОВЕТЫ",
            value="```\n• Выбирайте имя с умом (без пробелов)\n• Сохраняйте ваш ID канала\n• Учитывайте потребности пользователей при установке лимита\n• Передавайте только доверенным пользователям\n```",
            inline=False,
        )

        guide_embed.set_footer(
            text=f"Опубликовано {inter.author.name}",
            icon_url=inter.author.display_avatar.url,
        )

        await inter.response.send_message("📖 Отправка руководства...", ephemeral=True)
        await inter.channel.send(embed=guide_embed)

        await bot.log_moderation(
            f"Руководство по PR опубликовано {inter.author.mention} в #{inter.channel.name}"
        )

    except Exception as e:
        error_embed = disnake.Embed(
            description=f"Ошибка: {str(e)}", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=error_embed, ephemeral=True)


@pr_guides.error
async def pr_guides_error(inter, error):
    if isinstance(error, commands.MissingPermissions):
        embed = disnake.Embed(
            description="Требуется разрешение администратора",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = disnake.Embed(
            description=f"Неожиданная ошибка: {error}", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


class TicketButtonView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="Открыть тикет",
        style=disnake.ButtonStyle.primary,
        custom_id="create_ticket",
        emoji="🎫",
    )
    async def create_ticket_button(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        await create_ticket(inter)


async def create_ticket(inter):
    ticket_id = f"{inter.author.id}-{int(datetime.datetime.now().timestamp())}"
    channel_name = f"запрос-{ticket_id[:8]}"

    overwrites = {
        inter.guild.default_role: disnake.PermissionOverwrite(read_messages=False),
        inter.author: disnake.PermissionOverwrite(
            read_messages=True, send_messages=True
        ),
        inter.guild.me: disnake.PermissionOverwrite(
            read_messages=True, send_messages=True, manage_channels=True
        ),
    }

    try:
        channel = await inter.guild.create_text_channel(
            name=channel_name, overwrites=overwrites
        )

        await bot.db.execute(
            "INSERT INTO tickets (ticket_id, user_id, channel_id, created_at) VALUES (?, ?, ?, ?)",
            (ticket_id, inter.author.id, channel.id, datetime.datetime.now()),
        )
        await bot.db.commit()

        embed = disnake.Embed(
            title="Тикет создан",
            description="Если вас обманули на сервере или в BlinX, или вы хотите получить верификацию или подтвердить покупку премиума, опишите проблему здесь.",
            color=0x6A0DAD,
        )
        embed.add_field(name="Тикет ID", value=f"`{ticket_id}`")
        embed.add_field(
            name="Создан", value=f"<t:{int(datetime.datetime.now().timestamp())}:R>"
        )
        embed.set_footer(text="Администратор свяжется с вами в ближайшее время")

        await channel.send(f"{inter.author.mention}", embed=embed)

        confirm_embed = disnake.Embed(
            description=f"Тикет создан: {channel.mention}", color=0x6A0DAD
        )
        await inter.response.send_message(embed=confirm_embed, ephemeral=True)

    except Exception as e:
        error_embed = disnake.Embed(
            description="Ошибка при создании тикета", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=error_embed, ephemeral=True)


@bot.slash_command(name="ticket_setup", description="Настройка системы тикетов")
@commands.has_permissions(administrator=True)
async def ticket_setup(inter):
    embed = disnake.Embed(
        title="Система поддержки BlinX",
        description="Если вас обманули на сервере или в BlinX, или вы хотите получить верификацию или подтвердить покупку премиума, нажмите кнопку ниже чтобы открыть тикет.",
        color=0x6A0DAD,
    )

    view = TicketButtonView()
    await inter.channel.send(embed=embed, view=view)
    await inter.response.send_message("Панель тикетов создана", ephemeral=True)


@bot.slash_command(name="close_ticket", description="Закрыть тикет")
async def close_ticket(inter):
    async with bot.db.execute(
        "SELECT ticket_id, user_id FROM tickets WHERE channel_id = ?",
        (inter.channel.id,),
    ) as cursor:
        ticket = await cursor.fetchone()

    if not ticket:
        embed = disnake.Embed(
            description="Это не тикет-канал", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    if (
        inter.author.id != ticket[1]
        and not inter.author.guild_permissions.administrator
    ):
        embed = disnake.Embed(
            description="Только автор тикета или администратор может его закрыть",
            color=disnake.Color.red(),
        )
        await inter.response.send_message(embed=embed, ephemeral=True)
        return

    await bot.db.execute(
        "UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (inter.channel.id,)
    )
    await bot.db.commit()

    await inter.channel.delete()


@addcash.error
@removecash.error
async def admin_error(inter, error):
    if isinstance(error, commands.MissingPermissions):
        embed = disnake.Embed(
            description="Недостаточно прав", color=disnake.Color.red()
        )
        await inter.response.send_message(embed=embed, ephemeral=True)


bot.run(TOKEN)
