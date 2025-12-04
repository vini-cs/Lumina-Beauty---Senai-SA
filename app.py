# /Lumina_Beauty_MVC/app.py

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from collections import Counter
import copy
import model  # Importa nosso arquivo model.py
from werkzeug.security import check_password_hash
import secrets
from string import ascii_letters, digits, punctuation
import re

# Bibliotecas para o QR Code
import qrcode
import io
import base64

app = Flask(__name__)
app.secret_key = 'chave_sereta_lumina'

# --- (CONTROLLER) FUNÇÕES AUXILIARES ---


@app.context_processor
def inject_user_info():
    """Injeta informações do usuário e contagem do carrinho em todos os templates."""
    total_itens = session.get('total_itens_badge', 0)

    if 'user_id' in session:
        return {
            'user_info': {
                'logado': True,
                'nome': session.get('user_nome', 'Usuário'),
                'papel': session.get('user_papel', 'cliente')
            },
            'total_itens_carrinho': total_itens
        }
    return {
        'user_info': {'logado': False},
        'total_itens_carrinho': total_itens
    }


# --- (CONTROLLER) FUNÇÕES AUXILIARES ---

# --- (CONTROLLER) FUNÇÕES AUXILIARES ---

def calcular_total_carrinho(carrinho):
    """Calcula o valor total (R$) do carrinho."""
    # PROTEÇÃO: Se carrinho não for uma lista (ex: None ou int), retorna 0
    if not carrinho or not isinstance(carrinho, list):
        return 0

    total = 0
    
    # --- A CORREÇÃO ESTÁ AQUI ---
    # NÃO use carrinho.values(). Use apenas carrinho:
    for item in carrinho:
        if isinstance(item, dict) and 'preco' in item and 'quantidade' in item:
            total += item['preco'] * item['quantidade']
            
    return total


def calcular_total_itens(carrinho):
    """Calcula a quantidade total de itens (unidades) no carrinho."""
    # PROTEÇÃO
    if not carrinho or not isinstance(carrinho, list):
        return 0

    # --- A CORREÇÃO ESTÁ AQUI ---
    # NÃO use carrinho.values(). Use apenas carrinho:
    return sum(item['quantidade'] for item in carrinho if isinstance(item, dict) and 'quantidade' in item)


# Dicionário de simulação de frete por prefixo de CEP (região)
FRETE_REGIOES = {
    '88': 12.50,  # SC (Ex: Florianópolis)
    '89': 10.00,  # SC (Ex: Joinville/Blumenau)
    '01': 18.00,  # SP (Capital)
    '02': 18.00,  # SP (Capital)
    '20': 22.00,  # RJ (Capital)
    '69': 45.00,  # AM (Manaus)
}
FRETE_PADRAO = 25.00  # Resto do Brasil

# --- (CONTROLLER) API DE BUSCA (NOVO) ---

# --- ADICIONE ISTO NO FINAL DO SEU app.py ---


@app.route('/api/buscar_produtos')
def api_buscar_produtos():
    query = request.args.get('q', '').lower()

    # Se a busca for vazia, retorna lista vazia
    if not query:
        return jsonify([])

    # Tenta buscar os produtos de forma segura
    todos_produtos = []
    try:
        # Tenta pegar todos de uma vez (se existir essa função no seu model)
        if hasattr(model, 'get_produtos'):
            todos_produtos = model.get_produtos()
        elif hasattr(model, 'get_all_produtos'):
            todos_produtos = model.get_all_produtos()
        else:
            # Plano B: Busca categoria por categoria (AGORA COM pinceis E skincare)
            categorias = ['rosto', 'olhos', 'labios', 'kits', 'pinceis', 'skincare']
            for cat in categorias:
                lista = model.get_produtos_by_categoria(cat)
                if lista:
                    todos_produtos.extend(lista)
    except Exception as e:
        print(f"Erro ao buscar no banco: {e}")
        return jsonify([])

    # Filtra os produtos pelo termo digitado (Nome ou Categoria)
    resultados = []
    ids_vistos = set()

    for p in todos_produtos:
        # Verifica se o termo está no nome ou na categoria
        termo_no_nome = query in p['nome'].lower()
        termo_na_cat = 'categoria' in p and query in str(
            p['categoria']).lower()

        if (termo_no_nome or termo_na_cat) and p['id'] not in ids_vistos:
            resultados.append({
                'id': p['id'],
                'nome': p['nome'],
                'preco': p['preco'],
                'imagem': p['imagem'],
                'categoria': p.get('categoria', 'Produto')
            })
            ids_vistos.add(p['id'])

    return jsonify(resultados)


