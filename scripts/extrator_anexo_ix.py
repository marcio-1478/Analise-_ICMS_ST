"""
Extrator de NCMs do Anexo IX — Fonte: dados_anexo_ix.csv

- Leitura: pd.read_csv(..., sep=';', encoding='latin-1')
- NCM: remove todos os pontos e espaços (só dígitos). Ex: 18.06.90.00 -> 18069000
- MVA decimal: mva / 100
- MVA remanescente (Art. 17): mva_decimal * 0.7
- Upsert: on_conflict='ncm'
- Após carga: teste de busca NCM 8202 (Serrote)

Uso: python scripts/extrator_anexo_ix.py [--csv caminho.csv]
"""
import argparse
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
COL_CEST = "cest"
COL_DESCRICAO = "descricao"
COL_MVA_ST_INTERNA = "mva_st_interna"  # MVA original em decimal
COL_MVA_REMANESCENTE = "mva_remanescente"  # 70% da MVA (Art. 17)
BATCH_SIZE = 500
FATOR_ART_17 = 0.7  # 70% (Art. 17)


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Variaveis SUPABASE_URL e SUPABASE_KEY nao estao configuradas."
        )
    return create_client(url, key)


def apenas_digitos(s: str) -> str:
    """Remove tudo exceto dígitos."""
    return re.sub(r"\D", "", str(s)) if pd.notna(s) else ""


def carregar_csv(csv_path: str) -> list[dict]:
    """
    Lê dados_anexo_ix.csv e prepara registros para upsert.
    """
    # 1. Leitura Segura
    print(f"Lendo CSV: {csv_path}")
    df = pd.read_csv(csv_path, sep=';', encoding='latin-1')
    df.columns = df.columns.str.strip().str.lower()
    
    print(f"Colunas: {list(df.columns)}")
    print(f"Total de linhas: {len(df)}")
    
    # 2. Limpeza no ato: NCM só dígitos
    df["ncm"] = df["ncm"].astype(str).apply(apenas_digitos)
    df = df[df["ncm"].str.len() >= 2]
    df = df[~df["ncm"].isin(["", "nan", "None"])]
    # CEST: normaliza (só dígitos, ex: 03.001.00 -> 0300100)
    if "cest" in df.columns:
        df["cest"] = df["cest"].astype(str).apply(apenas_digitos)
    else:
        df["cest"] = ""
    
    # MVA: converte para decimal real (40 -> 0.40)
    df['mva'] = pd.to_numeric(df['mva'], errors='coerce').fillna(0)
    df['mva_decimal'] = df['mva'] / 100
    df['mva_remanescente'] = df['mva_decimal'] * FATOR_ART_17
    
    desc_col = 'descricao do produto' if 'descricao do produto' in df.columns else 'descricao'
    registros: list[dict] = []
    ncms_vistos: set[str] = set()
    
    print("\n" + "="*70)
    print("LOG DE CONFERÊNCIA")
    print("="*70)
    
    for _, row in df.iterrows():
        ncm = str(row['ncm']).strip()
        if not ncm or ncm in ncms_vistos:
            continue
        ncms_vistos.add(ncm)
        
        descricao = None
        if desc_col in df.columns:
            desc_raw = row.get(desc_col)
            if pd.notna(desc_raw) and str(desc_raw).strip():
                descricao = str(desc_raw).strip()[:500]
        
        mva_original = row['mva_decimal']
        mva_remanescente = row['mva_remanescente']
        cest = str(row.get('cest', '')).strip() if pd.notna(row.get('cest')) else ""
        
        mva_pct = row['mva']
        mva_ajust_pct = mva_remanescente * 100
        print(f"NCM: {ncm:10} | CEST: {cest or '-'} | MVA Original: {mva_pct:6.2f}% | MVA Ajustada: {mva_ajust_pct:6.2f}%")
        
        reg = {
            COL_NCM: ncm,
            COL_DESCRICAO: descricao,
            COL_MVA_ST_INTERNA: float(mva_original) if pd.notna(mva_original) else None,
            COL_MVA_REMANESCENTE: float(mva_remanescente) if pd.notna(mva_remanescente) else None,
        }
        if cest and len(cest) >= 4:
            reg[COL_CEST] = cest
        registros.append(reg)
    
    print("="*70)
    return registros


