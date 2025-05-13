from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, send_file
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
            return render_template('login.html', user_error="Invalid user credentials")
    return render_template('login.html')

@app.route('/admin_login', methods=['POST'])
def admin_login():
    username = request.form['admin_username']
    password = request.form['admin_password']
    if username == "Admin" and password == "1234":
        session['user_id'] = 0  # Admin doesn't need a user ID from the database
        session['username'] = "Admin"
        session['is_admin'] = True  # Flag to identify admin
        return redirect(url_for('home'))
    else:
        return render_template('login.html', admin_error="Invalid admin credentials")

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('signup.html', error="Passwords do not match")

        cur = mysql.connection.cursor()

        # Check if the email already exists
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        existing_user = cur.fetchone()

        if existing_user:
            return render_template('signup.html', error="Email already exists")

        # Insert the new user (default: not admin)
        cur.execute("INSERT INTO users (username, email, password, is_admin) VALUES (%s, %s, %s, %s)",
                    (username, email, password, False))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/home', methods=['GET', 'POST'])
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Handle forum message submission
    if request.method == 'POST' and 'message' in request.form:
        message = request.form['message']
        username = session['username']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO forum_posts (message, username) VALUES (%s, %s)", (message, username))
        mysql.connection.commit()
        cur.close()

    # Handle file search
    query = request.args.get('query', '').strip()
    cur = mysql.connection.cursor()
    if session.get('is_admin'):
        # Admin sees all files
        if query:
            cur.execute("SELECT id, file_name, uploaded_by, is_approved FROM files WHERE file_name LIKE %s", (f"%{query}%",))
        else:
            cur.execute("SELECT id, file_name, uploaded_by, is_approved FROM files")
        files = [{'id': row[0], 'file_name': row[1], 'uploaded_by': row[2], 'is_approved': row[3]} for row in cur.fetchall()]
    else:
        # Regular users see only approved files
        if query:
            cur.execute("SELECT id, file_name, uploaded_by FROM files WHERE is_approved = TRUE AND file_name LIKE %s", (f"%{query}%",))
        else:
            cur.execute("SELECT id, file_name, uploaded_by FROM files WHERE is_approved = TRUE")
        files = [{'id': row[0], 'file_name': row[1], 'uploaded_by': row[2]} for row in cur.fetchall()]

    # Fetch forum posts
    cur.execute("SELECT id, username, message FROM forum_posts ORDER BY posted_at DESC")
    posts = [{'id': row[0], 'username': row[1], 'message': row[2]} for row in cur.fetchall()]
    cur.close()

    return render_template('home.html', username=session['username'], files=files, posts=posts, query=query)

@app.route('/upload', methods=['GET', 'POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        file = request.files['file']
        if file:
            file_name = file.filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)
            file.save(file_path)

            is_approved = session.get('is_admin', False)  # Automatically approve if the uploader is an admin

            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO files (file_name, file_path, uploaded_by, is_approved) VALUES (%s, %s, %s, %s)",
                (file_name, file_path, session['username'], is_approved)
            )
            mysql.connection.commit()
            cur.close()

            if is_approved:
                return "File uploaded successfully and approved!"
            else:
                return "File uploaded successfully! Pending admin approval."
    return redirect(url_for('home'))

@app.route('/download', methods=['GET'])
def list_files():
    cur = mysql.connection.cursor()
    cur.execute("SELECT file_name, uploaded_by FROM files")
    files = [{'file_name': row[0], 'uploaded_by': row[1]} for row in cur.fetchall()]
    cur.close()
    return render_template('download.html', files=files)

@app.route('/download/<filename>')
def download_file_from_directory(filename):  # Renamed function
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/download_file/<filename>')
def download_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(file_path, as_attachment=True)

@app.route('/buffering/<action>')
def buffering(action):
    return render_template('buffering.html', action=action)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if 'is_admin' in session and session['is_admin']:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/admin/delete_file/<int:file_id>', methods=['POST'])
def delete_file_admin(file_id):
    if 'is_admin' in session and session['is_admin']:
        cur = mysql.connection.cursor()
        cur.execute("SELECT file_path FROM files WHERE id = %s", (file_id,))
        file = cur.fetchone()
        if file:
            file_path = file[0]
            if os.path.exists(file_path):
                os.remove(file_path)  # Delete the file from the server
        cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('home'))

@app.route('/admin/delete_message/<int:message_id>', methods=['POST'])
def delete_message_admin(message_id):
    if 'is_admin' in session and session['is_admin']:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM forum_posts WHERE id = %s", (message_id,))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('forum'))
    return redirect(url_for('login'))

@app.route('/delete_message/<int:message_id>', methods=['POST'])
def delete_message(message_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM forum_posts WHERE id = %s", (message_id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('home'))

@app.route('/download')
def download():
    return render_template('download.html', files=files)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    return render_template('upload.html')

@app.route('/admin/approve_files', methods=['GET', 'POST'])
def approve_files():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    if request.method == 'POST':
        file_id = request.form['file_id']
        action = request.form['action']
        if action == 'approve':
            cur.execute("UPDATE files SET is_approved = TRUE WHERE id = %s", (file_id,))
        elif action == 'reject':
            cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
        mysql.connection.commit()
    cur.execute("SELECT id, file_name, uploaded_by FROM files WHERE is_approved = FALSE")
    pending_files = [{'id': row[0], 'file_name': row[1], 'uploaded_by': row[2]} for row in cur.fetchall()]
    cur.close()

    return render_template('approve_files.html', pending_files=pending_files)

@app.route('/approve_file/<int:file_id>', methods=['POST'])
def approve_file(file_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("UPDATE files SET is_approved = TRUE WHERE id = %s", (file_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('home'))

@app.route('/reject_file/<int:file_id>', methods=['POST'])
def reject_file(file_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM files WHERE id = %s", (file_id,))
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)