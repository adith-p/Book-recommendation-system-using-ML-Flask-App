import os
import uuid

import requests
from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector

from werkzeug.utils import secure_filename

# Database config
from config import db_config, API_KEY,ENDPOINT
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_migrate import Migrate
from flask_login import LoginManager, current_user, login_required, logout_user, login_user, UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from webforms import LoginForm, UserForm, AdminLoginForm

import pandas as pd
import numpy as np

popular_df = pd.read_pickle('popularBooks')
pt = pd.read_pickle('pt.pkl')
books = pd.read_pickle('books.pkl')
similarity_Score = pd.read_pickle('similarity_Score.pkl')

# popular_df = pd.pickle.load(open('popularBooks', 'rb'))

app = Flask(__name__, template_folder='templates')


def is_admin(self):
    return self.is_admin


app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:tiger@localhost/book_recommend'
app.config['SECRET_KEY'] = "g5h4j1gn548ng15j4"

UPLOAD_FOLDER = 'static/images/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Initialize the Flask-Login extension
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(userId):
    # Return the user object for the user with the given id
    return Users.query.get(int(userId))


# Create Admin Page
@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash("Sorry, you must be an admin to access the admin panel.")
        return redirect(url_for('dashboard'))

    our_users = Users.query.order_by(Users.date_added)
    return render_template("admin_panel.html", our_users=our_users)


@app.route('/')
def landing():
    return render_template('home.html')


app.secret_key = 'your_secret_key_here'


@app.route('/top50')
def index():
    return render_template('index.html',
                           book_name=list(popular_df['Book-Title'].values),
                           author=list(popular_df['Book-Author'].values),
                           image=list(popular_df['Image-URL-M'].values),
                           votes=list(popular_df['No_of_Rating'].values),
                           rating=list(popular_df['AvgRating'].values.round(2)),
                           ISBN=list(popular_df['ISBN'].values)

                           )


@app.route('/recommend')
def recommend_ui():
    return render_template('recommend.html')


@app.route('/recommend_books', methods=['POST'])
def recommend():
    user_input = request.form.get('user_input')

    result = np.where(pt.index == user_input)
    if len(result[0]) == 0:
        flash(f"We couldn't find matches for {user_input}", 'error')

        # Handle error here
        # return render_template('Book_not_found.html', user_input=user_input)
        return render_template('recommend.html')
    index = result[0][0]

    similar_items = sorted(list(enumerate(similarity_Score[index])), key=lambda x: x[1], reverse=True)[1:9]
    data = []
    for i in similar_items:
        items = []
        temp_df = books[books['Book-Title'] == pt.index[i[0]]]
        items.extend(list(temp_df.drop_duplicates('Book-Title')['Book-Title'].values))
        items.extend(list(temp_df.drop_duplicates('Book-Title')['Book-Author'].values))
        items.extend(list(temp_df.drop_duplicates('Book-Title')['Image-URL-M'].values))

        data.append(items)
    print(data)

    return render_template('recommend.html', data=data)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(username=form.username.data).first()
        if user:
            # Check the hash
            if check_password_hash(user.password_hash, form.password.data):
                login_user(user)
                flash("Login Successful!!")
                return redirect(url_for('dashboard'))
            else:
                flash("Wrong Password - Try Again!")
        else:
            flash("That User Doesn't Exist! Try Again...")

    return render_template('login.html', form=form)


# Create Logout Page
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash("You Have Been Logged Out!  Thanks For Stopping By...")
    return redirect(url_for('login'))


# Create Dashboard Page
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    form = UserForm()
    id = current_user.id
    name_to_update = Users.query.get_or_404(id)
    if request.method == "POST":
        name_to_update.name = request.form['name']
        name_to_update.email = request.form['email']
        name_to_update.favorite_color = request.form['favorite_color']
        name_to_update.username = request.form['username']
        name_to_update.about_author = request.form['about_author']

        # Check for profile pic
        if request.files['profile_pic']:
            name_to_update.profile_pic = request.files['profile_pic']

            # Grab Image Name
            pic_filename = secure_filename(name_to_update.profile_pic.filename)
            # Set UUID
            pic_name = str(uuid.uuid1()) + "_" + pic_filename
            # Save That Image
            saver = request.files['profile_pic']

            # Change it to a string to save to db
            name_to_update.profile_pic = pic_name
            try:
                db.session.commit()
                saver.save(os.path.join(app.config['UPLOAD_FOLDER'], pic_name))
                flash("User Updated Successfully!")
                return render_template("dashboard.html",
                                       form=form,
                                       name_to_update=name_to_update)
            except:
                flash("Error!  Looks like there was a problem...try again!")
                return render_template("dashboard.html",
                                       form=form,
                                       name_to_update=name_to_update)

        else:
            db.session.commit()
            flash("User Updated Successfully!")
            return render_template("dashboard.html",
                                   form=form,
                                   name_to_update=name_to_update)
    else:
        return render_template("dashboard.html",
                               form=form,
                               name_to_update=name_to_update,
                               id=id)

    return render_template('dashboard.html')


@app.route('/home')
def home():
    return render_template('home.html')


@app.route('/book-details')
def book_details():
    return render_template('one-site.html')


@app.route('/search', methods=['POST'])
def search():
    if request.method == "POST":
        conn = mysql.connector.connect(**db_config)

        search_query = request.form.get('search_query')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM book_recommend.books WHERE `Book-Title` LIKE %s AND CHAR_LENGTH(`Book-Title`) <= 50",
            (f"%{search_query}%",))

        search_results = cursor.fetchall()
        cursor.close()

        # close mysql connection
        conn.close()

    if not search_results:
        return render_template('Book_not_found.html', user_input=search_query)
    else:
        return render_template('search.html', search_results=search_results)


