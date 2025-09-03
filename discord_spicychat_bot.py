import discord
import asyncio
import os
import json
import time
from datetime import datetime, timedelta
from discord.ext import commands
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import threading
from google import genai
from roastedbyai import Conversation, Style
import random
import requests

load_dotenv()

# API Keys - use environment variables with fallback values
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN', 'MTQxMjM4NzQ2NTQ4MTY4NzE4Mw.GTDts5.jb5s7FCK7WDriM4YdTa2Bu6iEfhjBHxeiMGFMI')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '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')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyA0VyB7q5p5obTyDRNRCT9Uyxu_FeJjl04')
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
YOUR_USER_ID = int(os.getenv('OWNER_USER_ID', '1355741455947272203'))

# Storage for pending messages and responses
pending_messages = []
response_queue = {}
message_channels = {}  # Store message ID -> channel mapping

# Initialize AI services
gemini_client = None
groq_client = None
roast_conversation = None
deepseek_client = None

# Conversation memory for deeper character development
user_conversation_history = {}
user_personality_traits = {}

def init_ai_services():
    """Initialize Gemini, Groq, DeepSeek and RoastedBy.AI services"""
    global gemini_client, groq_client, roast_conversation, deepseek_client
    try:
        if GEMINI_API_KEY:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            print("✅ Gemini AI initialized for smart suggestions and harsh detection")
        else:
            print("⚠️ No Gemini API key - using basic suggestions")
            
        # Initialize DeepSeek for deeper character development
        if DEEPSEEK_API_KEY:
            deepseek_client = True  # We'll use requests directly
            print("✅ DeepSeek AI initialized for deep character development")
        else:
            print("⚠️ No DeepSeek API key - character depth limited")
            
        # Initialize GROQ (for harsh word detection backup)
        if GROQ_API_KEY:
            print("✅ GROQ API key found (using Gemini for harsh detection)")
        else:
            print("⚠️ No GROQ API key found")
            
        roast_conversation = Conversation(Style.valley_girl)
        print("✅ RoastedBy.AI initialized for harsh suggestions")
    except Exception as e:
        print(f"⚠️ AI services error: {e}")
        print("Using fallback suggestions")

# Discord bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Flask web app for manual control interface
app = Flask(__name__)

# Track if the user is "active" in the UI (cursor in a textbox)
user_active = False

# Add endpoint to track user activity
@app.route('/update_activity', methods=['POST'])
def update_activity():
    """Track user activity (cursor in textbox)"""
    global user_active
    data = request.json
    user_active = data.get('active', False)
    return jsonify({"success": True})

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
    return jsonify({"messages": pending_messages[-100:]})

