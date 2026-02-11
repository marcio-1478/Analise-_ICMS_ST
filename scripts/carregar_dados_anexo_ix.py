"""
Script de carga: dados_anexo_ix.csv -> Supabase base_normativa_ncm.

- Leitura robusta: pandas com sep=';' e encoding latin-1 ou utf-8-sig (acentos).
- Normalização de NCM: remove pontos e espaços antes do upsert (ex: 8507.80.00 -> 85078000).
- Art. 17: mva_remanescente = mva (ou mva_st_interna) * 0,7 (70%); salva no Supabase.
- Upsert por NCM na tabela base_normativa_ncm.

Tabela: ncm (PK), descricao, mva_original, mva_remanescente.
Uso: python scripts/carregar_dados_anexo_ix.py [--csv caminho.csv]
"""
import os
import re

import pandas as pd
from supabase import create_client, Client  # type: ignore

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

COL_NCM = "ncm"
COL_DESCRICAO = "descricao"
COL_MVA_ORIGINAL = "mva_original"
COL_MVA_REMANESCENTE = "mva_remanescente"
BATCH_SIZE = 500
FATOR_ART_17 = 0.7  # 70% (Art. 17 - alíquota interna 19,5% PR)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Variaveis SUPABASE_URL e SUPABASE_KEY nao estao configuradas."
        )
    return create_client(url, key)


def limpar_ncm(valor: str | None) -> str | None:
    """Normalização de NCM: remove pontos e espaços; só números (ex: 8507.80.00 -> 85078000)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip()
    if not s:
        return None
    ncm = re.sub(r"[.\s\-]", "", s)
    ncm = re.sub(r"\D", "", ncm)
    return ncm if ncm else None


def parse_mva(valor: str | float | None) -> float | None:
    """Converte MVA (ex: 40, 69.43, 40%) para float. Retorna None se inválido."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = str(valor).strip().replace(",", ".").replace("%", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _ler_csv_robusto(csv_path: str) -> pd.DataFrame:
    """Leitura robusta: pandas com sep=';' e encoding utf-8-sig ou latin-1 (acentos)."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(csv_path, sep=";", encoding=encoding, dtype=str)
        except (UnicodeDecodeError, Exception):
            continue
    return pd.read_csv(csv_path, sep=";", encoding="latin-1", dtype=str)


def carregar_csv(csv_path: str) -> list[dict]:
    """
    Lê CSV com pandas (sep=';', encoding latin-1 ou utf-8-sig).
    Colunas: descricao do produto (ou descricao), ncm, mva (ou mva_st_interna).
    Art. 17: mva_remanescente = mva * 0,7. NCM normalizado antes do upsert.
    """
    df = _ler_csv_robusto(csv_path)
    df.columns = df.columns.str.strip()
    por_ncm: dict[str, dict] = {}

    desc_col = "descricao do produto" if "descricao do produto" in df.columns else "descricao"
    mva_col = "mva" if "mva" in df.columns else "mva_st_interna"

    for _, row in df.iterrows():
        descricao_raw = row.get(desc_col)
        descricao = None
        if descricao_raw is not None and str(descricao_raw).strip():
            descricao = str(descricao_raw).strip()[:500]

        ncm_raw = row.get("ncm", "")
        ncm = limpar_ncm(ncm_raw)
        if not ncm:
            continue

        mva_val = parse_mva(row.get(mva_col) or row.get("mva_original"))
        mva_original = mva_val if mva_val is not None else None
        mva_remanescente = (
            (mva_original * FATOR_ART_17) if mva_original is not None else None
        )

        por_ncm[ncm] = {
            COL_NCM: ncm,
            COL_DESCRICAO: descricao,
            COL_MVA_ORIGINAL: mva_original,
            COL_MVA_REMANESCENTE: mva_remanescente,
        }

    return list(por_ncm.values())


def upsert_registros(supabase: Client, registros: list[dict]) -> None:
    """Envia registros para base_normativa_ncm em lotes; upsert por NCM."""
    if not registros:
        return
    for i in range(0, len(registros), BATCH_SIZE):
        lote = registros[i : i + BATCH_SIZE]
        supabase.table("base_normativa_ncm").upsert(
            lote, on_conflict=COL_NCM
        ).execute()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Carrega dados_anexo_ix.csv (delimitador ;) na tabela base_normativa_ncm."
    )
    parser.add_argument(
        "--csv",
        default=os.path.join(os.path.dirname(__file__), "dados_anexo_ix.csv"),
        help="Caminho para o CSV",
    )
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        raise FileNotFoundError(f"CSV nao encontrado: {args.csv}")

    print(f"Lendo {args.csv} (delimitador ;)...")
    registros = carregar_csv(args.csv)
    print(f"Registros lidos: {len(registros)}")

    supabase = get_supabase_client()
    print("Enviando para Supabase (upsert por NCM)...")
    upsert_registros(supabase, registros)
    print(f"Total enviado: {len(registros)} linhas na base_normativa_ncm.")


if __name__ == "__main__":
    main()
