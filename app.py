# Import flask modules
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

# Import other necessary modules
import os
import mysql.connector
from datetime import datetime
from functools import wraps

# Import project modules
from models import db, Project, User, Bug, Comment, Attachment, Notification
from database import create_connection

# Initialize the Flask application
app = Flask(__name__)

# Configuration for the Flask application
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:@localhost/bug_tracker_website'
app.config['UPLOAD_FOLDER'] = 'D:\\DBMS PROJECTS\\bug_tracker_website\\code_files'
app.secret_key = 'no_secret_key'

# Initialize the database
db.init_app(app)

# Initialize the login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize the bcrypt instance
bcrypt = Bcrypt(app)

# User authentication model
class AuthenticatedUser(UserMixin):
    def __init__(self, id, username, email, password_hash, role):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role

# Load the user and check for its existence
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

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

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

@app.route('/project/create', methods=['GET', 'POST'])
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

@app.route('/dashboard')
@login_required
def dashboard():
    projects = Project.query.all()
    return render_template('dashboard.html', projects=projects)

# @app.route('/project/<int:project_id>', methods=['GET'])
# @login_required
# def view_project(project_id):
#     project = Project.query.get_or_404(project_id)
#     search_query = request.args.get('search_query')
#     if search_query:
#         bugs = Bug.query.filter(Bug.project_id == project_id, Bug.title.like(f'%{search_query}%')).all()
#     else:
#         bugs = Bug.query.filter_by(project_id=project.id).all()
#     return render_template('view_project.html', project=project, bugs=bugs)

@app.route('/project/<int:project_id>', methods=['GET'])
@login_required
def view_project(project_id):
    project = Project.query.get_or_404(project_id)
    search_query = request.args.get('search_query')
    sort_by = request.args.get('sort_by', default='id')
    priority_filter = request.args.get('priority_filter')
    status_filter = request.args.get('status_filter')
    
    bugs = Bug.query.filter_by(project_id=project.id)

    if search_query:
        bugs = bugs.filter(Bug.title.like(f'%{search_query}%'))

    if priority_filter:
        bugs = bugs.filter_by(priority=priority_filter)
    
    if status_filter:
        bugs = bugs.filter_by(status=status_filter)

    if sort_by:
        if sort_by == 'title':
            bugs = bugs.order_by(Bug.title)
        elif sort_by == 'priority':
            bugs = bugs.order_by(Bug.priority)
        elif sort_by == 'status':
            bugs = bugs.order_by(Bug.status)
        else:
            bugs = bugs.order_by(Bug.id)

    bugs = bugs.all()
    bugs_priority_count = db.session.query(Bug.priority, db.func.count(Bug.id)).group_by(Bug.priority).filter(Bug.project_id == project_id).all()
    bugs_priority_count = dict(bugs_priority_count)
    return render_template('view_project.html', project=project, bugs=bugs, bugs_priority_count=bugs_priority_count)

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

@app.route('/project/<int:project_id>/bug/create', methods=['GET', 'POST'])
@login_required
def create_bug(project_id):
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        priority = request.form.get('priority')
        assignee_id = request.form.get('assignee_id')
        status = request.form.get('status')
        bug = Bug(title=title, description=description, priority=priority, status=status, creator_id=current_user.id, project_id=project_id, assignee_id=assignee_id)
        db.session.add(bug)

        notification_content = f"New bug assigned to you: {bug.title}"
        notification = Notification(content=notification_content, user_id=assignee_id, created_at=datetime.utcnow())
        db.session.add(notification)

        file = request.files.get('file')
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            attachment = Attachment(filename=filename, file_path=file_path, bug_id=bug.id)
            db.session.add(attachment)

        db.session.commit()
        flash('Bug created successfully.', 'success')
        return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
    users = User.query.all()
    return render_template('create_bug.html', users=users)

@app.route('/project/<int:project_id>/bug/<int:bug_id>', methods=['GET'])
@login_required
def view_bug(project_id, bug_id):
    bug = Bug.query.get_or_404(bug_id)
    comments = Comment.query.filter_by(bug_id=bug_id).order_by(Comment.created_at.desc()).all()
    attachments = Attachment.query.filter_by(bug_id=bug_id).all()
    return render_template('view_bug.html', bug=bug, project_id=project_id,attachments=attachments, comments=comments)

@app.route('/project/<int:project_id>/bug/<int:bug_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_bug(project_id, bug_id):
    bug = Bug.query.get_or_404(bug_id)
    if request.method == 'POST':
        old_assignee_id = bug.assignee_id
        new_assignee_id = request.form.get('assignee_id')
    
        bug.title = request.form.get('title')
        bug.description = request.form.get('description')
        bug.priority = request.form.get('priority')
        bug.status = request.form.get('status')
        bug.assignee_id = request.form.get('assignee_id')
        db.session.add(bug)

        if old_assignee_id != new_assignee_id:
            old_assignee_notification_content = f"You have been unassigned from bug: {bug.title}"
            old_assignee_notification = Notification(content=old_assignee_notification_content, user_id=old_assignee_id, created_at=datetime.utcnow())
            db.session.add(old_assignee_notification)

            new_assignee_notification_content = f"New bug assigned to you: {bug.title}"
            new_assignee_notification = Notification(content=new_assignee_notification_content, user_id=new_assignee_id, created_at=datetime.utcnow())
            db.session.add(new_assignee_notification)

        db.session.commit()
        flash('Bug updated successfully.', 'success')
        return redirect(url_for('view_bug', project_id=project_id, bug_id=bug.id))
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

@app.route('/notifications')
@login_required
def notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifications)

# Removable
@app.route('/project/<int:project_id>/search', methods=['GET', 'POST'])
@login_required
def search_bug(project_id):
    if request.method == 'POST':
        search_query = request.form.get('search_query')
        bugs = Bug.query.filter(Bug.project_id == project_id, Bug.title.like(f'%{search_query}%')).all()
        return render_template('search_results.html', bugs=bugs, project_id=project_id)
    return render_template('search_bug.html', project_id=project_id)

@app.route('/profile', methods=['GET'])
@login_required
def profile():
    current_user_id = current_user.id
    assigned_bugs = Bug.query.filter_by(assignee_id=current_user_id).all()
    return render_template('profile.html', bugs=assigned_bugs)


@app.context_processor
def inject_notifications_count():
    if current_user.is_authenticated:
        count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
        return dict(notifications_count=count)
    return dict(notifications_count=0)

if __name__ == '__main__':
    app.run(debug=True)
