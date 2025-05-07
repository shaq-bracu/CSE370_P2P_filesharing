from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_mysqldb import MySQL
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''  # Replace with your MySQL password
app.config['MYSQL_DB'] = 'peer_to_peer_file_sharing'

mysql = MySQL(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
        user = cur.fetchone()
        cur.close()
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            return redirect(url_for('home'))
        else:
            return "Invalid credentials"
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()

        # Check if the email already exists
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            cur.close()
            return render_template('signup.html', error="Email already exists. Please use a different email.")

        # Insert the new user
        cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", (username, email, password))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Handle forum message submission
    if request.method == 'POST':
        message = request.form['message']
        username = session['username']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO forum_posts (message, username) VALUES (%s, %s)", (message, username))
        mysql.connection.commit()
        cur.close()

    # Fetch files from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, uploaded_by FROM files")
    files = [{'file_name': row[0], 'uploaded_by': row[1]} for row in cur.fetchall()]

    # Fetch forum posts
    cur.execute("SELECT username, message FROM forum_posts ORDER BY posted_at DESC")
    posts = cur.fetchall()
    cur.close()

    # Pass files and posts to the template
    return render_template('home.html', username=session['username'], files=files, posts=posts)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']
        if file:
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(file_path)

            # Save file metadata with the user who uploaded it
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO files (file_name, file_path, uploaded_by) VALUES (%s, %s, %s)", 
                        (file.filename, file_path, session['username']))
            mysql.connection.commit()
            cur.close()

            # Redirect to buffering page
            return redirect(url_for('buffering', action='upload'))

    return render_template('upload.html')

@app.route('/download', methods=['GET'])
def list_files():
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, uploaded_by FROM files")
    files = [{'file_name': row[0], 'uploaded_by': row[1]} for row in cur.fetchall()]
    cur.close()
    return render_template('download.html', files=files)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/buffering/<action>')
def buffering(action):
    return render_template('buffering.html', action=action)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/forum', methods=['GET', 'POST'])
def forum():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Add a new message to the forum
        message = request.form['message']
        username = session['username']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO forum_posts (message, username) VALUES (%s, %s)", (message, username))
        mysql.connection.commit()
        cur.close()

    # Fetch all forum posts
    cur = mysql.connection.cursor()
    cur.execute("SELECT username, message FROM forum_posts ORDER BY posted_at DESC")
    posts = cur.fetchall()
    cur.close()

    return render_template('forum.html', posts=posts)

if __name__ == '__main__':
    app.run(debug=True)