from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
import bcrypt
from flask_mysqldb import MySQL
import os
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from jinja2 import Template
from log_types import LogType
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from flask_socketio import SocketIO, emit
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import re
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from datetime import datetime, timedelta, timezone
import tiktoken
from collections import Counter

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=True)
load_dotenv()

# Google OAuth Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['MYSQL_HOST'] = 'localhost'  # host address of the database
app.config['MYSQL_USER'] = 'root'  # username of the database
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")  # password of the database
app.config['MYSQL_DB'] = 'productadvice'  # database name
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # session timeout

mysql = MySQL(app)

deepseek_chat = ChatGroq(
    api_key=DEEPSEEK_API_KEY,
    model_name="deepseek-r1-distill-llama-70b"  # or "deepseek-r1-distill-llama-70b" if available
)

def count_tokens(text):
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # veya en yakın olanı
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")  # fallback
    return len(encoding.encode(text))

def load_countries_from_db():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT code, name FROM countries ORDER BY name")
    countries = cursor.fetchall()
    cursor.close()
    return [{"code": code, "name": name} for code, name in countries]

def get_country_name(country_code):
    if not country_code:
        return None    
    countries = load_countries_from_db()
    for country in countries:
        if country['code'] == country_code:
            return country['name']
    return country_code

# Token serializer
s = URLSafeTimedSerializer(app.secret_key)

def get_db_connection():
    conn = mysql.connection
    try:
        conn.ping(reconnect=True)
    except Exception:
        conn = mysql.connect
    return conn

