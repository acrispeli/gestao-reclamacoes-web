from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

app = Flask(__name__)
app.secret_key = 'univesp_secret_key'

# CONFIGURAÇÃO MYSQL (Porta 3307)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:univesp2026@localhost:3307/gestao_reclamacoes'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelo atualizado com campos de resposta
class Reclamacao(db.Model):
    __tablename__ = 'reclamacoes'
    id = db.Column(db.Integer, primary_key=True)
    codigo_unico = db.Column(db.String(36), unique=True, nullable=False)
    nome_cliente = db.Column(db.String(100), nullable=False)
    produto_servico = db.Column(db.String(100), nullable=False)
    descricao_problema = db.Column(db.Text, nullable=False)
    data_abertura = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default='Pendente')
    
    # NOVOS CAMPOS PARA O ADMIN
    resposta_admin = db.Column(db.Text, nullable=True)
    data_resposta = db.Column(db.DateTime, nullable=True)

    def __init__(self, nome_cliente, produto_servico, descricao_problema):
        self.nome_cliente = nome_cliente
        self.produto_servico = produto_servico
        self.descricao_problema = descricao_problema
        self.codigo_unico = str(uuid.uuid4())[:8]

# --- ROTAS DO CLIENTE ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/cadastrar', methods=['POST'])
def cadastrar():
    nome = request.form.get('nome')
    produto = request.form.get('produto')
    descricao = request.form.get('descricao')
    nova = Reclamacao(nome, produto, descricao)
    db.session.add(nova)
    db.session.commit()
    return render_template('sucesso.html', codigo=nova.codigo_unico)

@app.route('/consultar', methods=['GET', 'POST'])
def consultar():
    reclamacao = None
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        reclamacao = Reclamacao.query.filter_by(codigo_unico=codigo).first()
        if not reclamacao:
            flash('Código não encontrado. Verifique e tente novamente.')
    return render_template('consultar.html', reclamacao=reclamacao)

# --- ROTAS DO ADMINISTRADOR (Protegidas) ---

ADMIN_PASSWORD = "admin_univesp" # Senha simples para o protótipo do PI

@app.route('/admin', methods=['GET', 'POST'])
def admin_painel():
    # Verifica se a senha foi enviada via formulário ou sessão
    senha = request.form.get('senha')
    if senha == ADMIN_PASSWORD:
        reclamacoes = Reclamacao.query.order_by(Reclamacao.data_abertura.desc()).all()
        return render_template('admin_painel.html', reclamacoes=reclamacoes)
    
    return render_template('admin_login.html')

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
    # Cria os novos campos no MySQL automaticamente
    with app.app_context():
        db.create_all()
    app.run(debug=True)