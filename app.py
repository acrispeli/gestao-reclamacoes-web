import os
import smtplib
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy

# Carrega as variáveis do arquivo .env (Local) ou Environment do Render
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chave_padrao_pizzaria_2026')

# --- CONFIGURAÇÃO CLOUDINARY ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'), 
    api_key = os.environ.get('CLOUDINARY_API_KEY'), 
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# --- CONFIGURAÇÃO BANCO DE DADOS (AIVEN COM SSL) ---
path_to_ca = os.path.join(os.getcwd(), 'ca.pem')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {
        "ssl": {"ca": path_to_ca}
    }
}

db = SQLAlchemy(app)

# --- FUNÇÃO AUXILIAR: ENVIO DE E-MAIL (BREVO) ---
def enviar_email(destinatario, assunto, corpo_html):
    server_smtp = os.environ.get('SMTP_SERVER')
    port_smtp = int(os.environ.get('SMTP_PORT', 587))
    user_smtp = os.environ.get('SMTP_USER')
    pass_smtp = os.environ.get('SMTP_PASS')
    remetente = os.environ.get('EMAIL_REMETENTE')

    try:
        msg = MIMEMultipart()
        msg['From'] = f"Pizzaria XYZ <{remetente}>"
        msg['To'] = destinatario
        msg['Subject'] = assunto
        msg.attach(MIMEText(corpo_html, 'html'))

        with smtplib.SMTP(server_smtp, port_smtp) as server:
            server.starttls()
            server.login(user_smtp, pass_smtp)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False

# --- MODELOS ---
class Reclamacao(db.Model):
    __tablename__ = 'reclamacoes'
    id = db.Column(db.Integer, primary_key=True)
    codigo_unico = db.Column(db.String(36), unique=True, nullable=False)
    nome_cliente = db.Column(db.String(100), nullable=False)
    email_cliente = db.Column(db.String(100), nullable=False)
    telefone_cliente = db.Column(db.String(20), nullable=False)
    produto_servico = db.Column(db.String(100), nullable=False)
    descricao_problema = db.Column(db.Text, nullable=False)
    data_abertura = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default='Pendente')
    resposta_admin = db.Column(db.Text, nullable=True)
    data_resposta = db.Column(db.DateTime, nullable=True)
    fotos = db.relationship('FotoReclamacao', backref='reclamacao', lazy=True)

    def __init__(self, nome_cliente, email_cliente, telefone_cliente, produto_servico, descricao_problema):
        self.nome_cliente = nome_cliente
        self.email_cliente = email_cliente
        self.telefone_cliente = telefone_cliente
        self.produto_servico = produto_servico
        self.descricao_problema = descricao_problema
        self.codigo_unico = str(uuid.uuid4())[:8]

class FotoReclamacao(db.Model):
    __tablename__ = 'fotos_reclamacao'
    id = db.Column(db.Integer, primary_key=True)
    reclamacao_id = db.Column(db.Integer, db.ForeignKey('reclamacoes.id'), nullable=False)
    caminho_arquivo = db.Column(db.String(255), nullable=False)

# --- ROTAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    nome = request.form.get('nome')
    email = request.form.get('email')
    telefone = request.form.get('telefone')
    produto = request.form.get('produto')
    descricao = request.form.get('descricao')
    
    try:
        nova = Reclamacao(nome, email, telefone, produto, descricao)
        db.session.add(nova)
        db.session.commit()

        if 'foto' in request.files:
            arquivos = request.files.getlist('foto')
            for arquivo in arquivos:
                if arquivo and arquivo.filename != '':
                    upload_result = cloudinary.uploader.upload(arquivo, folder="reclamacoes_pizzaria")
                    nova_foto = FotoReclamacao(reclamacao_id=nova.id, caminho_arquivo=upload_result['secure_url'])
                    db.session.add(nova_foto)
            db.session.commit()

        # DISPARO DE E-MAIL: CONFIRMAÇÃO DE PROTOCOLO
        assunto = f"Atendimento Pizzaria - Protocolo: {nova.codigo_unico}"
        corpo = f"""
            <h3>Olá, {nome}!</h3>
            <p>Sua solicitação foi registrada com sucesso!</p>
            <p><strong>Seu Protocolo:</strong> {nova.codigo_unico}</p>
            <p>Utilize este código para consultar o status do seu atendimento em nosso site.</p>
        """
        enviar_email(email, assunto, corpo)

        return render_template('sucesso.html', codigo=nova.codigo_unico)
    except Exception as e:
        db.session.rollback()
        return f"Erro ao processar: {e}"

@app.route('/consultar', methods=['GET', 'POST'])
def consultar():
    reclamacao = None
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        reclamacao = Reclamacao.query.filter_by(codigo_unico=codigo).first()
        if not reclamacao:
            flash('Código não encontrado.')
    return render_template('consultar.html', reclamacao=reclamacao)

@app.route('/admin', methods=['GET', 'POST'])
def admin_painel():
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin_padrao')
    if request.method == 'POST':
        if request.form.get('senha') == admin_pass:
            session['admin_logado'] = True
            return redirect(url_for('admin_painel'))
        flash('Senha incorreta!')
    
    if session.get('admin_logado'):
        reclamacoes = Reclamacao.query.order_by(Reclamacao.data_abertura.desc()).all()
        return render_template('admin_painel.html', reclamacoes=reclamacoes)
    return render_template('admin_login.html')

@app.route('/responder/<int:id>', methods=['POST'])
def responder(id):
    if not session.get('admin_logado'): return redirect(url_for('admin_painel'))
    
    reclamacao = Reclamacao.query.get(id)
    if reclamacao:
        resposta = request.form.get('resposta')
        reclamacao.resposta_admin = resposta
        reclamacao.data_resposta = datetime.now()
        reclamacao.status = 'Respondido'
        db.session.commit()

        # DISPARO DE E-MAIL: NOTIFICAÇÃO DE RESPOSTA
        assunto = f"Resposta à sua solicitação - Protocolo: {reclamacao.codigo_unico}"
        corpo = f"""
            <h3>Olá, {reclamacao.nome_cliente}!</h3>
            <p>Sua solicitação foi analisada pela nossa equipe.</p>
            <p><strong>Resposta da Administração:</strong> {resposta}</p>
            <p>Agradecemos seu feedback, ele é essencial para nossa melhoria contínua.</p>
        """
        enviar_email(reclamacao.email_cliente, assunto, corpo)

    return redirect(url_for('admin_painel'))

@app.route('/admin/sair')
def admin_logout():
    session.pop('admin_logado', None)
    return redirect(url_for('admin_painel'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)