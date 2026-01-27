import os
from datetime import datetime
from io import BytesIO
import zipfile

import pandas as pd
import streamlit as st
import xmltodict
from supabase import create_client, Client  # type: ignore

# Tenta carregar variáveis do .env, se python-dotenv estiver instalado
try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

st.set_page_config(page_title="ST-Analyzer-PR", layout="wide")


@st.cache_resource
def get_supabase_client() -> Client | None:  # type: ignore[valid-type]
    """
    Inicializa o client do Supabase usando variáveis do .env / ambiente.
    Espera SUPABASE_URL e SUPABASE_KEY.
    """
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        # Erro típico: variáveis do .env não definidas ou com nome errado
        raise RuntimeError(
            "Variáveis de ambiente SUPABASE_URL e/ou SUPABASE_KEY não estão configuradas."
        )

    try:
        client = create_client(url, key)
    except Exception as exc:
        # Erro típico: chave inválida, projeto inexistente, etc.
        raise RuntimeError(f"Erro ao conectar ao Supabase: {exc}") from exc

    return client


def require_supabase() -> Client:
    """
    Obtém o client do Supabase e trata erros de conexão de forma amigável no Streamlit.
    """
    try:
        client = get_supabase_client()
        if client is None:
            raise RuntimeError("Não foi possível inicializar o cliente Supabase.")
        return client
    except Exception as exc:
        st.error(
            "❌ Erro ao conectar ao Supabase.\n\n"
            "Verifique se as variáveis SUPABASE_URL e SUPABASE_KEY estão corretas no seu .env.\n\n"
            f"Detalhes técnicos: {exc}"
        )
        st.stop()


def pagina_gestao_clientes() -> None:
    st.header("Gestão de Clientes")

    supabase = require_supabase()

    st.subheader("Cadastrar novo cliente")

    with st.form("form_cadastro_cliente"):
        razao_social = st.text_input("Razão Social")
        cnpj = st.text_input("CNPJ")
        submitted = st.form_submit_button("Salvar")

        if submitted:
            if not razao_social or not cnpj:
                st.warning("Preencha todos os campos (Razão Social e CNPJ).")
            else:
                try:
                    data = {
                        "razao_social": razao_social,
                        "nome_fantasia": razao_social,
                        "cnpj": cnpj,
                        "inscricao_estadual": None,
                        "uf": "PR",
                    }
                    response = supabase.table("clientes").insert(data).execute()

                    if response.data:
                        st.success("Cliente cadastrado com sucesso!")
                    else:
                        st.warning(
                            "Tentativa de cadastro realizada, mas não houve retorno de dados."
                        )
                except Exception as exc:
                    st.error(f"Erro ao salvar cliente na tabela 'clientes': {exc}")

    st.markdown("---")
    st.subheader("Clientes cadastrados")

    try:
        response = (
            supabase.table("clientes")
            .select("id, razao_social, cnpj, created_at")
            .order("created_at", desc=True)
            .execute()
        )
        clientes = response.data or []
    except Exception as exc:
        st.error(f"Erro ao carregar lista de clientes: {exc}")
        clientes = []

    if not clientes:
        st.info("Nenhum cliente cadastrado até o momento.")
    else:
        st.dataframe(clientes, use_container_width=True)