def log_action(log_type: LogType, message, user_id=None):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO app_logs (user_id, log_type, message)
        VALUES (%s, %s, %s)
    """, (user_id, log_type.value, message))
    mysql.connection.commit()
    cursor.close()

def log_email(template_name, recipient_email, subject, body, status="SUCCESS", error=None):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO email_logs (template_name, recipient_email, subject, body, status, error_message)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (template_name, recipient_email, subject, body, status, error))
    mysql.connection.commit()
    cursor.close()

def send_reset_email(to_email, token):
    reset_url = url_for('reset_password', token=token, _external=True)
    return send_email_from_template("RESETPASSWORD", to_email, {"reset_url": reset_url})

def send_password_changed_email(username, to_email):
    return send_email_from_template("PASSWORDCHANGED", to_email, {"username": username})

def get_email_template(template_name):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT subject, body FROM email_templates WHERE name = %s", (template_name,))
    result = cursor.fetchone()
    cursor.close()
    if result:
        return {"subject": result[0], "body": result[1]}
    return None

def render_template_from_db(text, variables):
    template = Template(text)
    return template.render(**variables)

def send_email_from_template(template_name, to_email, variables):
    template = get_email_template(template_name)
    if not template:
        print(f"Template {template_name} not found.")
        return False

    subject = render_template_from_db(template["subject"], variables)
    body = render_template_from_db(template["body"], variables)

    sender_email = os.getenv("EMAIL_USER")
    sender_name = "Botify"
    sender_password = os.getenv("EMAIL_PASS")

    message = MIMEText(body)
    message["Subject"] = subject
    message['From'] = f"{sender_name} <{sender_email}>"
    message["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)

        log_email(template_name, to_email, subject, body, status="SUCCESS")
        return True
    except Exception as e:
        print("Email send failed:", str(e))
        return False


def username_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (field.data,))
    existing_user = cursor.fetchone()
    cursor.close()
    
    if existing_user:
        raise ValidationError('This username is already taken. Please choose another one.')

def email_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (field.data,))
    existing_email = cursor.fetchone()
    cursor.close()
    
    if existing_email:
        raise ValidationError('This email is already taken.')

class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50), username_exists])
    email = StringField('Email', validators=[DataRequired(), Length(min=4, max=50), email_exists])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    country = SelectField('Country', choices=[], validate_choice=False)
    age = IntegerField('Age', validators=[Optional()])
    gender = SelectField('Gender', choices=[], validate_choice=False)
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Login')

class EditProfileForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[Length(min=4, max=50)])
    email = StringField('Email', validators=[DataRequired(), Length(min=5, max=50)])
    country = SelectField('Country', choices=[], validate_choice=False)
    age = IntegerField('Age', validators=[Optional()])
    gender = SelectField('Gender', choices=[], validate_choice=False)
    submit = SubmitField('EditProfile')
    change_username = SubmitField('Change Username')

class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Send Reset Link')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Reset Password')

class ChangeUsernameForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    new_username = StringField('New Username', validators=[DataRequired(), Length(min=4, max=50)])
    submit = SubmitField('Change Username')

class ContactForm(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Your Email', validators=[DataRequired(), Length(min=4, max=100)])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=10, max=1000)])
    submit = SubmitField('Send')

# Test database connection
@app.route('/testdb')
def testdb():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT VERSION()")
        data = cur.fetchone()
        return f"MySQL Version: {data[0]}"
    except Exception as e:
        return f"Database Connection Error: {str(e)}"

@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template("firstpage.html")

    user_id = session.get('user_id')
    username = session.get('username')
    fullname = session.get("name", "Guest") + " " + session.get("surname", "")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT conversation_id, title, created_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY last_activity_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conversations = [dict(zip(columns, row)) for row in rows]
    conn.close()

    return render_template(
        'index.html',
        user_id=user_id,
        username=username,
        fullname=fullname,
        conversations=conversations,
        messages=[],  # chatbox empty start
        active_conversation_id=None
    )


def get_user_context(user_id, conversation_id=None):
    # get user context from database
    print(f"Fetching user context for user_id: {user_id}, conversation_id: {conversation_id}")
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT age, gender, country FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()

    context = {}
    if result:
        context = {
            "age": result[0],
            "gender": result[1],
            "country": get_country_name(result[2])
        }

    # get keywords from conversation if conversation_id is provided
    print(f"Fetching keywords for conversation_id: {conversation_id}")
    if conversation_id:
        cursor.execute("SELECT keywords FROM conversations WHERE conversation_id = %s", (conversation_id,))
        keyword_result = cursor.fetchone()
        if keyword_result and keyword_result[0]:
            context["keywords"] = [word.strip() for word in keyword_result[0].split(",")]
            print(f"Keywords found: {context['keywords']}")

    cursor.close()
    return context

def extract_keywords(text, top_n=5):
    print(f"Extracting keywords from text: {text}")
    
    words = re.findall(r'\b\w+\b', text.lower())
    filtered_words = [
        word for word in words 
        if word not in ENGLISH_STOP_WORDS 
        and len(word) > 2 
        and not word.isdigit()
    ]

    word_counts = Counter(filtered_words)
    top_keywords = [word.capitalize() for word, count in word_counts.most_common(top_n)]

    print(f"Top keywords: {top_keywords}")
    return top_keywords

def start_new_conversation(user_id, title="Untitled"):
    print(f"Starting new conversation for user_id: {user_id}, title: {title}")
    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO conversations (user_id, title, created_at, keywords, is_active, last_activity_at)
        VALUES (%s, %s, NOW(), '', TRUE, NOW())
    """, (user_id, title))
    mysql.connection.commit()
    print(f"New conversation created with title: {title}")
    conversation_id = cursor.lastrowid
    cursor.close()
    print(f"New conversation started: {conversation_id}")
    session['conversation_id'] = conversation_id
    emit("conversation_initialized", {"conversation_id": conversation_id})
    print("EMIT conversation_initialized event emitted worked")
    # print all session variables
    print(f"Session variables: {session}")
    print(f"Session conversation_id: {session.get('conversation_id')}")
    print(f"Session user_id: {session['user_id']}")
    # method finish
    print(f"New conversation started: {conversation_id}")
    return conversation_id

