import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pdfplumber
import docx
from werkzeug.utils import secure_filename
import google.generativeai as genai
from dotenv import load_dotenv
import atexit
import secrets
from datetime import datetime, timedelta
from sqlalchemy.orm import joinedload

# Load environment variables from .env file
load_dotenv()

# Google Gemini API configuration
GOOGLE_API_KEY = "AIzaSyB5xV3D1u5YHJfC7yK4ocXK1LeCMW6GRVE"
genai.configure(api_key=GOOGLE_API_KEY)

# Initialize Gemini model with correct model name
model = genai.GenerativeModel('gemini-1.5-flash-8b')

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///mcq_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "You must be logged in to access this page."
login_manager.login_message_category = "danger"

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Plan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price_pkr = db.Column(db.Integer, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    mcq_limit = db.Column(db.Integer, nullable=False)
    short_limit = db.Column(db.Integer, nullable=False)
    long_limit = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship to Plan
    plan = db.relationship('Plan', backref='subscriptions')

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    amount_pkr = db.Column(db.Integer, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    user_note = db.Column(db.Text)  # For user's transaction ID
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='payments')
    plan = db.relationship('Plan', backref='payments')

class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, resolved
    admin_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='complaints')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database tables
with app.app_context():
    db.create_all()
    
    # Create default plans if they don't exist
    if not Plan.query.first():
        default_plans = [
            Plan(name='Free', price_pkr=0, duration_days=30, mcq_limit=10, short_limit=5, long_limit=2),
            Plan(name='Basic', price_pkr=500, duration_days=30, mcq_limit=50, short_limit=25, long_limit=10),
            Plan(name='Pro', price_pkr=1000, duration_days=30, mcq_limit=100, short_limit=50, long_limit=25),
            Plan(name='Enterprise', price_pkr=2000, duration_days=30, mcq_limit=-1, short_limit=-1, long_limit=-1)
        ]
        db.session.add_all(default_plans)
        db.session.commit()

    # --- Add yearly plans with 2-month discount if not present ---
    # For each paid plan, add a yearly version if not present
    paid_plans = Plan.query.filter(Plan.price_pkr > 0, Plan.duration_days == 30).all()
    for plan in paid_plans:
        yearly_name = f"{plan.name} Yearly"
        yearly_exists = Plan.query.filter_by(name=yearly_name).first()
        if not yearly_exists:
            yearly_plan = Plan(
                name=yearly_name,
                price_pkr=plan.price_pkr * 10,  # 2 months free (10x monthly price)
                duration_days=365,
                mcq_limit=plan.mcq_limit,
                short_limit=plan.short_limit,
                long_limit=plan.long_limit,
                is_active=True
            )
            db.session.add(yearly_plan)
    db.session.commit()

def query_model(prompt):
    try:
        if not prompt:
            print("Empty prompt provided")
            return None
            
        print(f"Sending prompt to Gemini: {prompt[:200]}...")
        response = model.generate_content(prompt)
        print(f"Raw response from Gemini: {response}")
        
        if response and response.text:
            print(f"Generated text: {response.text[:200]}...")
            return response.text
        print("No response text from model")
        return None
    except Exception as e:
        print(f"Error in query_model: {str(e)}")
        return None

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['RESULTS_FOLDER'] = 'results'
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'txt', 'docx'}

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULTS_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_file(file_path):
    ext = file_path.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        with pdfplumber.open(file_path) as pdf:
            text = ''.join([page.extract_text() for page in pdf.pages])
        return text
    elif ext == 'docx':
        doc = docx.Document(file_path)
        text = ' '.join([para.text for para in doc.paragraphs])
        return text
    elif ext == 'txt':
        with open(file_path, 'r') as file:
            return file.read()
    return None

