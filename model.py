import sqlite3
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash


# Configuração do Banco de Dados
DB_NAME = "lumina_beauty.db"


def get_db_connection():
    """Conecta ao banco de dados SQLite e retorna linhas como dicionários."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Cria todas as tabelas do sistema, incluindo Pedidos e Itens."""
    conn = get_db_connection()
    cursor = conn.cursor()
   
    # 1. Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            senha_plana TEXT,
            papel TEXT DEFAULT 'cliente',
            telefone TEXT,
            endereco TEXT
        )
    ''')

    # 2. Produtos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            descricao TEXT,
            imagem TEXT,
            estoque INTEGER DEFAULT 0,
            categoria TEXT
        )
    ''')


    # --- NOVAS TABELAS ---

    # 3. Pedidos (O Cabeçalho da Compra)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            data_pedido DATETIME DEFAULT CURRENT_TIMESTAMP,
            valor_total REAL NOT NULL,
            status TEXT DEFAULT 'Pago',  -- Ex: Pendente, Pago, Enviado
            metodo_pagamento TEXT,       -- Ex: Pix, Cartão
            endereco_entrega TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # 4. Itens do Pedido (Os detalhes do que foi comprado)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS itens_pedido (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            preco_unitario REAL NOT NULL, -- Importante: Preço no momento da compra
            FOREIGN KEY(pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY(produto_id) REFERENCES produtos(id)
        )
    ''')
   
    # Cria Admin Padrão se não existir
    cursor.execute('SELECT count(*) FROM users')
    if cursor.fetchone()[0] == 0:
        senha_hash = generate_password_hash('123')
        cursor.execute('''
            INSERT INTO users (nome, username, email, senha, senha_plana, papel)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ('Administrador', 'admin', 'admin@lumina.com', senha_hash, '123', 'admin'))

    conn.commit()
    conn.close()


# --- FUNÇÕES DE PRODUTO (CRUD) ---


def get_all_produtos():
    conn = get_db_connection()
    produtos = conn.execute('SELECT * FROM produtos').fetchall()
    conn.close()
    return [dict(p) for p in produtos]


def get_produtos_by_categoria(categoria):
    conn = get_db_connection()
    produtos = conn.execute('SELECT * FROM produtos WHERE categoria = ?', (categoria,)).fetchall()
    conn.close()
    return [dict(p) for p in produtos]


def get_produto_by_id(id):
    conn = get_db_connection()
    produto = conn.execute('SELECT * FROM produtos WHERE id = ?', (id,)).fetchone()
    conn.close()
    return dict(produto) if produto else None


def add_produto(nome, preco, descricao, imagem, estoque, categoria):
    conn = get_db_connection()
    # Se não vier imagem, coloca uma padrão
    if not imagem: imagem = 'https://placehold.co/400x300/E0D0D4/6B4950?text=Sem+Imagem'
    conn.execute('''
        INSERT INTO produtos (nome, preco, descricao, imagem, estoque, categoria)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (nome, preco, descricao, imagem, estoque, categoria))
    conn.commit()
    conn.close()


def update_produto(id, nome, preco, descricao, imagem, estoque, categoria):
    conn = get_db_connection()
    try:
        if imagem:
            conn.execute('''
                UPDATE produtos SET nome=?, preco=?, descricao=?, imagem=?, estoque=?, categoria=? WHERE id=?
            ''', (nome, preco, descricao, imagem, estoque, categoria, id))
        else:
            conn.execute('''
                UPDATE produtos SET nome=?, preco=?, descricao=?, estoque=?, categoria=? WHERE id=?
            ''', (nome, preco, descricao, estoque, categoria, id))
        conn.commit()
        conn.close()
        return True
    except Exception:
        conn.close()
        return False


def delete_produto(id):
    conn = get_db_connection()
    cursor = conn.execute('DELETE FROM produtos WHERE id = ?', (id,))
    conn.commit()
    sucesso = cursor.rowcount > 0
    conn.close()
    return sucesso


# --- FUNÇÕES DE USUÁRIO ---


def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(user) if user else None


def get_user_by_id(id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (id,)).fetchone()
    conn.close()
    return dict(user) if user else None


def baixar_estoque(produto_id, quantidade):
    """Diminui a quantidade do estoque de um produto."""
    conn = get_db_connection()
    try:
        # Verifica estoque atual
        atual = conn.execute('SELECT estoque FROM produtos WHERE id = ?', (produto_id,)).fetchone()
        if atual and atual['estoque'] >= quantidade:
            conn.execute('UPDATE produtos SET estoque = estoque - ? WHERE id = ?', (quantidade, produto_id))
            conn.commit()
            return True
        return False
    except Exception as e:
        print(f"Erro ao baixar estoque: {e}")
        return False
    finally:
        conn.close()

def add_user(nome, username, email, senha):
    conn = get_db_connection()
    cursor = conn.cursor()
    senha_hash = generate_password_hash(senha)
    try:
        cursor.execute('''
            INSERT INTO users (nome, username, email, senha, senha_plana, papel)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nome, username, email, senha_hash, senha, 'cliente'))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return get_user_by_id(user_id)
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_user(id, nome, email, telefone=None, endereco=None):
    """Atualiza dados do usuário (nome, email, telefone e endereço). Username NÃO muda."""
    conn = get_db_connection()
    
    # Verifica se o email já está sendo usado por outro usuário
    email_test = conn.execute('SELECT id FROM users WHERE email = ? AND id != ?', (email, id)).fetchone()
    if email_test:
        conn.close()
        return False, "Esse e-mail já está em uso."
    
    # Atualiza os dados (SEM mexer no username)
    conn.execute('''
        UPDATE users 
        SET nome=?, email=?, telefone=?, endereco=? 
        WHERE id=?
    ''', (nome, email, telefone, endereco, id))
    
    conn.commit()
    conn.close()
    return True, "Dados atualizados com sucesso!"


