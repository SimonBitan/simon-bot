# bot.py
import os
import csv
import datetime
import discord
from discord.ext import tasks
from dotenv import load_dotenv

# --- keepalive web server for Replit ---
from flask import Flask
import threading

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def home():
    return "ok", 200

@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "ok", 200

def run_keepalive():
    port = int(os.getenv("PORT", "3000"))  # Replit sets PORT; fall back to 3000 locally
    app.run(host="0.0.0.0", port=port)

# Start the keepalive web server in the background
threading.Thread(target=run_keepalive, daemon=True).start()

# --- env ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BDAY_CHANNEL_ID = os.getenv("BDAY_CHANNEL_ID")  # optional: numeric channel id as string

# --- discord client ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- CSV loading ---
CSV_PATH = "birthdays.csv"  # keep in repo root
BIRTHDAYS = {}              # {user_id: "MM-DD"}

def load_birthdays_from_csv():
    """Load birthdays into global dict {user_id: 'MM-DD'}."""
    global BIRTHDAYS
    BIRTHDAYS = {}
    try:
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            # expected headers: user_id,mm_dd,(optional) note
            for row in reader:
                uid = (row.get("user_id") or "").strip()
                md  = (row.get("mm_dd")  or "").strip()
                if uid and md:
                    BIRTHDAYS[uid] = md
        print(f"Loaded {len(BIRTHDAYS)} birthdays from {CSV_PATH}")
    except FileNotFoundError:
        print(f"WARN: {CSV_PATH} not found; no birthdays loaded")

load_birthdays_from_csv()

async def run_check_birthdays_once(target_channel: discord.abc.MessageableChannel | None = None):
    """Check today's birthdays and post once. If target_channel is provided, reply there."""
    today_md = datetime.date.today().strftime("%m-%d")
    hits = [uid for uid, md in BIRTHDAYS.items() if md == today_md]

    # choose channel
    channel = target_channel
    if channel is None and BDAY_CHANNEL_ID:
        channel = client.get_channel(int(BDAY_CHANNEL_ID))
    if channel is None:
        channel = discord.utils.get(client.get_all_channels(), name="general")

    if channel is None:
        print("No channel found to post birthdays; set BDAY_CHANNEL_ID env var or ensure a 'general' channel exists.")
        return

    if not hits:
        # If manually triggered via command, be explicit
        if target_channel is not None:
            await channel.send("No birthdays today!")
        return

    mentions = " and ".join(f"<@{uid}>" for uid in hits)
    await channel.send(f"🎉 Happy Birthday to {mentions}!")

@tasks.loop(hours=24)
async def check_birthdays():
    """Scheduled job that runs daily (time set in on_ready)."""
    await run_check_birthdays_once()

@client.event
async def on_ready():
    print(f"{client.user} is now running!")
    # Choose your daily send time (UTC). Adjust hour/minute as you like.
    check_birthdays.change_interval(time=datetime.time(hour=9, minute=0))
    check_birthdays.start()

@client.event
async def on_message(msg: discord.Message):
    if msg.author == client.user:
        return

    content = msg.content.strip().lower()

    if content == "!hello":
        await msg.channel.send(f"Hey {msg.author.name}, I'm alive!")

    if content == "!checkbirthdays":
        print(f"Manual !checkbirthdays requested in channel {msg.channel.id}")
        await run_check_birthdays_once(target_channel=msg.channel)

    if content == "!reloadbirthdays":
        load_birthdays_from_csv()
        await msg.channel.send("🔄 Reloaded birthdays from CSV.")

# Guard for missing token (helps catch bad secrets fast)
if not TOKEN or "." not in TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing/invalid. Set it in Replit Secrets (no quotes, no 'Bot ' prefix).")

client.run(TOKEN)