def obter_mapa_ncm_cest(csv_path: str) -> dict[str, str]:
    """
    Retorna mapa NCM -> CEST de todas as linhas do CSV (não deduplica por NCM).
    Usa o primeiro CEST encontrado por NCM para consistência.
    """
    df = pd.read_csv(csv_path, sep=';', encoding='latin-1')
    df.columns = df.columns.str.strip().str.lower()
    if "cest" not in df.columns:
        return {}
    df["ncm"] = df["ncm"].astype(str).apply(apenas_digitos)
    df["cest"] = df["cest"].astype(str).apply(apenas_digitos)
    mapa: dict[str, str] = {}
    for _, row in df.iterrows():
        ncm = str(row.get("ncm", "")).strip()
        cest = str(row.get("cest", "")).strip()
        if ncm and len(ncm) >= 2 and cest and len(cest) >= 4 and ncm not in mapa:
            mapa[ncm] = cest  # primeiro CEST vence por NCM
    return mapa


def atualizar_cest_explicito(supabase: Client, csv_path: str) -> int:
    """
    Atualiza a coluna CEST em base_normativa_ncm via UPDATE explícito.
    Funciona mesmo quando a tabela tem unique em (ncm, uf) ou outra estrutura.
    Retorna quantidade de linhas atualizadas.
    """
    mapa = obter_mapa_ncm_cest(csv_path)
    if not mapa:
        print("Nenhum CEST encontrado no CSV.")
        return 0
    
    print(f"\nAtualizando CEST para {len(mapa)} NCMs...")
    atualizados = 0
    for ncm, cest in mapa.items():
        try:
            resp = (
                supabase.table("base_normativa_ncm")
                .update({COL_CEST: cest})
                .eq(COL_NCM, ncm)
                .execute()
            )
            if resp.data:
                atualizados += len(resp.data)
        except Exception as e:
            print(f"  Erro ao atualizar NCM {ncm}: {e}")
    
    print(f"✓ {atualizados} linhas atualizadas com CEST.")
    return atualizados


def upsert_registros(supabase: Client, registros: list[dict]) -> None:
    """
    Envia registros para base_normativa_ncm (upsert por ncm).
    Se a tabela não tiver UNIQUE em ncm, faz insert em lote.
    """
    if not registros:
        return
    for i in range(0, len(registros), BATCH_SIZE):
        lote = registros[i : i + BATCH_SIZE]
        try:
            supabase.table("base_normativa_ncm").upsert(
                lote, on_conflict=COL_NCM
            ).execute()
            print(f"Lote {i // BATCH_SIZE + 1}: {len(lote)} registros enviados")
        except Exception as e:
            print(f"Erro no upsert (tentando insert): {e}")
            for r in lote:
                try:
                    supabase.table("base_normativa_ncm").insert(r).execute()
                except Exception as ins:
                    if "duplicate" in str(ins).lower() or "unique" in str(ins).lower():
                        upd = {
                            "descricao": r.get("descricao"),
                            "mva_st_interna": r.get("mva_st_interna"),
                            "mva_remanescente": r.get("mva_remanescente"),
                        }
                        if COL_CEST in r and r.get(COL_CEST):
                            upd[COL_CEST] = r[COL_CEST]
                        supabase.table("base_normativa_ncm").update(upd).eq(COL_NCM, r[COL_NCM]).execute()
                    else:
                        print(f"  Falha NCM {r.get(COL_NCM)}: {ins}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Carrega dados_anexo_ix.csv na base_normativa_ncm."
    )
    parser.add_argument(
        "--csv",
        default=os.path.join(os.path.dirname(__file__), "dados_anexo_ix.csv"),
        help="Caminho para o CSV",
    )
    args = parser.parse_args()

    if not os.path.exists(args.csv):
        raise FileNotFoundError(f"CSV nao encontrado: {args.csv}")

    registros = carregar_csv(args.csv)
    print(f"\nTotal de registros unicos: {len(registros)}")

    if not registros:
        print("Nenhum registro valido encontrado.")
        return

    supabase = get_supabase_client()
    print("\nEnviando para Supabase (base_normativa_ncm)...")
    upsert_registros(supabase, registros)
    print(f"\n✓ {len(registros)} NCMs enviados para base_normativa_ncm.")

    # Atualização explícita de CEST (garante que a coluna CEST seja preenchida)
    atualizar_cest_explicito(supabase, args.csv)

    # Teste de busca: NCM 8202 (Serrote)
    print("\n--- Teste de busca (NCM Serrote 8202) ---")
    try:
        r = (
            supabase.table("base_normativa_ncm")
            .select("ncm, descricao")
            .like("ncm", "8202%")
            .limit(5)
            .execute()
        )
        if r.data and len(r.data) > 0:
            print(f"  Match encontrado para NCM 8202 (Serrote): {r.data}")
        else:
            r2 = supabase.table("base_normativa_ncm").select("ncm").eq("ncm", "8202").limit(1).execute()
            if r2.data:
                print(f"  Match encontrado (exato 8202): {r2.data}")
            else:
                print("  Nenhum registro com NCM 8202 ou prefixo encontrado na base.")
    except Exception as e:
        print(f"  Erro no teste: {e}")


if __name__ == "__main__":
    main()
