from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

app = Flask(__name__)

# Configuração do Banco de Dados (será criado um arquivo chamado 'gestao.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gestao.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Definição da Tabela de Reclamações (Baseada na ISO 10002)
class Reclamacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_unico = db.Column(db.String(36), unique=True, nullable=False) # Exigência da Norma
    nome_cliente = db.Column(db.String(100), nullable=False)
    produto_servico = db.Column(db.String(100), nullable=False)
    descricao_problema = db.Column(db.Text, nullable=False)
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Aberto') # Aberto, Em Análise, Resolvido

    def __init__(self, nome_cliente, produto_servico, descricao_problema):
        self.nome_cliente = nome_cliente
        self.produto_servico = produto_servico
        self.descricao_problema = descricao_problema
        self.codigo_unico = str(uuid.uuid4())[:8] # Gera um código curto e único

@app.route('/')
def index():
    return "<h1>Banco de Dados Configurado!</h1><p>A estrutura da ISO 10002 já está no código.</p>"

if __name__ == '__main__':
    app.run(debug=True)