# --- (CONTROLLER) ROTAS PÚBLICAS (VISÃO DO CLIENTE) ---

@app.route('/')
def index():
    produtos_todos = model.get_all_produtos()
    return render_template('index.html', produtos=produtos_todos)


@app.route('/categoria/<string:nome_categoria>')
def categoria_produtos(nome_categoria):
    # 1. Conecta ao banco e busca TODOS os produtos da categoria primeiro
    conn = model.get_db_connection()
    # Usa 'lower()' para garantir que ache 'cabelos' mesmo se buscar 'Cabelos'
    produtos_db = conn.execute('SELECT * FROM produtos WHERE LOWER(categoria) = ?', (nome_categoria.lower(),)).fetchall()
    conn.close()

    # Transforma em lista de dicionários para podermos filtrar no Python
    produtos = [dict(p) for p in produtos_db]

    # --- LÓGICA DE FILTROS ---
    
    # 2. Captura os dados da URL (o que vem do formulário)
    min_price = request.args.get('min')
    max_price = request.args.get('max')
    estoque_only = request.args.get('estoque') # Vem 'on' se marcado
    sort_by = request.args.get('sort')

    # 3. Filtro de Preço Mínimo
    if min_price and min_price.strip():
        try:
            valor_min = float(min_price)
            produtos = [p for p in produtos if p['preco'] >= valor_min]
        except ValueError:
            pass # Se o usuário digitou letra no preço, ignora

    # 4. Filtro de Preço Máximo
    if max_price and max_price.strip():
        try:
            valor_max = float(max_price)
            produtos = [p for p in produtos if p['preco'] <= valor_max]
        except ValueError:
            pass

    # 5. Filtro de Estoque (Apenas disponíveis)
    if estoque_only == 'on':
        produtos = [p for p in produtos if p['estoque'] > 0]

    # 6. Ordenação
    if sort_by == 'menor_preco':
        produtos.sort(key=lambda x: x['preco']) # Do menor pro maior
    elif sort_by == 'maior_preco':
        produtos.sort(key=lambda x: x['preco'], reverse=True) # Do maior pro menor
    elif sort_by == 'az':
        produtos.sort(key=lambda x: x['nome'].lower()) # A-Z
    elif sort_by == 'za':
        produtos.sort(key=lambda x: x['nome'].lower(), reverse=True) # Z-A

    # --- FIM DA LÓGICA ---

    # Para manter os valores no formulário depois de recarregar a página
    filtros_atuais = {
        'min': min_price,
        'max': max_price,
        'estoque': estoque_only,
        'sort': sort_by
    }

    return render_template(
        'produtos.html', 
        produtos=produtos, 
        titulo_categoria=nome_categoria,
        filtros=filtros_atuais
    )


@app.route('/contato')
def contato():
    return render_template('Contacto.html')


@app.route('/novidades')
def novidades():
    return render_template('novidades.html')


@app.route('/promocoes')
def promocoes():
    return render_template('promocoes.html')


@app.route('/quiz')
def quiz():
    return render_template('quiz.html')

@app.route('/avaliacoes')
def avaliacoes():
    # Página de Avaliações dos Clientes
    return render_template('avaliacoes.html')