def Question_mcqs_generator(input_text, num_questions, difficulty_level):
    prompt = f"""Generate {num_questions} multiple-choice questions based on this text:

{input_text}

Rules:
1. Format each question exactly like this:
Q) [question]
    A) [option A]
    B) [option B]
    C) [option C]
    D) [option D]
    Answer: [correct option letter]

2. Difficulty level: {difficulty_level}
3. Make sure each question has exactly 4 options.
4. Questions should be clear and concise.
5. Options should be distinct and relevant to the question.
6. Always include the correct answer after the options.
7. Do not include any explanations or additional text."""

    try:
        print(f"Generating {num_questions} MCQs with difficulty {difficulty_level}")
        response = query_model(prompt)
        if not response:
            print("No response from API for MCQs")
            return []
            
        print(f"MCQ Response: {response}")
        
        # Clean up the response
        response = response.strip()
        if response.startswith('Q)'):
            response = response
        elif 'Q)' in response:
            response = response[response.index('Q)'):]
        
        # Extract questions from the response
        questions = []
        current_question = None
        current_options = []
        current_answer = None
        
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('Q)'):
                if current_question and len(current_options) == 4 and current_answer:
                    questions.append({
                        'question': current_question,
                        'options': current_options,
                        'answer': current_answer
                    })
                current_question = line[2:].strip()
                current_options = []
                current_answer = None
            elif line.startswith(('A)', 'B)', 'C)', 'D)')):
                current_options.append(line)
            elif line.startswith('Answer:'):
                current_answer = line[7:].strip()
        
        if current_question and len(current_options) == 4 and current_answer:
            questions.append({
                'question': current_question,
                'options': current_options,
                'answer': current_answer
            })
        
        print(f"Parsed MCQs: {questions}")
        return questions[:num_questions]
        
    except Exception as e:
        print(f"Error in Question_mcqs_generator: {str(e)}")
        return []

def open_ended_questions_generator(input_text, num_questions, difficulty_level, question_type='short'):
    if question_type == 'short':
        prompt = f"""Generate {num_questions} short-answer questions based on this text:

{input_text}

Rules:
1. Format each question exactly like this:
Q) [question]

2. Difficulty level: {difficulty_level}
3. Questions should be answerable in 1-2 sentences.
4. Questions should be clear and specific.
5. Do not include any explanations or additional text."""
    else:  # long questions
        prompt = f"""Generate {num_questions} detailed questions based on this text:

{input_text}

Rules:
1. Format each question exactly like this:
Q) [question]

2. Difficulty level: {difficulty_level}
3. Questions should require detailed answers.
4. Questions should be thought-provoking and comprehensive.
5. Do not include any explanations or additional text."""

    try:
        response = query_model(prompt)
        if not response:
            print("No response from API")
            return []
            
        print(f"{question_type} Response: {response}")
        
        # Clean up the response
        response = response.strip()
        if response.startswith('Q)'):
            response = response
        elif 'Q)' in response:
            response = response[response.index('Q)'):]
        
        questions = []
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('Q)'):
                questions.append(line[2:].strip())
        
        print(f"Parsed {question_type} questions: {questions}")
        return questions[:num_questions]
        
    except Exception as e:
        print(f"Error in open_ended_questions_generator: {str(e)}")
        return []

def generate_questions(input_text, num_mcqs, num_short, num_long, difficulty_level):
    if not input_text:
        print("No input text provided")
        return []
        
    all_questions = []
    
    # Generate MCQs
    if num_mcqs > 0:
        mcq_list = Question_mcqs_generator(input_text, num_mcqs, difficulty_level)
        if mcq_list:
            all_questions.append({
                'type': 'mcq',
                'questions': mcq_list
            })
        else:
            print("Failed to generate MCQs")
    
    # Generate Short Questions
    if num_short > 0:
        short_questions = open_ended_questions_generator(input_text, num_short, difficulty_level, 'short')
        if short_questions:
            short_list = [{'question': q} for q in short_questions]
            all_questions.append({
                'type': 'short',
                'questions': short_list
            })
        else:
            print("Failed to generate short questions")
    
    # Generate Long Questions
    if num_long > 0:
        long_questions = open_ended_questions_generator(input_text, num_long, difficulty_level, 'long')
        if long_questions:
            long_list = [{'question': q} for q in long_questions]
            all_questions.append({
                'type': 'long',
                'questions': long_list
            })
        else:
            print("Failed to generate long questions")
    
    return all_questions

