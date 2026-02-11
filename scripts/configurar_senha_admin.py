"""
Configura a senha do usuário admin no Supabase.
Use quando o login não funcionar - atualiza a senha para SHA256 de 'admin123'.

Requer: SUPABASE_URL e SUPABASE_KEY no .env (use a chave service_role do Supabase).

Uso: python scripts/configurar_senha_admin.py
"""
import os
import hashlib

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

try:
    from supabase import create_client
except ImportError:
    print("Instale: pip install supabase")
    exit(1)

SENHA_PADRAO = "admin123"
HASH_SHA256 = hashlib.sha256(SENHA_PADRAO.encode()).hexdigest()


def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        print("Configure SUPABASE_URL e SUPABASE_KEY no .env")
        print("Use a chave service_role (Settings > API) no Supabase, não a anon key.")
        exit(1)

    supabase = create_client(url, key)

    # 1. Verifica se o usuário existe
    resp = supabase.table("usuarios").select("id, usuario, senha, nome").eq("usuario", "admin").execute()
    if not resp.data or len(resp.data) == 0:
        print("Usuário 'admin' não encontrado na tabela usuarios.")
        print("Crie o registro primeiro no Supabase.")
        exit(1)

    # 2. Atualiza a senha
    supabase.table("usuarios").update({"senha": HASH_SHA256}).eq("usuario", "admin").execute()
    print(f"Senha do admin atualizada para SHA256 de '{SENHA_PADRAO}'.")
    print(f"Hash: {HASH_SHA256}")
    print("\nTente fazer login novamente: admin / admin123")


if __name__ == "__main__":
    main()
