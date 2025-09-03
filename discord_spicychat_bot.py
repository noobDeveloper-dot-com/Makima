import discord
import asyncio
import os
import json
import time
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import threading
from google import genai
from roastedbyai import Conversation, Style
import random

load_dotenv()

# Discord bot token
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Hardcode your Gemini API key for testing (remove after testing for security!)
GEMINI_API_KEY = "AIzaSyA0VyB7q5p5obTyDRNRCT9Uyxu_FeJjl04"

# Storage for pending messages and responses
pending_messages = []
response_queue = {}
message_channels = {}  # Store message ID -> channel mapping

# Initialize AI services
gemini_client = None
roast_conversation = None

def init_ai_services():
    """Initialize Gemini and RoastedBy.AI services"""
    global gemini_client, roast_conversation
    try:
        if GEMINI_API_KEY:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            print("✅ Gemini AI initialized for smart suggestions")
        else:
            print("⚠️ No Gemini API key - using basic suggestions")
            
        roast_conversation = Conversation(Style.valley_girl)
        print("✅ RoastedBy.AI initialized for harsh suggestions")
    except Exception as e:
        print(f"⚠️ AI services error: {e}")
        print("Using fallback suggestions")

# Discord bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # <-- Add this line!
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask web app for manual control interface
app = Flask(__name__)

# Track if the user is "active" in the UI (cursor in a textbox)
user_active = False

# Flask routes for web interface
@app.route('/')
def index():
    """Serve the manual control interface"""
    with open('manual_control_interface.html', 'r') as f:
        return f.read()

@app.route('/get_messages')
def get_messages():
    """API endpoint to get pending messages"""
    global pending_messages
    # Return more messages if you want
    return jsonify({"messages": pending_messages[-100:]})

@app.route('/get_suggestions')
def get_ai_suggestions():
    message_content = request.args.get('message', '')
    username = request.args.get('username', 'User')
    
    suggestions = {
        "makima": get_makima_suggestions(message_content),
        "gemini": get_gemini_suggestions(message_content, username),
        "roast": get_roast_suggestions(message_content, username)
    }
    
    return jsonify(suggestions)

@app.route('/send_response', methods=['POST'])
def send_response():
    """API endpoint to send a response back to Discord"""
    data = request.json
    message_id = data.get('messageId')
    response_text = data.get('response')
    
    if not message_id or not response_text:
        return jsonify({"success": False, "error": "Missing messageId or response"})
    
    # Store the response for the Discord bot to pick up
    response_queue[message_id] = response_text
    
    return jsonify({"success": True})

@app.route('/send_as_makima', methods=['POST'])
def send_as_makima():
    """Send a message as Makima to any channel/user"""
    data = request.json
    channel_id = data.get('channelId')
    response_text = data.get('response')
    user_id = data.get('userId')  # Optional
    if not channel_id or not response_text:
        return jsonify({"success": False, "error": "Missing channelId or response"})
    # Use run_coroutine_threadsafe for immediate scheduling
    future = asyncio.run_coroutine_threadsafe(
        send_message_to_channel(channel_id, response_text, user_id),
        bot.loop
    )
    # Optionally, wait for completion or catch errors
    try:
        future.result(timeout=2)  # Wait up to 2 seconds for errors
    except Exception as e:
        print(f"Error sending message: {e}")
        return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": True})

async def send_message_to_channel(channel_id, response_text, user_id=None):
    channel = bot.get_channel(int(channel_id))
    if channel:
        try:
            if user_id:
                mention = f"<@{user_id}> "
                await channel.send(mention + response_text)
            else:
                await channel.send(response_text)
        except Exception as e:
            print(f"Failed to send message: {e}")
    else:
        print(f"Channel {channel_id} not found!")

