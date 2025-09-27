# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import tu_script  # tu script de generación y envío de emails

# ---------- CONFIG ----------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-key'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')

# ---------- MODELS ----------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    stripe_customer_id = db.Column(db.String(200), nullable=True)
    stripe_subscription_id = db.Column(db.String(200), nullable=True)
    subscription_status = db.Column(db.String(50), default='inactive')  # inactive | active | cancelled

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------- AUTH ROUTES ----------
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        pw = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered')
            return redirect(url_for('register'))
        u = User(email=email)
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        login_user(u)
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        pw = request.form['password']
        u = User.query.filter_by(email=email).first()
        if u and u.check_password(pw):
            login_user(u)
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---------- DASHBOARD (PROTECTED) ----------
@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():
    if current_user.subscription_status != 'active':
        # Redirige a pantalla de suscripción
        return render_template('subscribe_prompt.html', publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY'))

    if request.method == 'POST':
        transcript_text = request.form.get('transcript')
        modo = request.form.get('modo', '0')
        informe = tu_script.generar_informe_financiero_desde_texto(transcript_text, modo)
        return render_template('result.html', informe=informe)

    return render_template('dashboard.html')

# ---------- STRIPE CHECKOUT ----------
@app.route('/create-checkout-session', methods=['POST'])
@login_required
def create_checkout_session():
    price_id = os.environ.get('STRIPE_PRICE_ID')
    domain = request.host_url.rstrip('/')
    try:
        if not current_user.stripe_customer_id:
            customer = stripe.Customer.create(email=current_user.email)
            current_user.stripe_customer_id = customer['id']
            db.session.commit()
        session = stripe.checkout.Session.create(
            customer=current_user.stripe_customer_id,
            success_url=domain + url_for('dashboard'),
            cancel_url=domain + url_for('dashboard'),
            payment_method_types=['card'],
            mode='subscription',
            line_items=[{'price': price_id, 'quantity': 1}],
        )
        return jsonify({'id': session.id})
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route('/success')
@login_required
def success():
    return render_template('success.html')

# ---------- STRIPE WEBHOOK ----------
@app.route('/webhook', methods=['POST'])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

    if event['type'] == 'invoice.paid':
        invoice = event['data']['object']
        sub_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.stripe_subscription_id = sub_id
            user.subscription_status = 'active'
            db.session.commit()
    if event['type'] in ('customer.subscription.deleted','customer.subscription.updated'):
        sub = event['data']['object']
        customer_id = sub.get('customer')
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.subscription_status = sub.get('status') or 'cancelled'
            user.stripe_subscription_id = sub.get('id')
            db.session.commit()
    return jsonify({'status': 'ok'})

# ---------- HOME ----------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# ---------- SEND EMAIL (PROTECTED) ----------
@app.route('/send_email', methods=['POST'])
@login_required
def send_email_route():
    if current_user.subscription_status != 'active':
        return "<h2>Subscription required</h2>", 403
    destinatario = request.form.get('email') or os.environ.get('EMAIL_DESTINO')
    informe = request.form.get('informe')
    tu_script.enviar_email(destinatario, "Your Financial Report", informe)
    return "<h2>Sent</h2>"

# ---------- MAIN ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # solo para desarrollo; usar migraciones en producción
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

