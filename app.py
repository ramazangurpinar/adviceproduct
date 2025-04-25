### All necessary library to meke the web application work:
### Import Flask and other utilities templates, handling sessions, redirects, requests, and JSON responses
from flask import Flask, json, render_template, redirect, url_for, session, request, jsonify
### Import FlaskForm for creating secure web forms and field types
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField, TextAreaField
### Validators and custom validators
from wtforms.validators import DataRequired, Length, ValidationError, Optional
### Secure password handling
import bcrypt
### Connection to MySQL Data Base
from flask_mysqldb import MySQL
### Handling ambient variables
import os
### Handle environment variables in a .env environment
from dotenv import load_dotenv
### SMTP ptotocol for handling emails
import smtplib
from email.mime.text import MIMEText
### Generating and verifying secure tokens
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
### Rendering of some templates
from jinja2 import Template
### Custom log type
from log_types import LogType
### Handling authentication with google ID
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
### Handling real time chat
from flask_socketio import SocketIO, emit
### Handlig AI API
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
### To work with regular expressions
import re
### NLP processing
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
### Handling dates and times
from datetime import datetime, timedelta, timezone
### Tokenisation 
import tiktoken
### Counter of occurrencies
from collections import Counter
### Creates default lists for each key
from collections import defaultdict

###-------------------------------------------------------------------------
### Configuration and Global Setup
### Init
app = Flask(__name__)
### Set up SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", manage_session=True)
### Load the environment
load_dotenv()

### Init keys
### DeepSeek key
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
### Google keys
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

### Setting the key for the environment
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
### Setting connection to the database
app.config['MYSQL_HOST'] = os.getenv("MYSQL_HOST") 
app.config['MYSQL_PORT'] = int(os.getenv("MYSQL_PORT"))  # host address of the database
app.config['MYSQL_USER'] =  os.getenv("MYSQL_USER")  # username of the database
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")  # password of the database
app.config['MYSQL_DB'] = os.getenv("MYSQL_DB")   # database name
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # session timeout
MAX_TOKENS = 6000

### Initialise MySQL with Flask app
mysql = MySQL(app)

### Create DeepSeek chat model
deepseek_chat = ChatGroq(
    api_key=DEEPSEEK_API_KEY,
    model_name="deepseek-r1-distill-llama-70b"  # or "deepseek-r1-distill-llama-70b" if available
)

### Token serializer
s = URLSafeTimedSerializer(app.secret_key)

###-------------------------------------------------------------------------
### Validators
### Custom validator to check if username is already used in the Data Base
def username_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (field.data,))
    existing_user = cursor.fetchone()
    cursor.close()
    
    if existing_user:
        raise ValidationError('This username is already taken. Please choose another one.')

### Custom validator to check if the email is already in use in the Data Base
def email_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (field.data,))
    existing_email = cursor.fetchone()
    cursor.close()
    
    if existing_email:
        raise ValidationError('This email is already taken.')

###-------------------------------------------------------------------------
### Forms

### Resgistration form and all restrictions for the fields
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

### Login form and all the restrictions for the fields
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Login')

### Edit profile form with all restriction on the fields 
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

### Forgot password form with all restrictions on the fields 
class ForgotPasswordForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    submit = SubmitField('Send Reset Link')

### Reset Password Form with all restrictions on the fields 
class ResetPasswordForm(FlaskForm):
    password = PasswordField('New Password', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), Length(min=6)])
    submit = SubmitField('Reset Password')

### Change username form with all restrictions on the fields
class ChangeUsernameForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    new_username = StringField('New Username', validators=[DataRequired(), Length(min=4, max=50)])
    submit = SubmitField('Change Username')

### Contact form with all restrictions on the fields 
class ContactForm(FlaskForm):
    name = StringField('Your Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Your Email', validators=[DataRequired(), Length(min=4, max=100)])
    message = TextAreaField('Message', validators=[DataRequired(), Length(min=10, max=1000)])
    submit = SubmitField('Send')

###-------------------------------------------------------------------------
### Utility Functions

### Function to count the tokens using tiktokens 
def count_tokens(text):
    try:
        ### Attempt to get the appropriate encoding for GPT-3.5 Turbo
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")  # veya en yakın olanı
    except KeyError:
        ### If the model is not found, fall back to a base encoding
        encoding = tiktoken.get_encoding("cl100k_base")  # fallback
    ### Return no of tokens
    return len(encoding.encode(text))

### Function to load from the Data Base the list of countries
def load_countries_from_db():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT code, name FROM countries ORDER BY name")
    countries = cursor.fetchall()
    cursor.close()
    return [{"code": code, "name": name} for code, name in countries]

### Parse country code to extended name of the country
def get_country_name(country_code):
    ### If input is empety return None
    if not country_code:
        return None    
    countries = load_countries_from_db()
    for country in countries:
        if country['code'] == country_code:
            return country['name']
    ### If the code is not found it will be retuned the country_code itself
    return country_code

### Function that ensures a working connection to the database, reconnecting if necessary
def get_db_connection():
    conn = mysql.connection
    try:
        conn.ping(reconnect=True)
    except Exception:
        conn = mysql.connect
    return conn

### Function that based on the name of a product return an url to shop that product on google
def get_google_shopping_url(product_name, category_name=None):
    query = product_name
    if category_name:
        query += f" {category_name}"
    query = query.replace(" ", "+")
    return f"https://www.google.com/search?tbm=shop&q={query}"

###-------------------------------------------------------------------------
### Logging & Tracking

### Returns the log type ID from the database based on an enum value
def get_log_type_id(log_type: LogType):
    cursor = mysql.connection.cursor()
    ### Query
    cursor.execute("SELECT log_type_id FROM log_types WHERE log_name = %s", (log_type.value,))
    log_type_id = cursor.fetchone() # Get the log type ID from result
    
    cursor.close()

    ### If log_type_id is found the function returns the ID
    if log_type_id:
        return log_type_id[0]
    ### If log_type_id is not found the function print an error on the terminal and returns None
    else:
        print(f"Error: Log type {log_type.value} not found in log_types table.")
        return None

### Function that inserts a int the Log (DB) an action
def log_action(log_type: LogType, message, user_id=None):
    log_type_id = get_log_type_id(log_type)
    
    ### Exit the function if log type is not valid
    if log_type_id is None:
        return
    
    cursor = mysql.connection.cursor()

    ### Query
    cursor.execute("""
        INSERT INTO app_logs (user_id, log_type_id, message)
        VALUES (%s, %s, %s)
    """, (user_id, log_type_id, message))

    mysql.connection.commit()
    cursor.close()

