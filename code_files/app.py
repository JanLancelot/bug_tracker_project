from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
import os
from functools import wraps
from models import db, Project, User, Bug, Comment, Attachment
import mysql.connector
from flask_login import UserMixin
from database import create_connection

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/bug_tracker_website'
# Bolt 1
app.config['UPLOAD_FOLDER'] = 'D:\\DBMS PROJECTS\\bug_tracker_website\\code_files'
app.secret_key = 'your_secret_key'
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

bcrypt = Bcrypt(app)

# Unsure of this class
class AuthenticatedUser(UserMixin):
    def __init__(self, id, username, email, password_hash, role):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role

@login_manager.user_loader
def load_user(user_id):
    connection = create_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    cursor.close()
    connection.close()

    if user_data:
        return AuthenticatedUser(**user_data)
    return None

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    else:
        return render_template('index.html')

# Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        connection = create_connection()
        cursor = connection.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                           (username, email, password_hash, role))
            connection.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f'Error: {err}', 'danger')
        finally:
            cursor.close()
            connection.close()

    return render_template('register.html')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        connection = create_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        cursor.close()
        connection.close()

        if user_data and bcrypt.check_password_hash(user_data['password_hash'], password):
            user = AuthenticatedUser(**user_data)
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('login.html')

# Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

# Role-based access control
# def require_role(role):
#     def decorator(f):
#         @wraps(f)
#         def decorated_function(*args, **kwargs):
#             if not current_user.is_authenticated or current_user.role != role:
#                 flash('You do not have permission to access this resource.', 'danger')
#                 return redirect(url_for('index'))
#             return f(*args, **kwargs)
#         return decorated_function
#     return decorator

