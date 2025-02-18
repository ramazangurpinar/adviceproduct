from flask import Flask, render_template, redirect, url_for
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, IntegerField, SelectField
from wtforms.validators import DataRequired, Length
import bcrypt
from flask_mysqldb import MySQL
import os

app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'  # host  address of the database
app.config  ['MYSQL_USER'] = 'root'  # username of the database
app.config['MYSQL_PASSWORD'] = ''  # password of the database
app.config['MYSQL_DB'] = 'productadvice'  # database name
app.secret_key = os.urandom(24) # secret key for the app

mysql = MySQL(app)

class RegistrationForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(min=2, max=50)])
    surname = StringField('Surname', validators=[DataRequired(), Length(min=2, max=50)])
    username = StringField('Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    country = StringField('Country', validators=[Length(max=100)])
    age = IntegerField('Age')
    gender = SelectField('Gender', choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    submit = SubmitField('Register')

@app.route('/')
def hello():
    return render_template('index.html')

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

@app.route('/register', methods=['GET', 'POST'])
def register():
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

@app.route('/login')
def login():
    return render_template('login.html')

if __name__ == '__main__':
    app.run(debug=True)