from app import app, db, Reclamacao

def gerar_testes():
    # Inicia o contexto da aplicação Flask para poder usar o banco de dados
    with app.app_context():
        print("Iniciando a inserção de 20 registros de teste...")
        
        for i in range(1, 21):
            # Cria os dados genéricos dinamicamente
            nome = f"Cliente {i}"
            email = f"cliente{i}@email.com"
            telefone = f"(17) 99999-00{i:02d}"
            produto = f"Pizza Sabor {i}"
            descricao = f"Teste número {i}."
            
            # Instancia o modelo Reclamacao (o __init__ vai gerar a data e o UUID automaticamente)
            nova_reclamacao = Reclamacao(nome, email, telefone, produto, descricao)
            
            # Adiciona à sessão do banco
            db.session.add(nova_reclamacao)
            
        # Confirma e salva tudo no banco de dados Aiven de uma só vez
        db.session.commit()
        print("Sucesso! 20 registros foram adicionados ao banco de dados.")

if __name__ == '__main__':
    gerar_testes()