# Role-based access control
def require_role(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                flash('You do not have permission to access this resource.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Other routes for project management, bug management, bug assignment, commenting, file attachments, notifications, dashboard, and search functionality go here
@app.route('/project/create', methods=['GET', 'POST'])
# Changed
# @require_role('project_manager')
@require_role(['project_manager', 'admin'])
def create_project():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        project = Project(name=name, description=description, created_by_id=current_user.id)
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully.', 'success')
        return redirect(url_for('view_project', project_id=project.id))
    return render_template('create_project.html')

# Remember this position
@app.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.all()
    return render_template('dashboard.html', projects=projects)


# @app.route('/project/<int:project_id>', methods=['GET'])
# def view_project(project_id):
#     project = Project.query.get_or_404(project_id)
#     return render_template('view_project.html', project=project)

@app.route('/project/<int:project_id>', methods=['GET'])
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    bugs = Bug.query.filter_by(project_id=project.id).all()  # Get all bugs associated with the project
    return render_template('view_project.html', project=project, bugs=bugs)


@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@require_role('project_manager')
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if request.method == 'POST':
        project.name = request.form.get('name')
        project.description = request.form.get('description')
        db.session.commit()
        flash('Project updated successfully.', 'success')
        return redirect(url_for('view_project', project_id=project.id))
    return render_template('edit_project.html', project=project)

@app.route('/project/<int:project_id>/delete', methods=['POST'])
@require_role('project_manager')
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('Project deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

# Unfreeze in case of emergency
# @app.route('/project/<int:project_id>/bug/create', methods=['GET', 'POST'])
# @login_required
# def create_bug(project_id):
#     if request.method == 'POST':
#         title = request.form.get('title')
#         description = request.form.get('description')
#         priority = request.form.get('priority')
#         bug = Bug(title=title, description=description, priority=priority, creator_id=current_user.id, project_id=project_id)
#         db.session.add(bug)
#         db.session.commit()
#         flash('Bug created successfully.', 'success')
#         return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
#     return render_template('create_bug.html')

# @app.route('/project/<int:project_id>/bug/create', methods=['GET', 'POST'])
# @login_required
# def create_bug(project_id):
#     if request.method == 'POST':
#         title = request.form.get('title')
#         description = request.form.get('description')
#         priority = request.form.get('priority')
#         assignee_id = request.form.get('assignee_id')  # Get the user id from the form data
#         status = request.form.get('status')
#         bug = Bug(title=title, description=description, priority=priority, status=status, creator_id=current_user.id, project_id=project_id, assignee_id=assignee_id)
#         db.session.add(bug)
#         db.session.commit()
#         flash('Bug created successfully.', 'success')
#         return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
#     # Fetch all the users from the database to populate the select box in the HTML form
#     users = User.query.all()
#     return render_template('create_bug.html', users=users)

# @app.route('/project/<int:project_id>/bug/create', methods=['GET', 'POST'])
# @login_required
# def create_bug(project_id):
#     if request.method == 'POST':
#         title = request.form.get('title')
#         description = request.form.get('description')
#         priority = request.form.get('priority')
#         status = request.form.get('status')
#         assignee_id = request.form.get('assignee_id')  # Get the user id from the form data
#         bug = Bug(title=title, description=description, priority=priority, status=status, creator_id=current_user.id, project_id=project_id, assignee_id=assignee_id)

#         # check if the post request has the file part
#         if 'file' in request.files:
#             file = request.files['file']
#             # if user does not select file, browser also submit an empty part without filename
#             if file.filename != '':
#                 filename = secure_filename(file.filename)
#                 file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#                 file.save(file_path)
#                 attachment = Attachment(filename=filename, file_path=file_path, bug_id=bug.id)
#                 db.session.add(attachment)

#         db.session.add(bug)
#         db.session.commit()
#         flash('Bug created successfully.', 'success')
#         return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))

#     # Fetch all the users from the database to populate the select box in the HTML form
#     users = User.query.all()
#     return render_template('create_bug.html', users=users)

@app.route('/project/<int:project_id>/bug/create', methods=['GET', 'POST'])
@login_required
def create_bug(project_id):
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority')
        assignee_id = request.form.get('assignee_id')  # Get the user id from the form data
        status = request.form.get('status')
        bug = Bug(title=title, description=description, priority=priority, status=status, creator_id=current_user.id, project_id=project_id, assignee_id=assignee_id)
        db.session.add(bug)
        db.session.commit()  # Commit here so the bug id is generated

        # File handling
        file = request.files.get('file')  # Get the file from the form data
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            attachment = Attachment(filename=filename, file_path=file_path, bug_id=bug.id)  # Use the bug id here
            db.session.add(attachment)
            db.session.commit()  # Commit again to save the attachment

        flash('Bug created successfully.', 'success')
        return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
    # Fetch all the users from the database to populate the select box in the HTML form
    users = User.query.all()
    return render_template('create_bug.html', users=users)


# @app.route('/project/<int:project_id>/bug/<int:bug_id>', methods=['GET'])
# @login_required
# def view_bug(project_id, bug_id):
#     bug = Bug.query.get_or_404(bug_id)
#     return render_template('view_bug.html', bug=bug)

# @app.route('/project/<int:project_id>/bug/<int:bug_id>', methods=['GET'])
# @login_required
# def view_bug(project_id, bug_id):
#     bug = Bug.query.get_or_404(bug_id)
#     return render_template('view_bug.html', bug=bug, project_id=project_id)

# @app.route('/project/<int:project_id>/bug/<int:bug_id>', methods=['GET'])
# @login_required
# def view_bug(project_id, bug_id):
#     bug = Bug.query.get_or_404(bug_id)
#     comments = Comment.query.filter_by(bug_id=bug_id).order_by(Comment.created_at.desc()).all()
#     return render_template('view_bug.html', bug=bug, project_id=project_id, comments=comments)

@app.route('/project/<int:project_id>/bug/<int:bug_id>', methods=['GET'])
@login_required
def view_bug(project_id, bug_id):
    bug = Bug.query.get_or_404(bug_id)
    comments = Comment.query.filter_by(bug_id=bug_id).order_by(Comment.created_at.desc()).all()
    attachments = Attachment.query.filter_by(bug_id=bug_id).all()
    return render_template('view_bug.html', bug=bug, project_id=project_id,attachments=attachments, comments=comments)




# Unfreeze in case of emergency
# @app.route('/project/<int:project_id>/bug/<int:bug_id>/edit', methods=['GET', 'POST'])
# @login_required
# def edit_bug(project_id, bug_id):
#     bug = Bug.query.get_or_404(bug_id)
#     if request.method == 'POST':
#         bug.title = request.form.get('title')
#         bug.description = request.form.get('description')
#         bug.priority = request.form.get('priority')
#         db.session.commit()
#         flash('Bug updated successfully.', 'success')
#         return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
#     return render_template('edit_bug.html', bug=bug)

@app.route('/project/<int:project_id>/bug/<int:bug_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bug(project_id, bug_id):
    bug = Bug.query.get_or_404(bug_id)
    if request.method == 'POST':
        bug.title = request.form.get('title')
        bug.description = request.form.get('description')
        bug.priority = request.form.get('priority')
        bug.status = request.form.get('status')  # Add this line to update status
        bug.assignee_id = request.form.get('assignee_id')  # Update the assigned user
        db.session.add(bug)  # Add the bug object back to the session
        db.session.commit()
        flash('Bug updated successfully.', 'success')
        return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
    # Fetch all the users from the database to populate the select box in the HTML form
    users = User.query.all()
    return render_template('edit_bug.html', bug=bug, users=users)

@app.route('/project/<int:project_id>/bug/<int:bug_id>/delete', methods=['POST'])
@login_required
def delete_bug(project_id, bug_id):
    bug = Bug.query.get_or_404(bug_id)
    db.session.delete(bug)
    db.session.commit()
    flash('Bug deleted successfully.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/project/<int:project_id>/bug/<int:bug_id>/comment', methods=['POST'])
@login_required
def comment_on_bug(project_id, bug_id):
    content = request.form.get('comment')
    comment = Comment(content=content, user_id=current_user.id, bug_id=bug_id)
    db.session.add(comment)
    db.session.commit()
    flash('Comment added successfully.', 'success')
    return redirect(url_for('view_bug', project_id=project_id, bug_id=bug_id))

# @app.route('/project/<int:project_id>/bug/<int:bug_id>/attach', methods=['POST'])
# @login_required
# def attach_file_to_bug(project_id, bug_id):
#     # check if the post request has the file part
#     if 'file' not in request.files:
#         flash('No file part', 'error')
#         return redirect(request.url)
#     file = request.files['file']
#     # if user does not select file, browser also submit an empty part without filename
#     if file.filename == '':
#         flash('No selected file', 'error')
#         return redirect(request.url)
#     filename = secure_filename(file.filename)
#     file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#     file.save(file_path)
#     attachment = Attachment(filename=filename, file_path=file_path, bug_id=bug_id)
#     db.session.add(attachment)
#     db.session.commit()
#     flash('File successfully uploaded', 'success')
#     return redirect(url_for('view_bug', project_id=project_id, bug_id=bug_id))

# Causing a bug. Uncomment in case of plan A
# @app.route('/project/<int:project_id>/bug/<int:bug_id>/assign', methods=['POST'])
# @login_required
# def assign_bug(project_id, bug_id):
#     user_id = request.form.get('user_id')
#     bug = Bug.query.get_or_404(bug_id)
#     bug.assigned_to_id = user_id
#     db.session.commit()
#     flash('Bug assigned successfully.', 'success')
#     return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))

# @app.before_first_request
# def create_tables():
#     db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