### Logs an email event in the database, including status and any errors
def log_email(template_name, recipient_email, subject, body, status="SUCCESS", error=None):
    cursor = mysql.connection.cursor()

    ### Query
    cursor.execute("""
        INSERT INTO email_logs (template_name, recipient_email, subject, body, status, error_message)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (template_name, recipient_email, subject, body, status, error))

    mysql.connection.commit()
    cursor.close()

###-------------------------------------------------------------------------
### E-mail Handling

### Fetches the subject and body of an email template from the database
def get_email_template(template_name):
    cursor = mysql.connection.cursor()
    ### Query
    cursor.execute("SELECT subject, body FROM email_templates WHERE name = %s", (template_name,))
    result = cursor.fetchone()
    cursor.close()
    if result:
        return {"subject": result[0], "body": result[1]}
    return None

### Function that using Jinja2 renders template string using the provided variables
def render_template_from_db(text, variables):
    template = Template(text)
    return template.render(**variables)

### Function that sends an email using a DB stored template
def send_email_from_template(template_name, to_email, variables):
    template = get_email_template(template_name)
    ### If the template is not found, print an error message and return False
    if not template:
        print(f"Template {template_name} not found.")
        return False

    ### Render the subject and body using the provided variables
    subject = render_template_from_db(template["subject"], variables)
    ### Render the body using the provided variables
    body = render_template_from_db(template["body"], variables)

    ### Set up the email sender
    sender_email = os.getenv("EMAIL_USER")
    ### Set up the sender name
    sender_name = "Botify"
    ### Set up the sender password
    sender_password = os.getenv("EMAIL_PASS")

    ### Create the email message
    message = MIMEText(body)
    ### Set the email headers
    message["Subject"] = subject
    message['From'] = f"{sender_name} <{sender_email}>"
    message["To"] = to_email

    ### Try to set the email sender
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)

        log_email(template_name, to_email, subject, body, status="SUCCESS")
        return True
    ### If the email sender fails, log the error and return False
    except Exception as e:
        print("Email send failed:", str(e))
        return False

### Send password reset email using a token
def send_reset_email(to_email, token):
    reset_url = url_for('reset_password', token=token, _external=True)
    return send_email_from_template("RESETPASSWORD", to_email, {"reset_url": reset_url})

### Sends confirmation email when a password has been changed
def send_password_changed_email(username, to_email):
    return send_email_from_template("PASSWORDCHANGED", to_email, {"username": username})

###-------------------------------------------------------------------------
### AI & Chat Logic

### Function to extract keywords from a given text ignoring common stop words
def extract_keywords(text, top_n=5):
    print(f"Extracting keywords from text: {text}")
    
    ### Basic word extraction using regex
    words = re.findall(r'\b\w+\b', text.lower())
    ### Filter out stop words, short words, and digits
    filtered_words = [
        word for word in words 
        if word not in ENGLISH_STOP_WORDS 
        and len(word) > 2 
        and not word.isdigit()
    ]

    ### No words found
    word_counts = Counter(filtered_words)
    ### Get the most common words
    top_keywords = [word.capitalize() for word, count in word_counts.most_common(top_n)]

    print(f"Top keywords: {top_keywords}")
    return top_keywords

### Function to remove <think> tags from the input string (DeepSeek response)
def remove_thinking_tags(input_string):
    cleaned_string = re.sub(r'<think>.*?</think>', '', input_string, flags=re.DOTALL).strip()
    return cleaned_string

### Function to separate products from DeepSeek responce
def separate_numbered_suggestions(text):
    pattern = r"<PRODUCT>\s*-\s*(.*?)\s*-\s*(.*?)($|\n)"
    matches = re.findall(pattern, text)
    return [{"name": name.strip(), "description": desc.strip()} for name, desc, _ in matches]

### Function to get products suggestions from DeepSeek
def ask_deepseek(user_message, user_context=None, conversation_history=None):
    if conversation_history is None:
        conversation_history = []

    ### Terminal response
    print(f"🧠🧠🧠 ask_deepseek called | message: {user_message}")
    print(f"User context: {user_context}")
    print(f"Conversation history length: {len(conversation_history)}")
    print(f"Session: {session}")

    try:
        ### Prompt for the DeepSeek model
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
        ### Add context if available
        if user_context:
            if user_context.get("age"):
                ### Age of the user
                system_prompt += f" The user is {user_context['age']} years old."
            if user_context.get("gender"):
                ### gender of the user
                system_prompt += f" The user is a {user_context['gender']}."
            if user_context.get("country"):
                ### Country of the user
                system_prompt += f" The user is from {user_context['country']}."
            if user_context.get("keywords"):
                ### Keywords of the user
                system_prompt += f" The user's key concerns are: {', '.join(user_context['keywords'])}."

        ### Build LangChain message list
        messages = [SystemMessage(content=system_prompt)]
        ### Terminal output
        print (f"System prompt: {system_prompt}")
        print (f"Messages: {messages}")
        ### Add conversation history
        for msg in conversation_history:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "bot":
                messages.append(AIMessage(content=msg["content"]))

        ### Add new user message
        messages.append(HumanMessage(content=user_message))
        print(f"Messages: {messages}")

        ### Call the model
        response = deepseek_chat(messages)
        ### Terminal output response
        print(f"Response: {response.content}")
        ### Saving response variable with <think> tags removed
        bot_reply = remove_thinking_tags(response.content)
        print(f"Bot reply: {bot_reply}")
        ### Clean response with previous functions
        structured = separate_numbered_suggestions(bot_reply)
        print(f"Structured response: {structured}")
        ### Update history for next call
        conversation_history.append({"role": "user", "content": user_message})
        conversation_history.append({"role": "bot", "content": bot_reply})
        print (f"Conversation history updated: {conversation_history}")
        ### return row response and structured response
        return bot_reply, structured

    ### If the model fails to respond, log the error and return a default message
    except Exception as e:
        log_action(
            LogType.AI_RESPONSE_FAILED,
            f"AI response failed in conversation {session.get('conversation_id')}: {str(e)}",
            user_id=session.get("user_id")
        )        
        return "Sorry, I couldn't generate a response.", conversation_history

### Function to get user informations (age, gender, country)
def get_user_context(user_id, conversation_id=None):
    ### get user context from database
    print(f"Fetching user context for user_id: {user_id}, conversation_id: {conversation_id}")
    cursor = mysql.connection.cursor()
    ### Query
    cursor.execute("SELECT age, gender, country FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()

    context = {}
    ### If user is found, get the context
    if result:
        context = {
            "age": result[0],
            "gender": result[1],
            ### Get country name from the code using the function get_country_name(code)
            "country": get_country_name(result[2])
        }

    # get keywords from conversation if conversation_id is provided
    print(f"Fetching keywords for conversation_id: {conversation_id}")
    if conversation_id:
        ### Query
        cursor.execute("SELECT keywords FROM conversations WHERE conversation_id = %s", (conversation_id,))
        keyword_result = cursor.fetchone()
        if keyword_result and keyword_result[0]:
            context["keywords"] = [word.strip() for word in keyword_result[0].split(",")]
            print(f"Keywords found: {context['keywords']}")

    cursor.close()
    return context

###--------------------------------------------------------------------------
### Conversation Management

### Function to start a new conversation
def start_new_conversation(user_id, title="Untitled"):
    cursor = mysql.connection.cursor()
    ### Query to insert a new conversation in DB
    cursor.execute("""
        INSERT INTO conversations (user_id, title, created_at, keywords, is_active, last_activity_at)
        VALUES (%s, %s, NOW(), '', TRUE, NOW())
    """, (user_id, title))

    mysql.connection.commit()
    conversation_id = cursor.lastrowid
    cursor.close()
    session['conversation_id'] = conversation_id

    ### Emit event to frontend
    emit("conversation_initialized", {"conversation_id": conversation_id})
    log_action(
        LogType.CONVERSATION_STARTED,
        f"Conversation started with ID: {conversation_id}",
        user_id=user_id
    )
    return conversation_id

### Function to update conversation keywords
def update_conversation_keywords(conversation_id, new_keywords):
    cursor = mysql.connection.cursor()

    ### Query to get existing keywords
    cursor.execute("SELECT keywords FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    existing_keywords = set()

    ### If keywords are found, split them into a set
    if result and result[0]:
        existing_keywords = set(k.strip() for k in result[0].split(','))

    ### Union with new keywords
    combined_keywords = existing_keywords.union(set(new_keywords))
    ### Remove duplicates
    keyword_text = ", ".join(sorted(combined_keywords))

    ### Query update keywords
    cursor.execute("""
        UPDATE conversations SET keywords = %s WHERE conversation_id = %s
    """, (keyword_text, conversation_id))
    mysql.connection.commit()
    cursor.close()

### Function to update last activity timestamp
def update_last_activity(conversation_id):
    print(f"Updating last activity for conversation_id: {conversation_id}")
    cursor = mysql.connection.cursor()
    ### Query to update last activity timestamp
    cursor.execute("""
        UPDATE conversations SET last_activity_at = NOW() WHERE conversation_id = %s
    """, (conversation_id,))
    mysql.connection.commit()
    cursor.close()

### Function to check if a conversation has expired
def is_conversation_expired(conversation_id, minutes= 30):
    print(f"Checking if conversation_id: {conversation_id} is expired")
    cursor = mysql.connection.cursor()
    ### Query to get last activity timestamp
    cursor.execute("SELECT last_activity_at FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    print(f"Last activity result: {result}")
    cursor.close()
    if result and result[0]:
        last_active = result[0]
        ### If last activity is older than the specified time, return True
        if datetime.now(timezone.utc) - last_active.replace(tzinfo=timezone.utc) > timedelta(minutes=minutes):
            return True
    ### Else return False
    return False

### Function to end a conversation
def end_conversation(conversation_id):
    cursor = mysql.connection.cursor()
    ### Query to end the conversation
    cursor.execute("""
        UPDATE conversations SET is_active = 0 WHERE conversation_id = %s
    """, (conversation_id,))
    mysql.connection.commit()
    cursor.close()
    ### Log the action
    log_action(LogType.CONVERSATION_ENDED, f"Conversation {conversation_id} auto-ended (timeout)", user_id=session.get("user_id"))
    session.pop('conversation_id', None)

### Function to save a message in the database
def save_message(conversation_id, sender_type, content):
    ### If content is a list/tuple join into a single string
    if isinstance(content, (list, tuple)):
        ### Ensure all elements are strings and concatenate
        content = " ".join(map(str, content))

    cursor = mysql.connection.cursor()
    ### Query to insert a new message
    cursor.execute("""
        INSERT INTO messages (conversation_id, sender_type, content, sent_at)
        VALUES (%s, %s, %s, NOW())
    """, (conversation_id, sender_type, content))
    mysql.connection.commit()
    cursor.close()

### Function to get conversation history
def get_conversation_history(conversation_id):
    cursor = mysql.connection.cursor()
    ### Query to get conversation history
    cursor.execute("""
        SELECT sender_type, content
        FROM messages
        WHERE conversation_id = %s
        ORDER BY sent_at
    """, (conversation_id,))
    raw_history = cursor.fetchall()
    cursor.close()

    history = []
    ### Iterate through the raw history and format it
    for sender_type, content in raw_history:
        if sender_type == "user":
            history.append({"role": "user", "content": content})
        elif sender_type == "bot":
            history.append({"role": "bot", "content": content})
    return history

### Function to get the conversation status
def update_conversation_status(conversation_id, status):
    connection = get_db_connection()
    cursor = connection.cursor()

    ### Query to update the conversation status
    query = "UPDATE conversations SET is_active = %s WHERE conversation_id = %s"
    cursor.execute(query, (status, conversation_id))

    connection.commit()
    cursor.close()
    connection.close()

###----------------------------------------------------------------------------
### AI Title & Keywords Handling

### Auxiliary function to extract the title from the LLM output
def extract_title_from_llm_output(cleaned_text):
    ### Use regex to find the content inside <TITLE> tags
    match = re.search(r"<TITLE>(.*?)</TITLE>", cleaned_text, re.IGNORECASE | re.DOTALL)
    ### If a match is found, extract the title
    if match:
        title = match.group(1).strip()
        word_count = len(title.split())
        if 2 <= word_count <= 15:
            return title
        else:
            ### If the word count is too short print on terninal error message
            print(f"Invalid title word count ({word_count}): '{title}'")
    else:
        ### If tag <TITLE> is not found, print on terminal error message
        print("<TITLE> tag not found in LLM output.")
    return None

### Function to extract from the DB the keywords for a conversation
def get_keywords_for_conversation(conversation_id):
    cursor = mysql.connection.cursor()
    ### Query to get keywords for the conversation
    cursor.execute("SELECT keywords FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    cursor.close()

    ### If no keywords are found, return an empty list
    if not result or not result[0]:
        return []
    return [k.strip() for k in result[0].split(',') if k.strip()]

### Function that using keywords from the conversation generates a title (AI)
def generate_ai_title_from_keywords(conversation_id):
    ### Get keywords for the conversation using the function get_keywords_for_conversation
    keywords = get_keywords_for_conversation(conversation_id)
    ### If no keywords are found, return a default title
    if not keywords:
        return "Chat Session"
    ### If keywords are found, join them into a string separated ", "
    keyword_text = ", ".join(keywords)

    ### Prompt to generate a title
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
    ### User prompt with keywords
    user_prompt = f"Keywords: {keyword_text}"
    print(f"[🧠 PROMPT] {system_prompt}")
    
    try:
        ### Call the model with system and user prompts
        response = deepseek_chat([
            ### System message with the prompt
            SystemMessage(content=system_prompt),
            ### User message with the keywords
            HumanMessage(content=user_prompt)
        ])
        ### Terminal output response
        print(f"[🧠 RESPONSE - response.content:] {response.content}")

        ### Clean response with previous function
        bot_reply_title = remove_thinking_tags(response.content)
        print(f"[🧠 CLEANED bot_reply_title] {bot_reply_title}")
        ### Extract title from the cleaned response
        title = extract_title_from_llm_output(bot_reply_title)
        ### If title is not found, return a default title
        return title or f"{keyword_text}"
    
    ### If the model fails to respond, log the error and return a default title
    except Exception as e:
        ### Comsole output error message
        print(f"❌ AI title generation failed: {e}")
        return f"Chat Session: {keyword_text}"

### Function to update the conversation title in the database
def update_conversation_title(conversation_id, new_title):
    cursor = mysql.connection.cursor()

    ### Query to update the conversation title
    cursor.execute("""
        UPDATE conversations SET title = %s WHERE conversation_id = %s
    """, (new_title, conversation_id))
    mysql.connection.commit()
    cursor.close()

### Function that change title if it's too generic
def try_generate_title_if_needed(conversation_id):
    """
    If the current title is default (e.g., 'Chat Session', 'Untitled', etc.),
    and there are enough keywords, generate a new title using AI.
    """
    cursor = mysql.connection.cursor()
    
    ### Query to get the current title
    cursor.execute("SELECT title FROM conversations WHERE conversation_id = %s", (conversation_id,))
    result = cursor.fetchone()
    
    ### If no title is found return nothing 
    if not result:
        cursor.close()
        return  # No such conversation

    ### Clean current title
    current_title = result[0].strip().lower()
    ### List of different default titles
    default_titles = {"chat session", "untitled", "new chat after timeout"}

    ### If the current title is in the list of default titles generate a new title
    if current_title in default_titles:
        generated_title = generate_ai_title_from_keywords(conversation_id)
        ### If successfully generated a title, update the conversation title in the database
        if generated_title:
            update_conversation_title(conversation_id, generated_title)
            log_action(
                LogType.AI_TITLE_GENERATED,
                f"AI generated a title for conversation {conversation_id}: {generated_title}",
                user_id=session.get("user_id")
            )
            ### Terminal output
            print("✅ Title generated:", generated_title)

    cursor.close()

###------------------------------------------------------------------------
### Product Suggestions & Likes

### Function to save product suggestions in the database
def save_product_suggestions(user_id, conversation_id, message_id, structured_products):

    cursor = mysql.connection.cursor()

    ### for each product in the structured products insert into the database
    for product in structured_products:
        product_name = product.get("name")
        product_description = product.get("description")

        cursor.execute("""
            INSERT INTO product_suggestions (
                conversation_id, message_id, user_id,
                product_name, product_description
            ) VALUES (%s, %s, %s, %s, %s)
        """, (
            conversation_id, message_id, user_id,
            product_name, product_description
        ))

    mysql.connection.commit()
    ### Emit event to frontend
    log_action(
        LogType.PRODUCT_SUGGESTION_SAVED,
        f"{len(structured_products)} product(s) saved for conversation {conversation_id}.",
        user_id=user_id
    )
    cursor.close()

### Handles a real-time 'toggle_like' event from the client.
### Updates the 'liked' status of a product suggestion in the database,
### Logs the like/unlike action for the specified user.
@socketio.on("toggle_like")
def handle_toggle_like(data):
    ### Getting user id from the session
    user_id = data.get("user_id")
    ### Getting message id from the session
    message_id = data.get("message_id")
    ### Getting conversation id from the session
    conversation_id = data.get("conversation_id")
    ### Getting product name from the session
    product_name = data.get("product_name")
    ### Getting liked status from the session
    liked = data.get("liked")

    cursor = mysql.connection.cursor()

    ### Query to update the liked status of a product suggestion
    cursor.execute("""
        UPDATE product_suggestions
        SET liked = %s
        WHERE user_id = %s AND message_id = %s AND conversation_id = %s AND product_name = %s
        LIMIT 1
    """, (1 if liked else 0, user_id, message_id, conversation_id, product_name))
    mysql.connection.commit()
    cursor.close()

    ### Frontend "herat"
    if liked:
        log_action(LogType.PRODUCT_LIKED, f"User {user_id} liked product: {product_name}", user_id=user_id)
    else:
        log_action(LogType.PRODUCT_UNLIKED, f"User {user_id} unliked product: {product_name}", user_id=user_id)

###-------------------------------------------------------------------------
### SocketIO Events

### Handles a real-time 'session_check' event from the client.
@socketio.on("session_check")
### Function for checking the session
def handle_session_check():
    print("✅ WebSocket connection built.")
    print("📦 Session:")
    ### Print labels and values of the session
    for key, value in session.items():
        print(f"  {key}: {value}")

### Handles a real-time 'localstorage_sync' event from the client.
@socketio.on("localstorage_sync")
### Function for syncing localStorage data with the server
def handle_localstorage_sync(data):
    ### Getting data from the session and saving them in local variables
    key = data.get("key")
    value = data.get("value")
    action = data.get("action")
    user_id = session.get("user_id")

    ### Terminal output
    print(f"🛰️ localStorage sync from user_id {user_id} — {action.upper()} → {key} = {value}")

    ### Check if the key is "conversation_id" and if action is "set" or "remove"
    if key == "conversation_id":    
        ### If action is "set"
        if action == "set":
            ### Set the conversation_id in the session with "value" casted to int
            session["conversation_id"] = int(value)
            print(f"✅ conversation_id set in session from localStorage: {value}")
        ### If action is "remove"
        elif action == "remove":
            print(f"🧹 conversation_id removed from session due to localStorage removal. (previous value: {value})")
            ### Remove conversation_id from the session
            session.pop("conversation_id", None)

### Listens for incoming user messages sent via websocket
@socketio.on("user_message")
### Function that handles user messages
def handle_user_message(data):
    print(f"🟡 handle_user_message called with data: {data}")
    ### Saving cleaned user message in user_text
    user_text = data.get("content", "").strip()
    ### Saveing user_id from the session
    user_id = session.get("user_id")
    
    ### If user_id is not found, emit an info message to the frontend
    if not user_id:
        emit("info_message", {"content": "User session not found. Please log in again."})
        return

    ### If user_id is not empty save conversation_id from the session variable
    conversation_id = session.get("conversation_id")

    ### If there's no conversation ID in the session, start a new one
    if not conversation_id:
        conversation_id = start_new_conversation(user_id, title="Chat Session")

    else:
        ### Check if the conversation has expired (30 minutes of inactivity)
        if is_conversation_expired(conversation_id, minutes=30):
            ### Closing the conversation
            end_conversation(conversation_id)
            ### Saving log
            log_action(
                LogType.CONVERSATION_TIMEOUT,
                f"Conversation {conversation_id} expired and was ended due to inactivity.",
                user_id=user_id
            )            
            conversation_id = start_new_conversation(user_id, title="New Chat After Timeout")
            emit("info_message", {"content": "Your chat session has expired. A new conversation has been started."})

    ### Update session with the valid conversation_id
    session["conversation_id"] = conversation_id

    ### Save user's message to the database
    save_message(conversation_id, 'user', user_text)

    ### Extract conversation keywords
    new_keywords = extract_keywords(user_text)
    ### Update conversation keywords in the database
    update_conversation_keywords(conversation_id, new_keywords)
    ### Save log for keywords extraction
    log_action(
        LogType.AI_KEYWORDS_EXTRACTED,
        f"Keywords extracted from message in conversation {conversation_id}: {', '.join(new_keywords)}",
        user_id=user_id
    )

    ### Update last activity timestamp for session timeout tracking
    update_last_activity(conversation_id)

    ### Fetch user context (age, gender, country, keywords, etc.)
    user_context = get_user_context(user_id, conversation_id)

    ### Get AI assistant's response based on conversation history and user context
    conversation_history = get_conversation_history(conversation_id)
    bot_reply, structured = ask_deepseek(user_text, user_context, conversation_history)

    ### Save bot's reply to the database
    save_message(conversation_id, 'bot', bot_reply)

    cursor = mysql.connection.cursor()
    ### Query to get the last inserted message ID
    cursor.execute("SELECT LAST_INSERT_ID()")
    message_id = cursor.fetchone()[0]
    cursor.close()    

    ### Save log for bot's reply
    log_action(
        LogType.AI_REPLY_GENERATED,
        f"AI generated a reply in conversation {conversation_id}. Message ID: {message_id}",
        user_id=user_id
    )

    ### Send bot's reply to frontend in real-time
    if structured:
        ### Save product suggestions to the database
        save_product_suggestions(user_id, conversation_id, message_id, structured)
        ### Generate a title if needed
        try_generate_title_if_needed(conversation_id)
        ### Send structured product suggestions to the frontend
        emit("bot_reply", {
            "products": structured,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id
        })
    else:
        ### Sends plain text response if there are no structured suggestions
        emit("bot_reply", {
            "content": bot_reply,
            "message_id": message_id,
            "conversation_id": conversation_id,
            "user_id": user_id
        })

###------------------------------------------------------------------------
### Category Matching & Resolution

### Function to resolve category ID from a given path
def resolve_category_id_from_path(path):
    ### Terminal output
    print(f"🔍 Resolving category ID from path: {path}")
    ### If path is empty or None, print a warning and return None
    if not path:
        ### Terminal output
        print("⚠️ No path provided.")
        return None

    ### Split the path by ">" and strip whitespace
    parts = [p.strip() for p in path.split(">")]
    cursor = mysql.connection.cursor()
    ### Set the initial parent_id to None
    current_parent_id = None

    ### Iterate through each part of the path in parts
    for part in parts:
        ### Terminal output
        print(f"➡️ Searching for category: {part} (parent_id={current_parent_id})")
        ### Query to find the category ID based on name and parent_id
        cursor.execute("""
            SELECT id FROM categories
            WHERE name = %s AND (parent_id = %s OR (%s IS NULL AND parent_id IS NULL))
        """, (part, current_parent_id, current_parent_id))
        ### save the result of the query
        result = cursor.fetchone()
        ### If a category is found, update the current_parent_id
        if result:
            current_parent_id = result[0]
            print(f"✔️ Found category ID: {current_parent_id}")
        ### If no category is found, print an error message on terminal and return None
        else:
            print(f"❌ Category not found for: {part}")
            cursor.close()
            return None

    cursor.close()
    ### Terminal output category ID
    print(f"🏁 Final category ID: {current_parent_id}")
    return current_parent_id

### Function to get the full category path from the database
def get_deep_category_path(product_name, product_description):
    ### Terminal output
    print("🚀 Starting step-by-step category path resolution")

    cursor = mysql.connection.cursor()
    ### Query to get id and name of the categories where parent_id is NULL
    cursor.execute("SELECT id, name FROM categories WHERE parent_id IS NULL")
    level_categories = cursor.fetchall()

    path = []
    parent_id = None
    ### Loop until there are no more categories to check
    while level_categories:
        print(f"🔎 Searching among {len(level_categories)} categories at level {len(path) + 1}")
        ### Saving options
        options = [name for _, name in level_categories]
        ### Prompt for the AI model
        system_prompt = f"""
        You are a product categorization assistant.

        Given a product name and description, and a list of category options at a specific level,
        choose the most appropriate category.

        Product Name: {product_name}
        Description: {product_description}

        Categories:
        {json.dumps(options, indent=2)}

        ❗Only return ONE category name from the list above that best fits. Do NOT explain.
        """

        try:
            ### Call the model with system and user prompts
            response = deepseek_chat([
                SystemMessage(content=system_prompt),
                HumanMessage(content="Select the best fitting category from the list.")
            ])
            ### Clean the output from <think> tags
            cleaned_category = remove_thinking_tags(response.content)
            chosen_category = cleaned_category.strip()
            print(f"✅ AI selected: {repr(chosen_category)}")
        ### Manage exceptions
        except Exception as e:
            print("❌ Error during AI selection:", e)
            ### Stop the loop
            break

        # Fetch selected category ID
        cursor.execute("""
            SELECT id FROM categories
            WHERE name = %s AND (parent_id = %s OR (%s IS NULL AND parent_id IS NULL))
        """, (chosen_category, parent_id, parent_id))
        ### Save thw result of the query
        result = cursor.fetchone()
        ### If result of the query is empty, print an error message and break the loop
        if not result:
            print(f"❌ Category '{chosen_category}' not found in DB.")
            break

        ### Saving category ID
        category_id = result[0]
        ### Add chosen category to the path
        path.append(chosen_category)
        ### Set parent_id to the current category ID
        parent_id = category_id

        ### Fetch children for next loop
        cursor.execute("SELECT id, name FROM categories WHERE parent_id = %s", (parent_id,))
        ### Save the result of the query
        level_categories = cursor.fetchall()

    cursor.close()

    ### If path is found add it to the full path
    if path:
        full_path = " > ".join(path)
        ### Terminal output
        print(f"🏁 Final path: {full_path}")
        return full_path
    ### If path is empty, print a warning message and return None
    else:
        print("⚠️ No category path could be determined.")
        return None

### Function to get the category path by ID
def get_category_path_by_id(category_id):
    ### Initialize an empty list for the path
    path = []
    cursor = mysql.connection.cursor()
    ### Loop until there are no more parent categories
    while category_id:
        cursor.execute("SELECT name, parent_id FROM categories WHERE id = %s", (category_id,))
        result = cursor.fetchone()
        if result:
            name, parent_id = result
            path.insert(0, name)
            category_id = parent_id
        else:
            ### if no result is found break the loop
            break
    cursor.close()
    return " > ".join(path) if path else None

### Function to get the full path of a category by ID
def get_category_full_path(cat_id, cursor, cache={}):
    ### If the path for this category ID is already computed return it from cache
    if cat_id in cache:
        return cache[cat_id]
    
    ### Query to get the name and parent_id of the category
    cursor.execute("SELECT name, parent_id FROM categories WHERE id = %s", (cat_id,))
    row = cursor.fetchone()
    ### If no row is found, return an empty string
    if not row:
        return ""

    ### If row is found, unpack the name and parent_id
    name, parent_id = row
    ### If parent_id is not None, recursively get the full path of the parent category
    if parent_id:
        parent_path = get_category_full_path(parent_id, cursor, cache)
        full_path = f"{parent_path} > {name}"
    ### If parent_id is None, the full path is just the name
    else:
        full_path = name
    ### Save the computed path in the cache
    cache[cat_id] = full_path

    return full_path

###------------------------------------------------------------------------
### Routes

### 1.General Pages & Home

### Route fierstpage
@app.route('/firstpage')
### Function called when firstpage is requested
def firstpage():
    return render_template('firstpage.html')

### Route index
@app.route('/')
### Function called when index is requested
def index():
    ### When user not authenticated, redirect to firstpage page
    if 'user_id' not in session:
        return render_template("firstpage.html")

    ### Saving session variables in local variables
    user_id = session.get('user_id')
    username = session.get('username')
    fullname = session.get("name", "Guest") + " " + session.get("surname", "")

    conn = get_db_connection()
    cursor = conn.cursor()
    ### Query to get the conversations for the user
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

    ### return template index.html with the user information and conversations
    return render_template(
        'index.html',
        user_id=user_id,
        username=username,
        fullname=fullname,
        conversations=conversations,
        messages=[],  # chatbox empty start
        active_conversation_id=None
    )

### DEBUG
### Route /temp
@app.route('/temp', methods=['GET', 'POST'])
### Function called when temp is requested
def temp():
    return render_template('temp.html')

### Route testdb
@app.route('/testdb')
### Function called when testdb is requested DEBUG
def testdb():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT VERSION()")
        data = cur.fetchone()
        return f"MySQL Version: {data[0]}"
    except Exception as e:
        return f"Database Connection Error: {str(e)}"

###-------------------------------------------------
### 2.Chat & Conversation Management

### Route for conversation
@app.route('/conversation/<int:conversation_id>')
### Function called when conversation is requested
def view_conversation(conversation_id):
    ### Save user_id from the session in local variable
    user_id = session.get("user_id")
    ### if user_id is not found in the session varibles redirect to login page
    if not user_id:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    ### Query to get the conversation information
    cursor.execute("""
        SELECT title, created_at FROM conversations
        WHERE conversation_id = %s AND user_id = %s
    """, (conversation_id, user_id))
    ### Saving result of the query in convo_info
    convo_info = cursor.fetchone()
    ### If no conversation is found, redirect to index page
    if not convo_info:
        conn.close()
        return redirect(url_for("index"))

    ### Unpacking the conversation information in local variables
    title, created_at = convo_info

    ### Update log
    log_action(
        LogType.CONVERSATION_RESTORED,
        f"Conversation {conversation_id} restored by user.",
        user_id=user_id
    )
    ### Query to get the messages for the conversation
    cursor.execute("""
        SELECT message_id, sender_type, content, sent_at
        FROM messages
        WHERE conversation_id = %s
        ORDER BY sent_at ASC
    """, (conversation_id,))
    ### Saving result of the query in raw_messages
    raw_messages = cursor.fetchall()

    ### Init empty list for messages
    messages = []
    ### For each element in raw_messages
    for row in raw_messages:
        ### Unpacking the row in local variables
        message_id, sender_type, content, sent_at = row
        ###
        msg_dict = {
            ### Unique message ID
            "message_id": message_id,
            ### Message sender type (user or bot)
            "sender_type": sender_type,
            ### Message content
            "content": content,
            ### Message sent timestamp
            "sent_at": sent_at.strftime("%d.%m.%Y %H:%M"),
        }

        ### If the message is from the bot
        if "<PRODUCT>" in content and sender_type == "bot":
            ### Query to get the product suggestions for the message
            cursor.execute("""
                SELECT product_name, product_description, liked
                FROM product_suggestions
                WHERE conversation_id = %s AND message_id = %s AND user_id = %s
            """, (conversation_id, message_id, user_id))
            ### Fetch product from the database
            product_rows = cursor.fetchall()
            ### Init empty list for products
            products = []
            ### for each product in the product_rows
            for p in product_rows:
                ### Add the product to the list "products"
                products.append({
                    "name": p[0],
                    "description": p[1],
                    "liked": bool(p[2])
                })
            ### Add the products to the message dictionary
            msg_dict["products"] = products
        ### Add the fully built message dictionary to the messages list
        messages.append(msg_dict)
    ### Query to get the conversations for the user
    cursor.execute("""
        SELECT conversation_id, title, created_at
        FROM conversations
        WHERE user_id = %s
        ORDER BY last_activity_at DESC
    """, (user_id,))
    ### Unpacking the result of the query in local variables
    raw_conversations = cursor.fetchall()
    conversations = [
        {
            ### Unique conversation ID
            "conversation_id": row[0],
            ### Conversation title
            "title": row[1],
            ### Timestamp of the conversation creation
            "created_at": row[2].strftime("%d %B %Y %H:%M")
        }
        ### Build a list of dictionaries from the raw query result
        for row in raw_conversations
    ]

    conn.close()
    ### Render the template with user info ant the conversation
    return render_template(
        "index.html",
        fullname=session.get("name", "Guest") + " " + session.get("surname", ""),
        conversations=conversations,
        messages=messages,
        active_conversation_id=conversation_id,
        active_title=title,
        active_created_at=created_at.strftime("%d %B %Y %H:%M")
    )

### Route for endig the conversation
@app.route('/end_chat', methods=['POST'])
### Function called when end_chat is requested
def end_chat():
    print("Ending chat backend started") 
    
    ### Get conversation_id from form (POST)
    form_conversation_id = request.form.get("conversation_id")
    print(f"Form conversation_id: {form_conversation_id}")
    ### If form_conversation_id is found
    if form_conversation_id:
        ### Try to cast it to int
        try:
            conversation_id = int(form_conversation_id)
        except ValueError:
            ### If casting fails, get conversation_id from session
            conversation_id = session.get('conversation_id')
    ### If form_conversation_id is not found
    else:
        ### Get conversation_id from session
        conversation_id = session.get('conversation_id')

    print(f"Ending conversation: {conversation_id}")
    ### If conversation_id is not found, redirect to index
    if not conversation_id:
        return redirect(url_for('index'))
    ### Try 
    try:
        update_conversation_status(conversation_id, 0)
        save_message(conversation_id, 'bot', 'Conversation ended.')
        log_action(
            LogType.CONVERSATION_ENDED,
            f"Conversation ended with ID: {conversation_id}",
            user_id=session.get("user_id")
        )
        final_title = generate_ai_title_from_keywords(conversation_id)
        print("Generated Title:", final_title)
        update_conversation_title(conversation_id, final_title)        
        
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error ending conversation: {e}")
        return redirect(url_for('404'))

### 3.Favourites & Product Detail

@app.route('/favourites')
def favourites():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor()

    cursor.execute("""
        SELECT ps.id, ps.product_name, ps.product_description, 
               c.title AS conversation_title, c.created_at,
               m.sent_at, c.conversation_id
        FROM product_suggestions ps
        JOIN conversations c ON ps.conversation_id = c.conversation_id
        JOIN messages m ON ps.message_id = m.message_id
        WHERE ps.user_id = %s AND ps.liked = 1
        ORDER BY c.created_at DESC, m.sent_at DESC
    """, (user_id,))

    rows = cursor.fetchall()
    cursor.close()

    grouped_products = defaultdict(lambda: {
        "title": "",
        "created_at": "",
        "products": []
    })

    for row in rows:
        product_id = row[0]
        product_name = row[1]
        product_description = row[2]
        conversation_title = row[3]
        conversation_created_at = row[4].strftime("%d %B %Y %H:%M")
        message_sent_at = row[5].strftime("%d %B %Y %H:%M")
        conversation_id = row[6]

        grouped_products[conversation_id]["title"] = conversation_title
        grouped_products[conversation_id]["created_at"] = conversation_created_at
        grouped_products[conversation_id]["products"].append({
            "product_id": product_id,
            "name": product_name,
            "description": product_description,
            "sent_at": message_sent_at
        })

    return render_template("favourites.html", grouped_products=grouped_products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT ps.product_name, ps.product_description, c.title, m.sent_at, 
               ps.category_id, cat.name AS category_name
        FROM product_suggestions ps
        JOIN conversations c ON ps.conversation_id = c.conversation_id
        JOIN messages m ON ps.message_id = m.message_id
        LEFT JOIN categories cat ON ps.category_id = cat.id
        WHERE ps.id = %s AND ps.user_id = %s
    """, (product_id, user_id))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return "Product not found", 404

    product = {
        "name": row[0],
        "description": row[1],
        "conversation_title": row[2],
        "sent_at": row[3].strftime("%d %B %Y %H:%M"),
        "category_id": row[4],
        "category_name": row[5]
    }

    log_action(
        LogType.PRODUCT_VIEWED,
        f"User viewed product: {product['name']}",
        user_id=user_id
    )
    google_url = get_google_shopping_url(product["name"], product.get("category_name"))
    category_path = get_category_path_by_id(product["category_id"]) if product["category_id"] else None
    return render_template("product_detail.html", product=product, product_id=product_id, google_url=google_url,category_path=category_path)

