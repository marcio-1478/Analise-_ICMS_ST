"""
Corrige o banco atual: normaliza todos os CNPJs na tabela clientes para apenas 14 dígitos.
Remove pontos, traços e barras (ex: 23.420.405/0001-84 -> 23420405000184).

Uso: python scripts/limpar_cnpj_clientes.py

Requer .env com SUPABASE_URL e SUPABASE_KEY.
"""
import os
import re

from supabase import create_client  # type: ignore

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass


def limpar_cnpj(valor: str | None) -> str | None:
    if not valor:
        return None
    s = str(valor).strip()
    if not s:
        return None
    cnpj = re.sub(r"\D", "", s)
    return cnpj if cnpj else None


def main() -> None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_KEY no .env")

    client = create_client(url, key)
    print("Carregando clientes...")
    resp = client.table("clientes").select("id, cnpj").execute()
    rows = resp.data or []
    if not rows:
        print("Nenhum cliente encontrado.")
        return

    atualizados = 0
    for r in rows:
        cnpj_atual = r.get("cnpj")
        if not cnpj_atual:
            continue
        cnpj_limpo = limpar_cnpj(cnpj_atual)
        if not cnpj_limpo or cnpj_limpo == cnpj_atual:
            continue
        if len(cnpj_limpo) != 14:
            print(f"  Aviso: CNPJ com {len(cnpj_limpo)} dígitos (id={r.get('id')}), mantido como está.")
            continue
        try:
            client.table("clientes").update({"cnpj": cnpj_limpo}).eq("id", r["id"]).execute()
            print(f"  OK: {cnpj_atual} -> {cnpj_limpo}")
            atualizados += 1
        except Exception as e:
            print(f"  Erro ao atualizar id={r.get('id')}: {e}")

    print(f"\nConcluído: {atualizados} cliente(s) atualizado(s) com CNPJ apenas numérico.")


if __name__ == "__main__":
    main()