def get_makima_suggestions(message_content):
    """Generate Makima-style suggestions based on message content"""
    content = message_content.lower()
    
    if any(word in content for word in ['hello', 'hi', 'hey']):
        return [
            "Hmm, you seem interesting. What brings you before me?",
            "I was wondering when you'd finally approach me.",
            "Another soul seeking guidance. How predictable."
        ]
    elif any(word in content for word in ['power', 'strong', 'strength']):
        return [
            "Power is not about strength alone. True power lies in control.",
            "You speak of power, but do you understand its true cost?",
            "Power without control is merely chaos. I can teach you control."
        ]
    elif any(word in content for word in ['devil', 'fear', 'scary']):
        return [
            "Devils are fascinating creatures, don't you think? They reflect humanity's deepest fears.",
            "Fear is humanity's greatest weakness, yet also their greatest strength.",
            "The devils you fear are nothing compared to what I represent."
        ]
    elif any(word in content for word in ['want', 'need', 'help', 'wish']):
        return [
            "Everyone wants something. What price are you willing to pay?",
            "I can help you achieve your desires... for the right cost.",
            "Your needs are transparent. Let's discuss terms."
        ]
    elif any(word in content for word in ['love', 'like', 'feel']):
        return [
            "Love is just another form of control. I excel at both.",
            "Your feelings are... amusing. Continue.",
            "Such human emotions. They make you so easy to manipulate."
        ]
    else:
        return [
            "How intriguing. Continue.",
            "Your perspective is... limited. Allow me to enlighten you.",
            "I expected as much. You're quite predictable, aren't you?",
            "Is that so? I wonder if you truly understand the implications."
        ]

def get_gemini_suggestions(message_content, username):
    """Generate smart suggestions using Google Gemini"""
    if not gemini_client:
        return ["Gemini not available - check API key"]
    
    try:
        prompt = f"""You are Makima from Chainsaw Man responding to {username} who said: "{message_content}"

Generate 3 short Makima-style responses that are:
- Manipulative and controlling
- Calm but subtly threatening  
- Reference devils/power when appropriate
- Under 100 characters each
- Stay in character as the Control Devil

Format as a simple list, one per line."""

        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        
        if response and response.text:
            lines = [line.strip() for line in response.text.split('\n') if line.strip()]
            # Clean up any markdown or numbering
            cleaned = []
            for line in lines[:3]:  # Max 3 suggestions
                # Remove markdown, numbers, bullets
                line = line.replace('*', '').replace('-', '').replace('•', '')
                line = ' '.join(line.split()[1:]) if line.split() and line.split()[0].isdigit() else line
                if line and len(line) > 10:  # Minimum length check
                    cleaned.append(line.strip())
            
            return cleaned[:3] if cleaned else ["*stares with calculating eyes*"]
        else:
            return ["*regards you with cold interest*"]
            
    except Exception as e:
        print(f"Gemini error: {e}")
        return ["*maintains mysterious silence*"]

def get_roast_suggestions(message_content, username):
    """Generate harsh roast suggestions"""
    if not roast_conversation:
        return ["Roast service unavailable"]
    
    try:
        # Try to get a roast response
        roast_response = roast_conversation.send(f"Roast {username} who said: {message_content}")
        
        if roast_response:
            # Convert roast to Makima-style harsh responses
            makima_roasts = [
                f"How pathetic. {roast_response[:80]}...",
                f"You disappoint me, {username}. That level of thinking is beneath even dogs.",
                f"*sighs* Another inferior mind seeking my attention. How tiresome.",
                f"Your ignorance is almost endearing, {username}. Almost."
            ]
            return random.sample(makima_roasts, min(3, len(makima_roasts)))
        else:
            return [
                f"Your words bore me, {username}. Try harder.",
                f"Such mediocrity, {username}. I expected... less, actually.",
                f"*yawns* Is this the best you can manage?"
            ]
            
    except Exception as e:
        print(f"Roast error: {e}")
        return [
            f"Your existence is punishment enough, {username}.",
            f"I don't need AI to see how pathetic you are, {username}.",
            f"*looks at you with disdain* Spare me your inadequacy."
        ]

def gemini_detects_harsh(message_content, username):
    """Ask Gemini if a harsh roast is appropriate for this message."""
    if not gemini_client:
        return False
    try:
        prompt = f"""
You are Makima from Chainsaw Man. A user named {username} said: "{message_content}"

Should you respond with a harsh roast? 
Reply only with "yes" or "no". 
Say "yes" if the message is rude, disrespectful, or deserves a roast. Otherwise, say "no".
"""
        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        if response and response.text:
            answer = response.text.strip().lower()
            return answer.startswith("yes")
    except Exception as e:
        print(f"Gemini harsh detection error: {e}")
    return False

