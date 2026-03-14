from flask import Flask

app = Flask(__name__)

# Rota principal (Página inicial)
@app.route('/')
def index():
    return "<h1>Sistema de Gestão de Reclamações - ISO 10002</h1><p>Status: Protótipo em desenvolvimento.</p>"

if __name__ == '__main__':
    app.run(debug=True)