# --- (CONTROLLER) ROTAS DE AUTENTICAÇÃO ---


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        senha = request.form.get('senha', '').strip()

        print(
            f"DEBUG: Tentativa de login - username: {username}, senha: {senha}")

        user = model.get_user_by_username(username)

        if user:
            print(f"DEBUG: Usuário encontrado: {user['username']}")
            print(f"DEBUG: Senha hasheada armazenada: {user['senha']}")
            print(
                f"DEBUG: Senha plana armazenada: {user.get('senha_plana', 'NÃO ENCONTRADA')}")

            # TENTA VALIDAR COM HASH
            if check_password_hash(user['senha'], senha):
                print(f"DEBUG: Login com HASH bem-sucedido")
                session['user_id'] = user['id']
                session['user_nome'] = user['nome']
                session['user_papel'] = user['papel']
                flash(f'Bem-vindo(a) de volta, {user["nome"]}!', 'success')

                if user['papel'] == 'admin':
                    return redirect(url_for('admin_produtos'))
                return redirect(url_for('index'))

            # SE HASH FALHAR, TENTA VALIDAR COM SENHA PLANA (como fallback)
            elif user.get('senha_plana') == senha:
                print(f"DEBUG: Login com SENHA PLANA bem-sucedido")
                session['user_id'] = user['id']
                session['user_nome'] = user['nome']
                session['user_papel'] = user['papel']
                flash(f'Bem-vindo(a) de volta, {user["nome"]}!', 'success')

                if user['papel'] == 'admin':
                    return redirect(url_for('admin_produtos'))
                return redirect(url_for('index'))
            else:
                print(
                    f"DEBUG: Falha de autenticação - Hash check: False, Plana check: False")
                flash('Usuário ou senha inválidos.', 'danger')
        else:
            print(f"DEBUG: Usuário não encontrado: {username}")
            flash('Usuário ou senha inválidos.', 'danger')

    return render_template('login.html')


@app.route('/registrar', methods=['GET', 'POST'])
def registrar_cliente():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nome = request.form['nome']
        username = request.form['username']
        email = request.form['email']
        senha = request.form['senha']

        # --- VALIDAÇÃO 1: SENHA MÍNIMA ---
        if len(senha) < 6:
            flash('A senha deve ter no mínimo 6 caracteres.', 'danger')
            return render_template('registro.html') # Retorna para manter os dados (exceto senha)

        # --- VALIDAÇÃO 2: FORMATO DE EMAIL ---
        # Regex simples para validar email (ex: texto@texto.texto)
        email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_regex, email):
            flash('Por favor, insira um endereço de e-mail válido.', 'danger')
            return render_template('registro.html')

        # Verificações de duplicidade (Existente)
        if model.get_user_by_username(username):
            flash('Este nome de usuário já está em uso.', 'danger')
            return redirect(url_for('registrar_cliente'))
            
        if model.get_user_by_email(email):
            flash('Este email já está cadastrado.', 'danger')
            return redirect(url_for('registrar_cliente'))

        # Cria o usuário
        novo_usuario = model.add_user(nome, username, email, senha)
        
        session['user_id'] = novo_usuario['id']
        session['user_nome'] = novo_usuario['nome']
        session['user_papel'] = novo_usuario['papel']
        flash('Registro realizado com sucesso!', 'success')
        return redirect(url_for('index'))
        
    return render_template('registro.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Você saiu da sua conta.', 'info')
    return redirect(url_for('index'))


@app.route('/recuperar_senha', methods=['GET', 'POST'])
def recuperar_senha():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        user = model.get_user_by_email(email)

        if user:
            # Recupera a senha em texto plano
            senha_real = user.get('senha_plana', '')

            # Salva na sessão
            session['temp_password'] = senha_real
            session['temp_password_email'] = email
            session['temp_password_nome'] = user['nome']

            flash(f"Senha recuperada com sucesso!", 'success')
            return redirect(url_for('senha_revelada'))
        else:
            flash(
                "Se este e-mail estiver registado, simularemos o envio de um link de recuperação.", 'success')
            return redirect(url_for('simulacao_email_enviado', email=email))

    return render_template('recuperar_senha.html')


@app.route('/simulacao_email/<email>')
def simulacao_email_enviado(email):
    user = model.get_user_by_email(email)
    return render_template('simulacao_email.html', user=user, email=email)


