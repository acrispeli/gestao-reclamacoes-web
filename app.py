import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'univesp_secret_key'

# CONFIGURAÇÃO DE PASTAS E ARQUIVOS
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB por envio

# Garante que a pasta de uploads existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# CONFIGURAÇÃO MYSQL (Porta 3307)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:univesp2026@localhost:3307/gestao_reclamacoes'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

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

    # Relacionamento 1 para Muitos: Uma reclamação pode ter várias fotos
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

# --- ROTAS DO CLIENTE ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    if request.method == 'POST':
        nome = request.form.get('nome')
        email = request.form.get('email')
        telefone = request.form.get('telefone')
        produto = request.form.get('produto')
        descricao = request.form.get('descricao')
        
        try:
            # 1. Cria e salva a reclamação para gerar o ID
            nova = Reclamacao(nome, email, telefone, produto, descricao)
            db.session.add(nova)
            db.session.commit()

            # 2. Processa as fotos enviadas
            if 'foto' in request.files:
                arquivos = request.files.getlist('foto')
                for arquivo in arquivos:
                    if arquivo and arquivo.filename != '':
                        # Gera um nome seguro: protocolo_nomeoriginal.ext
                        nome_seguro = secure_filename(f"{nova.codigo_unico}_{arquivo.filename}")
                        caminho_completo = os.path.join(app.config['UPLOAD_FOLDER'], nome_seguro)
                        arquivo.save(caminho_completo)
                        
                        # Salva a referência da foto no banco
                        nova_foto = FotoReclamacao(reclamacao_id=nova.id, caminho_arquivo=nome_seguro)
                        db.session.add(nova_foto)
                
                db.session.commit()

            return render_template('sucesso.html', codigo=nova.codigo_unico)
        except Exception as e:
            db.session.rollback()
            return f"Erro ao processar reclamação: {e}"

@app.route('/consultar', methods=['GET', 'POST'])
def consultar():
    reclamacao = None
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        reclamacao = Reclamacao.query.filter_by(codigo_unico=codigo).first()
        if not reclamacao:
            flash('Código não encontrado. Verifique e tente novamente.')
    return render_template('consultar.html', reclamacao=reclamacao)

# --- ROTAS DO ADMINISTRADOR ---

ADMIN_PASSWORD = "admin_univesp"

@app.route('/admin', methods=['GET', 'POST'])
def admin_painel():
    if request.method == 'POST':
        senha = request.form.get('senha')
        if senha == ADMIN_PASSWORD:
            session['admin_logado'] = True  # "Carimba" a sessão do usuário
            return redirect(url_for('admin_painel'))
        else:
            flash('Senha incorreta!')
            return render_template('admin_login.html')

    # Se for um GET (ou vindo de um redirect), verifica se está logado
    if session.get('admin_logado'):
        reclamacoes = Reclamacao.query.order_by(Reclamacao.data_abertura.desc()).all()
        return render_template('admin_painel.html', reclamacoes=reclamacoes)
    
    return render_template('admin_login.html')

@app.route('/admin/sair')
def admin_logout():
    session.pop('admin_logado', None) # Remove o "carimbo" de acesso
    return redirect(url_for('admin_painel'))

@app.route('/responder/<int:id>', methods=['POST'])
def responder(id):
    reclamacao = Reclamacao.query.get(id)
    resposta = request.form.get('resposta')
    if reclamacao:
        reclamacao.resposta_admin = resposta
        reclamacao.data_resposta = datetime.now()
        reclamacao.status = 'Respondido'
        db.session.commit()
    return redirect(url_for('admin_painel'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # O host='0.0.0.0' libera o acesso para outros dispositivos da rede
    app.run(host='0.0.0.0', port=5000, debug=True)