import os
import uuid
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory, abort)
from flask_login import (LoginManager, login_user, logout_user,
                          login_required, current_user)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

from database import db, User, Case, Document, CaseNote, Reminder, ChatHistory, Task

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///legal_cases.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'txt', 'xlsx', 'xls'}

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# --- Gemini AI Setup ---
# --- Gemini AI Setup ---
from google import genai

GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

def get_gemini_response(user_message, case_context=""):
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)  # ← MODIFY THIS LINE
        
        system_prompt = """You are LegalBot, an AI legal assistant integrated into a Case Management System.
        You provide general legal information, advice on case management, document organization tips,
        reminder suggestions, and procedural guidance. 
        
        IMPORTANT DISCLAIMERS:
        - Always remind users that your advice is informational and not a substitute for professional legal counsel.
        - Never provide specific legal opinions on ongoing cases.
        - Be helpful, empathetic, and professional.
        - If case context is provided, use it to give more relevant advice.
        """
        
        full_prompt = system_prompt
        if case_context:
            full_prompt += f"\n\nCase Context: {case_context}"
        full_prompt += f"\n\nUser: {user_message}"
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",  # This model works with v1 API
            contents=full_prompt
        )
        return response.text
    except Exception as e:
        return f"I'm sorry, I encountered an error processing your request. Please try again later. (Error: {str(e)})"
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_case_number():
    year = datetime.now().year
    count = Case.query.filter(
        Case.created_at >= datetime(year, 1, 1)
    ).count() + 1
    return f"CASE-{year}-{count:04d}"

# ============ ROUTES ============

@app.route('/')
def index():
    return render_template('index.html')

# --- AUTH ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'client')
        full_name = request.form.get('full_name', '').strip()
        phone = request.form.get('phone', '').strip()
        
        if password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password),
            role=role,
            full_name=full_name,
            phone=phone
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully!', 'info')
    return redirect(url_for('index'))

# --- DASHBOARD ---
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'lawyer':
        cases = Case.query.filter(
            (Case.lawyer_id == current_user.id) | (Case.user_id == current_user.id)
        ).order_by(Case.updated_at.desc()).all()
    else:
        cases = Case.query.filter_by(user_id=current_user.id).order_by(Case.updated_at.desc()).all()
    
    # Stats
    total_cases = len(cases)
    open_cases = sum(1 for c in cases if c.status == 'Open')
    in_progress = sum(1 for c in cases if c.status == 'In Progress')
    closed_cases = sum(1 for c in cases if c.status == 'Closed')
    
    # Upcoming reminders
    upcoming_reminders = Reminder.query.filter(
        Reminder.user_id == current_user.id,
        Reminder.is_completed == False,
        Reminder.remind_date >= datetime.utcnow()
    ).order_by(Reminder.remind_date.asc()).limit(5).all()
    
    # Upcoming hearings
    upcoming_hearings = [c for c in cases if c.next_hearing and c.next_hearing >= datetime.utcnow()]
    upcoming_hearings.sort(key=lambda x: x.next_hearing)
    upcoming_hearings = upcoming_hearings[:5]
    
    return render_template('dashboard.html',
                           cases=cases,
                           total_cases=total_cases,
                           open_cases=open_cases,
                           in_progress=in_progress,
                           closed_cases=closed_cases,
                           upcoming_reminders=upcoming_reminders,
                           upcoming_hearings=upcoming_hearings)