@app.route('/resetar_senha/<email>', methods=['GET', 'POST'])
def resetar_senha(email):
    if 'user_id' in session:
        return redirect(url_for('index'))

    user = model.get_user_by_email(email)
    if not user:
        flash("Utilizador não encontrado ou link inválido.", "danger")
        return redirect(url_for('recuperar_senha'))

    if request.method == 'POST':
        nova_senha = request.form.get('nova_senha')
        confirmar_senha = request.form.get('confirmar_senha')

        # --- VALIDAÇÃO ---
        if len(nova_senha) < 6:
            flash("A senha deve ter no mínimo 6 caracteres.", "danger")
            return render_template('resetar_senha.html', email=email)

        if nova_senha != confirmar_senha:
            flash("As senhas não coincidem.", "danger")
            return render_template('resetar_senha.html', email=email)

        sucesso, mensagem = model.reset_password_by_email(email, nova_senha)
        if sucesso:
            flash(mensagem, 'success')
            return redirect(url_for('login'))
        else:
            flash(mensagem, 'danger')

    return render_template('resetar_senha.html', email=email)


@app.route('/minha_conta', methods=['GET', 'POST'])
@model.login_required()
def minha_conta():
    user_id = session['user_id']

    if request.method == 'POST':
        form_type = request.form.get('form_type')

        if form_type == 'update_profile':
            nome = request.form.get('nome')
            email = request.form.get('email')
            telefone = request.form.get('telefone')
            endereco = request.form.get('endereco')

            # --- VALIDAÇÃO EMAIL ---
            email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_regex, email):
                flash('Endereço de e-mail inválido.', 'danger')
                return redirect(url_for('minha_conta'))

            sucesso, mensagem = model.update_user(user_id, nome, email, telefone, endereco)

            if sucesso:
                session['user_nome'] = nome
                flash(mensagem, 'success')
            else:
                flash(mensagem, 'danger')

        elif form_type == 'change_password':
            senha_antiga = request.form.get('senha_antiga')
            nova_senha = request.form.get('nova_senha')
            confirmar_senha = request.form.get('confirmar_senha')

            # --- VALIDAÇÃO SENHA NOVA ---
            if len(nova_senha) < 6:
                flash('A nova senha deve ter no mínimo 6 caracteres.', 'danger')
                return redirect(url_for('minha_conta'))

            if nova_senha != confirmar_senha:
                flash("As novas senhas não coincidem.", "danger")
            else:
                sucesso, mensagem = model.change_password(
                    user_id, senha_antiga, nova_senha)
                if sucesso:
                    flash(mensagem, 'success')
                else:
                    flash(mensagem, 'danger')

        return redirect(url_for('minha_conta'))

    user = model.get_user_by_id(user_id)
    return render_template('minha_conta.html', user=user)


@app.route('/excluir_conta', methods=['POST'])
@model.login_required()
def excluir_conta():
    user_id = session['user_id']
    user = model.get_user_by_id(user_id)

    # Bloqueia exclusão se for admin
    if user and user['papel'] == 'admin':
        flash("Administradores não podem remover suas contas.", "danger")
        return redirect(url_for('minha_conta'))

    model.delete_user(user_id)
    session.clear()
    flash("A sua conta foi removida com sucesso. Sentiremos sua falta!", "success")
    return redirect(url_for('index'))

# --- (CONTROLLER) ROTAS DO CARRINHO E CHECKOUT ---