def salvar_nota_e_itens(
    supabase: Client,
    numero_nfe: str,
    cliente_id: str | None,
    valor_total: float,
    icms_total: float,
    itens: list,
) -> tuple[bool, str]:
    """
    Salva uma nota fiscal e seus itens no banco de dados.
    Retorna (sucesso, mensagem).
    """
    try:
        # Verifica se a nota já existe (duplicidade)
        response_existente = (
            supabase.table("notas_fiscais")
            .select("id, numero_nfe")
            .eq("numero_nfe", numero_nfe)
            .execute()
        )
        
        if response_existente.data and len(response_existente.data) > 0:
            return False, f"Nota {numero_nfe} já existe no banco de dados"
        
        # Insere a nota fiscal
        nota_data = {
            "numero_nfe": numero_nfe,
            "cliente_id": cliente_id,
            "valor_total": float(valor_total),
            "icms_total": float(icms_total),
            "data_importacao": datetime.now().isoformat(),
        }
        
        response_nota = supabase.table("notas_fiscais").insert(nota_data).execute()
        
        if not response_nota.data or len(response_nota.data) == 0:
            st.error(
                "Erro ao salvar nota no Supabase. "
                f"Resposta completa: {response_nota}"
            )
            return False, f"Erro ao salvar nota {numero_nfe}"
        
        nota_id = response_nota.data[0]["id"]
        
        # Insere os itens da nota
        if itens:
            itens_data = []
            for item in itens:
                item_data = {
                    "nota_id": nota_id,
                    "codigo_produto": item.get("codigo_produto") or None,
                    "descricao": item.get("descricao") or None,
                    "ncm": item.get("ncm") or None,
                    "cest": item.get("cest") or None,
                    "cfop": item.get("cfop") or None,
                    "valor_unitario": float(item.get("valor_unitario", 0)),
                    "valor_total": float(item.get("valor_total", 0)),
                }
                itens_data.append(item_data)
            
            if itens_data:
                response_itens = supabase.table("itens_nota").insert(itens_data).execute()
                if not response_itens.data:
                    st.error(
                        "Erro ao salvar itens no Supabase. "
                        f"Resposta completa: {response_itens}"
                    )
                    return False, f"Nota {numero_nfe} salva, mas houve erro ao salvar itens"
        
        return True, f"Nota {numero_nfe} e {len(itens)} item(ns) salvos com sucesso"
        
    except Exception as exc:
        st.error(f"Erro inesperado ao salvar nota {numero_nfe}: {exc}")
        return False, f"Erro ao salvar nota {numero_nfe}: {exc}"


def verificar_st_produto(supabase: Client, ncm: str) -> list | None:
    """
    Consulta regras de ST por NCM na tabela regras_st_pr.
    """
    try:
        response = (
            supabase.table("regras_st_pr")
            .select("*")
            .eq("ncm", ncm)
            .execute()
        )
        return response.data
    except Exception as exc:
        st.error(f"Erro ao consultar regras ST para NCM {ncm}: {exc}")
        return None


def ncm_na_base_normativa(supabase: Client, ncm: str) -> bool:
    """
    Verifica se o NCM existe na tabela base_normativa_ncm.
    """
    try:
        response = (
            supabase.table("base_normativa_ncm")
            .select("ncm")
            .eq("ncm", ncm)
            .limit(1)
            .execute()
        )
        return bool(response.data)
    except Exception as exc:
        st.error(f"Erro ao consultar base normativa para NCM {ncm}: {exc}")
        return False


def buscar_mva_convenio(supabase: Client, ncm: str) -> float | None:
    """
    Busca a MVA na tabela convenios para o NCM informado.
    """
    try:
        response = (
            supabase.table("convenios")
            .select("mva")
            .eq("ncm", ncm)
            .limit(1)
            .execute()
        )
        if response.data:
            mva = response.data[0].get("mva")
            return float(mva) if mva is not None else None
        return None
    except Exception as exc:
        st.error(f"Erro ao consultar MVA para NCM {ncm}: {exc}")
        return None


def reprocessar_st_sessao(
    supabase: Client, resumo_notas: list[dict]
) -> list[dict]:
    """
    Reprocessa o status ST das notas ja carregadas na sessao.
    """
    notas_atualizadas = []
    for nota in resumo_notas:
        numero_nfe = nota.get("Número da Nota")
        sujeito_st_pr = False

        if numero_nfe and numero_nfe != "N/A":
            try:
                response_nota = (
                    supabase.table("notas_fiscais")
                    .select("id")
                    .eq("numero_nfe", str(numero_nfe))
                    .limit(1)
                    .execute()
                )
                if response_nota.data:
                    nota_id = response_nota.data[0]["id"]
                    response_itens = (
                        supabase.table("itens_nota")
                        .select("ncm, cfop")
                        .eq("nota_id", nota_id)
                        .execute()
                    )
                    for item in response_itens.data or []:
                        ncm = item.get("ncm")
                        if not ncm:
                            continue
                        if ncm_na_base_normativa(supabase, ncm):
                            sujeito_st_pr = True
                            _mva = buscar_mva_convenio(supabase, ncm)
            except Exception as exc:
                st.error(
                    f"Erro ao reprocessar ST da nota {numero_nfe}: {exc}"
                )

        nota_atualizada = dict(nota)
        nota_atualizada["Sujeito a ST (PR)"] = (
            "⚠️ SIM" if sujeito_st_pr else "Não"
        )
        notas_atualizadas.append(nota_atualizada)

    return notas_atualizadas


