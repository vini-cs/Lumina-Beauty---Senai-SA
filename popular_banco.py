import model
import sqlite3

def popular_produtos():
    print("--- INICIANDO RESET DO BANCO DE DADOS (COM IDs FIXOS) ---")
    
    conn = model.get_db_connection()
    cursor = conn.cursor()

    # 1. Limpeza Segura
    # Apaga dados antigos para evitar duplicidade de IDs
    try:
        cursor.execute("DELETE FROM itens_pedido") # Limpa pedidos antes para não dar erro   # Limpa avaliações
        cursor.execute("DELETE FROM produtos")     # Limpa produtos
        # Não precisamos mais do 'DELETE FROM sqlite_sequence' pois vamos forçar os IDs
    except sqlite3.OperationalError:
        pass # Tabelas ainda não existem, o model.init_db() vai criar

    conn.commit()
    conn.close()

    # 2. Garante que as tabelas existam
    model.init_db()

    conn = model.get_db_connection()
    cursor = conn.cursor()

    # 3. Lista de Produtos com ID EXPLÍCITO
    # Estrutura: (ID, Nome, Preço, Descrição, Categoria, Estoque, Imagem)
    produtos = [
        (1, "Base Líquida Lumina Matte", 89.90, "Cobertura média a alta com acabamento aveludado.", "rosto", 50, "https://images.unsplash.com/photo-1631729371254-42c2892f0e6e?w=600&q=80"),
        (2, "Blush Compacto Rosé", 45.50, "Pigmentação intensa com toque suave.", "rosto", 30, "https://cdn.awsli.com.br/1641/1641981/produto/242694743/blush_compacto_grupo_02_ruby_rose_hb_6121_kit_04_unid_virtual_make_500-akp0cy1w95.jpg"),
        (3, "Paleta de Sombras Nude Glam", 120.00, "12 cores neutras e cintilantes.", "olhos", 25, "https://images.unsplash.com/photo-1512496015851-a90fb38ba796?w=600&q=80"),
        (4, "Máscara de Cílios Volume Max", 55.90, "Cílios 3x mais volumosos.", "olhos", 60, "https://images.unsplash.com/photo-1631214524020-7e18db9a8f92?w=600&q=80"),
        (5, "Batom Líquido Matte Vermelho", 39.90, "Duração de 12 horas. Não transfere.", "labios", 100, "https://images.unsplash.com/photo-1586495777744-4413f21062fa?w=600&q=80"),
        (6, "Sérum Vitamina C 10%", 99.90, "Antioxidante poderoso. Uniformiza o tom.", "skincare", 40, "https://images.unsplash.com/photo-1620916566398-39f1143ab7be?w=600&q=80"),
        (7, "Kit Pincéis Essenciais", 149.90, "Cerdas sintéticas super macias.", "pinceis", 20, "https://images.unsplash.com/photo-1522337660859-02fbefca4702?w=600&q=80"),
        (8, "Esponja de Maquiagem 360", 25.00, "Perfeita para base e corretivo.", "pinceis", 150, "https://images.unsplash.com/photo-1599305090598-fe179d501227?w=600&q=80"),
        (9, "Maleta Completa Profissional", 890.00, "Tudo o que você precisa.", "kits", 5, "https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?w=600&q=80")
    ]

    try:
        print("--- Inserindo produtos com IDs fixos... ---")
        for id_prod, nome, preco, desc, cat, est, img in produtos:
            # Atenção: Adicionei o campo 'id' no INSERT
            cursor.execute('''
                INSERT OR REPLACE INTO produtos (id, nome, preco, descricao, categoria, estoque, imagem)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (id_prod, nome, preco, desc, cat, est, img))
            print(f"   -> Produto ID {id_prod}: {nome} (OK)")
        
        conn.commit()
        print("\n--- SUCESSO! O Banco está perfeitamente sincronizado com o Quiz! ---")
        
    except Exception as e:
        print(f"\nERRO: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    popular_produtos()