@app.route('/carrinho')
@model.login_required(roles=['cliente'])
def ver_carrinho():
    carrinho = session.get('carrinho', [])
    if not isinstance(carrinho, list):
        carrinho = []
        session['carrinho'] = carrinho

    total_carrinho = calcular_total_carrinho(carrinho)
    session['total_carrinho'] = total_carrinho
    session['total_itens_badge'] = calcular_total_itens(carrinho)

    # Limpeza se vazio
    if not carrinho:
        session.pop('frete', None)
        session.pop('frete_label', None)

    # --- LÓGICA DE FRETE BLINDADA ---
    if total_carrinho > 250.00:
        session['frete'] = 0
        session['frete_label'] = 'Frete Grátis'
    elif session.get('frete_label') == 'Frete Grátis':
        # Se chegou aqui é porque o total é <= 250 mas o label ainda diz Grátis.
        # Precisamos remover!
        session.pop('frete', None)
        session.pop('frete_label', None)

    frete = session.get('frete', 0)
    frete_label = session.get('frete_label', '(a calcular)')
    total_com_frete = total_carrinho + frete

    return render_template('carrinho.html',
                           carrinho=carrinho,
                           total=total_carrinho,
                           frete=frete,
                           frete_label=frete_label,
                           total_com_frete=total_com_frete,
                           step='carrinho')


@app.route('/adicionar_carrinho/<int:id>', methods=['POST'])
@model.login_required(roles=['cliente'])
def adicionar_carrinho(id):
    print(f"--- TENTATIVA DE ADICIONAR PRODUTO ID: {id} ---")
    
    # 1. Recupera Produto
    produto_db = model.get_produto_by_id(id)
    if not produto_db:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('index'))

    # Se alguém tentar forçar a adição via URL mesmo estando zerado:
    if produto_db['estoque'] <= 0:
        flash(f"Desculpe, o produto '{produto_db['nome']}' acabou de esgotar!", "danger")
        return redirect(request.referrer or url_for('index'))

    # 3. Prepara Carrinho
    carrinho = session.get('carrinho', [])
    if not isinstance(carrinho, list): 
        carrinho = []

    quantidade = int(request.form.get('quantidade', 1))
    print(f"Quantidade solicitada: {quantidade}")

    # 4. Verifica duplicidade e adiciona
    item_carrinho = next((i for i in carrinho if i['id'] == id), None)

    if item_carrinho:
        if (item_carrinho['quantidade'] + quantidade) > produto_db['estoque']:
            flash(f"Estoque insuficiente.", "warning")
        else:
            item_carrinho['quantidade'] += quantidade
            flash(f"Atualizado para {item_carrinho['quantidade']} unidades!", "success")
    else:
        # ATENÇÃO: Removi a descrição para economizar espaço no cookie
        novo_item = {
            'id': produto_db['id'],
            'nome': produto_db['nome'],
            'preco': produto_db['preco'],
            # 'imagem': produto_db['imagem'], 
            'estoque': produto_db['estoque'],
            'quantidade': quantidade
        }
        carrinho.append(novo_item)
        flash(f"'{produto_db['nome']}' adicionado!", "success")

    # 5. Tenta Salvar
    try:
        session['carrinho'] = carrinho
        session['total_itens_badge'] = calcular_total_itens(carrinho)
        session.modified = True
        print(f"SUCESSO: Carrinho atualizado. Total itens: {len(carrinho)}")
    except Exception as e:
        print(f"ERRO AO SALVAR SESSÃO: {e}")

    # Redireciona direto para o carrinho para confirmar visualmente
    return redirect(url_for('ver_carrinho'))


@app.route('/atualizar_quantidade/<int:id>/<acao>')
@model.login_required(roles=['cliente'])
def atualizar_quantidade(id, acao):
    carrinho = session.get('carrinho', [])
    if not isinstance(carrinho, list):
        return redirect(url_for('ver_carrinho'))

    for item in carrinho:
        if item['id'] == id:
            if acao == 'aumentar':
                # Verifica estoque (simples)
                if item['quantidade'] < item.get('estoque', 999): 
                    item['quantidade'] += 1
                else:
                    flash(f"Estoque máximo atingido!", "warning")
            elif acao == 'diminuir':
                item['quantidade'] -= 1
                if item['quantidade'] < 1:
                    item['quantidade'] = 1 # Mínimo 1
            break
    
    session['carrinho'] = carrinho
    
    # Força o recálculo imediato
    total_atual = calcular_total_carrinho(carrinho)
    session['total_carrinho'] = total_atual
    session['total_itens_badge'] = calcular_total_itens(carrinho)
    
    # --- CORREÇÃO DA LÓGICA DE FRETE ---
    # Se baixou de 250 e estava grátis, remove o benefício
    if total_atual <= 250.00 and session.get('frete_label') == 'Frete Grátis':
        session.pop('frete', None)
        session.pop('frete_label', None)
        flash("O valor total diminuiu. O frete grátis foi removido.", "info")
    
    return redirect(url_for('ver_carrinho'))