# --- CASE MANAGEMENT ---
@app.route('/case/add', methods=['GET', 'POST'])
@login_required
def add_case():
    lawyers = User.query.filter_by(role='lawyer').all() if current_user.role == 'client' else []
    
    if request.method == 'POST':
        case = Case(
            case_number=generate_case_number(),
            title=request.form.get('title', '').strip(),
            description=request.form.get('description', '').strip(),
            case_type=request.form.get('case_type', 'Civil'),
            status=request.form.get('status', 'Open'),
            priority=request.form.get('priority', 'Medium'),
            court_name=request.form.get('court_name', '').strip(),
            judge_name=request.form.get('judge_name', '').strip(),
            opposing_party=request.form.get('opposing_party', '').strip(),
            user_id=current_user.id
        )
        
        next_hearing = request.form.get('next_hearing')
        if next_hearing:
            case.next_hearing = datetime.strptime(next_hearing, '%Y-%m-%dT%H:%M')
        
        lawyer_id = request.form.get('lawyer_id')
        if lawyer_id:
            case.lawyer_id = int(lawyer_id)
        elif current_user.role == 'lawyer':
            case.lawyer_id = current_user.id
        
        db.session.add(case)
        db.session.commit()
        
        flash(f'Case {case.case_number} created successfully!', 'success')
        return redirect(url_for('case_detail', case_id=case.id))
    
    return render_template('add_case.html', lawyers=lawyers)

@app.route('/case/<int:case_id>')
@login_required
def case_detail(case_id):
    case = Case.query.get_or_404(case_id)
    
    # Access control
    if current_user.role == 'client' and case.user_id != current_user.id:
        abort(403)
    if current_user.role == 'lawyer' and case.lawyer_id != current_user.id and case.user_id != current_user.id:
        abort(403)
    
    notes = CaseNote.query.filter_by(case_id=case.id).order_by(CaseNote.created_at.desc()).all()
    documents = Document.query.filter_by(case_id=case.id).order_by(Document.uploaded_at.desc()).all()
    reminders = Reminder.query.filter_by(case_id=case.id).order_by(Reminder.remind_date.asc()).all()
    
    return render_template('case_detail.html', case=case, notes=notes, documents=documents, reminders=reminders, now=datetime.now())

@app.route('/case/<int:case_id>/edit', methods=['POST'])
@login_required
def edit_case(case_id):
    case = Case.query.get_or_404(case_id)
    
    case.title = request.form.get('title', case.title)
    case.description = request.form.get('description', case.description)
    case.case_type = request.form.get('case_type', case.case_type)
    case.status = request.form.get('status', case.status)
    case.priority = request.form.get('priority', case.priority)
    case.court_name = request.form.get('court_name', case.court_name)
    case.judge_name = request.form.get('judge_name', case.judge_name)
    case.opposing_party = request.form.get('opposing_party', case.opposing_party)
    
    next_hearing = request.form.get('next_hearing')
    if next_hearing:
        case.next_hearing = datetime.strptime(next_hearing, '%Y-%m-%dT%H:%M')
    
    if case.status == 'Closed':
        case.closing_date = datetime.utcnow()
    
    db.session.commit()
    flash('Case updated successfully!', 'success')
    return redirect(url_for('case_detail', case_id=case.id))

@app.route('/case/<int:case_id>/delete', methods=['POST'])
@login_required
def delete_case(case_id):
    case = Case.query.get_or_404(case_id)
    if case.user_id != current_user.id:
        abort(403)
    
    # Delete associated files
    for doc in case.documents:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    
    db.session.delete(case)
    db.session.commit()
    flash('Case deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

# --- DOCUMENT MANAGEMENT ---
@app.route('/case/<int:case_id>/upload', methods=['POST'])
@login_required
def upload_document(case_id):
    case = Case.query.get_or_404(case_id)
    
    if 'document' not in request.files:
        flash('No file selected!', 'danger')
        return redirect(url_for('case_detail', case_id=case_id))
    
    file = request.files['document']
    if file.filename == '':
        flash('No file selected!', 'danger')
        return redirect(url_for('case_detail', case_id=case_id))
    
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        ext = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{ext}"
        
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        doc = Document(
            filename=unique_filename,
            original_filename=original_filename,
            file_type=ext,
            file_size=os.path.getsize(filepath),
            category=request.form.get('category', 'General'),
            description=request.form.get('doc_description', ''),
            case_id=case_id,
            uploaded_by=current_user.id
        )
        db.session.add(doc)
        db.session.commit()
        
        flash('Document uploaded successfully!', 'success')
    else:
        flash('File type not allowed!', 'danger')
    
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/document/<int:doc_id>/download')
@login_required
def download_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        doc.filename,
        as_attachment=True,
        download_name=doc.original_filename
    )

