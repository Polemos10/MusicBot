import os
import random
import discord
from discord.ext import commands
from yt_dlp import YoutubeDL
from collections import deque
import asyncio
from keep_alive import keep_alive

# Configuration
TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_PLAYLIST = [
    "more than you know", "takeaway chainsmokers", "12 notes", "hana ni natte",
    "akuma no ko", "your name little glee monster", "lisa gurenge",
    "season alisa takigawa", "scared to be lonely dua lipa", "clarity zedd",
    "wildest dreams taylor swift", "the nights avicii",
    "am i wrong nico & vinz", "summer calvin harris", "dynasty miia",
    "rolling in the deep adele", "supercollide banners",
    "chasing paradise kygo", "dont blame me taylor swift",
    "the motto alban chela", "voices damiano david", "firestone kygo"
]

# Bot setup
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Global state
song_queue = deque()
current_track = None
is_paused = False
should_replay = False

# Audio configuration
FFMPEG_OPTIONS = {
    'before_options':
    '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -af "loudnorm=I=-16:LRA=11:TP=-1.5"',
    'executable': 'ffmpeg'
}

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'skip': ['dash', 'hls']
        }
    }
}


@bot.event
async def on_ready():
    print(f'✅ Bot ready as {bot.user}')
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.listening, name="!help"))


async def extract_audio_info(query):
    """Handle both searches and direct URLs"""
    with YoutubeDL(YDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(
                f"ytsearch:{query}" if not query.startswith(
                    ('http://', 'https://')) else query,
                download=False)

            if not info:
                return None

            entry = info['entries'][0] if 'entries' in info else info
            return {
                'url': entry['url'],
                'title': entry.get('title', query),
                'query': query
            }
        except Exception as e:
            print(f"Extraction error: {e}")
            return None


async def play_next(ctx):
    global current_track, is_paused, should_replay

    if should_replay and current_track:
        track = current_track
        should_replay = False
    elif song_queue:
        next_query = song_queue.popleft()
        track = await extract_audio_info(next_query)
    else:
        return  # Queue is empty

    if not track or not track.get('url'):
        await ctx.send("❌ Couldn't play track")
        return

    current_track = track
    player = discord.FFmpegPCMAudio(track['url'], **FFMPEG_OPTIONS)

    def after_playing(error):
        if error:
            print(f"Playback error: {error}")
        asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop)

    ctx.voice_client.play(player, after=after_playing)
    await ctx.send(f"🎶 Now playing: **{track['title']}**")


@bot.command()
async def play(ctx, *, query=None):
    """Play music or resume playback"""
    global is_paused

    if not ctx.author.voice:
        return await ctx.send("⚠ Join a voice channel first!")

    if ctx.voice_client and is_paused:
        ctx.voice_client.resume()
        is_paused = False
        return await ctx.send("▶ Resumed playback")

    if not ctx.voice_client:
        await ctx.author.voice.channel.connect()
    elif ctx.voice_client.channel != ctx.author.voice.channel:
        await ctx.voice_client.move_to(ctx.author.voice.channel)

    if not query:
        songs = DEFAULT_PLAYLIST.copy()
        random.shuffle(songs)
        song_queue.extend(songs)
        await ctx.send(f"🔀 Shuffled {len(songs)} default songs!")
    else:
        songs = [s.strip()
                 for s in query.split(',')] if ',' in query else [query]
        song_queue.extend(songs)
        await ctx.send(f"📥 Added {len(songs)} songs to queue!")

    if not ctx.voice_client.is_playing() and not is_paused:
        await play_next(ctx)


@bot.command()
async def replay(ctx):
    """Replay the current track"""
    global should_replay

    if not ctx.voice_client or not current_track:
        await ctx.send("❌ No track is currently playing")
        return

    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()

    should_replay = True
    await play_next(ctx)
    await ctx.send("🔂 Replaying current track")


@bot.command()
async def pause(ctx):
    """Pause playback"""
    global is_paused
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        is_paused = True
        await ctx.send("⏸ Playback paused")
    else:
        await ctx.send("❌ Nothing is playing!")


@bot.command()
async def resume(ctx):
    """Resume playback"""
    global is_paused
    if ctx.voice_client and is_paused:
        ctx.voice_client.resume()
        is_paused = False
        await ctx.send("▶ Playback resumed")
    else:
        await ctx.send("❌ Playback not paused!")


@bot.command()
async def skip(ctx):
    """Skip current song"""
    if ctx.voice_client and (ctx.voice_client.is_playing() or is_paused):
        ctx.voice_client.stop()
        await ctx.send("⏭ Skipped current song")
    else:
        await ctx.send("❌ Nothing to skip!")


@bot.command()
async def stop(ctx):
    """Stop playback and clear queue"""
    global current_track, is_paused, should_replay
    if ctx.voice_client:
        song_queue.clear()
        current_track = None
        is_paused = False
        should_replay = False
        ctx.voice_client.stop()
        await ctx.send("⏹ Stopped playback and cleared queue")
    else:
        await ctx.send("❌ Not in a voice channel!")


@bot.command()
async def queue(ctx):
    """Show current queue"""
    if not song_queue:
        return await ctx.send("Queue is empty!")

    queue_list = "\n".join(f"{i+1}. {song[:50]}{'...' if len(song)>50 else ''}"
                           for i, song in enumerate(list(song_queue)[:10]))
    extra = "\n..." if len(song_queue) > 10 else ""
    await ctx.send(f"🎧 Upcoming (next 10):\n{queue_list}{extra}")


@bot.command()
async def np(ctx):
    """Show currently playing song"""
    if current_track:
        await ctx.send(f"🎵 Now playing: **{current_track['title']}**")
    else:
        await ctx.send("❌ Nothing is playing")


@bot.command()
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    return await ctx.send(f"🏓 Pong! Latency: {latency}ms")


@bot.command()
async def help(ctx):
    """Show all commands"""
    embed = discord.Embed(title="🎵 Music Bot Commands", color=0x1DB954)
    commands_info = [("!play [song]", "Play or queue songs"),
                     ("!play song1, song2", "Queue multiple songs"),
                     ("!replay", "Replay current track"),
                     ("!pause", "Pause playback"),
                     ("!resume", "Resume playback"),
                     ("!skip", "Skip current song"),
                     ("!stop", "Stop and clear queue"),
                     ("!queue", "Show current queue"),
                     ("!np", "Now playing info"),
                     ("!help", "Show this message")]

    for name, value in commands_info:
        embed.add_field(name=name, value=value, inline=False)

    await ctx.send(embed=embed)


# Start the keep_alive server (for Replit)
keep_alive()
print(
    f"🌐 Web server URL: https://{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.co"
)

try:
    bot.run(TOKEN)
except discord.errors.LoginFailure:
    print("❌ Invalid Discord token. Set it in Replit Secrets (DISCORD_TOKEN)")
except Exception as e:
    print(f"❌ Fatal error: {e}")
