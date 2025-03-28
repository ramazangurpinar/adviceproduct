from flask import Flask, flash, render_template, redirect, url_for, session, request, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Length, ValidationError, Optional
import bcrypt
from flask_mysqldb import MySQL
import os
from dotenv import load_dotenv
from datetime import timedelta
import json
import smtplib
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from jinja2 import Template
from deepseek_chat_api import chat
from log_types import LogType
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests


app = Flask(__name__)
load_dotenv()

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['MYSQL_HOST'] = 'localhost'  # host address of the database
app.config['MYSQL_USER'] = 'root'  # username of the database
app.config['MYSQL_PASSWORD'] = os.getenv("MYSQL_PASSWORD")  # password of the database
app.config['MYSQL_DB'] = 'productadvice'  # database name
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # session timeout

mysql = MySQL(app)

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
    """Ensure the MySQL connection is active before using it."""
    if mysql.connection.open:
        return mysql.connection
    else:
        mysql.connection.ping(reconnect=True)
        return mysql.connection


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
    else:
        user_id = session.get('user_id', None)
        username = session.get('username', None)
        fullname = session.get("name", "Guest") + " "+session.get("surname", "")
    return render_template('index.html', user_id=user_id, username=username, fullname=fullname)

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
        else:
            flash("Your message could not be sent. Please try again later.", "danger")

    return render_template('contact.html', form=form)

@app.route('/contact-success')
def contact_success():
    return render_template('contact_success.html')

@app.route('/chat', methods=['POST'])
def chat_route():
    user_id = session.get('user_id', None)
    data = request.get_json()
    user_message = data.get('message')

    if user_message:

        bot_response, title = chat(user_message)
        cur = mysql.connection.cursor()

        # Insert conversation in DB
        cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s)", (user_id, title))
        # Get the conversation id
        conversation_id = cur.lastrowid
        # User
        cur.execute("INSERT INTO messages (conversation_id, sender_type, content, sent_at) VALUES (%s, %s, %s, NOW())",(conversation_id, "user", user_message))
        
        # Bot
        for i in bot_response:
            cur.execute("INSERT INTO messages (conversation_id, sender_type, content, sent_at) VALUES (%s, %s, %s, NOW())",(conversation_id, "bot", i))
        
        mysql.connection.commit()
        return jsonify({'response': bot_response})

    return jsonify({'error': 'No message received'}), 400

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
    
