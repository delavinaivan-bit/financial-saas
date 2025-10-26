# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import stripe
import tu_script  # script de generación y envío de emails
import markdown

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
    
    # Credenciales básicas
    email = db.Column(db.String(200), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    # === Configuración SMTP por usuario ===
    smtp_email = db.Column(db.String(200), nullable=True)                # correo remitente (desde el que se enviarán informes)
    smtp_password = db.Column(db.String(300), nullable=True)             # contraseña de aplicación o token SMTP
    smtp_server = db.Column(db.String(120), default='smtp.gmail.com')    # servidor SMTP (por defecto Gmail)
    smtp_port = db.Column(db.Integer, default=587)                       # puerto TLS típico (587)

    # === Stripe / suscripciones ===
    stripe_customer_id = db.Column(db.String(200), nullable=True)
    stripe_subscription_id = db.Column(db.String(200), nullable=True)
    subscription_status = db.Column(db.String(50), default='inactive')   # inactive | active | cancelled

    # === Relaciones ===
    listas = db.relationship('EmailList', backref='user', cascade='all, delete-orphan')

    # === Métodos de utilidad ===
    def set_password(self, pw):
        """Genera y guarda el hash seguro de la contraseña del usuario."""
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        """Verifica si una contraseña ingresada coincide con el hash guardado."""
        return check_password_hash(self.password_hash, pw)

    def __repr__(self):
        return f"<User id={self.id} email={self.email}>"


class EmailList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contactos = db.relationship('EmailContact', backref='lista', cascade='all, delete-orphan')

@app.route('/smtp_config', methods=['GET', 'POST'])
@login_required
def smtp_config():
    if request.method == 'POST':
        # Guardar valores del formulario
        current_user.smtp_email = request.form.get('smtp_email', '').strip() or None
        current_user.smtp_server = request.form.get('smtp_server', '').strip() or 'smtp.gmail.com'
        try:
            current_user.smtp_port = int(request.form.get('smtp_port', 587))
        except Exception:
            current_user.smtp_port = 587

        pwd = request.form.get('smtp_password', '').strip()
        if pwd:  # solo actualiza si escribes algo
            current_user.smtp_password = pwd  # (más adelante lo ciframos si quieres)

        db.session.commit()
        flash("SMTP settings saved ✅")
        return redirect(url_for('dashboard'))

    # GET: mostrar formulario
    return render_template('smtp_config.html')


class EmailContact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), nullable=False)
    lista_id = db.Column(db.Integer, db.ForeignKey('email_list.id'), nullable=False)

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
    return redirect(url_for('login'))

# ---------- DASHBOARD (PROTECTED) ----------
@app.route('/dashboard', methods=['GET','POST'])
@login_required
def dashboard():
    if current_user.subscription_status != 'active':
        # Usuario sin suscripción → mostrar pantalla de pago
        return render_template(
            'subscribe_prompt.html',
            publishable_key=os.environ.get('STRIPE_PUBLISHABLE_KEY')
        )

    if request.method == 'POST':
        transcript_text = request.form.get('transcript')
        modo = request.form.get('modo', '0')
        informe_md = tu_script.generar_informe_financiero_desde_texto(transcript_text, modo)

        # ✅ convertir aquí de Markdown a HTML
        informe_html = markdown.markdown(informe_md, extensions=['extra'])

        # ✅ pasamos HTML limpio al template
        listas = EmailList.query.filter_by(user_id=current_user.id).all()
        return render_template('result.html', informe=informe_html, listas=listas)

    return render_template('dashboard.html')

# ---------- EMAIL LISTS ----------
@app.route('/email_lists', methods=['GET', 'POST'])
@login_required
def email_lists():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        if nombre:
            nueva_lista = EmailList(nombre=nombre, user_id=current_user.id)
            db.session.add(nueva_lista)
            db.session.commit()
    listas = EmailList.query.filter_by(user_id=current_user.id).all()
    return render_template('email_lists.html', listas=listas)

@app.route('/add_contact/<int:lista_id>', methods=['POST'])
@login_required
def add_contact(lista_id):
    """Permite añadir contactos a una lista por formulario clásico o vía JSON (AJAX)."""
    lista = EmailList.query.filter_by(id=lista_id, user_id=current_user.id).first_or_404()

    # Si viene como JSON (desde fetch)
    if request.is_json:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip()
        if not email:
            return jsonify({'ok': False, 'error': 'Email required'}), 400

        nuevo_contacto = EmailContact(email=email, lista_id=lista.id)
        db.session.add(nuevo_contacto)
        db.session.commit()
        return jsonify({'ok': True, 'contact': {'id': nuevo_contacto.id, 'email': nuevo_contacto.email}}), 200

    # Si viene del formulario HTML tradicional
    email = request.form.get('email', '').strip()
    if email:
        nuevo_contacto = EmailContact(email=email, lista_id=lista.id)
        db.session.add(nuevo_contacto)
        db.session.commit()

    return redirect(url_for('email_lists'))


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
    return redirect(url_for('dashboard'))

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
    return redirect(url_for('login'))

# ---------- SEND EMAIL ----------
@app.route('/send_email', methods=['POST'])
@login_required
def send_email_route():
    if current_user.subscription_status != 'active':
        return "<h2>Subscription required</h2>", 403

    lista_id = request.form.get('lista_id')
    emails = []

    if lista_id:
        lista = EmailList.query.filter_by(id=lista_id, user_id=current_user.id).first()
        if lista:
            emails = [c.email for c in lista.contactos]
    else:
        destinatario = request.form.get('email')
        if destinatario:
            emails = [destinatario]

    informe = request.form.get('informe')
    if not emails:
        return "<h2>Error: no recipient email(s)</h2>", 400

    for e in emails:
        tu_script.enviar_email(e, "Your Financial Report", informe)

    return "<h2>Sent ✅</h2>"

# ---------- MAIN ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

