"""
Remove todas as notas fiscais e seus itens do banco (para limpar dados de teste).

Os itens em itens_nota são removidos automaticamente (ON DELETE CASCADE).
Requer confirmação explícita antes de executar.

Uso: python scripts/limpar_notas_teste.py
"""
import os

from supabase import create_client, Client  # type: ignore

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Variáveis SUPABASE_URL e SUPABASE_KEY não configuradas.")
    return create_client(url, key)


def main() -> None:
    print("=== Limpar notas fiscais de teste ===\n")
    supabase = get_supabase_client()

    # Conta notas antes
    resp = supabase.table("notas_fiscais").select("id", count="exact").limit(1).execute()
    total = resp.count or 0

    if total == 0:
        print("Não há notas para remover.")
        return

    print(f"Total de notas a remover: {total}")
    print("Os itens de cada nota serão removidos automaticamente (CASCADE).")
    print()
    confirma = input("Digite 'SIM' para confirmar a exclusão: ").strip().upper()

    if confirma != "SIM":
        print("Operação cancelada.")
        return

    # Remove em lotes: busca IDs, deleta, repete até não haver mais
    removidos = 0
    lote_size = 100
    while True:
        resp = (
            supabase.table("notas_fiscais")
            .select("id")
            .limit(lote_size)
            .execute()
        )
        ids = [r["id"] for r in (resp.data or [])]
        if not ids:
            break
        supabase.table("notas_fiscais").delete().in_("id", ids).execute()
        removidos += len(ids)
        print(f"  Removidas {removidos} notas...")

    print(f"\n✓ {removidos} nota(s) removida(s) com sucesso.")


if __name__ == "__main__":
    main()