### 4.Conversation Title Management

@app.route("/generate_title/<int:conversation_id>", methods=["POST"])
def generate_title(conversation_id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    title = generate_ai_title_from_keywords(conversation_id)
    update_conversation_title(conversation_id, title)
    log_action(
        LogType.CONVERSATION_TITLE_EDITED,
        f"Title updated for conversation {conversation_id}: {title}",
        user_id=user_id
    )
    return redirect(url_for("view_conversation", conversation_id=conversation_id))

### 5.Category Management

@app.route("/api/categories/tree")
def get_category_tree():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, name, parent_id FROM categories")
    rows = cursor.fetchall()
    cursor.close()

    categories = [{"id": r[0], "name": r[1], "parent_id": r[2]} for r in rows]

    # id -> category map
    category_map = {cat["id"]: {**cat, "children": []} for cat in categories}
    root_categories = []

    for cat in categories:
        if cat["parent_id"] is None:
            root_categories.append(category_map[cat["id"]])
        else:
            parent = category_map.get(cat["parent_id"])
            if parent:
                parent["children"].append(category_map[cat["id"]])

    return jsonify(root_categories)

@app.route('/assign-category/<int:product_id>', methods=['POST'])
def assign_category_from_detail(product_id):
    print(f"🧾 Assigning category from detail page for product {product_id}")

    if 'user_id' not in session:
        print("⛔ Unauthorized access attempt.")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT product_name, product_description
        FROM product_suggestions
        WHERE id = %s AND user_id = %s
    """, (product_id, session["user_id"]))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        print("❌ Product not found in DB.")
        return "Product not found", 404

    product_name, product_description = row
    print(f"📦 Product: {product_name}")

    # 🧠 Step-by-step AI prediction
    path = get_deep_category_path(product_name, product_description)
    print("📌 Predicted Path:", path)

    # 🆔 Resolve the final category ID
    category_id = resolve_category_id_from_path(path)

    if category_id:
        print(f"💾 Updating product_suggestions with category_id={category_id}")
        cursor = mysql.connection.cursor()
        cursor.execute("""
            UPDATE product_suggestions SET category_id = %s WHERE id = %s
        """, (category_id, product_id))
        mysql.connection.commit()
        cursor.close()

        log_action(
            LogType.CATEGORY_PREDICTED,
            f"Auto-assigned category {category_id} to product '{product_name}' via product detail page.",
            user_id=session.get("user_id")
        )
        print("✅ Category assignment successful.")
    else:
        log_action(
            LogType.CATEGORY_ASSIGNMENT_FAILED,
            f"Failed to assign category to product '{product_name}' (ID: {product_id}). Path: {path}",
            user_id=session.get("user_id")
        )

    return redirect(url_for("product_detail", product_id=product_id))

@app.route("/categories")
def show_categories():
    return render_template("category_tree.html")

@app.route('/product/<int:product_id>/manual-category', methods=['GET', 'POST'])
def manual_category_assign(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()

    # Fetch the product name and current category_id
    cursor.execute("""
        SELECT product_name, category_id FROM product_suggestions
        WHERE id = %s AND user_id = %s
    """, (product_id, session['user_id']))
    row = cursor.fetchone()

    if not row:
        cursor.close()
        return "Product not found or unauthorized", 404

    product_name = row[0]
    current_category_id = row[1]

    # Retrieve all category IDs
    cursor.execute("SELECT id FROM categories")
    category_ids = [r[0] for r in cursor.fetchall()]

    # Build full path for each category ID
    categories = []
    for cat_id in category_ids:
        path = get_category_full_path(cat_id, cursor)
        categories.append((cat_id, path))

    # Sort categories alphabetically by path
    categories.sort(key=lambda x: x[1])

    # If form is submitted
    if request.method == 'POST':
        selected_id = request.form.get('category_id')
        if selected_id:
            cursor.execute("""
                UPDATE product_suggestions
                SET category_id = %s
                WHERE id = %s
            """, (selected_id, product_id))
            mysql.connection.commit()
            log_action(
                LogType.PRODUCT_CATEGORY_ASSIGNED_MANUAL,
                f"Manually assigned category {selected_id} to product ID {product_id}.",
                user_id=session.get("user_id")
            )            
            cursor.close()
            return redirect(url_for('product_detail', product_id=product_id))

    cursor.close()

    # Render the manual category assignment page
    return render_template(
        "manual_category.html",
        product_id=product_id,
        product_name=product_name,
        categories=categories,
        selected_id=current_category_id
    )

### 6.User Registration & Authentication

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
            session['is_admin'] = (user[1].lower() == "admin")
            session.permanent = True
            log_action(LogType.USER_LOGGED_IN, f"User logged in: {username}", user_id=user[0])
            return redirect(url_for('index'))
        else:
            log_action(LogType.LOGIN_FAILED, f"Login failed for username: {username}")
            error_message = "Invalid username or password."

    return render_template('login.html', form=form, error=error_message)
 
@app.route('/login/google', methods=['POST'])
def google_login():
    print("🔵 /login/google endpoint called")

    try:
        token = request.json.get('token')

        id_info = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            GOOGLE_CLIENT_ID
        )
        print("✅ Google ID token verified")

        email = id_info.get('email')
        first_name = id_info.get('given_name', '')
        last_name = id_info.get('family_name', '')

        print("📧 Email:", email)
        print("👤 First Name:", first_name, " | Last Name:", last_name)

        if not first_name or not last_name:
            full_name = id_info.get('name', '')
            name_parts = full_name.split(' ', 1)
            first_name = first_name or name_parts[0]
            last_name = last_name or (name_parts[1] if len(name_parts) > 1 else '')
            print("🔁 Fallback name parts used")

        # Use a consistent connection object
        conn = mysql.connection
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute("SELECT id, username, name, surname FROM users WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        print("🔍 Existing user:", existing_user)

        if existing_user:
            print("✅ User exists. Creating session...")
            session['user_id'] = existing_user[0]
            session['username'] = existing_user[1]
            session['name'] = existing_user[2]
            session['surname'] = existing_user[3]
        else:
            print("🆕 New user. Creating username...")
            base_username = email.split('@')[0]
            username = base_username
            counter = 1

            while True:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if not cursor.fetchone():
                    break
                username = f"{base_username}{counter}"
                counter += 1

            print("✅ Username finalized:", username)

            cursor.execute("""
                INSERT INTO users (name, surname, username, email, country, age, gender)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (first_name, last_name, username, email, None, None, None))

            print("📝 Insert executed. rowcount:", cursor.rowcount)

            conn.commit()
            print("💾 Commit complete.")

            try:
                send_email_from_template("GOOGLE_LOGIN", email, {"username": username})
                print("📧 Welcome email sent")
            except Exception as e:
                print("⚠️ Email send error:", e)

            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            new_user = cursor.fetchone()
            print("🆔 New user ID fetched:", new_user)

            if not new_user:
                print("❌ User insert failed!")
                return jsonify({'error': 'User insert failed'}), 500

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
        print("✅ Google login completed successfully")
        return jsonify({'redirect': url_for('index')})

    except ValueError:
        print("❌ Invalid Google ID token")
        return jsonify({'error': 'Invalid Google ID token'}), 400

    except Exception as e:
        print(f"❌ Google OAuth Error: {str(e)}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/logout')
def logout():
    log_action(LogType.USER_LOGGED_OUT, f"User logged out: {session.get('username', 'unknown')}", user_id=session.get('user_id'))
    session.pop('user_id', None)  
    session.pop('username', None) 
    session.pop('name', None) 
    session.pop('surname', None)
    session.pop('is_google_user', None)
    session.pop('is_admin', None)
    return render_template('firstpage.html')

### 7.Profile Management

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

### 8.Password Reset

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

            try:
                token = s.dumps(email, salt='email-reset')
                reset_url = url_for('reset_password', token=token, _external=True)
                send_email_from_template("RESETPASSWORD", email, {"reset_url": reset_url})
                log_action(LogType.PASSWORD_RESET_LINK_SENT, f"Password reset link sent to: {email}", user_id=user_id)
                message = "A password reset link has been sent to your email."
            except Exception as e:
                log_action(LogType.PASSWORD_RESET_FAILED, f"Password reset failed for email: {email}. Error: {str(e)}", user_id=user_id)
                message = "An error occurred while sending the password reset link. Please try again later."

        else:
            message = "If this email is registered, a reset link has been sent."

    return render_template('forgot_password.html', form=form, message=message)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='email-reset', max_age=3600)  # 1 hour
    except SignatureExpired:
        log_action(LogType.TOKEN_INVALID, "Password reset token expired.")
        return "The reset link has expired.", 403
    except BadSignature:
        log_action(LogType.TOKEN_INVALID, "Invalid or tampered password reset token.")
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