def update_conversation_keywords(conversation_id, new_keywords):
    cursor = mysql.connection.cursor()

    cursor.execute("SELECT keywords FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    existing_keywords = set()

    if result and result[0]:
        existing_keywords = set(k.strip() for k in result[0].split(','))

    combined_keywords = existing_keywords.union(set(new_keywords))

    keyword_text = ", ".join(sorted(combined_keywords))

    cursor.execute("""
        UPDATE conversations SET keywords = %s WHERE conversation_id = %s
    """, (keyword_text, conversation_id))
    mysql.connection.commit()
    cursor.close()


def update_last_activity(conversation_id):
    print(f"Updating last activity for conversation_id: {conversation_id}")
    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE conversations SET last_activity_at = NOW() WHERE conversation_id = %s
    """, (conversation_id,))
    mysql.connection.commit()
    cursor.close()

def is_conversation_expired(conversation_id, minutes= 30):
    print(f"Checking if conversation_id: {conversation_id} is expired")
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT last_activity_at FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    print(f"Last activity result: {result}")
    cursor.close()
    if result and result[0]:
        last_active = result[0]
        if datetime.now(timezone.utc) - last_active.replace(tzinfo=timezone.utc) > timedelta(minutes=minutes):
            return True
    return False

def end_conversation(conversation_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE conversations SET is_active = 0 WHERE conversation_id = %s
    """, (conversation_id,))
    mysql.connection.commit()
    cursor.close()
    print(f"Conversation {conversation_id} ended.")
    print(f"Session variables before pop: {session}")
    print(f"Session conversation_id: {session.get('conversation_id')}")
    session.pop('conversation_id', None)
    print(f"Session variables after pop: {session}")
    print(f"Session conversation_id: {session.get('conversation_id')}")

def save_message(conversation_id, sender_type, content):
    if isinstance(content, (list, tuple)):
        content = " ".join(map(str, content))  # Her elemanı string yap ve birleştir
    print(f"type(content): {type(content)}")
    cursor = mysql.connection.cursor()
    cursor.execute("""
        INSERT INTO messages (conversation_id, sender_type, content, sent_at)
        VALUES (%s, %s, %s, NOW())
    """, (conversation_id, sender_type, content))
    mysql.connection.commit()
    cursor.close()

MAX_TOKENS = 6000

def remove_thinking_tags(input_string):
    cleaned_string = re.sub(r'<think>.*?</think>', '', input_string, flags=re.DOTALL)
    return cleaned_string

def separate_numbered_suggestions(text):
    pattern = r"<PRODUCT>\s*-\s*(.*?)\s*-\s*(.*?)($|\n)"
    matches = re.findall(pattern, text)
    return [{"name": name.strip(), "description": desc.strip()} for name, desc, _ in matches]

def ask_deepseek(user_message, user_context=None, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    print(f"🧠🧠🧠 ask_deepseek called | message: {user_message}")
    print(f"User context: {user_context}")
    print(f"Conversation history length: {len(conversation_history)}")
    print(f"Session: {session}")

    try:
        # 🧾 Base instruction prompt
        system_prompt = """
        You are an AI assistant designed to help users choose products.

        STRICT INSTRUCTIONS — FOLLOW CAREFULLY:
        1. If the user asks about buying a product, give a **brief overview (max 200 words)** of what key metrics or criteria to consider for that product type.
        2. If the user requests recommendations, return **ONLY up to 3 products**, each with:
            - A name
            - A short description (max 100 words)
            - Use the following format for each product:
              <PRODUCT> - [Product Name] - [Short Description]
        3. If the prompt is NOT about a product or recommendation, reply **exactly** with:
            "I am sorry but this box is only for the suggestion of products, please insert a new prompt."
        4. NEVER include more than 3 products. NEVER respond outside the specified format.
        Use EXACTLY the following format for each product (no numbering allowed!):
        <PRODUCT> - [Product Name] - [Short Description]
        ❗Do NOT use any numbering like "1.", "2.", etc. Only use <PRODUCT> tags.
        """
        print(f"System prompt: {system_prompt}")
        # 🎯 Add context if available
        if user_context:
            if user_context.get("age"):
                system_prompt += f" The user is {user_context['age']} years old."
            if user_context.get("gender"):
                system_prompt += f" They are {user_context['gender']}."
            if user_context.get("country"):
                system_prompt += f" They are from {user_context['country']}."
            if user_context.get("keywords"):
                system_prompt += f" The user's key concerns are: {', '.join(user_context['keywords'])}."

        # 🧱 Build LangChain message list
        messages = [SystemMessage(content=system_prompt)]
        print (f"System prompt: {system_prompt}")
        print (f"Messages: {messages}")
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "bot":
                messages.append(AIMessage(content=msg["content"]))

        # ➕ Add new user message
        messages.append(HumanMessage(content=user_message))
        print(f"Messages: {messages}")

        # 🔗 Call the model
        response = deepseek_chat(messages)
        print(f"Response: {response.content}")
        bot_reply = remove_thinking_tags(response.content)
        print(f"Bot reply: {bot_reply}")
        # 🧹 Clean response
        structured = separate_numbered_suggestions(bot_reply)
        print(f"Structured response: {structured}")
        # 🧾 Update history for next turn
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "bot", "content": bot_reply})
        print (f"Conversation history updated: {conversation_history}")
        return bot_reply, structured

    except Exception as e:
        print(f"❌ DeepSeek error: {str(e)}")
        return "Sorry, I couldn't generate a response.", conversation_history

