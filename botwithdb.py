import logging
import os
import json
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Configure the generative AI
genai.configure(api_key=GEMINI_API_KEY)

# Set up the generative model configuration
generation_config = {
    "temperature": 0.9,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

safety_settings = [
    {
        "category": "HARM_CATEGORY_HARASSMENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_HATE_SPEECH",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_MEDIUM_AND_ABOVE"
    },
]

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database setup
db_path = "chatbot.db"


def init_db():
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            user_id INTEGER,
            message TEXT,
            sender TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            user_id INTEGER PRIMARY KEY,
            conversation1 TEXT,
            conversation2 TEXT,
            conversation3 TEXT,
            conversation4 TEXT,
            conversation5 TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_message(user_id, message, sender):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chats (user_id, message, sender) VALUES (?, ?, ?)", (user_id, message, sender))
    conn.commit()
    conn.close()


def update_chat_history(user_id, user_message, bot_response):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Fetch existing chat history
    cursor.execute("SELECT * FROM chat_history WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    # Prepare new conversation string
    new_conversation = f"User: {user_message} | Bot: {bot_response}"

    if result:
        # Update existing record
        conversations = list(result[1:])
        if len(conversations) >= 5:
            conversations.pop(0)
        conversations.append(new_conversation)
        cursor.execute("""
            UPDATE chat_history 
            SET conversation1 = ?, conversation2 = ?, conversation3 = ?, conversation4 = ?, conversation5 = ? 
            WHERE user_id = ?
        """, (*conversations, user_id))
    else:
        # Insert new record
        cursor.execute("""
            INSERT INTO chat_history (user_id, conversation1) 
            VALUES (?, ?)
        """, (user_id, new_conversation))

    conn.commit()
    conn.close()


def get_chat_history(user_id):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_history WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[1:] if result else []


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user_id = update.message.from_user.id
    message = 'Hi! Welcome to OkayAyussbot!'
    log_message(user_id, message, 'bot')
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    user_id = update.message.from_user.id
    message = 'Help! How can I assist you?'
    log_message(user_id, message, 'bot')
    await update.message.reply_text(message)


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Echo the user message."""
    user_id = update.message.from_user.id
    user_message = update.message.text
    log_message(user_id, user_message, 'user')
    log_message(user_id, user_message, 'bot')
    await update.message.reply_text(user_message)


def get_weather_data(city_name):
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    complete_url = base_url + "appid=" + OPENWEATHERMAP_API_KEY + "&q=" + city_name
    response = requests.get(complete_url)
    if response.status_code == 200:
        return json.loads(response.text)
    else:
        return None


def create_funny_weather_phrase(weather_data):
    model = genai.GenerativeModel(model_name="gemini-1.5-flash",
                                  generation_config=generation_config,
                                  safety_settings=safety_settings)
    weather_description = weather_data['weather'][0]['description']
    prompt = f"The weather is {weather_description}. Write a funny phrase about this."
    response = model.generate_content(prompt)
    return response.text


async def funny_weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a funny weather phrase when the command /fw is issued."""
    user_id = update.message.from_user.id
    city_name = ' '.join(context.args) if context.args else "New York"  # Default to "New York" if no args are provided
    weather_data = get_weather_data(city_name)
    if weather_data:
        funny_phrase = create_funny_weather_phrase(weather_data)
        log_message(user_id, funny_phrase, 'bot')
        await update.message.reply_text(funny_phrase)
    else:
        error_message = f"Error fetching weather data for {city_name}."
        log_message(user_id, error_message, 'bot')
        await update.message.reply_text(error_message)


def ai(text, history):
    history_prompt = "\n".join([f"Conversation {i + 1}: {conv}" for i, conv in enumerate(history) if conv])
    prompt = f"{history_prompt}\nYou are named as Ayush Dhiman. You are a 4th year indian college going student who is a nerd, loves food and prefers personal time & space over everything, except coding, movies and music. he is kind, and usually speaks softly. Try to answer like ayush, in a very casual human like way, who may sometimes be funny(like as in dad jokes) and reply to the given prompt in a very natural language and human like friendly way, just like a conversation between two best friends. Also ayush does not like to speak extra, so his replies are always concise, meaning-full, supportive and single ended answers. Don't mention useless stuff, until asked, he just replies to what is questioned and especially AVOIDS small talks or explaining/saying useless stuff that would go un-noticed: {text}"
    model = genai.GenerativeModel(model_name="gemini-1.5-flash",
                                  generation_config=generation_config,
                                  safety_settings=safety_settings)
    response = model.generate_content(prompt)
    return response.text


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answers the user prompt using AI"""
    user_id = update.message.from_user.id
    if context.args:
        user_prompt = ' '.join(context.args)
        log_message(user_id, user_prompt, 'user')

        # Get chat history
        history = get_chat_history(user_id)

        # Generate AI answer
        ai_answer = ai(user_prompt, history)

        # Log and respond
        log_message(user_id, ai_answer, 'bot')
        update_chat_history(user_id, user_prompt, ai_answer)
        await update.message.reply_text(ai_answer)


def main() -> None:
    """Start the bot."""
    # Initialize the database
    init_db()

    # Initialize the bot application with the token from the .env file
    application = Application.builder().token(BOT_TOKEN).build()

    # on different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("fw", funny_weather))
    application.add_handler(CommandHandler("okayayuss", answer))

    # on non-command i.e message - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Start the Bot
    application.run_polling()


if __name__ == '__main__':
    main()