@app.route('/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    doc = Document.query.get_or_404(doc_id)
    case_id = doc.case_id
    
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], doc.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    
    db.session.delete(doc)
    db.session.commit()
    flash('Document deleted!', 'success')
    return redirect(url_for('case_detail', case_id=case_id))

# --- NOTES ---
@app.route('/case/<int:case_id>/note', methods=['POST'])
@login_required
def add_note(case_id):
    content = request.form.get('note_content', '').strip()
    if content:
        note = CaseNote(content=content, case_id=case_id, author_id=current_user.id)
        db.session.add(note)
        db.session.commit()
        flash('Note added!', 'success')
    return redirect(url_for('case_detail', case_id=case_id))

# --- REMINDERS ---
@app.route('/case/<int:case_id>/reminder', methods=['POST'])
@login_required
def add_reminder(case_id):
    title = request.form.get('reminder_title', '').strip()
    remind_date = request.form.get('remind_date')
    description = request.form.get('reminder_description', '').strip()
    
    if title and remind_date:
        reminder = Reminder(
            title=title,
            description=description,
            remind_date=datetime.strptime(remind_date, '%Y-%m-%dT%H:%M'),
            case_id=case_id,
            user_id=current_user.id
        )
        db.session.add(reminder)
        db.session.commit()
        flash('Reminder set!', 'success')
    return redirect(url_for('case_detail', case_id=case_id))

@app.route('/reminder/<int:reminder_id>/complete', methods=['POST'])
@login_required
def complete_reminder(reminder_id):
    reminder = Reminder.query.get_or_404(reminder_id)
    reminder.is_completed = True
    db.session.commit()
    return jsonify({'status': 'success'})

    # ============ TASK MANAGEMENT ROUTES ============

@app.route('/tasks')
@login_required
def view_tasks():
    """View all tasks for the current user"""
    if current_user.role == 'lawyer':
        tasks = Task.query.filter(
            (Task.assigned_to_id == current_user.id) | 
            (Task.assigned_by_id == current_user.id)
        ).order_by(Task.status.asc(), Task.priority.desc(), Task.due_date.asc()).all()
    else:
        tasks = Task.query.filter_by(assigned_to_id=current_user.id).order_by(
            Task.status.asc(), Task.due_date.asc()
        ).all()
    
    pending_tasks = [t for t in tasks if t.status == 'pending']
    completed_tasks = [t for t in tasks if t.status == 'completed']
    
    return render_template('tasks.html', 
                         pending_tasks=pending_tasks, 
                         completed_tasks=completed_tasks,
                         now=datetime.now())