### 9.Contact / Help

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


### 10.Logging & Admin Monitoring

@app.route('/logs')
def view_logs():
    user_id = session.get("user_id")
    is_admin = session.get("is_admin")

    cursor = mysql.connection.cursor()

    if is_admin:
        cursor.execute("""
            SELECT 
                al.id,
                al.user_id,
                al.message,
                al.timestamp,
                lt.log_name,
                lt.isActive
            FROM 
                app_logs al
            JOIN 
                log_types lt ON al.log_type_id = lt.log_type_id
            ORDER BY 
                al.timestamp DESC;
        """)
    else:
        cursor.execute("""
            SELECT 
                al.id,
                al.user_id,
                al.message,
                al.timestamp,
                lt.log_name,
                lt.isActive
            FROM 
                app_logs al
            JOIN 
                log_types lt ON al.log_type_id = lt.log_type_id
            WHERE
                al.user_id = %s
            ORDER BY 
                al.timestamp DESC;
        """, (user_id,))

    logs = cursor.fetchall()
    cursor.close()

    columns = ['id', 'user_id', 'message', 'timestamp', 'log_name', 'isActive']
    return render_template("logs.html", logs=[dict(zip(columns, row)) for row in logs])


@app.route("/email-logs")
def email_logs():
    user_id = session.get("user_id")
    is_admin = session.get("is_admin")

    cursor = mysql.connection.cursor()

    if is_admin:
        cursor.execute("""
            SELECT 
                id,
                template_name,
                recipient_email,
                subject,
                body,
                status,
                error_message,
                sent_at
            FROM email_logs
            ORDER BY sent_at DESC
        """)
    else:
        cursor.execute("SELECT email FROM users WHERE id = %s", (user_id,))
        user_email = cursor.fetchone()

        if not user_email:
            cursor.close()
            return "User email not found", 404
        
        cursor.execute("""
            SELECT 
                id,
                template_name,
                recipient_email,
                subject,
                body,
                status,
                error_message,
                sent_at
            FROM email_logs
            WHERE recipient_email = %s
            ORDER BY sent_at DESC
        """, (user_email[0],))

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    cursor.close()

    logs = [dict(zip(columns, row)) for row in rows]
    return render_template("email_logs.html", logs=logs)



### M.Main Entry Point

if __name__ == '__main__':
    app.run(debug=True)
    