@socketio.on("session_check")
def handle_session_check():
    print("✅ WebSocket connection built.")
    print("📦 Session:")
    for key, value in session.items():
        print(f"  {key}: {value}")

@socketio.on("localstorage_sync")
def handle_localstorage_sync(data):
    key = data.get("key")
    value = data.get("value")
    action = data.get("action")
    user_id = session.get("user_id")

    print(f"🛰️ localStorage sync from user_id {user_id} — {action.upper()} → {key} = {value}")
    log_action(LogType.LOCALSTORAGE_SYNC, f"User {user_id} synced localStorage: {key} = {value}", user_id=user_id)

    if key == "conversation_id":
        if action == "set":
            session["conversation_id"] = int(value)
            print(f"✅ conversation_id set in session from localStorage: {value}")
        elif action == "remove":
            print(f"🧹 conversation_id removed from session due to localStorage removal. (previous value: {value})")
            session.pop("conversation_id", None)


@socketio.on("user_message")
def handle_user_message(data):
    print(f"🟡 handle_user_message called with data: {data}")
    user_text = data.get("content", "").strip()
    user_id = session.get("user_id")
    
    if not user_id:
        emit("info_message", {"content": "User session not found. Please log in again."})
        return

    conversation_id = session.get("conversation_id")

    # ✅ If there's no conversation ID in the session, start a new one
    # (localStorage will also sync it to the backend, if present)
    if not conversation_id:
        print("➕ No conversation found in session. Starting new.")
        conversation_id = start_new_conversation(user_id, title="Chat Session")

    else:
        # ⏰ Check if the conversation has expired (e.g., 30 mins of inactivity)
        if is_conversation_expired(conversation_id, minutes=30):
            print(f"⏰ Conversation expired: {conversation_id}")
            end_conversation(conversation_id)
            conversation_id = start_new_conversation(user_id, title="New Chat After Timeout")
            emit("info_message", {"content": "Your chat session has expired. A new conversation has been started."})

    # 🔁 Update session with the valid conversation_id
    session["conversation_id"] = conversation_id

    print(f"✅ Using conversation_id: {conversation_id}")

    # 💬 Save user's message to the database
    save_message(conversation_id, 'user', user_text)

    # 🗝️ Extract and update conversation keywords
    new_keywords = extract_keywords(user_text)
    update_conversation_keywords(conversation_id, new_keywords)

    # ⏱️ Update last activity timestamp for session timeout tracking
    update_last_activity(conversation_id)

    # 👤 Fetch user context (age, gender, country, keywords, etc.)
    user_context = get_user_context(user_id, conversation_id)

    # 🤖 Get AI assistant's response based on conversation history and user context
    conversation_history = get_conversation_history(conversation_id)
    bot_reply, structured = ask_deepseek(user_text, user_context, conversation_history)

    # 💾 Save bot's reply to the database
    save_message(conversation_id, 'bot', bot_reply)

    # 🚀 Send bot's reply to frontend in real-time
    if structured:
        emit("bot_reply", {"content": structured})
    else:
        emit("bot_reply", {"content": bot_reply})

