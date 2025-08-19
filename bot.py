# bot.py
import os
import csv
import datetime
import discord
from discord.ext import tasks
from dotenv import load_dotenv

# --- keepalive web server for Replit ---
from flask import Flask
import threading, os

app = Flask(__name__)

# answer both GET and HEAD cleanly
@app.route("/", methods=["GET", "HEAD"])
def home():
    return "ok", 200

@app.route("/health", methods=["GET", "HEAD"])
def health():
    return "ok", 200

def run_keepalive():
    port = int(os.getenv("PORT", "3000"))  # <-- use Replit's port if provided
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_keepalive, daemon=True).start()


# --- env ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
BDAY_CHANNEL_ID = os.getenv("BDAY_CHANNEL_ID")  # optional: numeric channel id string

# --- discord client ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- CSV loading ---
CSV_PATH = "birthdays.csv"  # keep in repo root
BIRTHDAYS = {}              # {user_id: "MM-DD"}

def load_birthdays_from_csv():
    global BIRTHDAYS
    BIRTHDAYS = {}
    try:
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            # expected headers: user_id,mm_dd,(optional) note
            for row in reader:
                uid = row.get("user_id", "").strip()
                md  = row.get("mm_dd", "").strip()
                if uid and md:
                    BIRTHDAYS[uid] = md
        print(f"Loaded {len(BIRTHDAYS)} birthdays from {CSV_PATH}")
    except FileNotFoundError:
        print(f"WARN: {CSV_PATH} not found; no birthdays loaded")

load_birthdays_from_csv()

@client.event
async def on_ready():
    print(f"{client.user} is now running!")
    # schedule at 09:00 UTC by default; change as you like
    check_birthdays.change_interval(time=datetime.time(hour=9, minute=0))
    check_birthdays.start()

@tasks.loop(hours=24)
async def check_birthdays():
    today_md = datetime.date.today().strftime("%m-%d")
    hits = [uid for uid, md in BIRTHDAYS.items() if md == today_md]
    if not hits:
        return

    # choose channel to post in
    channel = None
    if BDAY_CHANNEL_ID:
        channel = client.get_channel(int(BDAY_CHANNEL_ID))
    if channel is None:
        # fallback: try a channel named "general"
        channel = discord.utils.get(client.get_all_channels(), name="general")

    if channel is None:
        print("No channel found to post birthdays; set BDAY_CHANNEL_ID env var")
        return

    mentions = " and ".join(f"<@{uid}>" for uid in hits)
    await channel.send(f"🎉 Happy Birthday to {mentions}!")

@client.event
async def on_message(msg):
    if msg.author == client.user:
        return

    content = msg.content.strip().lower()

    if content == "!hello":
        await msg.channel.send(f"Hey {msg.author.name}, I'm alive!")

    # manual check trigger
    if content == "!checkbirthdays":
        await check_birthdays()

    # reload CSV after editing it in Replit (admin-only idea: check author id if you want)
    if content == "!reloadbirthdays":
        load_birthdays_from_csv()
        await msg.channel.send("🔄 Reloaded birthdays from CSV.")
        
client.run(TOKEN)