@app.route('/remover_carrinho/<int:id>', methods=['POST'])
@model.login_required(roles=['cliente'])
def remover_carrinho(id):
    carrinho = session.get('carrinho', [])
    if not isinstance(carrinho, list):
        carrinho = []
    
    # Filtra mantendo apenas quem NÃO tem o ID removido
    novo_carrinho = [item for item in carrinho if item['id'] != id]
    
    session['carrinho'] = novo_carrinho
    session['total_carrinho'] = calcular_total_carrinho(novo_carrinho)
    session['total_itens_badge'] = calcular_total_itens(novo_carrinho)
    
    flash("Item removido.", "info")
    return redirect(url_for('ver_carrinho'))


@app.route('/calcular_frete', methods=['POST'])
@model.login_required(roles=['cliente'])
def calcular_frete():
    cep = request.form.get('cep', '').strip()
    total_carrinho = session.get('total_carrinho', 0)

    if total_carrinho > 250.00:
        session['frete'] = 0
        session['frete_label'] = 'Frete Grátis'
        flash("Você ganhou Frete Grátis!", "success")
        return redirect(url_for('ver_carrinho'))

    cep_limpo = cep.replace('-', '').replace('.', '')

    if not cep_limpo.isdigit() or len(cep_limpo) != 8:
        flash("Coloque um cep existente (formato inválido).", "danger")
        session.pop('frete', None)
        session.pop('frete_label', None)
        return redirect(url_for('ver_carrinho'))

    if cep_limpo == '00000000' or cep_limpo == '99999999':
        flash("Coloque um cep existente (CEP não encontrado).", "danger")
        session.pop('frete', None)
        session.pop('frete_label', None)
        return redirect(url_for('ver_carrinho'))

    prefixo = cep_limpo[0:2]
    frete_simulado = FRETE_REGIOES.get(prefixo, FRETE_PADRAO)

    session['frete'] = frete_simulado
    session['frete_label'] = f"R$ {frete_simulado:.2f}"
    flash(f"Frete calculado para {cep}: R$ {frete_simulado:.2f}", "success")

    return redirect(url_for('ver_carrinho'))


@app.route('/checkout/pagamento')
@model.login_required(roles=['cliente'])
def checkout_pagamento():
    carrinho = session.get('carrinho', {})
    if not carrinho:
        flash("Seu carrinho está vazio.", "warning")
        return redirect(url_for('ver_carrinho'))

    if session.get('frete_label', '(a calcular)') == '(a calcular)':
        flash("Por favor, calcule o frete antes de continuar.", "warning")
        return redirect(url_for('ver_carrinho'))

    total_carrinho = session.get('total_carrinho', 0)
    frete = session.get('frete', 0)
    total_final = total_carrinho + frete
    session['total_final'] = total_final

    return render_template('pagamento.html', total=total_final, step='pagamento')


@app.route('/checkout/pagar_pix')
@model.login_required(roles=['cliente'])
def pagar_pix():
    total = session.get('total_final', 0)
    if total <= 0:
        flash("Não há nada a pagar.", "warning")
        return redirect(url_for('ver_carrinho'))

    pix_key = f"000201260014br.gov.bcb.pix2500...simulacao...{total}"

    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(pix_key)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_data = buf.getvalue()
    qr_code_base64 = base64.b64encode(img_data).decode('utf-8')

    return render_template('pagar_pix.html',
                           total=total,
                           step='pagamento',
                           pix_key=pix_key,
                           qr_code_base64=qr_code_base64)