def get_conversation_history(conversation_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT sender_type, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY sent_at
    """, (conversation_id,))
    raw_history = cursor.fetchall()
    cursor.close()

    history = []
    for sender_type, content in raw_history:
        if sender_type == "user":
            history.append({"role": "user", "content": content})
        elif sender_type == "bot":
            history.append({"role": "bot", "content": content})
    return history


@app.route('/conversation/<int:conversation_id>')
def view_conversation(conversation_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT title, created_at FROM conversations
        WHERE conversation_id = %s AND user_id = %s
    """, (conversation_id, user_id))
    convo_info = cursor.fetchone()

    if not convo_info:
        conn.close()
        return redirect(url_for("index"))

    title, created_at = convo_info

    cursor.execute("""
        SELECT sender_type, content, sent_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY sent_at ASC
    """, (conversation_id,))
    raw_messages = cursor.fetchall()
    messages = [
        {
            "sender_type": row[0],
            "content": row[1],
            "sent_at": row[2].strftime("%d.%m.%Y %H:%M")
        }
        for row in raw_messages
    ]

    cursor.execute("""
        SELECT conversation_id, title, created_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY last_activity_at DESC
    """, (user_id,))
    raw_conversations = cursor.fetchall()
    conversations = [
        {
            "conversation_id": row[0],
            "title": row[1],
            "created_at": row[2].strftime("%d %B %Y %H:%M")
        }
        for row in raw_conversations
    ]

    conn.close()
    return render_template(
        "index.html",
        fullname=session.get("name", "Guest") + " " + session.get("surname", ""),
        conversations=conversations,
        messages=messages,
        active_conversation_id=conversation_id,
        active_title=title,
        active_created_at=created_at.strftime("%d %B %Y %H:%M")
    )

def update_conversation_status(conversation_id, status):
    # Assuming you have a Conversation model or direct SQL query to update the status
    connection = get_db_connection()  # Your database connection method
    cursor = connection.cursor()

    # SQL query to update the status of the conversation
    query = "UPDATE conversations SET is_active = %s WHERE conversation_id = %s"
    cursor.execute(query, (status, conversation_id))

    connection.commit()
    cursor.close()
    connection.close()

@app.route('/end_chat', methods=['POST'])
def end_chat():
    print("Ending chat backend started") 
    
    # Get conversation_id from form (POST)
    form_conversation_id = request.form.get("conversation_id")
    print(f"Form conversation_id: {form_conversation_id}")

    if form_conversation_id:
        try:
            conversation_id = int(form_conversation_id)
        except ValueError:
            conversation_id = session.get('conversation_id')
    else:
        conversation_id = session.get('conversation_id')

    print(f"Ending conversation: {conversation_id}")
    
    if not conversation_id:
        return redirect(url_for('index'))

    try:
        update_conversation_status(conversation_id, 0)
        save_message(conversation_id, 'bot', 'Conversation ended.')

        final_title = generate_ai_title_from_keywords(conversation_id)
        print("Generated Title:", final_title)
        update_conversation_title(conversation_id, final_title)        
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error ending conversation: {e}")
        return redirect(url_for('404'))

def extract_title_from_llm_output(cleaned_text):
    match = re.search(r"<TITLE>(.*?)</TITLE>", cleaned_text, re.IGNORECASE | re.DOTALL)
    if match:
        title = match.group(1).strip()
        word_count = len(title.split())
        if 2 <= word_count <= 15:
            return title
        else:
            print(f"Invalid title word count ({word_count}): '{title}'")
    else:
        print("<TITLE> tag not found in LLM output.")
    return None

def get_keywords_for_conversation(conversation_id):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT keywords FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    cursor.close()

    if not result or not result[0]:
        return []
    return [k.strip() for k in result[0].split(',') if k.strip()]

