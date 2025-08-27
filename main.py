import discord
from discord.ext import commands
import mysql.connector
import asyncio
from datetime import datetime
import os
import aiohttp
import json

# Configuration du bot
BOT_TOKEN = ""

# Configuration MySQL (XAMPP)
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Par défaut vide sur XAMPP
    'database': 'discord_dashboard',
    'port': 3306
}

# Intents nécessaires pour accéder à tous les événements
intents = discord.Intents.default()
intents.message_content = True
intents.guild_messages = True
intents.guild_reactions = True
intents.guilds = True
intents.members = True

# Création du bot
bot = commands.Bot(command_prefix='!', intents=intents)

class DiscordDatabase:
    def __init__(self, db_config):
        self.db_config = db_config
        self.init_database()
    
    def get_connection(self):
        """Obtient une connexion à la base de données"""
        return mysql.connector.connect(**self.db_config)
    
    def init_database(self):
        """Initialise la base de données avec toutes les tables nécessaires"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table des serveurs (guilds)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id BIGINT PRIMARY KEY,
                guild_name VARCHAR(255) NOT NULL,
                owner_id BIGINT,
                member_count INT,
                created_at DATETIME,
                joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table des catégories
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                category_id BIGINT PRIMARY KEY,
                guild_id BIGINT,
                category_name VARCHAR(255) NOT NULL,
                position INT,
                created_at DATETIME,
                FOREIGN KEY (guild_id) REFERENCES guilds (guild_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des salons
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id BIGINT PRIMARY KEY,
                guild_id BIGINT,
                category_id BIGINT,
                channel_name VARCHAR(255) NOT NULL,
                channel_type VARCHAR(50) NOT NULL,
                position INT,
                created_at DATETIME,
                FOREIGN KEY (guild_id) REFERENCES guilds (guild_id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des utilisateurs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255) NOT NULL,
                display_name VARCHAR(255),
                discriminator VARCHAR(10),
                bot BOOLEAN DEFAULT FALSE,
                created_at DATETIME,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Table des membres par serveur
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_members (
                guild_id BIGINT,
                user_id BIGINT,
                nickname VARCHAR(255),
                joined_at DATETIME,
                roles JSON,
                PRIMARY KEY (guild_id, user_id),
                FOREIGN KEY (guild_id) REFERENCES guilds (guild_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                message_id BIGINT PRIMARY KEY,
                channel_id BIGINT,
                guild_id BIGINT,
                user_id BIGINT,
                content TEXT,
                created_at DATETIME,
                edited_at DATETIME,
                message_type VARCHAR(50),
                embeds JSON,
                attachments JSON,
                FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE,
                FOREIGN KEY (guild_id) REFERENCES guilds (guild_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des pièces jointes (photos, vidéos, fichiers)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attachments (
                attachment_id BIGINT PRIMARY KEY,
                message_id BIGINT,
                filename VARCHAR(255),
                url TEXT,
                proxy_url TEXT,
                size INT,
                content_type VARCHAR(100),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages (message_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des réactions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id BIGINT,
                user_id BIGINT,
                emoji_name VARCHAR(255),
                emoji_id BIGINT,
                emoji_animated BOOLEAN DEFAULT FALSE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages (message_id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des éditions de messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_edits (
                id INT AUTO_INCREMENT PRIMARY KEY,
                message_id BIGINT,
                old_content TEXT,
                new_content TEXT,
                edited_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages (message_id) ON DELETE CASCADE
            )
        ''')
        
        # Table des suppressions de messages
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS deleted_messages (
                message_id BIGINT PRIMARY KEY,
                channel_id BIGINT,
                guild_id BIGINT,
                user_id BIGINT,
                content TEXT,
                deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                original_created_at DATETIME
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ Base de données initialisée avec succès!")
    
    def save_guild(self, guild):
        """Sauvegarde les informations d'un serveur"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO guilds (guild_id, guild_name, owner_id, member_count, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            guild_name = VALUES(guild_name),
            member_count = VALUES(member_count)
        ''', (guild.id, guild.name, guild.owner_id, guild.member_count, guild.created_at))
        
        conn.commit()
        conn.close()
    
    def save_category(self, category):
        """Sauvegarde une catégorie"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO categories (category_id, guild_id, category_name, position, created_at)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            category_name = VALUES(category_name),
            position = VALUES(position)
        ''', (category.id, category.guild.id, category.name, category.position, category.created_at))
        
        conn.commit()
        conn.close()
    
    def save_channel(self, channel):
        """Sauvegarde un salon"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        category_id = channel.category_id if channel.category else None
        
        cursor.execute('''
            INSERT INTO channels (channel_id, guild_id, category_id, channel_name, channel_type, position, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            channel_name = VALUES(channel_name),
            position = VALUES(position)
        ''', (channel.id, channel.guild.id, category_id, channel.name, str(channel.type), channel.position, channel.created_at))
        
        conn.commit()
        conn.close()
    
    def save_user(self, user):
        """Sauvegarde un utilisateur"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO users (user_id, username, display_name, discriminator, bot, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            username = VALUES(username),
            display_name = VALUES(display_name)
        ''', (user.id, user.name, user.display_name, user.discriminator, user.bot, user.created_at))
        
        conn.commit()
        conn.close()
    
    def save_member(self, member):
        """Sauvegarde un membre d'un serveur"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # D'abord sauvegarder l'utilisateur
        self.save_user(member)
        
        # Puis sauvegarder les infos de membre
        roles = [role.id for role in member.roles]
        
        cursor.execute('''
            INSERT INTO guild_members (guild_id, user_id, nickname, joined_at, roles)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            nickname = VALUES(nickname),
            roles = VALUES(roles)
        ''', (member.guild.id, member.id, member.nick, member.joined_at, json.dumps(roles)))
        
        conn.commit()
        conn.close()
    
    def save_message(self, message):
        """Sauvegarde un message"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Sauvegarder l'utilisateur s'il n'existe pas
        self.save_user(message.author)
        
        # Préparer les données des embeds et attachments
        embeds_data = []
        for embed in message.embeds:
            embeds_data.append(embed.to_dict())
        
        attachments_data = []
        for attachment in message.attachments:
            attachments_data.append({
                'id': attachment.id,
                'filename': attachment.filename,
                'url': attachment.url,
                'proxy_url': attachment.proxy_url,
                'size': attachment.size,
                'content_type': attachment.content_type
            })
        
        # Sauvegarder le message
        cursor.execute('''
            INSERT INTO messages (message_id, channel_id, guild_id, user_id, content, created_at, message_type, embeds, attachments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
            content = VALUES(content),
            edited_at = VALUES(edited_at)
        ''', (
            message.id, 
            message.channel.id, 
            message.guild.id if message.guild else None,
            message.author.id, 
            message.content, 
            message.created_at,
            str(message.type),
            json.dumps(embeds_data) if embeds_data else None,
            json.dumps(attachments_data) if attachments_data else None
        ))
        
        # Sauvegarder les attachments séparément
        for attachment in message.attachments:
            cursor.execute('''
                INSERT INTO attachments (attachment_id, message_id, filename, url, proxy_url, size, content_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE filename = VALUES(filename)
            ''', (
                attachment.id,
                message.id,
                attachment.filename,
                attachment.url,
                attachment.proxy_url,
                attachment.size,
                attachment.content_type
            ))
        
        conn.commit()
        conn.close()
    
    def save_reaction(self, message_id, user, emoji):
        """Sauvegarde une réaction"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Sauvegarder l'utilisateur
        self.save_user(user)
        
        emoji_id = getattr(emoji, 'id', None)
        emoji_animated = getattr(emoji, 'animated', False)
        
        cursor.execute('''
            INSERT INTO reactions (message_id, user_id, emoji_name, emoji_id, emoji_animated)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE created_at = VALUES(created_at)
        ''', (message_id, user.id, str(emoji), emoji_id, emoji_animated))
        
        conn.commit()
        conn.close()
    
    def save_message_edit(self, old_message, new_message):
        """Sauvegarde une édition de message"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO message_edits (message_id, old_content, new_content)
            VALUES (%s, %s, %s)
        ''', (new_message.id, old_message.content if old_message else None, new_message.content))
        
        # Mettre à jour le message principal
        cursor.execute('''
            UPDATE messages SET content = %s, edited_at = %s WHERE message_id = %s
        ''', (new_message.content, datetime.now(), new_message.id))
        
        conn.commit()
        conn.close()
    
    def save_deleted_message(self, message):
        """Sauvegarde un message supprimé"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO deleted_messages (message_id, channel_id, guild_id, user_id, content, original_created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            message.id,
            message.channel.id,
            message.guild.id if message.guild else None,
            message.author.id,
            message.content,
            message.created_at
        ))
        
        conn.commit()
        conn.close()

# Instance de la base de données
db = DiscordDatabase(DB_CONFIG)

@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt"""
    print(f'✅ Bot connecté: {bot.user.name}')
    print(f'📊 Connecté à {len(bot.guilds)} serveurs')
    
    # Synchroniser tous les serveurs existants
    for guild in bot.guilds:
        print(f'🔄 Synchronisation du serveur: {guild.name}')
        await sync_guild(guild)

async def sync_guild(guild):
    """Synchronise complètement un serveur"""
    # Sauvegarder le serveur
    db.save_guild(guild)
    
    # Sauvegarder les catégories
    for category in guild.categories:
        db.save_category(category)
    
    # Sauvegarder tous les salons
    for channel in guild.channels:
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
            db.save_channel(channel)
    
    # Sauvegarder tous les membres
    for member in guild.members:
        db.save_member(member)
    
    print(f'✅ Serveur {guild.name} synchronisé!')

@bot.event
async def on_guild_join(guild):
    """Quand le bot rejoint un serveur"""
    print(f'🎉 Bot ajouté au serveur: {guild.name}')
    await sync_guild(guild)

@bot.event
async def on_message(message):
    """Événement message envoyé"""
    if message.guild:  # Seulement les messages de serveur
        db.save_message(message)
        print(f'💬 Message sauvegardé: {message.author.name} dans #{message.channel.name}')
    
    # Traiter les commandes
    await bot.process_commands(message)

@bot.event
async def on_message_edit(before, after):
    """Événement message édité"""
    if after.guild:
        db.save_message_edit(before, after)
        print(f'✏️ Message édité: {after.author.name} dans #{after.channel.name}')

@bot.event
async def on_message_delete(message):
    """Événement message supprimé"""
    if message.guild:
        db.save_deleted_message(message)
        print(f'🗑️ Message supprimé: {message.author.name} dans #{message.channel.name}')

@bot.event
async def on_reaction_add(reaction, user):
    """Événement réaction ajoutée"""
    if reaction.message.guild and not user.bot:
        db.save_reaction(reaction.message.id, user, reaction.emoji)
        print(f'👍 Réaction ajoutée: {user.name} a réagi avec {reaction.emoji}')

@bot.event
async def on_member_join(member):
    """Événement membre rejoint"""
    db.save_member(member)
    print(f'👋 Nouveau membre: {member.name} a rejoint {member.guild.name}')

@bot.event
async def on_guild_channel_create(channel):
    """Événement salon créé"""
    if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
        db.save_channel(channel)
        print(f'📝 Nouveau salon: #{channel.name} créé')

@bot.event
async def on_guild_channel_update(before, after):
    """Événement salon mis à jour"""
    if isinstance(after, (discord.TextChannel, discord.VoiceChannel)):
        db.save_channel(after)
        print(f'🔄 Salon mis à jour: #{after.name}')

# Commandes du bot
@bot.command(name='sync')
@commands.has_permissions(administrator=True)
async def sync_command(ctx):
    """Commande pour synchroniser manuellement le serveur"""
    await ctx.send('🔄 Synchronisation en cours...')
    await sync_guild(ctx.guild)
    await ctx.send('✅ Synchronisation terminée!')

@bot.command(name='stats')
async def stats_command(ctx):
    """Affiche les statistiques de la base de données"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Compter les différents éléments
    cursor.execute('SELECT COUNT(*) FROM messages WHERE guild_id = %s', (ctx.guild.id,))
    message_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users')
    user_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM channels WHERE guild_id = %s', (ctx.guild.id,))
    channel_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM reactions r JOIN messages m ON r.message_id = m.message_id WHERE m.guild_id = %s', (ctx.guild.id,))
    reaction_count = cursor.fetchone()[0]
    
    conn.close()
    
    embed = discord.Embed(title="📊 Statistiques de la base de données", color=0x00ff00)
    embed.add_field(name="Messages", value=f"{message_count:,}", inline=True)
    embed.add_field(name="Utilisateurs", value=f"{user_count:,}", inline=True)
    embed.add_field(name="Salons", value=f"{channel_count:,}", inline=True)
    embed.add_field(name="Réactions", value=f"{reaction_count:,}", inline=True)
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    # Démarrer le bot
    print("🚀 Démarrage du bot Discord...")
    print("📄 Assurez-vous d'avoir créé la base de données 'discord_bot' dans XAMPP!")
    bot.run(BOT_TOKEN)