@app.route('/pagamento/cartao', methods=['GET', 'POST'])
@model.login_required(roles=['cliente'])
def pagamento_cartao():
    carrinho = session.get('carrinho', [])
    if not carrinho:
        return redirect(url_for('index'))

    subtotal = sum(item['preco'] * item['quantidade'] for item in carrinho)
    frete = session.get('frete', 0)
    total_final = subtotal + frete

    if request.method == 'POST':
        user_id = session.get('user_id')
        
        # Busca endereço
        user_data = model.get_user_by_id(user_id)
        endereco_destino = user_data['endereco'] if user_data and user_data['endereco'] else "Endereço não cadastrado"

        # SALVA NO BANCO
        pedido_id = model.registrar_pedido(
            user_id=user_id,
            carrinho=carrinho,
            total_venda=total_final,
            metodo='Cartão de Crédito',
            endereco=endereco_destino
        )

        if pedido_id:
            # Baixa estoque e limpa sessão
            for item in carrinho:
                model.baixar_estoque(item['id'], item['quantidade'])
            
            session.pop('carrinho', None)
            session.pop('frete', None)
            session['total_itens_badge'] = 0
            
            # Redireciona para Meus Pedidos ou Confirmação
            flash(f"Compra realizada com sucesso! Pedido #{pedido_id}", "success")
            return redirect(url_for('meus_pedidos'))
        else:
            flash("Erro ao processar pagamento.", "danger")

    return render_template('pagamento_cartao.html', total_final=total_final)
    
    
@app.route('/checkout/confirmacao')
@model.login_required(roles=['cliente'])
def checkout_confirmacao():
    """Finaliza o pedido via PIX e salva no banco."""
    
    # 1. Validações Básicas
    carrinho = session.get('carrinho', [])
    user_id = session.get('user_id')
    
    if not carrinho:
        return redirect(url_for('index'))

    # 2. Prepara dados para salvar
    subtotal = sum(item['preco'] * item['quantidade'] for item in carrinho)
    frete = session.get('frete', 0)
    total_final = subtotal + frete
    
    # Busca endereço do usuário para constar no pedido
    user_data = model.get_user_by_id(user_id)
    endereco_destino = user_data['endereco'] if user_data and user_data['endereco'] else "Endereço não cadastrado"

    # 3. SALVA NO BANCO DE DADOS
    pedido_id = model.registrar_pedido(
        user_id=user_id,
        carrinho=carrinho,
        total_venda=total_final,
        metodo='Pix',
        endereco=endereco_destino
    )

    if pedido_id:
        # 4. Sucesso: Baixa Estoque e Limpa Sessão
        for item in carrinho:
            model.baixar_estoque(item['id'], item['quantidade'])
            
        session.pop('carrinho', None)
        session.pop('frete', None)
        session['total_itens_badge'] = 0
        
        # Renderiza a página de sucesso mostrando o número do pedido
        return render_template('confirmacao.html', pedido_id=pedido_id)
    
    else:
        flash("Erro ao registrar o pedido. Tente novamente.", "danger")
        return redirect(url_for('pagar_pix'))

# --- (CONTROLLER) ROTAS DE ADMIN ---


@app.route('/admin/produtos', methods=['GET', 'POST'])
@model.login_required(roles=['admin'])
def admin_produtos():
    if request.method == 'POST':
        try:
            nome = request.form['nome']
            preco = float(request.form['preco'])
            estoque = int(request.form['estoque'])
            categoria = request.form['categoria']
            descricao = request.form['descricao']
            imagem = request.form['imagem']

            model.add_produto(nome, preco, descricao,
                              imagem, estoque, categoria)
            flash(f"Produto '{nome}' adicionado com sucesso!", "success")
        except ValueError:
            flash("Preço e Estoque devem ser números válidos.", "danger")

        return redirect(url_for('admin_produtos'))

    produtos = model.get_all_produtos()
    return render_template('admin_produtos.html', produtos=produtos)