def generate_ai_title_from_keywords(conversation_id):
    keywords = get_keywords_for_conversation(conversation_id)
    if not keywords:
        return "Chat Session"

    keyword_text = ", ".join(keywords)

    system_prompt = """
    You are a product recommendation assistant.

    Your ONLY task is to generate a title based on a list of keywords from a user conversation.

    Follow these strict rules:
    1. Wrap the title with <TITLE> and </TITLE> tags.
    2. The title must be between 5 and 10 words.
    3. DO NOT include any other tags like <think>, <response>, or explanations.
    4. DO NOT explain, comment, list, or return anything except the title.
    5. Output must contain ONLY the <TITLE> tag and the final title.

    Example:
    <TITLE>Best Budget Smartphones for Gaming Enthusiasts</TITLE>
    """

    user_prompt = f"Keywords: {keyword_text}"
    print(f"[🧠 PROMPT] {system_prompt}")
    
    try:
        response = deepseek_chat([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ])
        print(f"[🧠 RESPONSE - response.content:] {response.content}")

        bot_reply_title = remove_thinking_tags(response.content)
        print(f"[🧠 CLEANED bot_reply_title] {bot_reply_title}")
        title = extract_title_from_llm_output(bot_reply_title)
        return title or f"{keyword_text}"
    except Exception as e:
        print(f"❌ AI title generation failed: {e}")
        return f"Chat Session: {keyword_text}"


