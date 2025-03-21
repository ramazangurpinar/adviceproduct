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

def username_exists(form, field):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id FROM users WHERE username = %s", (field.data,))
    existing_user = cursor.fetchone()
    cursor.close()
    
    if existing_user:
        raise ValidationError('This username is already taken. Please choose another one.')

class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50), username_exists])
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
    country = SelectField('Country', choices=[(c["code"], c["name"]) for c in countries], validators=[DataRequired()])
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    submit = SubmitField('EditProfile')


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
        password = form.password.data
        country = form.country.data
        age = form.age.data
        gender = form.gender.data

        hashed_password = bcrypt.hashpw(password.encode('utf-8'),bcrypt.gensalt())

        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO users (name, surname, username, password, country, age, gender) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (name, surname, username, hashed_password, country, age, gender))

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
            return redirect(url_for('index'))
        else:
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
    cursor.execute("SELECT username, country, name, surname, age, gender FROM users WHERE id = %s", (user_id,))
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
        cursor.execute("SELECT name, surname, country, age, gender FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.close()

        if not user_data:
            return "User not found", 404

        # Formu doldur
        form.name.data = user_data[0]
        form.surname.data = user_data[1]
        form.country.data = user_data[2]
        form.age.data = user_data[3]
        form.gender.data = user_data[4]

    elif form.validate_on_submit():
        # Form verilerini al
        name = form.name.data
        surname = form.surname.data
        country = form.country.data
        age = form.age.data
        gender = form.gender.data

        cursor.execute("""
            UPDATE users 
            SET name = %s, surname = %s, country = %s, age = %s, gender = %s 
            WHERE id = %s
        """, (name, surname, country, age, gender, user_id))
        mysql.connection.commit()
        cursor.close()

        # Session'ı güncelle
        session['name'] = name
        session['surname'] = surname

        return redirect(url_for('profile'))

    return render_template('edit_profile.html', form=form)

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    cursor = mysql.connection.cursor()
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cursor.close()

    session.clear()

    return redirect(url_for('login'))

@app.route('/logout')
def logout():
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
    