def safe_float(valor: object, default: float = 0.0) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return default


def extrair_valor_ipi(item: dict) -> float:
    try:
        ipi = item.get("imposto", {}).get("IPI", {})
        if not isinstance(ipi, dict):
            return 0.0
        if "IPITrib" in ipi:
            return safe_float(ipi["IPITrib"].get("vIPI"))
        return safe_float(ipi.get("vIPI"))
    except Exception:
        return 0.0


def extrair_valor_icms_origem(item: dict) -> float:
    try:
        icms = item.get("imposto", {}).get("ICMS", {})
        if not isinstance(icms, dict) or not icms:
            return 0.0
        # Pega o primeiro bloco ICMS encontrado (ICMS00, ICMS10, etc)
        for _, icms_val in icms.items():
            if isinstance(icms_val, dict):
                return safe_float(icms_val.get("vICMS"))
        return 0.0
    except Exception:
        return 0.0


def extrair_valor_frete(item: dict) -> float:
    try:
        prod = item.get("prod", {})
        return safe_float(prod.get("vFrete"))
    except Exception:
        return 0.0
    except Exception as exc:
        st.error(f"Erro ao consultar MVA para NCM {ncm}: {exc}")
        return None


def processar_xml(
    xml_string: str,
    nome_arquivo: str,
    supabase: Client,
    todos_itens: list,
    resumo_notas: list,
    alertas_notas: list,
) -> None:
    """
    Processa um XML de NF-e e extrai informações, acumulando nos dados consolidados.
    """
    try:
        # Parseia o XML usando xmltodict
        xml_dict = xmltodict.parse(xml_string)
        
        # Extrai infNFe
        inf_nfe = {}
        try:
            if "NFe" in xml_dict:
                inf_nfe = xml_dict["NFe"].get("infNFe", {})
            elif "nfeProc" in xml_dict:
                inf_nfe = xml_dict["nfeProc"].get("NFe", {}).get("infNFe", {})
            else:
                for key in xml_dict:
                    if isinstance(xml_dict[key], dict) and "infNFe" in xml_dict[key]:
                        inf_nfe = xml_dict[key]["infNFe"]
                        break
        except (KeyError, AttributeError, TypeError):
            st.error(f"❌ Erro ao processar estrutura do XML: {nome_arquivo}")
            return
        
        # Extrai número da nota (nNF)
        n_nf = None
        try:
            ide = inf_nfe.get("ide", {})
            n_nf = ide.get("nNF") or "N/A"
        except (KeyError, AttributeError, TypeError):
            n_nf = "N/A"
        
        # Extrai o CNPJ do destinatário
        cnpj_destinatario = None
        try:
            dest = inf_nfe.get("dest", {})
            cnpj_destinatario = dest.get("CNPJ") or dest.get("cnpj")
        except (KeyError, AttributeError, TypeError):
            pass
        
        # Verifica se o CNPJ foi encontrado e consulta no banco
        alerta_cliente = None
        nome_cliente = None
        if cnpj_destinatario:
            try:
                response = (
                    supabase.table("clientes")
                    .select("id, razao_social, nome_fantasia, cnpj")
                    .eq("cnpj", cnpj_destinatario)
                    .execute()
                )
                
                if response.data and len(response.data) > 0:
                    cliente = response.data[0]
                    nome_cliente = cliente.get("nome_fantasia") or cliente.get("razao_social", "N/A")
                else:
                    alerta_cliente = "ERRO: NF_DESTINATARIO_NAO_CADASTRADO"
                    st.error(f"❌ {alerta_cliente} - Nota {n_nf} ({nome_arquivo})")
            except Exception as exc:
                st.error(f"Erro ao consultar cliente no banco de dados ({nome_arquivo}): {exc}")
        else:
            st.warning(f"CNPJ do destinatário não encontrado no XML ({nome_arquivo}).")
        
        # Extrai todos os itens (det)
        det = inf_nfe.get("det", [])
        if not isinstance(det, list):
            det = [det]
        
        # Processa cada item e identifica CFOPs
        tem_cfop_6 = False
        cfops_encontrados = set()
        itens_para_salvar = []
        ncm_cache: dict[str, bool] = {}
        sujeito_st_pr = False
        
        for item in det:
            try:
                prod = item.get("prod", {})
                
                codigo_produto = prod.get("cProd") or prod.get("cEAN") or "N/A"
                descricao = prod.get("xProd") or "N/A"
                ncm = prod.get("NCM") or "N/A"
                cest = prod.get("CEST") or None
                cfop = prod.get("CFOP") or "N/A"
                valor_total = prod.get("vProd") or "0.00"
                quantidade = prod.get("qCom") or "1.00"
                valor_ipi = extrair_valor_ipi(item)
                valor_frete = extrair_valor_frete(item)
                icms_origem = extrair_valor_icms_origem(item)
                
                # Calcula valor unitário
                try:
                    valor_unitario = float(valor_total) / float(quantidade) if float(quantidade) > 0 else 0.0
                except (ValueError, TypeError):
                    valor_unitario = 0.0
                
                # Coleta CFOPs únicos
                if cfop != "N/A":
                    cfops_encontrados.add(str(cfop))
                    if str(cfop).startswith("6"):
                        tem_cfop_6 = True

                # Verifica se o NCM esta na base normativa e prepara MVA
                ncm_encontrado = False
                mva = None
                if ncm and ncm != "N/A":
                    if ncm not in ncm_cache:
                        ncm_cache[ncm] = ncm_na_base_normativa(supabase, ncm)
                    ncm_encontrado = ncm_cache[ncm]
                    if ncm_encontrado:
                        sujeito_st_pr = True
                        mva = buscar_mva_convenio(supabase, ncm)

                # Alerta de antecipacao para item interestadual
                if ncm_encontrado and tem_cfop_6:
                    st.warning(
                        "Cálculo de Antecipação Necessário "
                        f"(NCM {ncm}, CFOP {cfop}, Nota {n_nf})"
                    )
                
                # Dados para exibição
                todos_itens.append({
                    "Arquivo": nome_arquivo,
                    "Numero Nota": n_nf,
                    "Código do Produto": codigo_produto,
                    "Descrição": descricao,
                    "NCM": ncm,
                    "CFOP": cfop,
                    "Valor Produto": safe_float(valor_total),
                    "IPI": valor_ipi,
                    "Frete": valor_frete,
                    "MVA": mva,
                    "ICMS Origem": icms_origem,
                    "Sujeito ST": ncm_encontrado,
                })
                
                # Dados para salvar no banco
                itens_para_salvar.append({
                    "codigo_produto": codigo_produto if codigo_produto != "N/A" else None,
                    "descricao": descricao if descricao != "N/A" else None,
                    "ncm": ncm if ncm != "N/A" else None,
                    "cest": cest,
                    "cfop": cfop if cfop != "N/A" else None,
                    "valor_unitario": valor_unitario,
                    "valor_total": float(valor_total) if valor_total else 0.0,
                })
            except (KeyError, AttributeError, TypeError) as e:
                st.warning(f"Erro ao processar item ({nome_arquivo}): {e}")
                continue
        
        # Determina CFOP principal (primeiro encontrado ou "Múltiplos" se houver vários)
        cfop_principal = "N/A"
        if cfops_encontrados:
            if len(cfops_encontrados) == 1:
                cfop_principal = list(cfops_encontrados)[0]
            else:
                cfop_principal = f"Múltiplos ({', '.join(sorted(cfops_encontrados))})"
        
        # Verifica alerta de CFOP interestadual
        if tem_cfop_6:
            alerta_cfop = "⚠️ Operação Interestadual Detectada - Verificar Antecipação ICMS-ST"
            st.warning(f"{alerta_cfop} - Nota {n_nf} ({nome_arquivo})")
            if alerta_cliente:
                alertas_notas.append(f"Nota {n_nf}: {alerta_cliente} | {alerta_cfop}")
            else:
                alertas_notas.append(f"Nota {n_nf}: {alerta_cfop}")
        elif alerta_cliente:
            alertas_notas.append(f"Nota {n_nf}: {alerta_cliente}")
        
        # Extrai valores totais da nota
        v_nf = "0.00"
        v_icms = "0.00"
        try:
            total = inf_nfe.get("total", {}).get("ICMSTot", {})
            v_nf = total.get("vNF") or "0.00"
            v_icms = total.get("vICMS") or "0.00"
        except (KeyError, AttributeError, TypeError):
            st.warning(f"Não foi possível extrair valores totais de {nome_arquivo}")
        
        # Obtém o ID do cliente se encontrado
        cliente_id = None
        if cnpj_destinatario:
            try:
                response_cliente = (
                    supabase.table("clientes")
                    .select("id")
                    .eq("cnpj", cnpj_destinatario)
                    .execute()
                )
                if response_cliente.data and len(response_cliente.data) > 0:
                    cliente_id = response_cliente.data[0]["id"]
            except Exception:
                pass
        
        # Salva a nota e itens no banco de dados
        status_banco = "Nao gravada"
        if n_nf != "N/A":
            sucesso, mensagem = salvar_nota_e_itens(
                supabase,
                str(n_nf),
                cliente_id,
                float(v_nf) if v_nf else 0.0,
                float(v_icms) if v_icms else 0.0,
                itens_para_salvar,
            )
            if sucesso:
                status_banco = "Gravada"
                st.success(f"💾 {mensagem}")
            else:
                if "já existe" in mensagem.lower():
                    status_banco = "Ja existente"
                    st.info(f"ℹ️ {mensagem}")
                else:
                    status_banco = "Falha ao gravar"
                    st.warning(f"⚠️ {mensagem}")
        else:
            status_banco = "Sem numero"
        
        # Adiciona ao resumo de notas
        resumo_notas.append({
            "Número da Nota": n_nf,
            "Nome do Cliente": nome_cliente or "N/A",
            "Valor Total (vNF)": v_nf,
            "Valor ICMS (vICMS)": v_icms,
            "CFOP": cfop_principal,
            "Sujeito a ST (PR)": "⚠️ SIM" if sujeito_st_pr else "Não",
            "Status Banco": status_banco,
            "Arquivo": nome_arquivo,
        })
            
    except Exception as exc:
        st.error(f"Erro ao processar o XML {nome_arquivo}: {exc}")