def update_conversation_title(conversation_id, new_title):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        UPDATE conversations SET title = %s WHERE conversation_id = %s
    """, (new_title, conversation_id))
    mysql.connection.commit()
    cursor.close()

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()

    if form.validate_on_submit():
        name = form.name.data
        email = form.email.data
        message = form.message.data

        variables = {
            "name": name,
            "email": email,
            "message": message
        }

        success = send_email_from_template("CONTACT_FORM", email, variables)

        if success:
            return redirect(url_for('contact_success'))

    return render_template('contact.html', form=form)

@app.route('/contact-success')
def contact_success():
    return render_template('contact_success.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    countries = load_countries_from_db()    
    session.pop('user_id', None)  
    session.pop('username', None)
    session.pop('name', None)  
    session.pop('surname', None)
    form = RegistrationForm()
    form.submit.label.text = "Sign Up"
    form.country.choices = [('', '-- Select --')] + [(c["code"], c["name"]) for c in countries] 
    form.gender.choices = [('', '-- Select --'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')]

    if form.validate_on_submit():
        name = form.name.data
        surname = form.surname.data
        username = form.username.data
        email = form.email.data
        password = form.password.data
        country = form.country.data or None
        age = form.age.data or None
        gender = form.gender.data or None

        hashed_password = bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt())

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (name, surname, username, email, password, country, age, gender) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (name, surname, username, email, hashed_password, country, age, gender))

        mysql.connection.commit()

        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()

        # Session Creation
        session['user_id'] = user[0]
        session['username'] = username
        session['name'] = name
        session['surname'] = surname
        session.permanent = True        

        log_action(LogType.USER_REGISTERED, f"New user registered: {username}", user_id=user[0])
        send_email_from_template("WELCOME", email, {"username": username,"name": name})
        return redirect(url_for('register_success'))

    return render_template('register.html', form=form)

@app.route('/register-success')
def register_success():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('register_success.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    error_message = None
    if 'username' in session:
       return redirect(url_for('index'))

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, username, password, name, surname FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):  
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['name'] = user[3]
            session['surname'] = user[4]
            session['is_google_user'] = False
            session.permanent = True
            log_action(LogType.USER_LOGGED_IN, f"User logged in: {username}", user_id=user[0])
            return redirect(url_for('index'))
        else:
            log_action(LogType.LOGIN_FAILED, f"Login failed for username: {username}")
            error_message = "Invalid username or password."

    return render_template('login.html', form=form, error=error_message)

@app.route('/login/google', methods=['POST'])
def google_login():
    try:
        token = request.json.get('token')

        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # Get user information
        email = id_info.get('email')
        first_name = id_info.get('given_name', '')
        last_name = id_info.get('family_name', '')

        # If Google has not sent family_name or given_name, split from name
        if not first_name or not last_name:
            full_name = id_info.get('name', '')
            name_parts = full_name.split(' ', 1)
            first_name = first_name or name_parts[0]
            last_name = last_name or (name_parts[1] if len(name_parts) > 1 else '')

        # user exist in database?
        cursor = get_db_connection().cursor()
        cursor.execute("SELECT id, username, name, surname FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            # create session for existing user
            session['user_id'] = existing_user[0]
            session['username'] = existing_user[1]
            session['name'] = existing_user[2]
            session['surname'] = existing_user[3]
        else:
            # create a new username
            base_username = email.split('@')[0]
            username = base_username
            counter = 1

            while True:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if not cursor.fetchone():
                    break
                username = f"{base_username}{counter}"
                counter += 1

            cursor.execute("""
                INSERT INTO users (name, surname, username, email, country, age, gender)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, username, email, None, None, None))

            mysql.connection.commit()

            send_email_from_template("GOOGLE_LOGIN", email, {"username": username})

            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            new_user = cursor.fetchone()

            session['user_id'] = new_user[0]
            session['username'] = username
            session['name'] = first_name
            session['surname'] = last_name

        session['is_google_user'] = True
        session.permanent = True

        log_action(
            LogType.GOOGLE_LOGIN,
            f"User logged in via Google: {session['username']}",
            user_id=session['user_id']
        )

        cursor.close()
        return jsonify({'redirect': url_for('index')})

    except ValueError:
        return jsonify({'error': 'Invalid Google ID token'}), 400
    except Exception as e:
        print(f"Google OAuth Error: {str(e)}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('index')) 

    user_id = session['user_id']

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT username, country, name, surname, age, gender, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()

    if not user:
        return "User not found!", 404

    user = list(user)
    user[1] = get_country_name(user[1])
    user[5] = user[5].capitalize() if user[5] else None
    return render_template('profile.html', user=user)


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    countries = load_countries_from_db()
    form = EditProfileForm() 
    form.country.choices = [('', '-- Select --')] + [(c["code"], c["name"]) for c in countries]
    form.gender.choices = [('', '-- Select --'), ('male', 'Male'), ('female', 'Female'), ('other', 'Other')]

    cursor = mysql.connection.cursor()

    if request.method == 'GET':
        print("GET Request")
        cursor.execute("SELECT name, surname, country, age, gender, email, username FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.close()

        if not user_data:
            return "User not found", 404

        form.name.data = user_data[0]
        form.surname.data = user_data[1]
        form.country.data = user_data[2]
        form.age.data = user_data[3]
        form.gender.data = user_data[4]
        form.email.data = user_data[5]
        form.username.data = user_data[6]

    elif form.validate_on_submit():
        name = form.name.data
        surname = form.surname.data
        email = form.email.data
        country = form.country.data or None
        age = int(form.age.data) if form.age.data else None
        gender = form.gender.data or None        

        cursor.execute("""
            UPDATE users 
            SET name = %s, surname = %s, country = %s, age = %s, gender = %s, email = %s
            WHERE id = %s
        """, (name, surname, country, age, gender, email, user_id))
        mysql.connection.commit()
        cursor.close()

        session['name'] = name
        session['surname'] = surname
        log_action(LogType.USER_UPDATED, f"User updated their profile: {session['username']}", user_id=session['user_id'])
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', form=form)

@app.route('/change-username', methods=['GET', 'POST'])
def change_username():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if session.get('is_google_user'):
        return "Google users cannot change their username.", 403
    
    form = ChangeUsernameForm()
    error_message = None

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        new_username = form.new_username.data
        user_id = session['user_id']

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT email, password, username FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            cursor.close()
            error_message = "User not found."
        else:
            user_email, hashed_pw, current_username = user
            if email != user_email or not bcrypt.checkpw(password.encode('utf-8'), hashed_pw.encode('utf-8')):
                cursor.close()
                error_message = "Invalid email or password."
            else:
                # New username is already taken by another user
                cursor.execute("SELECT id FROM users WHERE username = %s", (new_username,))
                if cursor.fetchone():
                    cursor.close()
                    error_message = "Username already taken."
                else:
                    cursor.execute("UPDATE users SET username = %s WHERE id = %s", (new_username, user_id))
                    mysql.connection.commit()
                    cursor.close()

                    # Send email to confirm username change
                    send_email_from_template("USERNAME_CHANGED", email, {
                        "old_username": current_username,
                        "new_username": new_username
                    })

                    # Log the username change action
                    log_action(LogType.USERNAME_CHANGED,
                               f"Username changed from {current_username} to {new_username}",
                               user_id=user_id)

                    session['username'] = new_username

                    return redirect(url_for('profile'))

    return render_template('change_username.html', form=form, error=error_message)


@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    # Redirect to login if user is not logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session.get('user_id')
    username = session.get('username', 'unknown')

    cursor = mysql.connection.cursor()

    # Retrieve user information (name, surname, email) before deleting
    cursor.execute("SELECT name, surname, email FROM users WHERE id = %s", (user_id,))
    user_info = cursor.fetchone()

    if user_info:
        name, surname, email = user_info

        # Delete the user account
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        mysql.connection.commit()

        # Send an account deletion confirmation email to the user
        variables = {
            "name": name,
            "surname": surname,
            "username": username
        }
        send_email_from_template("ACCOUNT_DELETED", email, variables)

        # Log the account deletion action
        log_action(LogType.USER_DELETED, f"User deleted their account: {username} (ID: {user_id})", user_id=user_id)

    cursor.close()
    session.clear()

    # Redirect the user to the login page after deletion
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    form = ForgotPasswordForm()
    message = None
    if form.validate_on_submit():
        email = form.email.data
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, password FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            user_id, password_hash = user

            # Prevent Google users from resetting password
            if password_hash is None:
                message = "Google users cannot reset password. Please use Google Sign-In to log in."
                return render_template('forgot_password.html', form=form, message=message)

            token = s.dumps(email, salt='email-reset')
            reset_url = url_for('reset_password', token=token, _external=True)
            send_email_from_template("RESETPASSWORD", email, {"reset_url": reset_url})
            log_action(LogType.PASSWORD_RESET_LINK_SENT, f"Password reset link sent to: {email}", user_id=user_id)
            message = "A password reset link has been sent to your email."
        else:
            message = "If this email is registered, a reset link has been sent."

    return render_template('forgot_password.html', form=form, message=message)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='email-reset', max_age=3600)  # 1 hour
    except SignatureExpired:
        return "The reset link has expired.", 403
    except BadSignature:
        return "Invalid or tampered link.", 403

    # Check if the user is a Google account user
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, password FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()

    if not user:
        return "User not found.", 404

    user_id, password_hash = user

    if password_hash is None:
        return "Google users cannot reset password.", 403

    form = ResetPasswordForm()
    if form.validate_on_submit():
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            return render_template('reset_password.html', form=form, error="Passwords do not match.")

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET password = %s WHERE id = %s", (hashed_password, user_id))
        mysql.connection.commit()

        cursor.execute("SELECT username, name, surname FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.close()

        if user_data:
            username, name, surname = user_data
            session['user_id'] = user_id
            session['username'] = username
            session['name'] = name
            session['surname'] = surname
            session['is_google_user'] = False
            session.permanent = True

            send_email_from_template("PASSWORDCHANGED", email, {"username": username})
            log_action(LogType.PASSWORD_CHANGED, f"Password successfully changed for user: {username}", user_id=user_id)

        return redirect(url_for('index'))

    return render_template('reset_password.html', form=form)

@app.route('/logout')
def logout():
    log_action(LogType.USER_LOGGED_OUT, f"User logged out: {session.get('username', 'unknown')}", user_id=session.get('user_id'))
    session.pop('user_id', None)  
    session.pop('username', None) 
    session.pop('name', None) 
    session.pop('surname', None)
    session.pop('is_google_user', None)
    return render_template('firstpage.html')

@app.route('/firstpage')
def firstpage():
    return render_template('firstpage.html')

@app.route('/temp', methods=['GET', 'POST'])
def temp():
    return render_template('temp.html')


@app.route('/favourites', methods=['GET', 'POST'])
def favourites():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('favourites.html')

if __name__ == '__main__':
    app.run(debug=True)
    