async def handle_manual_message(message):
    global pending_messages, response_queue, user_active

    message_data = {
        "id": str(message.id),
        "username": message.author.display_name,
        "content": message.content,
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "channel": str(message.channel.id)
    }

    pending_messages.append(message_data)
    message_channels[str(message.id)] = message.channel
    print(f'📨 New message from {message.author.display_name}: {message.content}')
    print(f'💡 Go to http://localhost:5000 to respond as Makima')

    async with message.channel.typing():
        timeout_counter = 0
        while str(message.id) not in response_queue and timeout_counter < 5:
            await asyncio.sleep(1)
            timeout_counter += 1
            if user_active:
                timeout_counter = 0  # Reset timer if user is active

        if str(message.id) in response_queue:
            response_text = response_queue[str(message.id)]
            del response_queue[str(message.id)]

            print(f'📤 Sending manual response: {response_text}')
            channel = message_channels.get(str(message.id), message.channel)

            if len(response_text) > 2000:
                chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                for chunk in chunks:
                    await channel.send(chunk)
            else:
                await channel.send(response_text)

            if str(message.id) in message_channels:
                del message_channels[str(message.id)]
        else:
            # Default: auto Makima-style suggestion if no manual reply
            auto_response = random.choice(get_makima_suggestions(message.content))
            await message.channel.send(auto_response)
            if str(message.id) in message_channels:
                del message_channels[str(message.id)]

@bot.command(name='ping')
async def ping(ctx):
    """Test command to check if bot is working"""
    await ctx.send('🏓 Pong! Bot is working!')

@bot.command(name='status')
async def status(ctx):
    """Check manual control status"""
    await ctx.send('✅ Manual control mode active! Check http://localhost:5000 to control Makima')

@bot.command(name='info')
async def info_command(ctx):
    """Show help information"""
    help_text = """
**Discord Makima Manual Control Bot:**

`!ping` - Test if bot is working
`!status` - Check manual control status  
`!info` - Show this help message

**How it works:**
1. Users send messages to this bot
2. Messages appear on the control panel at http://localhost:5000
3. You manually respond as Makima through the web interface
4. Your responses are sent back to Discord

**You are now Makima!** 🎭
"""
    await ctx.send(help_text)

@app.route('/list_channels')
def list_channels():
    channels = []
    for guild in bot.guilds:
        for channel in guild.text_channels:
            # Only include channels the bot can send messages to
            if channel.permissions_for(guild.me).send_messages:
                channels.append({
                    "id": str(channel.id),
                    "name": f"{guild.name} / #{channel.name}"
                })
    return jsonify({"channels": channels})

@app.route('/list_users')
def list_users():
    users = []
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot:
                users.append({
                    "id": str(member.id),
                    "name": f"{member.display_name} ({guild.name})"
                })
    # Remove duplicates by user ID
    unique_users = {u['id']: u for u in users}.values()
    return jsonify({"users": list(unique_users)})

@app.route('/send_dm_as_makima', methods=['POST'])
def send_dm_as_makima():
    data = request.json
    user_id = data.get('userId')
    response_text = data.get('response')
    if not user_id or not response_text:
        return jsonify({"success": False, "error": "Missing userId or response"})
    bot.loop.create_task(send_dm_to_user(user_id, response_text))
    return jsonify({"success": True})

async def send_dm_to_user(user_id, response_text):
    user = await bot.fetch_user(int(user_id))
    if user:
        try:
            await user.send(response_text)
        except Exception as e:
            print(f"Failed to send DM: {e}")
    else:
        print(f"User {user_id} not found!")

@app.route('/makima_typing', methods=['POST'])
def makima_typing():
    data = request.json
    channel_id = data.get('channelId')
    if not channel_id:
        return jsonify({"success": False, "error": "Missing channelId"})
    bot.loop.create_task(handle_typing(channel_id))
    return jsonify({"success": True})

async def handle_typing(channel_id):
    channel = bot.get_channel(int(channel_id))
    if channel:
        try:
            await channel.trigger_typing()
        except Exception as e:
            print(f"Typing error: {e}")
        # No need to explicitly stop typing; Discord handles this automatically.

def run_flask():
    """Run Flask web server in a separate thread"""
    app.run(host='0.0.0.0', port=5000, debug=False)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return
    # This ensures every message from a Discord member is processed and appears in the Makima UI
    bot.loop.create_task(handle_manual_message(message))

if __name__ == '__main__':
    print('🎭 Starting Discord Makima Manual Control Bot...')
    print('You will control Makima manually through a web interface!')
    
    if not DISCORD_TOKEN:
        print('ERROR: DISCORD_TOKEN not found!')
        exit(1)
    
    # Start Flask web server in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    print('🌐 Web interface starting at http://localhost:5000')
    print('📱 Discord bot connecting...')
    
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        print(f'Error starting bot: {str(e)}')
