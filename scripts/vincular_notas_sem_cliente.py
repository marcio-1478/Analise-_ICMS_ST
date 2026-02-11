"""
Vínculo retroativo: percorre todas as notas sem cliente_id e tenta vinculá-las
ao cliente correto comparando CNPJ (apenas dígitos) entre notas_fiscais.cnpj_destinatario
e clientes.cnpj.

Uso: python scripts/vincular_notas_sem_cliente.py
"""
import os
import re

from supabase import create_client, Client  # type: ignore

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass


def limpar_cnpj(valor: str | None) -> str | None:
    """Remove pontos, traços e barras do CNPJ. Retorna só os 14 dígitos."""
    if not valor:
        return None
    s = str(valor).strip()
    if not s:
        return None
    cnpj = re.sub(r"\D", "", s)
    return cnpj if cnpj else None


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Variáveis SUPABASE_URL e SUPABASE_KEY não configuradas.")
    return create_client(url, key)


def main() -> None:
    print("=== Vínculo retroativo: notas sem cliente_id ===\n")
    supabase = get_supabase_client()

    # 1. Busca notas sem cliente_id
    resp_notas = (
        supabase.table("notas_fiscais")
        .select("id, numero_nfe, cnpj_destinatario")
        .is_("cliente_id", None)
        .execute()
    )
    notas = resp_notas.data or []
    print(f"Notas sem cliente_id: {len(notas)}")

    if not notas:
        print("Nenhuma nota para vincular.")
        return

    # 2. Carrega clientes (cnpj limpo)
    resp_clientes = (
        supabase.table("clientes")
        .select("id, razao_social, nome_fantasia, cnpj")
        .execute()
    )
    clientes = resp_clientes.data or []
    mapa_cnpj_cliente: dict[str, str] = {}
    for c in clientes:
        cnpj_limpo = limpar_cnpj(c.get("cnpj"))
        if cnpj_limpo:
            mapa_cnpj_cliente[cnpj_limpo] = c["id"]

    print(f"Clientes na base: {len(mapa_cnpj_cliente)}")

    # 3. Percorre notas e vincula por CNPJ
    vinculadas = 0
    sem_cnpj = 0
    sem_match = 0

    for n in notas:
        nota_id = n["id"]
        numero_nfe = n.get("numero_nfe", "")
        cnpj_dest = n.get("cnpj_destinatario")

        if not cnpj_dest:
            sem_cnpj += 1
            print(f"  NF {numero_nfe}: sem cnpj_destinatario no banco (não é possível vincular)")
            continue

        cnpj_limpo = limpar_cnpj(cnpj_dest)
        if not cnpj_limpo or len(cnpj_limpo) != 14:
            sem_cnpj += 1
            print(f"  NF {numero_nfe}: cnpj_destinatario inválido ({cnpj_dest})")
            continue

        cliente_id = mapa_cnpj_cliente.get(cnpj_limpo)
        if not cliente_id:
            sem_match += 1
            print(f"  NF {numero_nfe}: CNPJ {cnpj_limpo} não encontrado em clientes")
            continue

        try:
            supabase.table("notas_fiscais").update(
                {"cliente_id": str(cliente_id)}
            ).eq("id", nota_id).execute()
            vinculadas += 1
            nome = next(
                (c.get("nome_fantasia") or c.get("razao_social", "?")
                for c in clientes
                if str(c["id"]) == str(cliente_id)
            )
            print(f"  NF {numero_nfe}: vinculada a {nome}")
        except Exception as e:
            print(f"  NF {numero_nfe}: erro ao atualizar: {e}")

    print(f"\n=== Resultado ===")
    print(f"  Vinculadas: {vinculadas}")
    print(f"  Sem cnpj_destinatário: {sem_cnpj}")
    print(f"  CNPJ sem match em clientes: {sem_match}")


if __name__ == "__main__":
    main()