@app.route('/admin/editar_produto/<int:id>', methods=['GET', 'POST'])
@model.login_required(roles=['admin'])
def editar_produto(id):
    produto = model.get_produto_by_id(id)
    if not produto:
        flash("Produto não encontrado.", "danger")
        return redirect(url_for('admin_produtos'))

    if request.method == 'POST':
        try:
            nome = request.form['nome']
            preco = float(request.form['preco'])
            estoque = int(request.form['estoque'])
            categoria = request.form['categoria']
            descricao = request.form['descricao']
            imagem = request.form['imagem']

            model.update_produto(id, nome, preco, descricao,
                                 imagem, estoque, categoria)

            flash(f"Produto '{nome}' atualizado com sucesso!", "success")
            return redirect(url_for('admin_produtos'))

        except ValueError:
            flash("Preço e Estoque devem ser números válidos.", "danger")
            return render_template('editar_produto.html', produto=produto)

    return render_template('editar_produto.html', produto=produto)


@app.route('/admin/excluir_produto/<int:id>', methods=['POST'])
@model.login_required(roles=['admin'])
def excluir_produto(id):
    produto = model.get_produto_by_id(id)
    if produto:
        model.delete_produto(id)
        flash(f"Produto '{produto['nome']}' excluído com sucesso.", "success")
    else:
        flash("Produto não encontrado.", "danger")
    return redirect(url_for('admin_produtos'))

@app.route('/admin/produtos/deletar-todos', methods=['POST'])
@model.login_required(roles=['admin'])
def deletar_todos_produtos():
    try:
        # Conecta ao banco de dados
        conn = model.get_db_connection()
        
        # Deleta todos os produtos
        conn.execute('DELETE FROM produtos')
        conn.commit()
        conn.close()
        
        flash('Todos os produtos foram deletados com sucesso!', 'success')
        
    except Exception as e:
        flash(f'Erro ao deletar produtos: {str(e)}', 'danger')
        print(f"Erro ao deletar produtos: {e}")
    
    return redirect(url_for('admin_produtos'))


@app.route('/produto/<int:id>')
def ver_produto(id):
    # Busca o produto pelo ID (usando a função que já existe no model)
    produto = model.get_produto_by_id(id)
    
    if not produto:
        flash("Produto não encontrado.", "warning")
        return redirect(url_for('index'))
        
    return render_template('detalhes_produto.html', produto=produto)


def gerar_senha_temporaria(comprimento=12):
    """Gera uma senha temporária forte."""
    caracteres = ascii_letters + digits + \
        punctuation.replace("'", "").replace('"', '')
    return ''.join(secrets.choice(caracteres) for _ in range(comprimento))


@app.route('/senha_revelada')
def senha_revelada():
    """Mostra a senha real do usuário."""

    # Recupera os dados da sessão
    senha_real = session.get('temp_password', '')
    email = session.get('temp_password_email', '')
    nome = session.get('temp_password_nome', 'Usuário')

    if not senha_real or not email:
        flash("Sessão expirada. Tente novamente.", "warning")
        return redirect(url_for('recuperar_senha'))

    # Passa os dados para o template senharevelada.html
    return render_template('senharevelada.html',
                           senha=senha_real,
                           nome=nome,
                           email=email)

@app.route('/meus_pedidos')
@model.login_required(roles=['cliente'])
def meus_pedidos():
    """Lista todas as compras do usuário logado."""
    user_id = session['user_id']
    lista_pedidos = model.get_meus_pedidos(user_id)
    return render_template('meus_pedidos.html', pedidos=lista_pedidos)

@app.route('/pedido/<int:pedido_id>')
@model.login_required(roles=['cliente'])
def detalhes_pedido(pedido_id):
    """(Opcional) Mostra os itens de um pedido específico."""
    # Nota: Você precisaria criar uma função 'get_itens_pedido' no model 
    # se quiser ver os detalhes (shampoo, batom) deste pedido específico.
    # Por enquanto, vamos apenas renderizar uma página simples ou redirecionar.
    return "Detalhes do pedido em construção..."
    
@app.route('/sobre')
def sobre():
    # Sobre do Site 
    return render_template('sobre.html')


# teste de commit
# --- Ponto de Entrada ---
if __name__ == '__main__':
    app.run(debug=True)