def change_password(user_id, old_password, new_password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return False, "Utilizador não encontrado."
    check = check_password_hash(user['senha'], old_password) or user['senha_plana'] == old_password
    if not check:
        conn.close()
        return False, "Senha antiga incorreta."
    novo_hash = generate_password_hash(new_password)
    conn.execute('UPDATE users SET senha=?, senha_plana=? WHERE id=?', (novo_hash, new_password, user_id))
    conn.commit()
    conn.close()
    return True, "Senha alterada com sucesso!"


def reset_password_by_email(email, new_password):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not user:
        conn.close()
        return False, "E-mail não encontrado."
    novo_hash = generate_password_hash(new_password)
    conn.execute('UPDATE users SET senha=?, senha_plana=? WHERE email=?', (novo_hash, new_password, email))
    conn.commit()
    conn.close()
    return True, "Senha redefinida com sucesso!"


def delete_user(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    return True


# --- LÓGICA DE AUTENTICAÇÃO ---


def login_required(roles=None):
    if roles is None:
        roles = []
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Você precisa fazer login para acessar esta página.', 'warning')
                return redirect(url_for('login'))
            user_papel = session.get('user_papel')
            if roles and user_papel not in roles:
                flash(f'Acesso negado. Você precisa ser {", ".join(roles)}.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def registrar_pedido(user_id, carrinho, total_venda, metodo, endereco):
    """
    Salva o pedido e os itens no banco de dados de uma só vez.
    Retorna o ID do pedido se der certo.
    """
    conn = get_db_connection()
    try:
        # 1. Cria o registro na tabela PEDIDOS
        cursor = conn.execute('''
            INSERT INTO pedidos (user_id, valor_total, status, metodo_pagamento, endereco_entrega)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, total_venda, 'Pago', metodo, endereco))
        
        pedido_id = cursor.lastrowid # Pega o ID gerado (ex: Pedido #10)

        # 2. Cria os registros na tabela ITENS_PEDIDO
        for item in carrinho:
            conn.execute('''
                INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, preco_unitario)
                VALUES (?, ?, ?, ?)
            ''', (pedido_id, item['id'], item['quantidade'], item['preco']))

        conn.commit()
        return pedido_id
    except Exception as e:
        print(f"Erro ao registrar pedido: {e}")
        conn.rollback() # Desfaz se der erro no meio
        return None
    finally:
        conn.close()

def get_meus_pedidos(user_id):
    """Lista o histórico de compras de um usuário."""
    conn = get_db_connection()
    pedidos = conn.execute('SELECT * FROM pedidos WHERE user_id = ? ORDER BY data_pedido DESC', (user_id,)).fetchall()
    conn.close()
    return [dict(p) for p in pedidos]


# --- INICIALIZAÇÃO ---
init_db()