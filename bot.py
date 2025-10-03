import discord
from discord.ext import commands
import os
import aiohttp
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv

load_dotenv("token.env")

MONGO_URL = os.getenv("MONGO_URL")
client = MongoClient(MONGO_URL, server_api=ServerApi('1'))

db = client["whitelist_auth"]  # your database name
links_col = db["links"]
whitelist_col = db["whitelisted"]

TOKEN = os.getenv("DISCORD_TOKEN")
INTENTS = discord.Intents.default()
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)
bot.remove_command("help")


async def roblox_user_exists(user_id: str):
    url = f"https://users.roblox.com/v1/users/{user_id}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("name")


@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    sync = await bot.tree.sync()
    print(f"Synced {len(sync)} command(s)")


@bot.tree.command(name="whitelist", description="Whitelist your Discord to a Roblox ID")
async def link(interaction: discord.Interaction, roblox_id: str):
    await interaction.response.defer(thinking=True)

    discord_id = str(interaction.user.id)
    discord_name = str(interaction.user)

    # Validate Roblox ID
    if not roblox_id.isdigit():
        return await interaction.followup.send("❌ Roblox ID must be numbers only!")

    roblox_name = await roblox_user_exists(roblox_id)
    if not roblox_name:
        return await interaction.followup.send("❌ Invalid Roblox user ID.")

    # Check if Roblox already linked to another Discord
    existing_link = links_col.find_one({"roblox_id": roblox_id})
    if existing_link and existing_link["discord_id"] != discord_id:
        return await interaction.followup.send(
            f"❌ Roblox `{roblox_id}` is already whitelisted to another Discord account!"
        )

    # Check if this Discord already linked
    existing_discord = links_col.find_one({"discord_id": discord_id})
    if existing_discord:
        if existing_discord["roblox_id"] == roblox_id:
            return await interaction.followup.send(
                f"✅ Roblox {roblox_name} ({roblox_id}) is already whitelisted with your Discord!"
            )
        else:
            return await interaction.followup.send(
                f"❌ Your Discord is already linked to Roblox {existing_discord['roblox_id']}."
            )

    # Save to MongoDB
    links_col.insert_one({
        "discord_id": discord_id,
        "discord_name": discord_name,
        "roblox_id": roblox_id
    })
    whitelist_col.insert_one({
        "roblox_id": roblox_id,
        "roblox": roblox_name,
        "discord": discord_name
    })

    await interaction.followup.send(
        f"✅ Whitelisted! Roblox `{roblox_name}` ({roblox_id}) linked to your Discord `{discord_name}`"
    )


@bot.event
async def on_member_remove(member):
    discord_id = str(member.id)
    existing = links_col.find_one({"discord_id": discord_id})

    if existing:
        roblox_id = existing["roblox_id"]
        whitelist_col.delete_one({"roblox_id": roblox_id})
        links_col.delete_one({"discord_id": discord_id})

        channel = discord.utils.get(member.guild.text_channels, name="・scripts-log")
        if channel:
            await channel.send(
                f"❌ Auto-Unwhitelisted Roblox `{roblox_id}` (Discord {member})"
            )

        print(f"[AUTO-UNWHITELIST] Removed Roblox {roblox_id} (Discord {member})")


if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ No token found!")
