from flask import Flask, render_template, redirect, url_for, session, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, ValidationError
import bcrypt
from flask_mysqldb import MySQL
from ignore.secret import secretpw
import os
from dotenv import load_dotenv
from datetime import timedelta
import json
import smtplib
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from jinja2 import Template
from datetime import datetime
from log_types import LogType

app = Flask(__name__)
load_dotenv()

app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['MYSQL_HOST'] = 'localhost'  # host address of the database
app.config['MYSQL_USER'] = 'root'  # username of the database
app.config['MYSQL_PASSWORD'] = secretpw()  # password of the database
app.config['MYSQL_DB'] = 'productadvice'  # database name
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # session timeout

mysql = MySQL(app)

def load_countries():
    with open("static/countries.json", "r", encoding="utf-8") as file:
        return json.load(file)
    
countries = load_countries()

# Token serializer
s = URLSafeTimedSerializer(app.secret_key)

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
    country = SelectField('Country', choices=[(c["code"], c["name"]) for c in countries], validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], validators=[DataRequired()])
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
    country = SelectField('Country', choices=[(c["code"], c["name"]) for c in countries], validators=[DataRequired()])
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
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
        return redirect(url_for('login'))
    else:
        user_id = session.get('user_id', None)
        username = session.get('username', None)
        fullname = session.get("name", "Guest") + " "+session.get("surname", "")
    return render_template('index.html', user_id=user_id, username=username, fullname=fullname)

@app.route('/register', methods=['GET', 'POST'])
def register():
    session.pop('user_id', None)  
    session.pop('username', None)
    session.pop('name', None)  
    session.pop('surname', None)
    form = RegistrationForm()
    form.submit.label.text = "Sign Up"

    if form.validate_on_submit():
        name = form.name.data
        surname = form.surname.data
        username = form.username.data
        email = form.email.data
        password = form.password.data
        country = form.country.data
        age = form.age.data
        gender = form.gender.data

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
            session.permanent = True
            log_action(LogType.USER_LOGGED_IN, f"User logged in: {username}", user_id=user[0])
            return redirect(url_for('index'))
        else:
            log_action(LogType.LOGIN_FAILED, f"Login failed for username: {username}")
            error_message = "Invalid username or password."

    return render_template('login.html', form=form, error=error_message)


def get_country_name(country_code):
    countries = load_countries()  
    country_dict = {item["code"]: item["name"] for item in countries}
    return country_dict.get(country_code, country_code) 

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
    user[5] = user[5].capitalize()
    return render_template('profile.html', user=user)


@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    form = EditProfileForm()

    cursor = mysql.connection.cursor()

    if request.method == 'GET':
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
        country = form.country.data
        age = form.age.data
        gender = form.gender.data

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
        cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()

        if user:
            user_id = user[0]
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
        email = s.loads(token, salt='email-reset', max_age=3600) # 1 hour
    except SignatureExpired:
        return "The reset link has expired.", 403
    except BadSignature:
        return "Invalid or tampered link.", 403

    form = ResetPasswordForm()
    if form.validate_on_submit():
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            return render_template('reset_password.html', form=form, error="Passwords do not match.")

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE users SET password = %s WHERE email = %s", (hashed_password, email))
        mysql.connection.commit()

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, username, name, surname FROM users WHERE email = %s", (email,))
        user_data = cursor.fetchone()
        cursor.close()

        if user_data:
            # Unpack user data
            user_id, username, name, surname = user_data

            # Create session
            session['user_id'] = user_id
            session['username'] = username
            session['name'] = name
            session['surname'] = surname
            session.permanent = True

            # Send email to confirm password change
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
    return redirect(url_for('login'))

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
    