@app.route('/task/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = request.form.get('priority', 'medium')
        due_date_str = request.form.get('due_date')
        case_id = request.form.get('case_id')
        assigned_to_id = request.form.get('assigned_to_id')
        
        if not title:
            flash('Task title is required!', 'danger')
            return redirect(url_for('add_task'))
        
        due_date = None
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        
        task = Task(
            title=title,
            description=description,
            priority=priority,
            due_date=due_date,
            case_id=int(case_id) if case_id else None,
            assigned_by_id=current_user.id,
            assigned_to_id=int(assigned_to_id) if assigned_to_id else current_user.id,
            status='pending'
        )
        
        db.session.add(task)
        db.session.commit()
        
        flash(f'Task "{task.title}" created successfully!', 'success')
        return redirect(url_for('view_tasks'))
    
    # GET request - show form
    if current_user.role == 'lawyer':
        cases = Case.query.filter(
            (Case.lawyer_id == current_user.id) | (Case.user_id == current_user.id)
        ).all()
        users = User.query.filter(User.role.in_(['lawyer', 'admin'])).all()
    else:
        cases = Case.query.filter_by(user_id=current_user.id).all()
        users = User.query.filter_by(role='lawyer').all()
    
    return render_template('add_task.html', cases=cases, users=users)

@app.route('/task/<int:task_id>/toggle', methods=['POST'])
@login_required
def toggle_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.assigned_to_id != current_user.id and task.assigned_by_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if task.status == 'pending':
        task.status = 'completed'
        task.completed_at = datetime.utcnow()
    else:
        task.status = 'pending'
        task.completed_at = None
    
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': task.status})
    else:
        flash(f'Task "{task.title}" updated!', 'success')
        return redirect(url_for('view_tasks'))

@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    
    if task.assigned_by_id != current_user.id and current_user.role != 'admin':
        flash('You can only delete tasks you created!', 'danger')
        return redirect(url_for('view_tasks'))
    
    title = task.title
    db.session.delete(task)
    db.session.commit()
    
    flash(f'Task "{title}" deleted successfully!', 'success')
    return redirect(url_for('view_tasks'))

# --- CHATBOT ---
@app.route('/chatbot')
@login_required
def chatbot():
    history = ChatHistory.query.filter_by(user_id=current_user.id).order_by(
        ChatHistory.created_at.desc()
    ).limit(20).all()
    history.reverse()
    
    cases = Case.query.filter(
        (Case.user_id == current_user.id) | (Case.lawyer_id == current_user.id)
    ).all()
    
    return render_template('chatbot.html', history=history, cases=cases)

@app.route('/chatbot/send', methods=['POST'])
@login_required
def chatbot_send():
    data = request.get_json()
    user_message = data.get('message', '').strip()
    case_id = data.get('case_id')
    
    if not user_message:
        return jsonify({'error': 'Empty message'}), 400
    
    case_context = ""
    if case_id:
        case = Case.query.get(case_id)
        if case:
            case_context = f"""
            Case Number: {case.case_number}
            Title: {case.title}
            Type: {case.case_type}
            Status: {case.status}
            Priority: {case.priority}
            Court: {case.court_name or 'N/A'}
            Next Hearing: {case.next_hearing.strftime('%Y-%m-%d %H:%M') if case.next_hearing else 'Not scheduled'}
            Description: {case.description[:500]}
            """
    
    bot_response = get_gemini_response(user_message, case_context)
    
    chat = ChatHistory(
        user_id=current_user.id,
        message=user_message,
        response=bot_response
    )
    db.session.add(chat)
    db.session.commit()
    
    return jsonify({
        'response': bot_response,
        'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    })

# --- SEARCH ---
@app.route('/search')
@login_required
def search():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for('dashboard'))
    
    if current_user.role == 'lawyer':
        cases = Case.query.filter(
            ((Case.lawyer_id == current_user.id) | (Case.user_id == current_user.id)),
            (Case.title.ilike(f'%{query}%') |
             Case.case_number.ilike(f'%{query}%') |
             Case.description.ilike(f'%{query}%'))
        ).all()
    else:
        cases = Case.query.filter(
            Case.user_id == current_user.id,
            (Case.title.ilike(f'%{query}%') |
             Case.case_number.ilike(f'%{query}%') |
             Case.description.ilike(f'%{query}%'))
        ).all()
    
    return render_template('dashboard.html',
                           cases=cases,
                           total_cases=len(cases),
                           open_cases=sum(1 for c in cases if c.status == 'Open'),
                           in_progress=sum(1 for c in cases if c.status == 'In Progress'),
                           closed_cases=sum(1 for c in cases if c.status == 'Closed'),
                           upcoming_reminders=[],
                           upcoming_hearings=[],
                           search_query=query)


# --- INIT DB ---
with app.app_context():
    db.create_all()
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

if __name__ == '__main__':
    app.run(debug=True, port=5000)