def check_user_limits(user, num_mcqs, num_short, num_long):
    """Check if user has enough limits for the requested questions"""
    # Get user's active subscription
    active_subscription = Subscription.query.filter_by(
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not active_subscription:
        # Free user limits (match the Free plan: MCQs=5, Short=3, Long=1)
        return num_mcqs <= 5 and num_short <= 3 and num_long <= 1
    
    plan = Plan.query.get(active_subscription.plan_id)
    if plan.mcq_limit == -1 and plan.short_limit == -1 and plan.long_limit == -1:
        return True  # Unlimited plan
    
    return (num_mcqs <= plan.mcq_limit and 
            num_short <= plan.short_limit and 
            num_long <= plan.long_limit)

def check_user_export_permission(user):
    """Check if user has permission to export files based on their subscription"""
    # Get user's active subscription
    active_subscription = Subscription.query.filter_by(
        user_id=user.id, 
        is_active=True
    ).first()
    
    if not active_subscription:
        # Free users cannot export
        return False
    
    plan = Plan.query.get(active_subscription.plan_id)
    # Only paid plans (price > 0) can export
    return plan.price_pkr > 0

@app.route('/')
def index():
    plans = Plan.query.filter_by(is_active=True).all()
    return render_template('index.html', plans=plans)

@app.route('/generate', methods=['GET', 'POST'])
@login_required
def generate():
    if request.method == 'POST':
        input_text = request.form.get('input_text', '')
        file = request.files.get('file')
        
        if file and file.filename:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            input_text = extract_text_from_file(file_path)
            os.remove(file_path)
        
        # Handle empty or invalid number inputs
        try:
            num_mcqs = int(request.form.get('num_mcqs', 0) or 0)
            num_short = int(request.form.get('num_short', 0) or 0)
            num_long = int(request.form.get('num_long', 0) or 0)
        except ValueError:
            flash('Invalid number of questions. Please enter valid numbers.', 'danger')
            return redirect(url_for('index'))
        
        # Ensure numbers are non-negative
        num_mcqs = max(0, num_mcqs)
        num_short = max(0, num_short)
        num_long = max(0, num_long)
        
        # Check user limits
        if not check_user_limits(current_user, num_mcqs, num_short, num_long):
            flash('You have exceeded your plan limits. Please upgrade your plan or stay within your current plan limits per request.', 'warning')
            return redirect(url_for('pricing'))
        
        difficulty_level = request.form.get('difficulty_level', 'medium')
        
        if not input_text:
            flash('Please provide text or upload a file.', 'danger')
            return redirect(url_for('index'))
        
        print(f"Input text length: {len(input_text)}")
        print(f"Requested questions: MCQs={num_mcqs}, Short={num_short}, Long={num_long}")
        
        # Check if at least one type of question is requested
        if num_mcqs == 0 and num_short == 0 and num_long == 0:
            flash('Please select at least one type of question to generate.', 'danger')
            return redirect(url_for('index'))
        
        try:
            all_questions = generate_questions(input_text, num_mcqs, num_short, num_long, difficulty_level)
            
            # Get marks per question from form
            marks_per_mcq = int(request.form.get('marks_per_mcq', 1) or 1)
            marks_per_short = int(request.form.get('marks_per_short', 2) or 2)
            marks_per_long = int(request.form.get('marks_per_long', 5) or 5)
            marks_dict = {
                'mcq': marks_per_mcq,
                'short': marks_per_short,
                'long': marks_per_long
            }

            if not all_questions:
                flash('Failed to generate questions. Please try again with a different input or reduce the number of questions.', 'danger')
                return redirect(url_for('index'))
            
            # Check if user has export permission
            can_export = check_user_export_permission(current_user)
            
            return render_template('results.html', all_questions=all_questions, marks_dict=marks_dict, can_export=can_export)
        except Exception as e:
            print(f"Error generating questions: {str(e)}")
            flash('An error occurred while generating questions. Please try again.', 'danger')
            return redirect(url_for('index'))
    
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            # Do not flash login successful message
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('signup.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('signup.html')
        
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/pricing')
def pricing():
    plans = Plan.query.filter_by(is_active=True).all()
    user_subscriptions = []
    user_existing_plans = []
    if current_user.is_authenticated:
        # Get active subscriptions
        user_subscriptions = [sub.plan_id for sub in Subscription.query.filter_by(user_id=current_user.id, is_active=True).all()]
        # Get all existing subscriptions (active or inactive) to prevent duplicate subscriptions
        user_existing_plans = [sub.plan_id for sub in Subscription.query.filter_by(user_id=current_user.id).all()]
    return render_template('pricing.html', plans=plans, user_subscriptions=user_subscriptions, user_existing_plans=user_existing_plans)

@app.route('/subscribe/<int:plan_id>')
@login_required
def subscribe(plan_id):
    # Check for any active subscription for the current user
    active_subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).first()
    if active_subscription:
        flash('You already have an active plan. Please cancel it before subscribing to a new one.', 'warning')
        return redirect(url_for('my_plans'))

    # Check if user already has a subscription to this specific plan (active or inactive)
    existing_subscription = Subscription.query.filter_by(
        user_id=current_user.id, 
        plan_id=plan_id
    ).first()
    
    if existing_subscription:
        flash('You have already subscribed to this plan before. You cannot subscribe to the same plan twice.', 'warning')
        return redirect(url_for('my_plans'))

    plan = Plan.query.get_or_404(plan_id)

    if plan.price_pkr == 0:
        # Free plan logic - no active subscription, so we can subscribe.
        subscription = Subscription(
            user_id=current_user.id,
            plan_id=plan.id,
            end_date=datetime.utcnow() + timedelta(days=plan.duration_days),
            is_active=True
        )
        db.session.add(subscription)
        db.session.commit()
        flash('You have been subscribed to the Free plan!', 'success')
        return redirect(url_for('my_plans')) # Redirect to my_plans
    else:
        # Paid plan logic - no active plan, user can proceed to payment.
        if not current_user.is_authenticated: # This check is redundant with @login_required but safe
            return redirect(url_for('login', next=url_for('subscribe', plan_id=plan_id)))
        return redirect(url_for('payment_instructions', plan_id=plan_id))

@app.route('/payment_instructions/<int:plan_id>')
@login_required
def payment_instructions(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    return render_template('payment_instructions.html', plan=plan)

@app.route('/submit_payment/<int:plan_id>', methods=['POST'])
@login_required
def submit_payment(plan_id):
    plan = Plan.query.get_or_404(plan_id)
    
    # Check if user already has a subscription to this specific plan (active or inactive)
    existing_subscription = Subscription.query.filter_by(
        user_id=current_user.id, 
        plan_id=plan_id
    ).first()
    
    if existing_subscription:
        flash('You have already subscribed to this plan before. You cannot subscribe to the same plan twice.', 'warning')
        return redirect(url_for('pricing'))
    
    user_transaction_id = request.form.get('transaction_id', '').strip()
    if not user_transaction_id:
        flash('Please enter your transaction ID.', 'danger')
        return redirect(url_for('payment_instructions', plan_id=plan_id))
    payment = Payment(
        user_id=current_user.id,
        plan_id=plan.id,
        amount_pkr=plan.price_pkr,
        payment_method='NayaPay',
        transaction_id=f"TXN_{secrets.token_hex(8)}",
        user_note=user_transaction_id,
        status='pending'
    )
    db.session.add(payment)
    db.session.commit()
    flash('Successfully sent! Your plan is pending and will be approved soon after verification.', 'success')
    return redirect(url_for('plan_status'))

@app.route('/plan_status')
@login_required
def plan_status():
    # Get the latest payment for the user
    payment = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.created_at.desc()).first()
    subscription = Subscription.query.filter_by(user_id=current_user.id, is_active=True).order_by(Subscription.created_at.desc()).first()
    return render_template('plan_status.html', payment=payment, subscription=subscription)

@app.route('/admin/approve_payment/<int:payment_id>')
@login_required
def approve_payment(payment_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    payment = Payment.query.get_or_404(payment_id)
    
    # Deactivate any existing active subscriptions for this user
    Subscription.query.filter_by(user_id=payment.user_id, is_active=True).update({"is_active": False})
    
    # Update payment status
    payment.status = 'completed'
    
    # Create new subscription
    subscription = Subscription(
        user_id=payment.user_id,
        plan_id=payment.plan_id,
        end_date=datetime.utcnow() + timedelta(days=payment.plan.duration_days),
        is_active=True
    )
    db.session.add(subscription)
    
    db.session.commit()
    
    flash(f'Payment approved! User subscription activated.', 'success')
    return redirect(url_for('admin_payments'))

@app.route('/admin/reject_payment/<int:payment_id>')
@login_required
def reject_payment(payment_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    payment = Payment.query.get_or_404(payment_id)
    payment.status = 'rejected'
    db.session.commit()
    
    flash(f'Payment rejected.', 'success')
    return redirect(url_for('admin_payments'))

@app.route('/admin/delete_payment/<int:payment_id>', methods=['POST'])
@login_required
def delete_payment(payment_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_payments'))
    payment = Payment.query.get_or_404(payment_id)
    db.session.delete(payment)
    db.session.commit()
    flash('Payment deleted successfully.', 'success')
    return redirect(url_for('admin_payments'))

# Admin routes
@app.route('/admin')
@login_required
def admin_dashboard():
    print(f"Admin dashboard accessed by user: {current_user.email}")
    print(f"User is_admin: {current_user.is_admin}")
    
    if not current_user.is_admin:
        print("Access denied - user is not admin")
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    total_users = User.query.count()
    total_subscriptions = Subscription.query.filter_by(is_active=True).count()
    total_revenue = db.session.query(db.func.sum(Payment.amount_pkr)).filter_by(status='completed').scalar() or 0
    
    print(f"Stats - Users: {total_users}, Subscriptions: {total_subscriptions}, Revenue: {total_revenue}")
    
    return render_template('admin/dashboard.html', 
                         total_users=total_users,
                         total_subscriptions=total_subscriptions,
                         total_revenue=total_revenue)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/plans')
@login_required
def admin_plans():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    plans = Plan.query.all()
    return render_template('admin/plans.html', plans=plans)

@app.route('/admin/payments')
@login_required
def admin_payments():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    # Start with a base query
    query = Payment.query.join(User).join(Plan)

    # Get filter criteria from request args
    user_email = request.args.get('user_email', '').strip()
    plan_id = request.args.get('plan_id', type=int)
    status = request.args.get('status', '').strip()
    
    # Apply filters
    if user_email:
        query = query.filter(User.email.ilike(f'%{user_email}%'))
    if plan_id:
        query = query.filter(Payment.plan_id == plan_id)
    if status:
        query = query.filter(Payment.status == status)

    payments = query.order_by(Payment.created_at.desc()).all()
    
    # Get all plans for the filter dropdown
    plans = Plan.query.all()
    
    return render_template('admin/payments.html', payments=payments, plans=plans)

@app.route('/my_plans')
@login_required
def my_plans():
    # Get all subscriptions for the current user
    subscriptions = Subscription.query.filter_by(user_id=current_user.id).order_by(Subscription.created_at.desc()).all()
    
    # Get all pending, rejected, and cancelled payments for the user
    pending_payments = Payment.query.filter(
        Payment.user_id == current_user.id,
        Payment.status.in_(['pending', 'rejected', 'cancelled'])
    ).order_by(Payment.created_at.desc()).all()

    # Eagerly load plan for each subscription and determine status
    for sub in subscriptions:
        sub.plan = Plan.query.get(sub.plan_id)
        if sub.is_active:
            if sub.end_date < datetime.utcnow():
                sub.status = "Expired"
                # Also update the database
                sub.is_active = False
            else:
                sub.status = "Active"
        else:
            sub.status = "Cancelled"
    
    # Commit any status changes for expired plans
    db.session.commit()
            
    return render_template('my_plans.html', subscriptions=subscriptions, pending_payments=pending_payments)

@app.route('/cancel_subscription/<int:sub_id>', methods=['POST'])
@login_required
def cancel_subscription(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_plans'))
    sub.is_active = False
    db.session.commit()
    flash('Subscription cancelled.', 'success')
    return redirect(url_for('my_plans'))

@app.route('/delete_payment_history/<int:payment_id>', methods=['POST'])
@login_required
def delete_payment_history(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_plans'))
    
    db.session.delete(payment)
    db.session.commit()
    flash('Payment history deleted.', 'success')
    return redirect(url_for('my_plans'))

@app.route('/cancel_payment/<int:payment_id>', methods=['POST'])
@login_required
def cancel_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_plans'))
    
    # Only allow cancelling pending payments
    if payment.status != 'pending':
        flash('Only pending payments can be cancelled.', 'warning')
        return redirect(url_for('my_plans'))
    
    # Change status to cancelled instead of deleting
    payment.status = 'cancelled'
    db.session.commit()
    flash('Payment cancelled successfully.', 'success')
    return redirect(url_for('my_plans'))

@app.route('/delete_subscription_history/<int:sub_id>', methods=['POST'])
@login_required
def delete_subscription_history(sub_id):
    sub = Subscription.query.get_or_404(sub_id)
    if sub.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_plans'))
    
    # Prevent deleting an active subscription
    if sub.is_active:
        flash('Cannot delete an active subscription.', 'warning')
        return redirect(url_for('my_plans'))

    db.session.delete(sub)
    db.session.commit()
    flash('Subscription history deleted.', 'success')
    return redirect(url_for('my_plans'))

@app.route('/my_complaints', methods=['GET'])
@login_required
def my_complaints():
    complaints = Complaint.query.filter_by(user_id=current_user.id).order_by(Complaint.created_at.desc()).all()
    return render_template('my_complaints.html', complaints=complaints)

@app.route('/submit_complaint', methods=['POST'])
@login_required
def submit_complaint():
    content = request.form.get('content', '').strip()
    if not content:
        flash('Complaint cannot be empty.', 'complaint')
        return redirect(url_for('my_complaints'))
    complaint = Complaint(user_id=current_user.id, content=content)
    db.session.add(complaint)
    db.session.commit()
    flash('Complaint submitted successfully.', 'complaint')
    return redirect(url_for('my_complaints'))

@app.route('/delete_complaint/<int:complaint_id>', methods=['POST'])
@login_required
def delete_complaint(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    if complaint.user_id != current_user.id:
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('my_complaints'))
    
    db.session.delete(complaint)
    db.session.commit()
    flash('Complaint deleted successfully.', 'success')
    return redirect(url_for('my_complaints'))

@app.route('/admin/complaints')
@login_required
def admin_complaints():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    complaints = Complaint.query.options(joinedload(Complaint.user)).order_by(Complaint.created_at.desc()).all()
    print(f"Admin complaints found: {len(complaints)}")
    for c in complaints:
        print(f"Complaint: {c.id}, user: {c.user.name}, content: {c.content}")
    return render_template('admin/complaints.html', complaints=complaints)

@app.route('/admin/respond_complaint/<int:complaint_id>', methods=['POST'])
@login_required
def admin_respond_complaint(complaint_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    complaint = Complaint.query.get_or_404(complaint_id)
    response = request.form.get('admin_response', '').strip()
    if not response:
        flash('Response cannot be empty.', 'danger')
        return redirect(url_for('admin_complaints'))
    complaint.admin_response = response
    db.session.commit()
    flash('Response sent to user.', 'success')
    return redirect(url_for('admin_complaints'))

@app.route('/admin/resolve_complaint/<int:complaint_id>', methods=['POST'])
@login_required
def admin_resolve_complaint(complaint_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    complaint = Complaint.query.get_or_404(complaint_id)
    complaint.status = 'resolved'
    db.session.commit()
    flash('Complaint marked as resolved.', 'success')
    return redirect(url_for('admin_complaints'))

@app.route('/admin/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_users'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form['name']
        user.email = request.form['email']
        user.is_admin = 'is_admin' in request.form
        db.session.commit()
        flash('User updated.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/edit_user.html', user=user)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_users'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/create_plan', methods=['GET', 'POST'])
@login_required
def admin_create_plan():
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_plans'))
    if request.method == 'POST':
        plan = Plan(
            name=request.form['name'],
            price_pkr=int(request.form['price_pkr']),
            duration_days=int(request.form['duration_days']),
            mcq_limit=int(request.form['mcq_limit']),
            short_limit=int(request.form['short_limit']),
            long_limit=int(request.form['long_limit']),
            is_active='is_active' in request.form
        )
        db.session.add(plan)
        db.session.commit()
        flash('Plan created.', 'success')
        return redirect(url_for('admin_plans'))
    return render_template('admin/edit_plan.html', plan=None)

@app.route('/admin/edit_plan/<int:plan_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_plan(plan_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_plans'))
    plan = Plan.query.get_or_404(plan_id)
    if request.method == 'POST':
        plan.name = request.form['name']
        plan.price_pkr = int(request.form['price_pkr'])
        plan.duration_days = int(request.form['duration_days'])
        plan.mcq_limit = int(request.form['mcq_limit'])
        plan.short_limit = int(request.form['short_limit'])
        plan.long_limit = int(request.form['long_limit'])
        plan.is_active = 'is_active' in request.form
        db.session.commit()
        flash('Plan updated.', 'success')
        return redirect(url_for('admin_plans'))
    return render_template('admin/edit_plan.html', plan=plan)

@app.route('/admin/delete_plan/<int:plan_id>', methods=['POST'])
@login_required
def admin_delete_plan(plan_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_plans'))
    plan = Plan.query.get_or_404(plan_id)
    db.session.delete(plan)
    db.session.commit()
    flash('Plan deleted.', 'success')
    return redirect(url_for('admin_plans'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('No user found with that email.', 'danger')
            return redirect(url_for('forgot_password'))
        # For demo/dev: redirect to reset form directly (no email)
        return redirect(url_for('reset_password', user_id=user.id))
    return render_template('forgot_password.html')

@app.route('/reset_password/<int:user_id>', methods=['GET', 'POST'])
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password or new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('reset_password', user_id=user_id))
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Password reset successful. You can now log in.', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html', user=user)

@app.route('/admin/reset_password/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_reset_password(user_id):
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('admin_users'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not new_password or new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('admin_reset_password', user_id=user_id))
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        flash('Password reset for user.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('admin/reset_password.html', user=user)

if __name__ == "__main__":
    app.run(debug=True)