def pagina_analise_xml() -> None:
    st.header("Análise de XML")

    st.write(
        "Faça o upload de arquivos XML de NF-e (modelo 55) para futura análise "
        "de ICMS-ST por antecipação no PR."
    )

    supabase = require_supabase()

    uploaded_files = st.file_uploader(
        "Selecione um ou mais arquivos XML de NF-e ou arquivos ZIP contendo XMLs",
        type=["xml", "zip"],
        accept_multiple_files=True,
    )

    if uploaded_files is not None and len(uploaded_files) > 0:
        st.success(f"{len(uploaded_files)} arquivo(s) recebido(s)")
        
        # Listas para acumular dados
        todos_itens = []
        resumo_notas = []
        alertas_notas = []
        
        # Processa cada arquivo
        for uploaded_file in uploaded_files:
            nome_arquivo = uploaded_file.name
            extensao = nome_arquivo.lower().split('.')[-1] if '.' in nome_arquivo else ''
            
            if extensao == 'zip':
                # Processa arquivo ZIP
                st.markdown(f"### 📦 Processando ZIP: `{nome_arquivo}`")
                
                try:
                    # Lê o conteúdo do ZIP
                    zip_bytes = uploaded_file.read()
                    zip_buffer = BytesIO(zip_bytes)
                    
                    # Abre o ZIP
                    with zipfile.ZipFile(zip_buffer, 'r') as zip_ref:
                        # Lista todos os arquivos no ZIP
                        arquivos_no_zip = zip_ref.namelist()
                        
                        # Filtra apenas arquivos XML
                        xmls_no_zip = [f for f in arquivos_no_zip if f.lower().endswith('.xml')]
                        
                        if not xmls_no_zip:
                            st.warning(f"Nenhum arquivo XML encontrado no ZIP: {nome_arquivo}")
                            continue
                        
                        st.info(f"Encontrados {len(xmls_no_zip)} arquivo(s) XML no ZIP")
                        
                        # Processa cada XML dentro do ZIP
                        for xml_path in xmls_no_zip:
                            try:
                                # Extrai o nome do arquivo (sem o caminho)
                                xml_nome = xml_path.split('/')[-1] if '/' in xml_path else xml_path
                                
                                # Lê o conteúdo do XML do ZIP
                                xml_bytes = zip_ref.read(xml_path)
                                xml_string = xml_bytes.decode("utf-8", errors="ignore")
                                
                                # Processa o XML
                                st.markdown(f"  - Processando: `{xml_nome}`")
                                processar_xml(
                                    xml_string,
                                    f"{nome_arquivo}/{xml_nome}",
                                    supabase,
                                    todos_itens,
                                    resumo_notas,
                                    alertas_notas,
                                )
                            except Exception as exc:
                                st.error(f"Erro ao processar XML {xml_path} do ZIP {nome_arquivo}: {exc}")
                                continue
                                
                except zipfile.BadZipFile:
                    st.error(f"❌ Arquivo ZIP inválido: {nome_arquivo}")
                    continue
                except Exception as exc:
                    st.error(f"Erro ao processar ZIP {nome_arquivo}: {exc}")
                    continue
                    
            elif extensao == 'xml':
                # Processa arquivo XML diretamente
                st.markdown(f"### 📄 Processando: `{nome_arquivo}`")
                
                try:
                    # Lê o conteúdo do XML
                    xml_bytes = uploaded_file.read()
                    xml_string = xml_bytes.decode("utf-8", errors="ignore")
                    
                    # Processa o XML
                    processar_xml(
                        xml_string,
                        nome_arquivo,
                        supabase,
                        todos_itens,
                        resumo_notas,
                        alertas_notas,
                    )
                except Exception as exc:
                    st.error(f"Erro ao processar o XML {nome_arquivo}: {exc}")
                    continue
            else:
                st.warning(f"Tipo de arquivo não suportado: {nome_arquivo} (extensão: {extensao})")
                continue
        
        # Exibe resultados consolidados
        if resumo_notas:
            # Calcula totais para os cards
            try:
                df_resumo = pd.DataFrame(resumo_notas)
                df_resumo["Valor Total (vNF)"] = pd.to_numeric(df_resumo["Valor Total (vNF)"], errors="coerce").fillna(0)
                df_resumo["Valor ICMS (vICMS)"] = pd.to_numeric(df_resumo["Valor ICMS (vICMS)"], errors="coerce").fillna(0)
                
                total_notas_processadas = len(resumo_notas)
                soma_valores_totais = df_resumo["Valor Total (vNF)"].sum()
                soma_valores_icms = df_resumo["Valor ICMS (vICMS)"].sum()
            except Exception:
                total_notas_processadas = len(resumo_notas)
                soma_valores_totais = 0
                soma_valores_icms = 0
            
            # Cards no topo da página
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total de Notas Processadas", total_notas_processadas)
            with col2:
                st.metric("Soma dos Valores Totais (vNF)", f"R$ {soma_valores_totais:,.2f}")
            with col3:
                st.metric("Soma dos Valores de ICMS (vICMS)", f"R$ {soma_valores_icms:,.2f}")
            
            # Tabela resumo das notas
            st.markdown("---")
            st.subheader("📋 Resumo das Notas Processadas")
            df_resumo_display = df_resumo[
                [
                    "Número da Nota",
                    "Nome do Cliente",
                    "Valor Total (vNF)",
                    "Valor ICMS (vICMS)",
                    "CFOP",
                    "Sujeito a ST (PR)",
                    "Status Banco",
                    "Arquivo",
                ]
            ].copy()
            df_resumo_styled = df_resumo_display.style.apply(
                lambda row: [
                    "font-weight: bold;" if "⚠️ SIM" in str(value) else ""
                    for value in row
                ],
                axis=1,
            )
            st.dataframe(df_resumo_styled, use_container_width=True, hide_index=True)

            if st.button("🔄 Refazer Análise de ST"):
                resumo_notas = reprocessar_st_sessao(supabase, resumo_notas)
                df_resumo = pd.DataFrame(resumo_notas)
                df_resumo_display = df_resumo[
                    [
                        "Número da Nota",
                        "Nome do Cliente",
                        "Valor Total (vNF)",
                        "Valor ICMS (vICMS)",
                        "CFOP",
                        "Sujeito a ST (PR)",
                        "Status Banco",
                        "Arquivo",
                    ]
                ].copy()
                df_resumo_styled = df_resumo_display.style.apply(
                    lambda row: [
                        "font-weight: bold;" if "⚠️ SIM" in str(value) else ""
                        for value in row
                    ],
                    axis=1,
                )
                st.dataframe(
                    df_resumo_styled,
                    use_container_width=True,
                    hide_index=True,
                )
                st.success(
                    "Análise atualizada com base nas regras mais recentes!"
                )

            st.markdown("---")
            if st.button("🧮 Calcular Antecipação de ICMS-ST", type="primary"):
                memoria_rows = []
                aliquota_pr = 0.19

                for item in todos_itens:
                    if not item.get("Sujeito ST"):
                        continue
                    if not str(item.get("CFOP", "")).startswith("6"):
                        continue

                    mva = item.get("MVA")
                    mva_normalizada = safe_float(mva) if mva is not None else 0.0
                    if mva_normalizada > 1:
                        mva_normalizada = mva_normalizada / 100.0

                    valor_produto = safe_float(item.get("Valor Produto"))
                    valor_ipi = safe_float(item.get("IPI"))
                    valor_frete = safe_float(item.get("Frete"))
                    icms_origem = safe_float(item.get("ICMS Origem"))

                    base_calculo = (valor_produto + valor_ipi + valor_frete) * (
                        1 + mva_normalizada
                    )
                    icms_st = (base_calculo * aliquota_pr) - icms_origem

                    memoria_rows.append(
                        {
                            "Numero Nota": item.get("Numero Nota"),
                            "Código do Produto": item.get("Código do Produto"),
                            "Descrição": item.get("Descrição"),
                            "NCM": item.get("NCM"),
                            "CFOP": item.get("CFOP"),
                            "Valor Produto": valor_produto,
                            "IPI": valor_ipi,
                            "Frete": valor_frete,
                            "MVA": mva_normalizada,
                            "Base de Cálculo": base_calculo,
                            "ICMS Origem": icms_origem,
                            "Alíquota PR": aliquota_pr,
                            "ICMS-ST": icms_st,
                        }
                    )

                if memoria_rows:
                    st.subheader("🧾 Memória de Cálculo - ICMS-ST")
                    df_memoria = pd.DataFrame(memoria_rows)
                    st.dataframe(df_memoria, use_container_width=True, hide_index=True)

                    excel_buffer = BytesIO()
                    try:
                        df_memoria.to_excel(excel_buffer, index=False)
                        excel_buffer.seek(0)
                        st.download_button(
                            "⬇️ Exportar Memória para Excel",
                            data=excel_buffer,
                            file_name="memoria_calculo_icms_st.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )
                    except Exception as exc:
                        st.error(f"Erro ao gerar Excel: {exc}")

                    st.info(
                        "Exportação para PDF: gere o PDF a partir do Excel "
                        "ou ative uma biblioteca de PDF se desejar automatizar."
                    )
                else:
                    st.warning("Nenhum item sujeito a ST com CFOP interestadual encontrado.")
            
            # Exibe alertas apenas para erros específicos
            if alertas_notas:
                st.markdown("---")
                st.subheader("⚠️ Alertas")
                for alerta in alertas_notas:
                    if "ERRO: NF_DESTINATARIO_NAO_CADASTRADO" in alerta:
                        st.error(alerta)
                    elif "Operação Interestadual" in alerta:
                        st.warning(alerta)
                    else:
                        st.warning(alerta)
            
            # Botão de exportar para PDF
            st.markdown("---")
            if st.button("📄 Exportar para PDF", type="primary"):
                st.info("Funcionalidade de exportação para PDF será implementada em breve.")
        else:
            st.warning("Nenhuma nota foi processada dos arquivos XML enviados.")


def main() -> None:
    st.sidebar.title("ST-Analyzer-PR")

    menu = st.sidebar.radio(
        "Navegação",
        options=["Gestão de Clientes", "Análise de XML"],
    )

    if menu == "Gestão de Clientes":
        pagina_gestao_clientes()
    elif menu == "Análise de XML":
        pagina_analise_xml()


if __name__ == "__main__":
    main()