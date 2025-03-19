from flask import Flask, render_template, redirect, url_for, session, request
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length
import bcrypt
from flask_mysqldb import MySQL
from ignore.secret import secretpw
import os
from dotenv import load_dotenv
from datetime import timedelta

app = Flask(__name__)
load_dotenv()

# Uygulama başlatıldığında bir kez yapılacak işlemler
app.secret_key = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['MYSQL_HOST'] = 'localhost'  # host address of the database
app.config['MYSQL_USER'] = 'root'  # username of the database
app.config['MYSQL_PASSWORD'] = secretpw()  # password of the database
app.config['MYSQL_DB'] = 'productadvice'  # database name
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # session timeout

mysql = MySQL(app)

@app.before_request
def setup():
    print("before request method called.")
    print(session)


class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    country = StringField('Country', validators=[Length(max=100)])
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Login')


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
        user_id = session['user_id']
        username = session['username']
    return render_template('index.html', user_id=user_id, username=username)

@app.route('/register', methods=['GET', 'POST'])
def register():
    session.pop('user_id', None)  
    session.pop('username', None)
    form = RegistrationForm()
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
        cursor.close()

        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if 'username' in session:
       return redirect(url_for('index'))

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        cursor = mysql.connection.cursor()
        cursor.execute("SELECT id, username, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):  
            session['user_id'] = user[0]
            session['username'] = user[1]
            session.permanent = True
            print("Session Data After Login:", session)
            print("login route: SECRET_KEY (from .env):", os.getenv("SECRET_KEY"))            
            return redirect(url_for('index')) 
        else:
            return "Invalid username or password! <a href='/login'>Try again</a>"

    return render_template('login.html', form=form)


@app.route('/session-data')
def session_data():
    username = session.get('username', None)
    if username:
        html_content = f'''
        <html>
            <body>
                <h1>Session Data Page</h1>
                <p>Here is the username stored in session:</p>
                <span>{username}</span>
            </body>
        </html>
        '''
    else:
        html_content = '''
        <html>
            <body>
                <h1>Session Data Page</h1>
                <p>No username found in session.</p>
            </body>
        </html>
        '''
    
    return html_content

    
@app.route('/logout')
def logout():
    session.pop('user_id', None)  
    session.pop('username', None) 
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)