@app.route('/browse_books')
def browse_books():
    return render_template('browse.html')


@app.errorhandler(404)
def error_handle(e):
    return render_template('404.html'), 404


def book_not_found(e):
    return render_template('Book_not_found.html'), 404


@app.errorhandler(500)
def page_not_found(e):
    return render_template("500.html"), 500


# @app.route('/book-info/<book_id>')
# def book_info(book_id):
#   book = get_book_by_id(book_id)  # retrieve book information
#  return render_template('one-site.html', book=book)

class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    favorite_color = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))
    # about_author = db.Column(db.Text(), nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)
    profile_pic = db.Column(db.String(), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

    # Do some password stuff!
    password_hash = db.Column(db.String(128))

    # User Can Have Many Posts
    # posts = db.relationship('Posts', backref='poster')


@property
def password(self):
    raise AttributeError('password is not a readable attribute!')


@password.setter
def password(self, password):
    self.password_hash = generate_password_hash(password)


def verify_password(self, password):
    return check_password_hash(self.password_hash, password)


# Create A String
def __repr__(self):
    return '<Name %r>' % self.name


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    # Check logged in id vs. id to delete
    if id == current_user.id or current_user.is_admin:
        user_to_delete = Users.query.get_or_404(id)
        name = None
        form = UserForm()

        try:
            db.session.delete(user_to_delete)
            db.session.commit()
            flash("User Deleted Successfully!!")

            our_users = Users.query.order_by(Users.date_added)
            return render_template("add_user.html",
                                   form=form,
                                   name=name,
                                   our_users=our_users)

        except:
            flash("Whoops! There was a problem deleting user, try again...")
            return render_template("add_user.html",
                                   form=form, name=name, our_users=our_users)
    else:
        flash("Sorry, you can't delete that user! ")
        return redirect(url_for('dashboard'))


@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update(id):
    form = UserForm()
    name_to_update = Users.query.get_or_404(id)
    if request.method == "POST":
        name_to_update.name = request.form['name']
        name_to_update.email = request.form['email']

        name_to_update.username = request.form['username']
        try:
            db.session.commit()
            flash("User Updated Successfully!")
            return render_template("update.html",
                                   form=form,
                                   name_to_update=name_to_update, id=id)
        except:
            flash("Error!  Looks like there was a problem...try again!")
            return render_template("update.html",
                                   form=form,
                                   name_to_update=name_to_update,
                                   id=id)
    else:
        return render_template("update.html",
                               form=form,
                               name_to_update=name_to_update,
                               id=id)


@app.route('/user/add', methods=['GET', 'POST'])
def add_user():
    if current_user.is_authenticated:
        flash('You are already logged in.')
        return redirect(url_for('home'))

    name = None
    form = UserForm()
    if form.validate_on_submit():
        user = Users.query.filter_by(email=form.email.data).first()
        if user is None:
            # Hash the password!!!
            hashed_pw = generate_password_hash(form.password_hash.data, "sha256")
            user = Users(username=form.username.data, name=form.name.data, email=form.email.data,
                         password_hash=hashed_pw)
            db.session.add(user)
            db.session.commit()
        name = form.name.data
        form.name.data = ''
        form.username.data = ''
        form.email.data = ''

        form.password_hash.data = ''

        flash("User Added Successfully!")
    our_users = Users.query.order_by(Users.date_added)
    return render_template("add_user.html",
                           form=form,
                           name=name,
                           our_users=our_users)


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    form = AdminLoginForm()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        admin = Users.query.filter_by(username=username, is_admin=True).first()
        if admin and check_password_hash(admin.password_hash, password):
            login_user(admin)
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password')

    return render_template('admin_login.html', form=form)


@app.route('/req/<string:search_term>', methods=['GET', 'POST'])
def req(search_term):
    endpoint = ENDPOINT
    api_key = API_KEY

    if request.method == 'POST':
        search_query = request.form['search_query']
    else:
        search_query = request.args.get('search_query')

    # Build the API request URL
    url = f'{endpoint}?q={search_term}&key={api_key}'
    if search_query:
        url = f'{endpoint}?q={search_query}&key={api_key}'

    # Send the API request and get the response
    response = requests.get(url)

    # Check if the response was successful
    if response.status_code != 200:
        return f'Request failed: {response.content}'

    # Parse the JSON response
    data = response.json()

    # Check if the response contains the expected data
    if 'items' not in data:
        return 'No data found for the given search term'

    # Get the first book item from the response
    book = data['items'][0]['volumeInfo']

    # Get the book's author name
    author = book.get('authors', [''])[0]

    # Get the book's title
    title = book.get('title', '')

    # Get the book's image URL
    image_url = book.get('imageLinks', {}).get('large', '')
    if not image_url:
        image_url = book.get('imageLinks', {}).get('medium', '')
        if not image_url:
            image_url = book.get('imageLinks', {}).get('thumbnail', '')

    sale_info = book.get('saleInfo', {})
    buy_link = sale_info.get('buyLink', '')
    list_price = sale_info.get('listPrice', {}).get('amount', '')
    # Get the book's description
    description = book.get('description', 'No description available')

    # Return the book's author name, title, image URL, and description
    return render_template('one-site.html', author=author, title=title, image_url=image_url, description=description,
                           purchase_link=buy_link, price=list_price)


if __name__ == '__main__':
    app.run(debug=True)