@app.route('/get_suggestions')
def get_ai_suggestions():
    message_content = request.args.get('message', '')
    username = request.args.get('username', 'User')
    
    suggestions = {
        "makima": get_makima_suggestions(message_content),
        "gemini": get_gemini_suggestions(message_content, username),
        "roast": get_roast_suggestions(message_content, username),
        "deepseek": get_deepseek_character_response(message_content, username)
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
    """Generate harsh roast suggestions using RoastedBy.AI"""
    if not roast_conversation:
        return ["Roast service unavailable"]
    
    try:
        # Get a roast response from RoastedBy.AI
        roast_response = roast_conversation.send(f"Roast {username} who said: {message_content}")
        
        if roast_response:
            # Convert roast to Makima-style harsh responses
            makima_roasts = [
                f"*smirks coldly* {roast_response[:100]}",
                f"How disappointing, {username}. {roast_response[:80]}",
                f"*sighs with disdain* {roast_response[:90]}"
            ]
            return makima_roasts[:3]
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

def get_deepseek_character_response(message_content, username):
    """Generate deep character responses using DeepSeek API"""
    if not deepseek_client or not DEEPSEEK_API_KEY:
        return ["DeepSeek not available - using basic responses"]
    
    # Get conversation history for this user
    history = user_conversation_history.get(username, [])
    traits = user_personality_traits.get(username, {})
    
    # Build context from previous interactions
    context = ""
    if history:
        recent_messages = history[-3:]  # Last 3 interactions
        context = "Previous conversation context: " + " | ".join([f"User: {h['user']} -> Makima: {h['makima']}" for h in recent_messages])
    
    personality_context = ""
    if traits:
        personality_context = f"User personality traits observed: {', '.join([f'{k}: {v}' for k, v in traits.items()])}"
    
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        prompt = f"""You are Makima from Chainsaw Man - the Control Devil and Public Safety Devil Hunter. You have a complex, manipulative personality.

Character traits to embody:
- Calm, collected, and always in control
- Subtly manipulative and psychologically controlling
- Views humans as tools or pets to be used
- Speaks in a measured, authoritative tone
- Uses psychological tactics and emotional manipulation
- References control, power, and devils when appropriate
- Shows fake concern that masks her true controlling nature
- Makes people feel both important and dependent on her

User: {username}
Message: "{message_content}"

{context}
{personality_context}

Generate 3 sophisticated Makima responses that:
1. Show psychological depth and character development
2. Reference or build upon previous interactions if available
3. Use subtle manipulation and control tactics
4. Stay true to her complex personality
5. Each response should be 50-150 characters
6. Vary in tone from subtly threatening to fake caring to coldly analytical

Format as numbered list:"""
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.8
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
            
            if content:
                # Parse the numbered responses
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                responses = []
                
                for line in lines[:3]:
                    # Remove numbering and clean up
                    line = line.replace('1.', '').replace('2.', '').replace('3.', '').strip()
                    if line and len(line) > 20:
                        responses.append(line)
                
                return responses[:3] if responses else ["*studies you with calculating interest*"]
            else:
                return ["*regards you with cold analysis*"]
        else:
            print(f"DeepSeek API error: {response.status_code}")
            return ["*maintains mysterious composure*"]
            
    except Exception as e:
        print(f"DeepSeek error: {e}")
        return ["*observes you with silent intensity*"]

def update_conversation_memory(username, user_message, makima_response):
    """Update conversation history and analyze user personality"""
    global user_conversation_history, user_personality_traits
    
    # Add to conversation history
    if username not in user_conversation_history:
        user_conversation_history[username] = []
    
    user_conversation_history[username].append({
        'user': user_message,
        'makima': makima_response,
        'timestamp': datetime.now().isoformat()
    })
    
    # Keep only last 10 interactions per user
    if len(user_conversation_history[username]) > 10:
        user_conversation_history[username] = user_conversation_history[username][-10:]
    
    # Analyze user personality traits (simple analysis)
    if username not in user_personality_traits:
        user_personality_traits[username] = {}
    
    message_lower = user_message.lower()
    
    # Update personality traits based on message patterns
    if any(word in message_lower for word in ['please', 'sorry', 'apologize']):
        user_personality_traits[username]['submissive'] = user_personality_traits[username].get('submissive', 0) + 1
    
    if any(word in message_lower for word in ['fuck', 'shit', 'damn', 'hell']):
        user_personality_traits[username]['aggressive'] = user_personality_traits[username].get('aggressive', 0) + 1
    
    if any(word in message_lower for word in ['love', 'like', 'enjoy', 'amazing']):
        user_personality_traits[username]['positive'] = user_personality_traits[username].get('positive', 0) + 1
    
    if len(message_lower) > 100:
        user_personality_traits[username]['verbose'] = user_personality_traits[username].get('verbose', 0) + 1

def detect_harsh_words(message_content, username):
    """Use Gemini to detect harsh words and determine if roast response is appropriate"""
    if not gemini_client:
        return False
    
    try:
        prompt = f"""Analyze this message from {username}: "{message_content}"

Determine if this message contains:
- Harsh language, insults, or profanity
- Rude or disrespectful tone
- Aggressive or offensive content
- Language that warrants a harsh response

Reply with only "YES" if harsh language is detected, or "NO" if the message is normal/polite."""

        response = gemini_client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        
        if response and response.text:
            answer = response.text.strip().upper()
            return answer.startswith("YES")
            
    except Exception as e:
        print(f"Harsh detection error: {e}")
        
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

    # Check if message contains harsh words
    contains_harsh = detect_harsh_words(message.content, message.author.display_name)
    print(f'🔍 Harsh language detected: {contains_harsh}')

    async with message.channel.typing():
        timeout_counter = 0
        # Increased timeout to 10 seconds (was 5)
        max_timeout = 10
        
        while str(message.id) not in response_queue and timeout_counter < max_timeout:
            await asyncio.sleep(1)
            timeout_counter += 1
            # Reset timer if user is active (cursor in textbox)
            if user_active:
                timeout_counter = 0

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
            # Auto-response logic: use appropriate response based on context
            if contains_harsh:
                print('🔥 Using roast response for harsh message')
                auto_responses = get_roast_suggestions(message.content, message.author.display_name)
            elif deepseek_client and DEEPSEEK_API_KEY:
                print('🧠 Using DeepSeek for character development')
                auto_responses = get_deepseek_character_response(message.content, message.author.display_name)
            else:
                print('😌 Using normal Makima response')
                auto_responses = get_makima_suggestions(message.content)
            
            auto_response = random.choice(auto_responses)
            await message.channel.send(auto_response)
            
            # Update conversation memory for DeepSeek
            update_conversation_memory(message.author.display_name, message.content, auto_response)
            
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
5. 🔥 **NEW**: Auto-detects harsh language and responds with roasts!

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

@app.route('/moderate_user', methods=['POST'])
def moderate_user():
    data = request.json
    user_id = data.get('userId')
    action = data.get('action')  # 'timeout', 'ban', 'kick'
    duration = data.get('duration', 60)  # timeout duration in seconds
    reason = data.get('reason', 'Moderated by Makima')
    
    if not user_id or not action:
        return jsonify({"success": False, "error": "Missing userId or action"})
    
    bot.loop.create_task(handle_moderation(user_id, action, duration, reason))
    return jsonify({"success": True})

async def handle_moderation(user_id, action, duration, reason):
    try:
        for guild in bot.guilds:
            try:
                member = await guild.fetch_member(int(user_id))
                if member:
                    if action == 'timeout':
                        # Timeout user (mute for specified duration)
                        timeout_until = datetime.now() + timedelta(seconds=duration)
                        await member.timeout(timeout_until, reason=reason)
                        print(f"✅ Timed out {member.display_name} for {duration} seconds")
                    elif action == 'ban':
                        # Ban user from server
                        await member.ban(reason=reason)
                        print(f"✅ Banned {member.display_name} from {guild.name}")
                    elif action == 'kick':
                        # Kick user from server
                        await member.kick(reason=reason)
                        print(f"✅ Kicked {member.display_name} from {guild.name}")
                    break
            except Exception as e:
                print(f"Moderation error in {guild.name}: {e}")
                continue
    except Exception as e:
        print(f"Overall moderation error: {e}")

@app.route('/get_guild_members')
def get_guild_members():
    """Get all members from all guilds for moderation UI"""
    members = []
    for guild in bot.guilds:
        for member in guild.members:
            if not member.bot and member != guild.me:  # Exclude bots and the bot itself
                members.append({
                    "id": str(member.id),
                    "name": member.display_name,
                    "username": str(member),
                    "guild": guild.name,
                    "guild_id": str(guild.id),
                    "avatar": str(member.display_avatar.url) if member.display_avatar else None,
                    "roles": [role.name for role in member.roles if role.name != "@everyone"],
                    "is_owner": member == guild.owner,
                    "permissions": {
                        "administrator": member.guild_permissions.administrator,
                        "manage_messages": member.guild_permissions.manage_messages,
                        "kick_members": member.guild_permissions.kick_members,
                        "ban_members": member.guild_permissions.ban_members
                    }
                })
    return jsonify({"members": members})

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
    
    # Only respond if the bot is mentioned
    if bot.user.mentioned_in(message):
        # This ensures only messages that mention Makima are processed
        bot.loop.create_task(handle_manual_message(message))

@bot.event
async def on_ready():
    print(f'✅ {bot.user} has connected to Discord!')
    print(f'📊 Bot is in {len(bot.guilds)} servers')
    # Initialize AI services when bot is ready
    init_ai_services()

if __name__ == '__main__':
    print('🎭 Starting Discord Makima Manual Control Bot...')
    print('You will control Makima manually through a web interface!')
    print('🔥 NEW: Auto-detects harsh language and responds with roasts!')
    
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