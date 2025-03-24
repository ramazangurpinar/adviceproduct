from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length, ValidationError, Email
from flask_dance.contrib.google import make_google_blueprint, google
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
import os
import json
from dotenv import load_dotenv
from datetime import timedelta

# Load environment variables
load_dotenv()

app = Flask(__name__)

# 🔹 Secret Key for Sessions
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')

# 🔹 MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD', 'yourpassword')
app.config['MYSQL_DB'] = 'productadvice'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# 🔹 Google OAuth Blueprint
google_bp = make_google_blueprint(
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    redirect_to="google_login"
)

app.register_blueprint(google_bp, url_prefix="/login")

# Load Countries for Forms
def load_countries():
    with open("static/countries.json", "r", encoding="utf-8") as file:
        return json.load(file)

countries = load_countries()

# Custom Validators
def username_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (field.data,))
    if cursor.fetchone():
        cursor.close()
        raise ValidationError('This username is already taken.')
    cursor.close()

def email_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (field.data,))
    if cursor.fetchone():
        cursor.close()
        raise ValidationError('This email is already registered.')
    cursor.close()

# Forms
class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50), username_exists])
    email = StringField('Email', validators=[DataRequired(), Email(), email_exists])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    country = SelectField('Country', choices=[(c["code"], c["name"]) for c in countries], validators=[DataRequired()])
    age = IntegerField('Age', validators=[DataRequired()])
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')], validators=[DataRequired()])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Login')

# Home Page
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', fullname=session.get("name", "Guest") + " " + session.get("surname", ""))

# Registration Route
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        cursor = mysql.connection.cursor()
        try:
            cursor.execute("""
                INSERT INTO users (name, surname, username, email, password, country, age, gender) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (form.name.data, form.surname.data, form.username.data, form.email.data, hashed_password, form.country.data, form.age.data, form.gender.data))
            mysql.connection.commit()
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error: {str(e)}", "danger")
        finally:
            cursor.close()

        session['user_id'] = cursor.lastrowid
        session['username'] = form.username.data
        session['name'] = form.name.data
        session['surname'] = form.surname.data
        session.modified = True  

        return redirect(url_for('index'))

    return render_template('register.html', form=form)

# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if 'user_id' in session:
        return redirect(url_for('index'))

    if form.validate_on_submit():
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, username, password, name, surname FROM users WHERE username = %s", (form.username.data,))
        user = cursor.fetchone()
        cursor.close()

        if user and bcrypt.check_password_hash(user[2], form.password.data):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['name'] = user[3]
            session['surname'] = user[4]
            session.modified = True
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html', form=form)

# Google Login
@app.route('/login/google')
def google_login():
    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if not resp.ok:
        return "Failed to fetch user info!", 500

    user_info = resp.json()
    email = user_info["email"]
    name = user_info.get("given_name", "Unknown")
    surname = user_info.get("family_name", "")

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("INSERT INTO users (username, email, name, surname) VALUES (%s, %s, %s, %s)", (email, email, name, surname))
        mysql.connection.commit()
        user_id = cursor.lastrowid
    else:
        user_id = user[0]

    cursor.close()

    session['user_id'] = user_id
    session['username'] = email
    session['name'] = name
    session['surname'] = surname
    session.modified = True  

    return redirect(url_for('index'))

# Logout Route
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Profile Route
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT username, email, name, surname FROM users WHERE id = %s", (session['user_id'],))
    user = cursor.fetchone()
    cursor.close()

    return render_template('profile.html', user=user)

if __name__ == '__main__':
    app.run(debug=True)
