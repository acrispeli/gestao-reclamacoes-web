import os
import uuid
import threading
from datetime import datetime

import pytz
import cloudinary
import cloudinary.uploader
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)

# --- CONFIGURAÇÃO DE FUSO HORÁRIO (Brasília) ---
fuso_horario = pytz.timezone('America/Sao_Paulo')

# --- SEGURANÇA E CONFIGURAÇÃO FLASK ---
app.secret_key = os.environ.get('SECRET_KEY', 'pizzaria_xyz_2026_safe')

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,  
    SESSION_COOKIE_SAMESITE='Lax',
)

# --- CONFIGURAÇÃO BREVO API v3 ---
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = os.environ.get('BREVO_API_KEY')

# --- CONFIGURAÇÃO CLOUDINARY ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'), 
    api_key = os.environ.get('CLOUDINARY_API_KEY'), 
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# --- CONFIGURAÇÃO BANCO DE DADOS (AIVEN) ---
# Usando dirname para garantir que encontre o ca.pem independente de onde o Render inicie o app
path_to_ca = os.path.join(os.path.dirname(__file__), 'ca.pem')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "connect_args": {"ssl": {"ca": path_to_ca}}
}

db = SQLAlchemy(app)

# --- FUNÇÃO DE ENVIO VIA BREVO API ---
def enviar_email(destinatario, assunto, corpo_html):
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    remetente_email = os.environ.get('EMAIL_REMETENTE')
    remetente = {"name": "Atendimento Pizzaria", "email": remetente_email}
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": destinatario}],
        html_content=corpo_html,
        sender=remetente,
        subject=assunto
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
    except ApiException as e:
        print(f"Erro na API do Brevo: {e}")

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
    data_abertura = db.Column(db.DateTime, default=lambda: datetime.now(fuso_horario))
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
        self.data_abertura = datetime.now(fuso_horario)

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

        assunto = f"Atendimento Pizzaria - Protocolo: {nova.codigo_unico}"
        corpo = f"<h3>Olá, {nome}!</h3><p>Sua solicitação foi registrada: <strong>{nova.codigo_unico}</strong></p>"
        threading.Thread(target=enviar_email, args=(email, assunto, corpo)).start()

        return redirect(url_for('pagina_sucesso', codigo=nova.codigo_unico))
    except Exception as e:
        db.session.rollback()
        return f"Erro: {e}"

@app.route('/sucesso/<codigo>')
def pagina_sucesso(codigo):
    return render_template('sucesso.html', codigo=codigo)

@app.route('/consultar', methods=['GET', 'POST'])
def consultar():
    reclamacao = None
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        reclamacao = Reclamacao.query.filter_by(codigo_unico=codigo).first()
    return render_template('consultar.html', reclamacao=reclamacao)

@app.route('/admin', methods=['GET', 'POST'])
def admin_painel():
    erro = None
    
    # 1. TRATAMENTO DO LOGIN (POST) - Quando o admin aperta o botão "Entrar"
    if request.method == 'POST':
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'mude_isso_no_render')
        if request.form.get('senha') == admin_pass:
            session['admin_logado'] = True
            return redirect(url_for('admin_painel'))
        else:
            erro = "Senha Incorreta. Tente novamente."
            
    # 2. VERIFICAÇÃO DE SEGURANÇA (GET ou POST com senha errada)
    if not session.get('admin_logado'):
        # MUDEI AQUI: Agora ele carrega o arquivo 'admin_login.html' que você criou!
        return render_template('admin_login.html', erro=erro) 

    # 3. SÓ EXECUTA A BUSCA NO BANCO SE ESTIVER LOGADO E COM SUCESSO
    quantidade_por_pagina = request.args.get('per_page', 20, type=int)
    page_num = request.args.get('page', 1, type=int)
    
    pagination = Reclamacao.query.order_by(Reclamacao.data_abertura.desc()).paginate(
        page=page_num, 
        per_page=quantidade_por_pagina
    )
    
    return render_template('admin_painel.html', pagination=pagination)

@app.route('/responder/<int:id>', methods=['POST'])
def responder(id):
    if not session.get('admin_logado'): return redirect(url_for('admin_painel'))
    reclamacao = Reclamacao.query.get(id)
    if reclamacao:
        resposta = request.form.get('resposta')
        reclamacao.resposta_admin = resposta
        reclamacao.data_resposta = datetime.now(fuso_horario)
        reclamacao.status = 'Respondido'
        db.session.commit()
    return redirect(url_for('admin_painel'))

@app.route('/logout')
def admin_logout():
    # Usando clear() é mais seguro, ele limpa qualquer vestígio do usuário na sessão
    session.clear() 
    return redirect(url_for('admin_painel'))

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))