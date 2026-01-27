import argparse
import os
import re
from collections import defaultdict

import pdfplumber
from supabase import create_client, Client  # type: ignore

try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

COL_NCM = "ncm"
COL_DESCRICAO = "descricao"
COL_MVA = "mva_original"
COL_ALIQUOTA = "aliquota_interna_destino"
COL_MVA_REMANESCENTE = "mva_remanescente"

ALIQUOTA_PADRAO = 0.195
BATCH_SIZE = 500


def get_supabase_client() -> Client:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Variaveis SUPABASE_URL e SUPABASE_KEY nao estao configuradas."
        )
    return create_client(url, key)


def limpar_ncm(valor: str | None) -> str | None:
    if not valor:
        return None
    ncm = re.sub(r"\D", "", str(valor))
    return ncm if ncm else None


def parse_percentual(valor: str | None) -> float | None:
    if not valor:
        return None
    texto = str(valor)
    match = re.search(r"(\d+[.,]?\d*)", texto)
    if not match:
        return None
    numero = match.group(1).replace(".", "").replace(",", ".")
    try:
        return float(numero)
    except ValueError:
        return None


def detectar_secao(texto: str | None) -> str | None:
    if not texto:
        return None
    for linha in texto.splitlines():
        match = re.search(r"Se[cç][aã]o\s+([IVXLCDM]+)", linha, re.IGNORECASE)
        if match:
            return linha.strip()
    return None


def normalizar_header(valor: str) -> str:
    return re.sub(r"\s+", " ", valor.strip().lower())


def mapear_indices(header: list[str]) -> dict[str, int]:
    indices = {}
    for i, col in enumerate(header):
        col_norm = normalizar_header(col)
        if "ncm" in col_norm:
            indices["ncm"] = i
        elif "descricao" in col_norm or "descrição" in col_norm:
            indices["descricao"] = i
        elif "mva" in col_norm and "ajustada" not in col_norm:
            indices["mva_original"] = i
        elif "aliquota" in col_norm or "alíquota" in col_norm or "carga" in col_norm:
            indices["aliquota"] = i
    return indices


def processar_tabela(
    table: list[list[str]],
    indices: dict[str, int],
    secao: str,
    registros: list[dict],
    contagem_secoes: dict[str, int],
) -> None:
    for row in table[1:]:
        if not row or len(row) == 0:
            continue
        ncm = limpar_ncm(row[indices["ncm"]]) if "ncm" in indices else None
        if not ncm:
            continue

        descricao = (
            row[indices["descricao"]].strip()
            if "descricao" in indices and row[indices["descricao"]]
            else None
        )
        mva = (
            parse_percentual(row[indices["mva_original"]])
            if "mva_original" in indices
            else None
        )
        aliquota = (
            parse_percentual(row[indices["aliquota"]])
            if "aliquota" in indices
            else None
        )
        if aliquota is None:
            aliquota = ALIQUOTA_PADRAO
        elif aliquota > 1:
            aliquota = aliquota / 100.0

        # MVA remanescente (Art. 17)
        mva_remanescente = 0.70 if aliquota >= 0.18 else 0.50

        registros.append(
            {
                COL_NCM: ncm,
                COL_DESCRICAO: descricao,
                COL_MVA: mva,
                COL_ALIQUOTA: aliquota,
                COL_MVA_REMANESCENTE: mva_remanescente,
            }
        )
        contagem_secoes[secao] += 1


def upsert_registros(supabase: Client, registros: list[dict]) -> None:
    if not registros:
        return
    for i in range(0, len(registros), BATCH_SIZE):
        lote = registros[i : i + BATCH_SIZE]
        supabase.table("base_normativa_ncm").upsert(
            lote, on_conflict=COL_NCM
        ).execute()


def extrair_anexo_ix(pdf_path: str) -> None:
    supabase = get_supabase_client()

    contagem_secoes: dict[str, int] = defaultdict(int)
    registros: list[dict] = []

    secao_atual = "Secao desconhecida"
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            texto = page.extract_text()
            secao_detectada = detectar_secao(texto)
            if secao_detectada:
                secao_atual = secao_detectada

            tabelas = page.extract_tables() or []
            for table in tabelas:
                if not table or len(table) < 2:
                    continue
                header = [col or "" for col in table[0]]
                indices = mapear_indices(header)
                if "ncm" not in indices:
                    continue
                processar_tabela(
                    table, indices, secao_atual, registros, contagem_secoes
                )

    upsert_registros(supabase, registros)

    for secao, total in contagem_secoes.items():
        print(f"{secao}: {total} itens importados")
    print(f"Total geral: {sum(contagem_secoes.values())} itens")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrai NCM, descricao e MVA do Anexo IX e envia ao Supabase."
    )
    parser.add_argument(
        "--pdf",
        default=os.path.join(os.getcwd(), "Anexo IX.pdf"),
        help="Caminho para o PDF do Anexo IX",
    )
    args = parser.parse_args()

    if not os.path.exists(args.pdf):
        raise FileNotFoundError(f"PDF nao encontrado: {args.pdf}")

    extrair_anexo_ix(args.pdf)


if __name__ == "__main__":
    main()
