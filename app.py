import hashlib
import os
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
import zipfile

import pandas as pd
import streamlit as st
import xmltodict
from supabase import create_client, Client  # type: ignore

try:
    from st_aggrid import AgGrid, GridOptionsBuilder
    HAS_AGGRID = True
except ImportError:
    HAS_AGGRID = False

from streamlit_option_menu import option_menu

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

# Tenta carregar variáveis do .env, se python-dotenv estiver instalado
try:
    from dotenv import load_dotenv

    load_dotenv()
except ModuleNotFoundError:
    pass

st.set_page_config(page_title="ST-Analyzer-PR", layout="wide", initial_sidebar_state="expanded")

# CSS: Glassmorphism, fundo #0E1117, fonte Inter, sem menus Streamlit
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [data-testid="stAppViewContainer"], .stMarkdown, .stText, p, span, div, label, input, button {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    }
    h1, h2, h3, h4 { font-family: 'Inter', sans-serif !important; }

    /* Remover menus padrão Streamlit (software profissional) */
    #MainMenu, footer, header, [data-testid="stHeader"], [data-testid="stToolbar"], .stDeployButton,
    [data-testid="stDecoration"] { visibility: hidden !important; display: none !important; }

    /* Reduzir padding */
    .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; padding-left: 2rem !important; padding-right: 2rem !important; max-width: 100% !important; }
    [data-testid="stVerticalBlock"] > div { padding-top: 0.25rem !important; }

    /* Inputs e selects com glassmorphism */
    .stTextInput > div > div, .stSelectbox > div, .stDateInput > div {
        background: rgba(30, 33, 41, 0.6) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 10px !important;
    }

    /* Tema: fundo #0E1117 com gradiente sutil para glassmorphism */
    html, body, [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #0E1117 0%, #161B22 50%, #0E1117 100%) !important;
        color: #E6EDF3 !important;
    }
    [data-testid="stSidebar"] {
        background: rgba(14, 17, 23, 0.85) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-right: 1px solid rgba(48, 54, 61, 0.5) !important;
    }
    h1, h2, h3, h4 { color: #E6EDF3 !important; }

    /* Cards Glassmorphism (vidro fosco) — efeito visível */
    .premium-card {
        background: linear-gradient(135deg, rgba(30, 33, 41, 0.9) 0%, rgba(22, 27, 34, 0.95) 100%) !important;
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border-radius: 16px;
        padding: 20px;
        margin: 0 4px 12px 4px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px rgba(255,255,255,0.06), inset 0 1px 0 rgba(255,255,255,0.08);
        border: 1px solid rgba(255,255,255,0.1);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .premium-card:hover { transform: translateY(-3px); box-shadow: 0 16px 48px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.08); }
    .premium-card .card-icon { font-size: 1.5rem; margin-bottom: 8px; }
    .premium-card .card-label { font-size: 0.8rem; color: #8B949E !important; font-weight: 500; margin-bottom: 4px; }
    .premium-card .card-value { font-size: 1.6rem; font-weight: 700; color: #E6EDF3 !important; }
    .premium-card-blue { border-left: 4px solid #58A6FF; }
    .premium-card-green { border-left: 4px solid #3FB950; }
    .premium-card-red { border-left: 4px solid #F85149; }
    .premium-card-gold { border-left: 4px solid #D29922; }

    /* Tabelas com glassmorphism */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden !important;
        background: rgba(30, 33, 41, 0.5) !important;
        backdrop-filter: blur(8px);
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
    .stDataFrame table { background: transparent !important; color: #E6EDF3 !important; }
    .stDataFrame th { background-color: #161B22 !important; color: #58A6FF !important; border-color: rgba(48,54,61,0.5) !important; }
    .stDataFrame td { border-color: rgba(48,54,61,0.5) !important; }
    .stDataFrame tbody tr:hover td { background-color: rgba(33,38,45,0.6) !important; }

    /* AgGrid: Antecipação Pendente = vermelho pulsante */
    .ag-row.antecipacao-pendente .ag-cell { background-color: rgba(248, 81, 73, 0.2) !important; animation: pulse-row 2s ease-in-out infinite; }
    @keyframes pulse-row { 0%, 100% { background-color: rgba(248, 81, 73, 0.15) !important; } 50% { background-color: rgba(248, 81, 73, 0.3) !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def _render_premium_cards(total_itens: int, st_recolhida: int, antecipacao_pendente: int, valor_risco: float) -> None:
    """Renderiza os 4 cards de auditoria no topo."""
    _render_premium_cards_generic([
        ("Total de Itens", total_itens, "blue"),
        ("ST Recolhida (CFOPs 54xx/64xx)", st_recolhida, "green"),
        ("Antecipação Pendente (CFOP 61xx fora PR + operação comum)", antecipacao_pendente, "red"),
        ("Valor de Risco Estimado", valor_risco, "gold"),
    ])


def _render_premium_cards_generic(cards: list[tuple[str, str | int | float, str]]) -> None:
    """Renderiza N cards com glassmorphism. Cada card: (label, value, variant)."""
    icons = {"blue": "🛒", "green": "✅", "red": "🚨", "gold": "💰"}
    html_parts = []
    for label, value, variant in cards:
        if isinstance(value, (int, float)) and variant == "gold":
            val_str = f"R$ {value:,.2f}"
        elif value == "—":
            val_str = "—"
        else:
            val_str = str(value)
        icon = icons.get(variant, "📊")
        html_parts.append(
            f'<div class="premium-card premium-card-{variant}" style="flex: 1; min-width: 200px;">'
            f'<div class="card-icon">{icon}</div><div class="card-label">{label}</div><div class="card-value">{val_str}</div></div>'
        )
    st.markdown(
        f'<div style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 24px;">{"".join(html_parts)}</div>',
        unsafe_allow_html=True,
    )


def _render_metric_card(title: str, value: str | int, variant: str = "blue") -> None:
    """Card simples para páginas com uma única métrica."""
    v = "blue" if variant == "blue" else "green" if variant == "green" else "red" if variant == "rose" else "gold"
    cls = f"premium-card premium-card-{v}"
    st.markdown(f'<div class="{cls}"><div class="card-label">{title}</div><div class="card-value">{value}</div></div>', unsafe_allow_html=True)


def _get_supabase_credentials() -> tuple[str, str]:
    """
    Obtém SUPABASE_URL e SUPABASE_KEY: st.secrets (deploy) ou os.getenv (local).
    Nunca usa valores hardcoded.
    """
    url, key = "", ""
    try:
        # 1. st.secrets (Streamlit Cloud / deploy)
        sec = getattr(st, "secrets", None)
        if sec:
            supabase_sec = sec.get("supabase") or {}
            url = sec.get("SUPABASE_URL") or (supabase_sec.get("url") if isinstance(supabase_sec, dict) else "")
            key = sec.get("SUPABASE_KEY") or (supabase_sec.get("key") if isinstance(supabase_sec, dict) else "")
    except Exception:
        pass
    # 2. Fallback: variáveis de ambiente / .env (desenvolvimento local)
    if not url:
        url = os.getenv("SUPABASE_URL", "")
    if not key:
        key = os.getenv("SUPABASE_KEY", "")
    return (url or "").strip(), (key or "").strip()


@st.cache_resource
def get_supabase_client() -> Client | None:  # type: ignore[valid-type]
    """
    Inicializa o client do Supabase.
    Em deploy: use st.secrets (SUPABASE_URL, SUPABASE_KEY).
    Em local: use .env ou variáveis de ambiente.
    """
    url, key = _get_supabase_credentials()

    if not url or not key:
        raise RuntimeError(
            "Configure SUPABASE_URL e SUPABASE_KEY em st.secrets (deploy) ou .env (local). "
            "Nunca commite chaves no código."
        )

    try:
        client = create_client(url, key)
    except Exception as exc:
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
            "Configure SUPABASE_URL e SUPABASE_KEY em st.secrets (deploy) ou .env (local).\n\n"
            f"Detalhes técnicos: {exc}"
        )
        st.stop()


# --- Autenticação ---


def _hash_senha_sha256(senha: str) -> str:
    """Gera hash SHA256 da senha (sem salt), para comparação com o banco."""
    return hashlib.sha256(senha.encode()).hexdigest()


def _hash_senha_md5(senha: str) -> str:
    """Gera hash MD5 da senha (fallback para bancos legados)."""
    return hashlib.md5(senha.encode()).hexdigest()


def _senha_confere(senha: str, hash_banco: str) -> bool:
    """Compara senha digitada com hash no banco (SHA256 ou MD5)."""
    senha = (senha or "").strip()
    hash_banco = (hash_banco or "").strip().lower()
    if not hash_banco:
        return False
    # SHA256 (64 chars) ou MD5 (32 chars)
    if len(hash_banco) == 64:
        return _hash_senha_sha256(senha).lower() == hash_banco
    if len(hash_banco) == 32:
        return _hash_senha_md5(senha).lower() == hash_banco
    return False


def verificar_login(usuario: str, senha: str) -> dict | None:
    """
    Busca usuário na tabela public.usuarios, compara senha (SHA256 ou MD5).
    Retorna {'nome': str, 'usuario': str} se OK, None caso contrário.
    """
    usuario = (usuario or "").strip()
    senha = (senha or "").strip()
    if not usuario or not senha:
        return None

    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        resp = (
            supabase.table("usuarios")
            .select("usuario, senha, nome")
            .eq("usuario", usuario)
            .limit(1)
            .execute()
        )
        if not resp.data or len(resp.data) == 0:
            return None
        row = resp.data[0]
        hash_senha_banco = (row.get("senha") or "").strip()
        if not _senha_confere(senha, hash_senha_banco):
            return None
        nome = (row.get("nome") or row.get("usuario") or usuario).strip()
        return {"nome": nome, "usuario": row.get("usuario", usuario).strip()}
    except Exception:
        return None


def _validar_email(email: str) -> bool:
    """Valida formato de e-mail (ex: usuario@exemplo.com)."""
    if not email or not isinstance(email, str):
        return False
    email = email.strip()
    if "@" not in email or "." not in email:
        return False
    partes = email.split("@")
    if len(partes) != 2:
        return False
    local, dominio = partes[0].strip(), partes[1].strip()
    if not local or not dominio:
        return False
    if "." not in dominio or len(dominio.split(".")[-1]) < 2:
        return False
    return True


def _buscar_usuario_por_email(email: str) -> dict | None:
    """Busca usuário pelo e-mail na tabela usuarios."""
    try:
        supabase = get_supabase_client()
        if not supabase:
            return None
        resp = (
            supabase.table("usuarios")
            .select("id, usuario, nome, email")
            .eq("email", email.strip().lower())
            .limit(1)
            .execute()
        )
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
    except Exception:
        pass
    return None


def pagina_login() -> bool:
    """
    Exibe formulário de login e "Esqueci minha senha" se necessário.
    Retorna True se autenticado, False caso contrário.
    """
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; padding: 24px; border-radius: 16px; background: rgba(30, 33, 41, 0.6); border: 1px solid rgba(255,255,255,0.1);">
                <div style="font-size: 2.5rem; margin-bottom: 16px;">🔐</div>
                <h2 style="color: #E6EDF3; margin-bottom: 8px;">ST-Analyzer-PR</h2>
                <p style="color: #8B949E; font-size: 0.95rem;">Entre com suas credenciais para acessar o painel.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        mostra_esqueci_senha = st.session_state.get("esqueci_senha", False)
        if mostra_esqueci_senha:
            with st.form("form_esqueci_senha"):
                email_recuperacao = st.text_input("E-mail", placeholder="Digite o e-mail cadastrado", key="recuperacao_email")
                col_voltar, col_enviar, _ = st.columns([1, 1, 2])
                with col_voltar:
                    voltar = st.form_submit_button("← Voltar")
                with col_enviar:
                    enviado = st.form_submit_button("Enviar instruções")
                if voltar:
                    st.session_state["esqueci_senha"] = False
                    st.rerun()
                elif enviado and email_recuperacao:
                    if not _validar_email(email_recuperacao):
                        st.error("E-mail inválido. Use o formato correto (ex: usuario@empresa.com).")
                    else:
                        u = _buscar_usuario_por_email(email_recuperacao.strip().lower())
                        if u:
                            st.success(
                                "Instruções de recuperação enviadas para o e-mail informado. "
                                "Caso não receba em breve, entre em contato com o suporte interno (administrador)."
                            )
                        else:
                            st.warning("E-mail não encontrado. Verifique o endereço ou entre em contato com o suporte.")
        else:
            with st.form("form_login"):
                user = st.text_input("Usuário", placeholder="Digite o usuário", key="login_user")
                pwd = st.text_input("Senha", type="password", placeholder="Digite a senha", key="login_pwd")
                submitted = st.form_submit_button("Entrar")

                if submitted:
                    resultado = verificar_login(user, pwd)
                    if resultado:
                        st.session_state["user"] = resultado["nome"]
                        st.session_state["username"] = resultado["usuario"]
                        st.rerun()
                    else:
                        st.error("Usuário ou senha incorretos.")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Esqueci minha senha", key="btn_esqueci"):
                st.session_state["esqueci_senha"] = True
                st.rerun()

    return False


def pagina_configuracoes() -> None:
    """Aba de configurações: alterar senha (todos) e gestão de usuários (apenas admin)."""
    st.header("⚙️ Configurações")
    supabase = require_supabase()

    # Seção: Alterar minha senha (disponível para todos os usuários)
    st.subheader("🔐 Alterar minha senha")
    with st.form("form_alterar_senha"):
        senha_atual = st.text_input("Senha atual", type="password", placeholder="Digite sua senha atual")
        nova_senha = st.text_input("Nova senha", type="password", placeholder="Mínimo 6 caracteres")
        confirmar_senha = st.text_input("Confirmar nova senha", type="password", placeholder="Repita a nova senha")

        if st.form_submit_button("Alterar senha"):
            username = st.session_state.get("username")
            if not username:
                st.error("Sessão inválida. Faça login novamente.")
            elif not senha_atual or not senha_atual.strip():
                st.error("Informe a senha atual.")
            elif not nova_senha or len(nova_senha.strip()) < 6:
                st.error("A nova senha deve ter pelo menos 6 caracteres.")
            elif nova_senha.strip() != confirmar_senha.strip():
                st.error("A nova senha e a confirmação não coincidem.")
            else:
                try:
                    resp = supabase.table("usuarios").select("id, senha").eq("usuario", username).execute()
                    if not resp.data or len(resp.data) == 0:
                        st.error("Usuário não encontrado.")
                    else:
                        row = resp.data[0]
                        hash_banco = (row.get("senha") or "").strip()
                        if not _senha_confere(senha_atual.strip(), hash_banco):
                            st.error("Senha atual incorreta.")
                        else:
                            hash_nova = _hash_senha_sha256(nova_senha.strip())
                            supabase.table("usuarios").update({"senha": hash_nova}).eq("id", row["id"]).execute()
                            st.success("Senha alterada com sucesso!")
                            st.balloons()
                            st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao alterar senha: {exc}")

    st.markdown("---")

    # Seção: Gestão de usuários (apenas admin)
    eh_admin = st.session_state.get("username") == "admin"
    if not eh_admin:
        st.caption("A gestão de funcionários é restrita ao administrador.")
        return

    st.subheader("Gestão de usuários")
    st.caption("Cadastro de até 9 funcionários.")

    # Conta usuários (excluindo admin)
    try:
        resp = supabase.table("usuarios").select("id", count="exact").neq("usuario", "admin").execute()
        total_funcionarios = resp.count or 0
    except Exception:
        total_funcionarios = 0

    st.metric("Funcionários cadastrados", f"{total_funcionarios} / 9")

    if total_funcionarios >= 9:
        st.info("Limite de 9 funcionários atingido. Remova algum para cadastrar novo.")
        st.stop()

    st.markdown("---")
    st.subheader("Cadastrar novo funcionário")

    with st.form("form_cadastro_funcionario"):
        nome = st.text_input("Nome completo", placeholder="Ex: João da Silva")
        usuario = st.text_input("Usuário (login)", placeholder="Ex: joao.silva")
        email = st.text_input("E-mail", placeholder="Ex: joao@empresa.com")
        senha_inicial = st.text_input("Senha inicial", type="password", placeholder="Senha temporária")

        submitted = st.form_submit_button("Cadastrar")

        if submitted:
            erros = []
            if not nome or not nome.strip():
                erros.append("Nome é obrigatório.")
            if not usuario or not usuario.strip():
                erros.append("Usuário é obrigatório.")
            if not email or not email.strip():
                erros.append("E-mail é obrigatório.")
            elif not _validar_email(email):
                erros.append("E-mail inválido. Use o formato correto (ex: usuario@empresa.com).")
            if not senha_inicial or len(senha_inicial.strip()) < 6:
                erros.append("Senha inicial deve ter pelo menos 6 caracteres.")

            if erros:
                for e in erros:
                    st.error(e)
            else:
                # Verifica se usuário ou e-mail já existe
                try:
                    resp_u = supabase.table("usuarios").select("id").eq("usuario", usuario.strip()).execute()
                    if resp_u.data and len(resp_u.data) > 0:
                        st.error(f"Usuário '{usuario.strip()}' já existe.")
                    else:
                        resp_e = supabase.table("usuarios").select("id").eq("email", email.strip().lower()).execute()
                        if resp_e.data and len(resp_e.data) > 0:
                            st.error(f"E-mail já cadastrado.")
                        else:
                            hash_senha = _hash_senha_sha256(senha_inicial.strip())
                            supabase.table("usuarios").insert({
                                "nome": nome.strip(),
                                "usuario": usuario.strip(),
                                "email": email.strip().lower(),
                                "senha": hash_senha,
                            }).execute()
                            st.success(f"Funcionário {nome.strip()} cadastrado com sucesso.")
                            st.rerun()
                except Exception as exc:
                    err_msg = str(exc)
                    if "email" in err_msg.lower() or "column" in err_msg.lower():
                        st.error("Execute a migration 011_add_email_usuarios.sql no Supabase para habilitar o cadastro.")
                    else:
                        st.error(f"Erro ao cadastrar: {exc}")

    st.markdown("---")
    st.subheader("Funcionários cadastrados")
    try:
        resp_lista = supabase.table("usuarios").select("usuario, nome, email, created_at").neq("usuario", "admin").order("created_at", desc=True).execute()
        lista = resp_lista.data or []
    except Exception:
        try:
            resp_lista = supabase.table("usuarios").select("usuario, nome, created_at").neq("usuario", "admin").order("created_at", desc=True).execute()
            lista = resp_lista.data or []
        except Exception:
            lista = []
    if lista:
        df = pd.DataFrame(lista)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.caption("Nenhum funcionário cadastrado.")


def pagina_gestao_clientes() -> None:
    st.header("👥 Gestão de Clientes")

    supabase = require_supabase()

    # 4 Cards de KPIs no topo (glassmorphism)
    try:
        resp_c = supabase.table("clientes").select("id", count="exact").limit(1).execute()
        total_clientes = resp_c.count or 0
    except Exception:
        total_clientes = 0
    try:
        resp_n = supabase.table("notas_fiscais").select("id", count="exact").limit(1).execute()
        total_notas = resp_n.count or 0
    except Exception:
        total_notas = 0
    try:
        resp_i = supabase.table("itens_nota").select("id", count="exact").limit(1).execute()
        total_itens = resp_i.count or 0
    except Exception:
        total_itens = 0
    _render_premium_cards_generic([
        ("Total de Clientes", total_clientes, "blue"),
        ("Total de Notas", total_notas, "green"),
        ("Total de Itens", total_itens, "red"),
        ("Valor de Risco", "—", "gold"),
    ])
    st.markdown("<br>", unsafe_allow_html=True)

    st.subheader("Cadastrar novo cliente")
    st.caption("O sistema grava e utiliza apenas CNPJ numérico (14 dígitos). Pontos, traços e barras são removidos.")

    def _trava_cnpj():
        if "cnpj_cadastro" in st.session_state:
            v = st.session_state.cnpj_cadastro
            limpo = limpar_cnpj(v)
            if limpo is not None:
                st.session_state.cnpj_cadastro = limpo

    st.text_input(
        "CNPJ (apenas números serão mantidos)",
        key="cnpj_cadastro",
        max_chars=18,
        on_change=_trava_cnpj,
        help="Digite com ou sem pontuação; a pontuação é removida automaticamente.",
        placeholder="Ex: 23.420.405/0001-84",
    )

    with st.form("form_cadastro_cliente"):
        razao_social = st.text_input("Razão Social")
        submitted = st.form_submit_button("Salvar")

        if submitted:
            cnpj = st.session_state.get("cnpj_cadastro", "")
            cnpj_limpo = limpar_cnpj(cnpj)
            if not razao_social or not cnpj:
                st.warning("Preencha todos os campos (Razão Social e CNPJ).")
            elif not cnpj_limpo or len(cnpj_limpo) != 14:
                st.warning("CNPJ deve conter 14 dígitos (pontuação será ignorada).")
            else:
                try:
                    data = {
                        "razao_social": razao_social,
                        "nome_fantasia": razao_social,
                        "cnpj": cnpj_limpo,
                        "inscricao_estadual": None,
                        "uf": "PR",
                    }
                    response = supabase.table("clientes").insert(data).execute()

                    if response.data:
                        st.success("Cliente cadastrado com sucesso! (CNPJ: " + formatar_cnpj(cnpj_limpo) + ")")
                        st.session_state.cnpj_cadastro = ""
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
        # Exibição com máscara no CNPJ (banco guarda só dígitos)
        clientes_exibir = [
            {**c, "cnpj": formatar_cnpj(c.get("cnpj"))}
            for c in clientes
        ]
        st.dataframe(clientes_exibir, use_container_width=True)


def salvar_nota_e_itens(
    supabase: Client,
    numero_nfe: str,
    cliente_id: str | None,
    valor_total: float,
    icms_total: float,
    itens: list,
    cnpj_destinatario: str | None = None,
    data_emissao: str | None = None,
    totais_impostos: dict | None = None,
    uf_origem: str | None = None,
    cst_principal: str | None = None,
) -> tuple[bool, str]:
    """
    Salva uma nota fiscal e seus itens no banco de dados.
    cnpj_destinatario: gravado apenas com dígitos (limpar_cnpj) para consultas e re-vinculação.
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
        
        cnpj_gravar = limpar_cnpj(cnpj_destinatario) if cnpj_destinatario else None
        # Insere a nota fiscal (cnpj_destinatario só dígitos)
        nota_data = {
            "numero_nfe": numero_nfe,
            "cliente_id": cliente_id,
            "valor_total": float(valor_total),
            "icms_total": float(icms_total),
            "data_importacao": datetime.now().isoformat(),
        }
        if cnpj_gravar is not None:
            nota_data["cnpj_destinatario"] = cnpj_gravar
        if data_emissao:
            nota_data["data_emissao"] = data_emissao
        if uf_origem:
            nota_data["uf_origem"] = str(uf_origem).strip().upper()[:2]
        if cst_principal:
            nota_data["cst_principal"] = str(cst_principal).strip()[:50]
        if totais_impostos:
            for k, v in totais_impostos.items():
                if v is not None:
                    nota_data[k] = float(v)
        
        # Tenta gravar; se alguma coluna não existir, faz fallback gradual preservando data_emissao.
        try:
            response_nota = supabase.table("notas_fiscais").insert(nota_data).execute()
        except Exception as exc:
            msg = str(exc)
            if "PGRST204" in msg or "42703" in msg:
                # Primeiro tenta sem cnpj_destinatario (mantém data_emissao)
                nota_data.pop("cnpj_destinatario", None)
                nota_data.pop("uf_origem", None)
                nota_data.pop("cst_principal", None)
                for k in ("icms_bc_total", "icms_st_total", "pis_total", "cofins_total", "ipi_total", "ibs_total", "cbs_total"):
                    nota_data.pop(k, None)
                try:
                    response_nota = supabase.table("notas_fiscais").insert(nota_data).execute()
                except Exception:
                    # Último fallback: remove data_emissao se coluna inexistente
                    nota_data.pop("data_emissao", None)
                    response_nota = supabase.table("notas_fiscais").insert(nota_data).execute()
            else:
                raise
        
        if not response_nota.data or len(response_nota.data) == 0:
            st.error(
                "Erro ao salvar nota no Supabase. "
                f"Resposta completa: {response_nota}"
            )
            return False, f"Erro ao salvar nota {numero_nfe}"
        
        nota_id = response_nota.data[0]["id"]
        
        # Insere os itens da nota (status_st: SUJEITO A ST quando NCM na base ou CFOP 54/64)
        if itens:
            itens_data = []
            for item in itens:
                ncm_item = limpar_ncm(item.get("ncm"))
                item_data = {
                    "nota_id": nota_id,
                    "codigo_produto": item.get("codigo_produto") or None,
                    "descricao": item.get("descricao") or None,
                    "ncm": ncm_item,
                    "cest": item.get("cest") or None,
                    "cfop": item.get("cfop") or None,
                    "valor_unitario": float(item.get("valor_unitario", 0)),
                    "valor_total": float(item.get("valor_total", 0)),
                }
                if item.get("status_st") is not None:
                    item_data["status_st"] = item["status_st"]
                # Campos de impostos (ICMS, ICMS-ST, PIS, COFINS, IPI, IBS, CBS)
                for col in (
                    "icms_bc", "icms_aliq", "icms_valor",
                    "icms_st_bc", "icms_st_aliq", "icms_st_valor",
                    "pis_bc", "pis_aliq", "pis_valor",
                    "cofins_bc", "cofins_aliq", "cofins_valor",
                    "ipi_bc", "ipi_aliq", "ipi_valor",
                    "ibs_valor", "cbs_valor",
                ):
                    if col in item and item[col] is not None:
                        item_data[col] = float(item[col])
                if "cst" in item and item["cst"] is not None:
                    item_data["cst"] = str(item["cst"]).strip()
                itens_data.append(item_data)
            
            if itens_data:
                try:
                    response_itens = supabase.table("itens_nota").insert(itens_data).execute()
                except Exception as ins_exc:
                    err_str = str(ins_exc)
                    cols_inexistentes = (
                        "42703" in err_str
                        or "does not exist" in err_str.lower()
                        or "PGRST204" in err_str
                        or "Could not find" in err_str
                        or "schema cache" in err_str.lower()
                    )
                    if cols_inexistentes:
                        # Colunas de impostos não existem; insere sem elas
                        for d in itens_data:
                            for col in (
                                "icms_bc", "icms_aliq", "icms_valor",
                                "icms_st_bc", "icms_st_aliq", "icms_st_valor",
                                "pis_bc", "pis_aliq", "pis_valor",
                                "cofins_bc", "cofins_aliq", "cofins_valor",
                                "ipi_bc", "ipi_aliq", "ipi_valor",
                                "ibs_valor", "cbs_valor",
                                "cst",
                            ):
                                d.pop(col, None)
                        response_itens = supabase.table("itens_nota").insert(itens_data).execute()
                    else:
                        raise
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


def limpar_ncm(valor: str | None) -> str | None:
    """
    Normalização total: remove qualquer caractere não numérico do NCM.
    Ex: 85.27 -> 8527; 8527.10.00 -> 85271000. Usado no XML e no banco.
    """
    if not valor:
        return None
    s = str(valor).strip()
    if not s:
        return None
    ncm = re.sub(r"\D", "", s)
    return ncm if ncm else None


def limpar_cnpj(valor: str | None) -> str | None:
    """
    Remove pontos, traços e barras do CNPJ antes de gravar ou comparar.
    Ex: 23.420.405/0001-84 -> 23420405000184. Retorna só os 14 dígitos.
    """
    if not valor:
        return None
    s = str(valor).strip()
    if not s:
        return None
    cnpj = re.sub(r"\D", "", s)
    return cnpj if cnpj else None


def formatar_cnpj(valor: str | None) -> str:
    """
    Máscara de exibição: 23420405000184 -> 23.420.405/0001-84.
    Por baixo do capô o sistema usa apenas os 14 dígitos.
    """
    cnpj = limpar_cnpj(valor)
    if not cnpj or len(cnpj) != 14:
        return str(valor or "").strip() or "—"
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


# Sinalização quando há match ST mas a nota está com ICMS-ST zerado
STATUS_IRREGULAR_ST = "❌ IRREGULAR: SUJEITO A ST NÃO RECOLHIDA"
STATUS_SUJEITO_ST = "⚠️ SUJEITO A ST (PR)"
# Badges e mensagens no Painel de Auditoria — Lógica Tripla
BADGE_ST_RECOLHIDA = "✅ ST RECOLHIDA (OK)"
BADGE_ANTECIPACAO_PENDENTE = "🚨 ANTECIPAÇÃO PENDENTE"
BADGE_OPERACAO_COMUM = "⚪ OPERAÇÃO COMUM"
BADGE_SUJEITO_ST = "⚠️ SUJEITO A ST"  # fallback
DIAGNOSTICO_ERRO_ST = "🚨 ERRO: ST não identificada no XML"
DIAGNOSTICO_ANTECIPACAO_PENDENTE = "Item sujeito a ST no PR. Recolhimento obrigatório pelo destinatário"
DIAGNOSTICO_ST_RECOLHIDA = "ST recolhida na origem. CFOP de substituição tributária."
DIAGNOSTICO_NCM_BASE = "Identificado por NCM (Base PR)"
DIAGNOSTICO_CFOP_XML = "⚠️ NCM ausente na base, mas ST identificada no XML"
DIAGNOSTICO_NCM_MAIS_CFOP = "✅ Confirmado (NCM + CFOP)"

# Cache em memória da base normativa de NCM (já sanitizada)
BASE_NORMATIVA_CACHE: list[dict] | None = None


# CFOPs de substituição tributária (ST recolhida na origem)
CFOPS_SUBSTITUICAO = ("5401", "5403", "5405", "6401", "6403", "6405")


def cfop_substituicao(cfop: str | None) -> bool:
    """Retorna True se o CFOP for de substituição (5401, 5403, 5405, 6401, 6403, 6405)."""
    if not cfop:
        return False
    s = str(cfop).strip()
    return s in CFOPS_SUBSTITUICAO


def cfop_indica_st(cfop: str | None) -> bool:
    """Retorna True se o CFOP indica operação com ST (prefixo 54 ou 64)."""
    if not cfop:
        return False
    s = str(cfop).strip()
    return s.startswith("54") or s.startswith("64")


def cfop_inicia_54_ou_64(cfop: str | None) -> bool:
    """Retorna True se o CFOP inicia em 5.4 ou 6.4 (ST recolhida na origem)."""
    if not cfop:
        return False
    s = str(cfop).strip()
    return s.startswith("54") or s.startswith("64")


def cfop_inicia_61(cfop: str | None) -> bool:
    """Retorna True se o CFOP inicia em 6.1 (operação interestadual)."""
    if not cfop:
        return False
    s = str(cfop).strip()
    return s.startswith("61")


def cfop_inicia_51(cfop: str | None) -> bool:
    """Retorna True se o CFOP inicia em 5.1 (venda interna)."""
    if not cfop:
        return False
    s = str(cfop).strip()
    return s.startswith("51")


def cfop_5405_ou_5403(cfop: str | None) -> bool:
    """Retorna True se o CFOP for exatamente 5405 ou 5403 (prova por CFOP no diagnóstico)."""
    if not cfop:
        return False
    s = str(cfop).strip()
    return s in ("5405", "5403")


def _sanitizar_ncm(valor: str | None) -> str:
    """
    Limpa NCM para comparação: remove pontos, espaços e demais não-dígitos.
    Ex: "12.34.56.78" ou "1234 5678" -> "12345678".
    """
    if not valor:
        return ""
    s = str(valor).strip().replace(".", "").replace(" ", "")
    return re.sub(r"\D", "", s)


def _sanitizar_cest(valor: str | None) -> str:
    """
    Limpa CEST para comparação: remove pontos, espaços e demais não-dígitos.
    Ex: "03.001.00" -> "0300100".
    """
    if not valor:
        return ""
    s = str(valor).strip().replace(".", "").replace(" ", "")
    return re.sub(r"\D", "", s)


def buscar_regra_st(supabase: Client, ncm: str, cest: str | None = None) -> dict | None:
    """
    Busca regra ST: CEST primeiro (mais específico), depois NCM.
    NCM e CEST são normalizados (pontos e espaços removidos).
    - 1) Se CEST informado: match exato por CEST na base.
    - 2) Se não encontrar ou sem CEST: match por NCM (exato ou prefixo 2/4/6 dígitos).
    """
    global BASE_NORMATIVA_CACHE

    ncm_xml_limpo = _sanitizar_ncm(ncm)
    cest_xml_limpo = _sanitizar_cest(cest) if cest else ""

    if not ncm_xml_limpo or len(ncm_xml_limpo) < 2:
        print(f"Buscando NCM {ncm_xml_limpo or ncm!r} na base... Encontrado: Não (NCM inválido)")
        return None

    try:
        if BASE_NORMATIVA_CACHE is None:
            try:
                resp = (
                    supabase.table("base_normativa_ncm")
                    .select("ncm, descricao, cest")
                    .execute()
                )
            except Exception:
                resp = (
                    supabase.table("base_normativa_ncm")
                    .select("ncm, descricao")
                    .execute()
                )
            BASE_NORMATIVA_CACHE = []
            for row in resp.data or []:
                base_raw = row.get("ncm")
                base_limpo = _sanitizar_ncm(base_raw)
                if not base_limpo:
                    continue
                r = dict(row)
                r["_ncm_limpo"] = base_limpo
                r["_cest_limpo"] = _sanitizar_cest(row.get("cest"))
                BASE_NORMATIVA_CACHE.append(r)

        if not BASE_NORMATIVA_CACHE:
            print(f"Buscando NCM {ncm_xml_limpo} na base... Encontrado: Não (base vazia)")
            return None

        escolhido: dict | None = None
        regra_ncm: str = ""

        # 1) Match por CEST (mais específico) — quando informado
        if cest_xml_limpo and len(cest_xml_limpo) >= 4:
            for row in BASE_NORMATIVA_CACHE:
                base_cest = row.get("_cest_limpo")
                if base_cest and base_cest == cest_xml_limpo:
                    escolhido = row
                    regra_ncm = str(row.get("ncm", ""))
                    print(f"Match encontrado para o CEST {cest_xml_limpo} (regra NCM {regra_ncm})")
                    return escolhido

        # 2) Fallback: NCM — match exato
        for row in BASE_NORMATIVA_CACHE:
            base_limpo = row.get("_ncm_limpo")
            if base_limpo and base_limpo == ncm_xml_limpo:
                escolhido = row
                regra_ncm = str(row.get("ncm", ""))
                break

        # 3) Fallback: NCM — regra de prefixo (2, 4 ou 6 dígitos)
        if escolhido is None:
            for length in (6, 4, 2):
                if len(ncm_xml_limpo) < length:
                    continue
                for row in BASE_NORMATIVA_CACHE:
                    base_limpo = row.get("_ncm_limpo")
                    if base_limpo and len(base_limpo) == length and ncm_xml_limpo.startswith(base_limpo):
                        escolhido = row
                        regra_ncm = str(row.get("ncm", ""))
                        break
                if escolhido is not None:
                    break

        if escolhido is not None:
            print(f"Match encontrado para o NCM {ncm_xml_limpo} através da regra {regra_ncm}")
        else:
            print(f"Buscando NCM {ncm_xml_limpo} na base... Encontrado: Não")
        return escolhido
    except Exception as exc:
        st.error(f"Erro ao consultar base normativa para NCM {ncm}: {exc}")
        print(f"Buscando NCM {ncm_xml_limpo} na base... Encontrado: Não (erro)")
        return None


def ncm_na_base_normativa(supabase: Client, ncm: str, cest: str | None = None) -> bool:
    """Retorna True se o NCM/CEST está na base normativa (usa buscar_regra_st)."""
    return buscar_regra_st(supabase, ncm, cest) is not None


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
    Refazer Análise: verifica se o NCM de cada item (do XML/banco) existe na
    base_normativa_ncm. Se existir, exibe "⚠️ SUJEITO A ST (PR)" na tela.
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
                        .select("ncm, cest, cfop")
                        .eq("nota_id", nota_id)
                        .execute()
                    )
                    for item in response_itens.data or []:
                        ncm = item.get("ncm")
                        if not ncm:
                            continue
                        if ncm_na_base_normativa(supabase, ncm, item.get("cest")):
                            sujeito_st_pr = True
            except Exception as exc:
                st.error(
                    f"Erro ao reprocessar ST da nota {numero_nfe}: {exc}"
                )

        nota_atualizada = dict(nota)
        nota_atualizada["Sujeito a ST (PR)"] = (
            "⚠️ SUJEITO A ST (PR)" if sujeito_st_pr else "Não"
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


def _primeiro_bloco(objeto: dict) -> dict | None:
    """Retorna o primeiro sub-bloco dict de um objeto (ex: ICMS00, ICMS10...)."""
    if not isinstance(objeto, dict):
        return None
    for v in objeto.values():
        if isinstance(v, dict):
            return v
    return None


def extrair_data_emissao_ide(ide: dict) -> str | None:
    """
    Extrai a data de emissão (YYYY-MM-DD) do bloco ide da NF-e.
    Aceita dhEmi (datetime) ou dEmi (date) em vários formatos.
    """
    if not isinstance(ide, dict):
        return None
    dh = ide.get("dhEmi") or ide.get("dEmi") or ide.get("dhemi") or ide.get("demi") or ""
    if not dh:
        return None
    dh = str(dh)
    if "T" in dh:
        return dh.split("T")[0]  # "2024-01-15"
    if len(dh) == 10 and dh[4] == "-":
        return dh
    if "/" in dh:
        parts = dh.split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return None


def _extrair_cst_icms(icms: dict) -> str | None:
    """
    Extrai CST do bloco ICMS do item.
    Retorna CST (2 dígitos) ou CSOSN (1 dígito para Simples Nacional) ou None.
    """
    if not isinstance(icms, dict):
        return None
    bloco = _primeiro_bloco(icms)
    if not bloco:
        return None
    cst = bloco.get("CST") or bloco.get("cst")
    if cst is not None and str(cst).strip():
        return str(cst).strip()
    csosn = bloco.get("CSOSN") or bloco.get("csosn")
    if csosn is not None and str(csosn).strip():
        return str(csosn).strip()
    # Fallback: deriva do nome do bloco (ICMS00 -> 00, ICMS10 -> 10)
    for k, v in icms.items():
        if isinstance(v, dict) and k.startswith("ICMS"):
            suf = k.replace("ICMS", "").strip()
            if suf.isdigit():
                return suf.zfill(2)
    return None


def extrair_impostos_item(item: dict) -> dict:
    """
    Extrai base, alíquota e valor de ICMS, ICMS-ST, PIS, COFINS, IPI, IBS e CBS do item.
    Também extrai CST (Código de Situação Tributária) do bloco ICMS.
    Retorna dict com chaves em snake_case para persistência.
    """
    imp = item.get("imposto", {}) or {}
    resultado = {
        "icms_bc": None, "icms_aliq": None, "icms_valor": None,
        "icms_st_bc": None, "icms_st_aliq": None, "icms_st_valor": None,
        "pis_bc": None, "pis_aliq": None, "pis_valor": None,
        "cofins_bc": None, "cofins_aliq": None, "cofins_valor": None,
        "ipi_bc": None, "ipi_aliq": None, "ipi_valor": None,
        "ibs_valor": None, "cbs_valor": None,
        "cst": None,
    }

    try:
        # ICMS (ICMS00, ICMS10, ICMS20, ICMS30, ICMS40, ICMS51, ICMS60, ICMS70, ICMS90, ICMSPart, ICMSST...)
        icms = imp.get("ICMS", {}) or {}
        bloco = _primeiro_bloco(icms)
        if bloco:
            resultado["icms_bc"] = safe_float(bloco.get("vBC"))
            resultado["icms_aliq"] = safe_float(bloco.get("pICMS"))
            resultado["icms_valor"] = safe_float(bloco.get("vICMS"))
            resultado["icms_st_bc"] = safe_float(bloco.get("vBCST"))
            resultado["icms_st_aliq"] = safe_float(bloco.get("pICMSST")) or safe_float(bloco.get("pMST"))
            resultado["icms_st_valor"] = safe_float(bloco.get("vICMSST")) or safe_float(bloco.get("vST"))
            resultado["cst"] = _extrair_cst_icms(icms)
        # ICMSST pode estar em bloco próprio (ex: grupo ICMSST)
        icms_st = imp.get("ICMSST", {}) or {}
        if isinstance(icms_st, dict):
            st_bloco = _primeiro_bloco(icms_st) or icms_st
            if isinstance(st_bloco, dict) and not resultado["icms_st_valor"]:
                resultado["icms_st_bc"] = safe_float(st_bloco.get("vBCST"))
                resultado["icms_st_aliq"] = safe_float(st_bloco.get("pICMSST")) or safe_float(st_bloco.get("pMST"))
                resultado["icms_st_valor"] = safe_float(st_bloco.get("vICMSST")) or safe_float(st_bloco.get("vST"))

        # PIS (PISAliq/PIS01, PISNT/PIS04, PISOutr, PISST...)
        pis = imp.get("PIS", {}) or {}
        bloco_pis = _primeiro_bloco(pis) or pis
        if isinstance(bloco_pis, dict):
            resultado["pis_bc"] = safe_float(bloco_pis.get("vBC"))
            resultado["pis_aliq"] = safe_float(bloco_pis.get("pPIS"))
            resultado["pis_valor"] = safe_float(bloco_pis.get("vPIS"))

        # COFINS (COFINSAliq/COFINS01, COFINSNT/COFINS04, COFINSOutr, COFINSST...)
        cofins = imp.get("COFINS", {}) or {}
        bloco_cof = _primeiro_bloco(cofins) or cofins
        if isinstance(bloco_cof, dict):
            resultado["cofins_bc"] = safe_float(bloco_cof.get("vBC"))
            resultado["cofins_aliq"] = safe_float(bloco_cof.get("pCOFINS"))
            resultado["cofins_valor"] = safe_float(bloco_cof.get("vCOFINS"))

        # IPI (IPITrib)
        ipi = imp.get("IPI", {}) or {}
        ipi_trib = ipi.get("IPITrib", ipi) if isinstance(ipi, dict) else {}
        if isinstance(ipi_trib, dict):
            resultado["ipi_bc"] = safe_float(ipi_trib.get("vBC"))
            resultado["ipi_aliq"] = safe_float(ipi_trib.get("pIPI"))
            resultado["ipi_valor"] = safe_float(ipi_trib.get("vIPI"))

        # IBS e CBS (Reforma Tributária - quando disponível)
        ibs = imp.get("IBS", {}) or {}
        cbs = imp.get("CBS", {}) or {}
        if isinstance(ibs, dict):
            resultado["ibs_valor"] = safe_float(ibs.get("vIBS")) or safe_float(ibs.get("vValor"))
        if isinstance(cbs, dict):
            resultado["cbs_valor"] = safe_float(cbs.get("vCBS")) or safe_float(cbs.get("vValor"))
    except Exception:
        pass

    return resultado


def processar_xml(
    xml_string: str,
    nome_arquivo: str,
    supabase: Client,
    todos_itens: list,
    resumo_notas: list,
    alertas_notas: list,
    cliente_id_manual: str | None = None,
) -> None:
    """
    Processa um XML de NF-e e extrai informações, acumulando nos dados consolidados.
    Se cliente_id_manual for informado, todas as notas são vinculadas a esse cliente
    e a validação de CNPJ do destinatário é ignorada (sem alerta NF_DESTINATARIO_NAO_CADASTRADO).
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
        
        # Extrai número da nota (nNF) e data de emissão da NF-e (obrigatório nas próximas importações)
        n_nf = None
        data_emissao = None
        try:
            ide_raw = inf_nfe.get("ide", {})
            ide = ide_raw[0] if isinstance(ide_raw, list) and ide_raw else (ide_raw if isinstance(ide_raw, dict) else {})
            n_nf = ide.get("nNF") or ide.get("nnf") or "N/A"
            data_emissao = extrair_data_emissao_ide(ide)
        except (KeyError, AttributeError, TypeError):
            n_nf = "N/A"
        
        # Extrai o CNPJ do destinatário (sempre limpo: só dígitos)
        cnpj_destinatario = None
        try:
            dest = inf_nfe.get("dest", {})
            raw_cnpj_dest = dest.get("CNPJ") or dest.get("cnpj")
            cnpj_destinatario = limpar_cnpj(raw_cnpj_dest) if raw_cnpj_dest else None
        except (KeyError, AttributeError, TypeError):
            pass

        # Extrai UF do emitente (origem da mercadoria) para auditoria de ST
        uf_origem = None
        try:
            emit = inf_nfe.get("emit", {})
            ender = emit.get("enderEmit", {}) if isinstance(emit, dict) else {}
            uf_raw = ender.get("UF") or ender.get("uf") if isinstance(ender, dict) else None
            uf_origem = str(uf_raw).strip().upper()[:2] if uf_raw else None
        except (KeyError, AttributeError, TypeError):
            pass
        
        alerta_cliente = None
        nome_cliente = None
        # Só valida CNPJ no banco se não houver cliente selecionado manualmente
        if cliente_id_manual:
            try:
                resp = supabase.table("clientes").select("id, razao_social, nome_fantasia").eq("id", str(cliente_id_manual)).limit(1).execute()
                if resp.data:
                    nome_cliente = resp.data[0].get("nome_fantasia") or resp.data[0].get("razao_social", "N/A")
                else:
                    nome_cliente = "Cliente selecionado"
            except Exception:
                nome_cliente = "Cliente selecionado"
        elif cnpj_destinatario:
            cnpj_busca = limpar_cnpj(cnpj_destinatario) or cnpj_destinatario
            try:
                response = (
                    supabase.table("clientes")
                    .select("id, razao_social, nome_fantasia, cnpj")
                    .eq("cnpj", cnpj_busca)
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

        # Valor de ICMS-ST da nota (vST no total) para sinalização de irregularidade
        v_st = "0.00"
        try:
            total_tot = inf_nfe.get("total", {}).get("ICMSTot", {})
            v_st = total_tot.get("vST") or total_tot.get("vICMSST") or "0.00"
        except (KeyError, AttributeError, TypeError):
            pass
        try:
            icms_st_zerado = float(v_st or 0) == 0
        except (ValueError, TypeError):
            icms_st_zerado = True

        # Processa cada item e identifica CFOPs e CSTs
        tem_cfop_6 = False
        cfops_encontrados = set()
        csts_encontrados: set[str] = set()
        itens_para_salvar = []
        ncm_cache: dict[str, dict | None] = {}
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


                # Verifica se o NCM/CEST está na base normativa (CEST primeiro, depois NCM)
                regra_st = None
                if ncm and ncm != "N/A":
                    cache_key = f"{ncm}|{cest or ''}"
                    if cache_key not in ncm_cache:
                        ncm_cache[cache_key] = buscar_regra_st(supabase, ncm, cest)
                    regra_st = ncm_cache[cache_key]
                    if regra_st:
                        sujeito_st_pr = True

                # CFOP 54 ou 64: OBRIGATORIAMENTE marca como SUJEITO A ST (alerta mesmo sem NCM na base)
                st_por_cfop = cfop_indica_st(cfop)
                if st_por_cfop:
                    sujeito_st_pr = True
                sujeito_st_item = bool(regra_st) or st_por_cfop

                # Feedback visual: Status ST e MVA Remanescente (irregular se ST zerado na nota)
                if sujeito_st_item:
                    status_st = STATUS_IRREGULAR_ST if icms_st_zerado else STATUS_SUJEITO_ST
                else:
                    status_st = "Não"
                mva_remanescente_val = None
                if regra_st and regra_st.get("mva_remanescente") is not None:
                    mva_val = regra_st["mva_remanescente"]
                    mva_remanescente_val = f"{float(mva_val) * 100:.1f}%" if mva_val else None

                # Impostos extraídos do XML (base, alíquota, valor, cst)
                impostos = extrair_impostos_item(item)
                if impostos.get("cst"):
                    csts_encontrados.add(str(impostos["cst"]).strip())
                cst_exibir = impostos.get("cst") or "—"

                # Dados para exibição
                todos_itens.append({
                    "Arquivo": nome_arquivo,
                    "Numero Nota": n_nf,
                    "Código do Produto": codigo_produto,
                    "Descrição": descricao,
                    "NCM": ncm,
                    "CFOP": cfop,
                    "CST": cst_exibir,
                    "Valor Produto": safe_float(valor_total),
                    "IPI": valor_ipi,
                    "Frete": valor_frete,
                    "ICMS Origem": icms_origem,
                    "Status ST": status_st,
                    "MVA Remanescente": mva_remanescente_val,
                })

                # Dados para salvar no banco (NCM normalizado: só dígitos; status_st para Painel)
                ncm_limpo = limpar_ncm(ncm) if ncm and ncm != "N/A" else None
                status_st_gravar = (STATUS_IRREGULAR_ST if icms_st_zerado else STATUS_SUJEITO_ST) if sujeito_st_item else None
                item_salvar = {
                    "codigo_produto": codigo_produto if codigo_produto != "N/A" else None,
                    "descricao": descricao if descricao != "N/A" else None,
                    "ncm": ncm_limpo,
                    "cest": cest,
                    "cfop": cfop if cfop != "N/A" else None,
                    "valor_unitario": valor_unitario,
                    "valor_total": float(valor_total) if valor_total else 0.0,
                    "status_st": status_st_gravar,
                }
                # Adiciona impostos ao item (base, alíquota, valor, cst)
                for k, v in impostos.items():
                    if v is not None:
                        if k == "cst":
                            item_salvar[k] = str(v).strip()
                        elif isinstance(v, (int, float)):
                            item_salvar[k] = float(v)
                        else:
                            item_salvar[k] = v
                itens_para_salvar.append(item_salvar)
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

        # Determina CST principal (primeiro encontrado ou "Múltiplos" se houver vários)
        cst_principal = None
        if csts_encontrados:
            cst_principal = list(csts_encontrados)[0] if len(csts_encontrados) == 1 else f"Múltiplos ({', '.join(sorted(csts_encontrados))})"
        
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
        
        # Extrai valores totais da nota (ICMSTot)
        v_nf = "0.00"
        v_icms = "0.00"
        totais_impostos = {}
        try:
            total = inf_nfe.get("total", {}).get("ICMSTot", {})
            v_nf = total.get("vNF") or "0.00"
            v_icms = total.get("vICMS") or "0.00"
            totais_impostos = {
                "icms_bc_total": safe_float(total.get("vBC")),
                "icms_st_total": safe_float(total.get("vST") or total.get("vICMSST")),
                "pis_total": safe_float(total.get("vPIS")),
                "cofins_total": safe_float(total.get("vCOFINS")),
                "ipi_total": safe_float(total.get("vIPI")),
                "ibs_total": safe_float(total.get("vIBS")),
                "cbs_total": safe_float(total.get("vCBS")),
            }
        except (KeyError, AttributeError, TypeError):
            st.warning(f"Não foi possível extrair valores totais de {nome_arquivo}")
        
        # Cliente: prioridade ao selecionado manualmente; senão busca por CNPJ (normalizado)
        cliente_id = None
        if cliente_id_manual:
            cliente_id = str(cliente_id_manual)
        elif cnpj_destinatario:
            cnpj_busca = limpar_cnpj(cnpj_destinatario) or cnpj_destinatario
            try:
                response_cliente = (
                    supabase.table("clientes")
                    .select("id")
                    .eq("cnpj", cnpj_busca)
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
                cnpj_destinatario=cnpj_destinatario,
                data_emissao=data_emissao,
                totais_impostos=totais_impostos,
                uf_origem=uf_origem,
                cst_principal=cst_principal,
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
            "CST": cst_principal or "—",
            "Sujeito a ST (PR)": "⚠️ SUJEITO A ST (PR)" if sujeito_st_pr else "Não",
            "Status Banco": status_banco,
            "Arquivo": nome_arquivo,
        })
            
    except Exception as exc:
        st.error(f"Erro ao processar o XML {nome_arquivo}: {exc}")


def pagina_analise_xml() -> None:
    st.header("📄 Análise de XML")

    st.write(
        "Faça o upload de arquivos XML de NF-e (modelo 55) para futura análise "
        "de ICMS-ST por antecipação no PR."
    )

    supabase = require_supabase()

    # Seletor de cliente: obrigatório. Todas as notas do upload serão vinculadas a ele.
    try:
        resp_c = (
            supabase.table("clientes")
            .select("id, razao_social, nome_fantasia")
            .order("razao_social")
            .execute()
        )
        clientes_lista = resp_c.data or []
    except Exception as exc:
        st.error(f"Erro ao carregar clientes: {exc}")
        clientes_lista = []

    if not clientes_lista:
        st.error("Cadastre ao menos um cliente na página 'Gestão de Clientes' antes de importar XML.")
        return

    opcoes = [("Selecione um cliente...", None)]
    opcoes += [
        (c.get("nome_fantasia") or c.get("razao_social") or str(c["id"]), c["id"])
        for c in clientes_lista
    ]

    idx_cliente = st.selectbox(
        "Cliente (obrigatório — vincula todas as notas ao cliente selecionado)",
        options=range(len(opcoes)),
        format_func=lambda i: opcoes[i][0],
        index=0,
    )
    cliente_id_auditoria = opcoes[idx_cliente][1]
    nome_cliente_auditoria = opcoes[idx_cliente][0]
    cliente_selecionado = cliente_id_auditoria is not None

    if not cliente_selecionado:
        st.warning("Selecione um cliente antes de fazer o upload dos XMLs.")
        return

    st.markdown(f"**Importando notas para:** {nome_cliente_auditoria}")

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
                                    cliente_id_manual=cliente_id_auditoria,
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
                        cliente_id_manual=cliente_id_auditoria,
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
            
            st.success("Cruzamento concluído com a base normativa!")
            
            # Tabela resumo das notas
            st.markdown("---")
            st.subheader("📋 Resumo das Notas Processadas")
            colunas_resumo = ["Número da Nota", "Nome do Cliente", "Valor Total (vNF)", "Valor ICMS (vICMS)", "CFOP", "CST", "Sujeito a ST (PR)", "Status Banco", "Arquivo"]
            df_resumo_display = df_resumo[[c for c in colunas_resumo if c in df_resumo.columns]].copy()
            df_resumo_styled = df_resumo_display.style.apply(
                lambda row: [
                    "font-weight: bold;" if ("SUJEITO A ST" in str(value) or "IRREGULAR" in str(value)) else ""
                    for value in row
                ],
                axis=1,
            )
            st.dataframe(df_resumo_styled, use_container_width=True, hide_index=True)

            # Detalhamento por item (Status ST e MVA Remanescente)
            if todos_itens:
                st.markdown("---")
                with st.expander("📦 Itens por nota (Status ST e MVA Remanescente)", expanded=False):
                    df_itens = pd.DataFrame(todos_itens)
                    st.dataframe(df_itens, use_container_width=True, hide_index=True)

            if st.button("🔄 Refazer Análise de ST"):
                resumo_notas = reprocessar_st_sessao(supabase, resumo_notas)
                df_resumo = pd.DataFrame(resumo_notas)
                df_resumo_display = df_resumo[[c for c in colunas_resumo if c in df_resumo.columns]].copy()
                df_resumo_styled = df_resumo_display.style.apply(
                    lambda row: [
                        "font-weight: bold;" if ("SUJEITO A ST" in str(value) or "IRREGULAR" in str(value)) else ""
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


def _gerar_pdf_auditoria(
    itens_antecipacao: list[dict],
    nome_cliente: str,
    valor_total_antecipacao: float,
) -> bytes | None:
    """
    Gera PDF do relatório de auditoria focado em itens de Antecipação Pendente.
    Retorna bytes do PDF ou None se reportlab não disponível.
    """
    if not HAS_REPORTLAB or not itens_antecipacao:
        return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    elements = []

    # Cabeçalho profissional
    titulo = ParagraphStyle(
        name="TituloRelatorio",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=12,
        textColor=colors.HexColor("#1a1a1a"),
    )
    elements.append(Paragraph("Relatório de Auditoria de ICMS-ST", titulo))
    elements.append(Spacer(1, 0.5*cm))

    # Cliente e data
    dados_cabecalho = f"<b>Cliente:</b> {nome_cliente}<br/><b>Data da análise:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    elements.append(Paragraph(dados_cabecalho, styles["Normal"]))
    elements.append(Spacer(1, 1*cm))

    # Tabela: NCM, Descrição, Valor, Diagnóstico Fiscal
    headers = ["NCM", "Descrição", "Valor (R$)", "Diagnóstico Fiscal"]
    data = [[h for h in headers]]
    for item in itens_antecipacao:
        desc = str(item.get("Descrição", item.get("descricao", "—")) or "—")
        if len(desc) > 50:
            desc = desc[:50] + "…"
        valor = float(item.get("Valor Item", item.get("valor_total", 0)) or 0)
        valor_str = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        diag = str(item.get("Diagnóstico Fiscal", item.get("diagnostico", "—")) or "—")
        if len(diag) > 80:
            diag = diag[:80] + "…"
        data.append([str(item.get("NCM", item.get("ncm", "—")) or "—"), desc, valor_str, diag])

    col_widths = [3*cm, 6*cm, 3*cm, 6*cm]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 1*cm))

    # Totalização
    elements.append(Paragraph("<b>Totalização</b>", styles["Heading2"]))
    total_str = f"R$ {valor_total_antecipacao:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    total_text = f"Valor total de base de cálculo sujeito à antecipação de ICMS-ST: <b>{total_str}</b>"
    elements.append(Paragraph(total_text, styles["Normal"]))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("Itens listados requerem regularização pelo destinatário no Estado do Paraná.", styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()


def _compute_auditoria_kpis(supabase: Client, nota_ids: list) -> dict:
    """Calcula os KPIs (total_itens, st_recolhida, antecipacao_pendente, irregulars, valor_risco) para as notas."""
    try:
        resp_itens = supabase.table("itens_nota").select("id, nota_id, ncm, cest, valor_total, status_st, cfop").in_("nota_id", nota_ids).execute()
        itens_raw = resp_itens.data or []
        resp_notas = supabase.table("notas_fiscais").select("id, uf_origem").in_("id", nota_ids).execute()
        mapa_uf_origem: dict[str, str] = {}
        for n in (resp_notas.data or []):
            uf = n.get("uf_origem")
            mapa_uf_origem[str(n["id"])] = str(uf).strip().upper() if uf else ""
    except Exception:
        return {}
    ncm_base_cache: dict[str, bool] = {}
    st_recolhida = 0
    antecipacao_pendente = 0
    irregulars = 0
    valor_risco = 0.0
    for item in itens_raw:
        valor = float(item.get("valor_total", 0) or 0)
        ncm = item.get("ncm")
        cest = item.get("cest")
        cfop = item.get("cfop")
        nota_id = str(item.get("nota_id", ""))
        uf_origem = mapa_uf_origem.get(nota_id, "")
        status_db = (item.get("status_st") or "").strip()
        sujeito_st = bool(item.get("status_st"))
        irregular_db = sujeito_st and (STATUS_IRREGULAR_ST in status_db or "IRREGULAR" in status_db)
        cache_key = f"{ncm}|{cest or ''}"
        if cache_key not in ncm_base_cache:
            ncm_base_cache[cache_key] = buscar_regra_st(supabase, ncm, cest) is not None
        ncm_na_base = ncm_base_cache[cache_key]
        cfop_54_64 = cfop_inicia_54_ou_64(cfop)
        cfop_61 = cfop_inicia_61(cfop)
        cfop_51 = cfop_inicia_51(cfop)
        irregular = irregular_db or (cfop_51 and ncm_na_base)
        if irregular:
            irregulars += 1
        elif ncm_na_base and cfop_54_64:
            st_recolhida += 1
        elif (cfop_61 and uf_origem and uf_origem != "PR") or (ncm_na_base and not cfop_54_64 and not cfop_51):
            antecipacao_pendente += 1
            valor_risco += valor
    return {
        "total_itens": len(itens_raw),
        "st_recolhida": st_recolhida,
        "antecipacao_pendente": antecipacao_pendente,
        "irregulars": irregulars,
        "valor_risco": valor_risco,
    }


def _exibir_resultados_auditoria(supabase: Client, nota_ids: list) -> None:
    """Exibe resumo (KPIs), tabela de validação de sujeição e filtro."""
    itens_auditoria: list[dict] = []
    mapa_nota: dict[str, str] = {}

    mapa_cliente: dict[str, str] = {}
    try:
        resp_notas = (
            supabase.table("notas_fiscais")
            .select("id, numero_nfe, cliente_id, uf_origem")
            .in_("id", nota_ids)
            .execute()
        )
        mapa_uf_origem: dict[str, str] = {}
        for n in resp_notas.data or []:
            mapa_nota[str(n["id"])] = n.get("numero_nfe", "")
            uf = n.get("uf_origem")
            mapa_uf_origem[str(n["id"])] = str(uf).strip().upper() if uf else ""
        ids_clientes = {str(n["cliente_id"]) for n in (resp_notas.data or []) if n.get("cliente_id")}
        if ids_clientes:
            resp_c = supabase.table("clientes").select("id, nome_fantasia, razao_social").in_("id", list(ids_clientes)).execute()
            for c in resp_c.data or []:
                mapa_cliente[str(c["id"])] = c.get("nome_fantasia") or c.get("razao_social") or str(c["id"])

        try:
            resp_itens = (
                supabase.table("itens_nota")
                .select("id, nota_id, descricao, ncm, cest, valor_total, status_st, codigo_produto, cfop, cst")
                .in_("nota_id", nota_ids)
                .execute()
            )
        except Exception:
            resp_itens = (
                supabase.table("itens_nota")
                .select("id, nota_id, descricao, ncm, cest, valor_total, status_st, codigo_produto, cfop")
                .in_("nota_id", nota_ids)
                .execute()
            )
        itens_raw = resp_itens.data or []
    except Exception as exc:
        st.error(f"Erro ao carregar itens: {exc}")
        return

    # Cache NCM -> na base normativa (para diagnóstico fiscal)
    ncm_base_cache: dict[str, bool] = {}

    for item in itens_raw:
        valor = float(item.get("valor_total", 0) or 0)
        sujeito_st = bool(item.get("status_st"))
        status_db = (item.get("status_st") or "").strip()
        irregular_db = sujeito_st and (STATUS_IRREGULAR_ST in status_db or "IRREGULAR" in status_db)

        # Lógica de status: NCM na base + CFOP + UF de origem
        ncm = item.get("ncm")
        cest = item.get("cest")
        cfop = item.get("cfop")
        nota_id = str(item.get("nota_id", ""))
        uf_origem = mapa_uf_origem.get(nota_id, "")
        cache_key = f"{ncm}|{cest or ''}"
        if cache_key not in ncm_base_cache:
            ncm_base_cache[cache_key] = buscar_regra_st(supabase, ncm, cest) is not None
        ncm_na_base = ncm_base_cache[cache_key]
        cfop_subst = cfop_substituicao(cfop)
        cfop_54_64 = cfop_inicia_54_ou_64(cfop)
        cfop_61 = cfop_inicia_61(cfop)
        cfop_51 = cfop_inicia_51(cfop)

        # Status visual — Lógica atualizada:
        # ❌ IRREGULAR: já irregular no XML OU CFOP 5.1 (venda interna) que deveria ter ST
        # ✅ ST RECOLHIDA: NCM na base + CFOP 5.4 ou 6.4
        # 🚨 ANTECIPAÇÃO PENDENTE: CFOP 6.1 de fora do PR (ST na entrada) OU NCM na base + CFOP comum
        irregular = irregular_db or (cfop_51 and ncm_na_base)
        if irregular:
            status_badge = "❌ IRREGULAR"
            diagnostico = DIAGNOSTICO_ERRO_ST
        elif ncm_na_base and cfop_54_64:
            status_badge = BADGE_ST_RECOLHIDA
            diagnostico = DIAGNOSTICO_ST_RECOLHIDA
        elif (cfop_61 and uf_origem and uf_origem != "PR") or (ncm_na_base and not cfop_54_64 and not cfop_51):
            status_badge = BADGE_ANTECIPACAO_PENDENTE
            diagnostico = DIAGNOSTICO_ANTECIPACAO_PENDENTE
        elif sujeito_st and not ncm_na_base and cfop_indica_st(cfop):
            status_badge = "⚠️ SUJEITO A ST (via CFOP)"
            diagnostico = DIAGNOSTICO_CFOP_XML
            print(f"⚠️ NCM ausente na base, mas ST identificada no XML. NCM={ncm!r}, CFOP={cfop!r}")
        else:
            status_badge = BADGE_OPERACAO_COMUM
            diagnostico = "NCM não sujeito a ST na base normativa do PR."

        itens_auditoria.append({
            "Status": status_badge,
            "Diagnóstico Fiscal": diagnostico,
            "Número NF": mapa_nota.get(str(item.get("nota_id", "")), "—"),
            "Código": item.get("codigo_produto") or "—",
            "Descrição": (str(item.get("descricao") or "—")[:80] + "…") if len(str(item.get("descricao") or "")) > 80 else (item.get("descricao") or "—"),
            "NCM": item.get("ncm") or "—",
            "CEST": item.get("cest") or "—",
            "CFOP": item.get("cfop") or "—",
            "CST": item.get("cst") or "—",
            "Valor Item": valor,
            "_sujeito_st": sujeito_st,
            "_irregular": irregular,
        })

    if not itens_auditoria:
        st.warning("Nenhum item encontrado nas notas selecionadas.")
        return

    df = pd.DataFrame(itens_auditoria)
    total_notas = len(set(str(x) for x in nota_ids))
    total_itens = len(df)
    itens_st = int(df["_sujeito_st"].sum())
    irregulars = int(df["_irregular"].sum())
    antecipacao_pendente = int((df["Status"] == BADGE_ANTECIPACAO_PENDENTE).sum())
    st_recolhida = int((df["Status"] == BADGE_ST_RECOLHIDA).sum())
    valor_risco = float(df.loc[df["Status"] == BADGE_ANTECIPACAO_PENDENTE, "Valor Item"].sum())

    # Guarda KPIs no session_state para exibir no topo da página
    st.session_state["auditoria_kpis"] = {
        "total_itens": total_itens,
        "st_recolhida": st_recolhida,
        "antecipacao_pendente": antecipacao_pendente,
        "irregulars": irregulars,
        "valor_risco": valor_risco,
    }

    # 1. 4 Cards Premium no topo
    st.markdown("---")
    st.subheader("📊 Resumo da Auditoria")
    _render_premium_cards(total_itens, st_recolhida, antecipacao_pendente, valor_risco)

    # Botão PDF estilizado abaixo dos cards
    df_pendente_cards = df[df["Status"] == BADGE_ANTECIPACAO_PENDENTE].copy()
    nomes_uniq = list(dict.fromkeys(mapa_cliente.get(str(n.get("cliente_id", "")), "") for n in (resp_notas.data or []) if n.get("cliente_id")))
    nomes_uniq = [x for x in nomes_uniq if x]
    nome_cliente_pdf = nomes_uniq[0] if len(nomes_uniq) == 1 else (", ".join(nomes_uniq[:3]) + ("..." if len(nomes_uniq) > 3 else "")) if nomes_uniq else "Não identificado"
    if HAS_REPORTLAB and not df_pendente_cards.empty:
        pdf_bytes_btn = _gerar_pdf_auditoria(df_pendente_cards.to_dict("records"), nome_cliente_pdf, valor_risco)
        if pdf_bytes_btn:
            st.download_button(
                "📄 Exportar Relatório PDF",
                data=pdf_bytes_btn,
                file_name=f"relatorio_auditoria_icms_st_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                type="primary",
                key="btn_pdf_auditoria",
            )
    elif antecipacao_pendente == 0:
        st.caption("Nenhum item com Antecipação Pendente. O PDF será gerado quando houver itens a regularizar.")

    # 2. Resumo de auditoria (frase clara antes da tabela)
    st.markdown("---")
    st.markdown(
        f"Foram analisados **{total_itens}** itens: **{st_recolhida}** ST recolhida, **{antecipacao_pendente}** antecipação pendente e **{irregulars}** possíveis irregularidades."
    )

    # 3. Filtros
    filtro_col1, filtro_col2 = st.columns(2)
    with filtro_col1:
        mostrar_apenas_st = st.checkbox("Mostrar apenas itens com ST", value=False)
    with filtro_col2:
        mostrar_apenas_pendente = st.checkbox("🚨 Apenas Antecipação Pendente (foco)", value=False)
    if mostrar_apenas_pendente:
        df_exibir = df[df["Status"] == BADGE_ANTECIPACAO_PENDENTE].copy()
    elif mostrar_apenas_st:
        df_exibir = df[df["_sujeito_st"]].copy()
    else:
        df_exibir = df.copy()

    # 4. Tabela de Detalhes (AgGrid com destaque para Antecipação Pendente)
    st.subheader("📋 Tabela de Detalhes — Validação de Sujeição")
    colunas_exibir = ["Status", "Diagnóstico Fiscal", "Número NF", "Descrição", "NCM", "CEST", "CFOP", "CST", "Valor Item"]
    colunas_exibir = [c for c in colunas_exibir if c in df_exibir.columns]
    df_tabela = df_exibir[colunas_exibir].copy()
    df_tabela["Valor Item"] = df_tabela["Valor Item"].apply(lambda x: f"R$ {x:,.2f}")

    if HAS_AGGRID:
        try:
            gb = GridOptionsBuilder.from_dataframe(df_tabela)
            gb.configure_grid_options(
                domLayout="normal",
                rowClassRules={
                    "antecipacao-pendente": 'params.data.Status && params.data.Status.indexOf("ANTECIPAÇÃO PENDENTE") >= 0',
                },
            )
            gb.configure_default_column(resizable=True, sortable=True)
            gb.configure_column("Valor Item", width=120)
            gb.configure_column("Diagnóstico Fiscal", width=280)
            grid_options = gb.build()
            AgGrid(
                df_tabela,
                grid_options=grid_options,
                use_container_width=True,
                height=400,
                theme="streamlit",
            )
        except Exception:
            st.dataframe(df_tabela, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_tabela, use_container_width=True, hide_index=True)

    # 4. Exportação (Excel, HTML)
    st.markdown("---")
    st.subheader("📥 Exportar Relatório")
    col_ex1, col_ex2, _ = st.columns([1, 1, 2])
    with col_ex1:
        buffer_xlsx = BytesIO()
        df_export = df_exibir[colunas_exibir].copy()
        try:
            df_export.to_excel(buffer_xlsx, index=False, engine="openpyxl")
        except Exception:
            df_export.to_csv(buffer_xlsx, index=False, sep=";")
            buffer_xlsx.seek(0)
            st.download_button(
                "📥 Gerar Relatório (CSV)",
                data=buffer_xlsx.getvalue(),
                file_name=f"auditoria_st_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )
        else:
            buffer_xlsx.seek(0)
            st.download_button(
                "📥 Gerar Relatório (Excel)",
                data=buffer_xlsx.getvalue(),
                file_name=f"auditoria_st_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    with col_ex2:
        html_report = df_export.to_html(index=False, classes="table", escape=False)
        st.download_button(
            "📥 Gerar Relatório (HTML/PDF)",
            data=html_report,
            file_name=f"auditoria_st_{datetime.now().strftime('%Y%m%d_%H%M')}.html",
            mime="text/html",
        )


def pagina_painel_auditoria() -> None:
    """Painel de Auditoria: filtros, tabela de notas e reprocessamento ST."""
    st.header("📋 Painel de Auditoria")

    supabase = require_supabase()

    # 1. Dashboard de KPIs — 4 cards no topo (sempre visíveis)
    nota_ids = st.session_state.get("auditoria_nota_ids", [])
    if nota_ids:
        kpis = _compute_auditoria_kpis(supabase, nota_ids)
        if kpis:
            st.session_state["auditoria_kpis"] = kpis
    kpis = st.session_state.get("auditoria_kpis", {})
    total_itens = kpis.get("total_itens", 0)
    st_recolhida = kpis.get("st_recolhida", 0)
    antecipacao_pendente = kpis.get("antecipacao_pendente", 0)
    valor_risco = kpis.get("valor_risco", 0.0)
    _render_premium_cards(total_itens, st_recolhida, antecipacao_pendente, valor_risco)
    if not kpis:
        st.caption("Use os filtros abaixo, busque notas e clique em 'Visualizar Resultados' para carregar os KPIs.")

    st.markdown("---")
    # 2. Filtros de Busca
    st.subheader("Filtros de Busca")
    col_f1, col_f2, col_f3 = st.columns([2, 1, 1])

    with col_f1:
        # Carrega clientes; armazena (id, cnpj_limpo) para filtrar também notas sem vínculo por CNPJ
        try:
            resp_clientes = (
                supabase.table("clientes")
                .select("id, razao_social, nome_fantasia, cnpj")
                .order("razao_social")
                .execute()
            )
            clientes = resp_clientes.data or []
            opcoes_cliente = [("Todos os clientes", None, None)]
            for c in clientes:
                nome = c.get("nome_fantasia") or c.get("razao_social") or str(c["id"])
                cnpj_limpo = limpar_cnpj(c.get("cnpj"))
                opcoes_cliente.append((nome, c["id"], cnpj_limpo))
        except Exception as exc:
            st.error(f"Erro ao carregar clientes: {exc}")
            clientes = []
            opcoes_cliente = [("Todos os clientes", None, None)]

        idx_cliente = st.selectbox(
            "Cliente",
            options=range(len(opcoes_cliente)),
            format_func=lambda i: opcoes_cliente[i][0],
            index=0,
        )
        cliente_id = opcoes_cliente[idx_cliente][1]
        cliente_cnpj = opcoes_cliente[idx_cliente][2]

    with col_f2:
        data_inicial = st.date_input("Data emissão (inicial)", value=None)

    with col_f3:
        data_final = st.date_input("Data emissão (final)", value=None)

    if st.button("🔍 Buscar Notas"):
        st.session_state["auditoria_buscar"] = True
        st.session_state.pop("auditoria_nota_ids", None)
        st.session_state.pop("auditoria_kpis", None)

    if not st.session_state.get("auditoria_buscar", False):
        st.info("Defina os filtros e clique em 'Buscar Notas' para carregar as notas.")
        return

    # 2. Query de notas
    try:
        inicio = datetime.combine(data_inicial, datetime.min.time()).isoformat() + "Z" if data_inicial else None
        fim = datetime.combine(data_final, datetime.max.time()).isoformat() + "Z" if data_final else None

        def _exec_query(com_cnpj: bool, com_data_emissao: bool = True, com_cst: bool = True):
            base_cols = "id, numero_nfe, cliente_id, cnpj_destinatario, valor_total, icms_total, data_importacao, data_emissao" if com_cnpj else "id, numero_nfe, cliente_id, valor_total, icms_total, data_importacao, data_emissao"
            if com_cst:
                base_cols += ", cst_principal"
            if not com_data_emissao:
                base_cols = base_cols.replace(", data_emissao", "")
            q = supabase.table("notas_fiscais").select(base_cols).order("data_emissao" if com_data_emissao else "data_importacao", desc=True)
            if cliente_id:
                q = q.eq("cliente_id", str(cliente_id))
            if inicio:
                col_data = "data_emissao" if com_data_emissao else "data_importacao"
                val = str(inicio)[:10] if com_data_emissao else inicio
                q = q.gte(col_data, val)
            if fim:
                col_data = "data_emissao" if com_data_emissao else "data_importacao"
                val = str(fim)[:10] if com_data_emissao else fim
                q = q.lte(col_data, val)
            return q.execute()

        usar_data_emissao = True  # Controle para saber se usamos data_emissao ou data_importacao
        try:
            resp = _exec_query(com_cnpj=True, com_data_emissao=True)
            notas = list(resp.data or [])
        except Exception as exc:
            exc_str = str(exc)
            if "cnpj_destinatario" in exc_str or "data_emissao" in exc_str or "cst_principal" in exc_str or "42703" in exc_str:
                try:
                    # Tenta manter data_emissao (só remove cnpj_destinatario)
                    resp = _exec_query(com_cnpj=False, com_data_emissao=True)
                    notas = list(resp.data or [])
                    usar_data_emissao = True
                except Exception:
                    try:
                        # Tenta sem cst_principal (migration 013 não executada)
                        resp = _exec_query(com_cnpj=False, com_data_emissao=True, com_cst=False)
                        notas = list(resp.data or [])
                        usar_data_emissao = True
                    except Exception:
                        try:
                            # Último fallback: usa data_importacao (coluna data_emissao inexistente)
                            resp = _exec_query(com_cnpj=False, com_data_emissao=False, com_cst=False)
                            notas = resp.data or []
                            usar_data_emissao = False
                        except Exception:
                            raise exc
            else:
                raise

        if usar_data_emissao:
            # Inclui também notas sem cliente_id mas com cnpj_destinatario igual ao do cliente
            if cliente_id and cliente_cnpj and len(cliente_cnpj) == 14:
                extras = []
                try:
                    q2 = (
                        supabase.table("notas_fiscais")
                        .select("id, numero_nfe, cliente_id, cnpj_destinatario, valor_total, icms_total, data_importacao, data_emissao")
                        .is_("cliente_id", None)
                        .eq("cnpj_destinatario", cliente_cnpj)
                        .order("data_emissao", desc=True)
                    )
                    if inicio:
                        q2 = q2.gte("data_emissao", str(inicio)[:10])
                    if fim:
                        q2 = q2.lte("data_emissao", str(fim)[:10])
                    resp2 = q2.execute()
                    extras = resp2.data or []
                except Exception:
                    try:
                        q2 = (
                            supabase.table("notas_fiscais")
                            .select("id, numero_nfe, cliente_id, cnpj_destinatario, valor_total, icms_total, data_importacao")
                            .is_("cliente_id", None)
                            .eq("cnpj_destinatario", cliente_cnpj)
                            .order("data_importacao", desc=True)
                        )
                        if inicio:
                            q2 = q2.gte("data_importacao", inicio)
                        if fim:
                            q2 = q2.lte("data_importacao", fim)
                        resp2 = q2.execute()
                        extras = resp2.data or []
                    except Exception:
                        pass
                ids_vistos = {n["id"] for n in notas}
                for n in extras:
                    if n["id"] not in ids_vistos:
                        notas.append(n)
                        ids_vistos.add(n["id"])
                notas.sort(key=lambda x: x.get("data_emissao") or x.get("data_importacao") or "", reverse=True)

        if not usar_data_emissao and (data_inicial or data_final):
            st.warning("⚠️ Filtro usando **data de importação** (coluna data_emissao ainda não disponível). Execute a migration 006 para filtrar por data de emissão da NF-e.")
    except Exception as exc:
        st.error(f"Erro ao buscar notas: {exc}")
        notas = []

    if not notas:
        st.warning("Nenhuma nota encontrada para os filtros informados.")
        return

    # Mapeia cliente_id -> nome
    ids_clientes = {str(n["cliente_id"]) for n in notas if n.get("cliente_id")}
    mapa_cliente: dict[str, str] = {}
    if ids_clientes:
        try:
            resp_c = (
                supabase.table("clientes")
                .select("id, razao_social, nome_fantasia")
                .in_("id", list(ids_clientes))
                .execute()
            )
            for c in resp_c.data or []:
                nome = c.get("nome_fantasia") or c.get("razao_social") or str(c["id"])
                mapa_cliente[str(c["id"])] = nome
        except Exception:
            pass

    # 3. Tabela de Resultados com coluna Selecionar
    st.subheader("Notas Encontradas")
    def _col_cliente(n: dict) -> str:
        nome = mapa_cliente.get(str(n.get("cliente_id", "")), "")
        if nome:
            return nome
        cnpj = n.get("cnpj_destinatario")
        if cnpj:
            return f"CNPJ {formatar_cnpj(cnpj)} (sem vínculo)"
        return "—"

    df_notas = pd.DataFrame([
        {
            "Selecionar": True,
            "Número NF": n.get("numero_nfe", ""),
            "Cliente": _col_cliente(n),
            "Valor Total": float(n.get("valor_total", 0)),
            "ICMS Total": float(n.get("icms_total", 0)),
            "CST": n.get("cst_principal") or "—",
            "Data Emissão": n.get("data_emissao") or (n.get("data_importacao", "")[:10] if n.get("data_importacao") else ""),
            "_nota_id": n["id"],
        }
        for n in notas
    ])

    colunas_tabela = ["Selecionar", "Número NF", "Cliente", "Valor Total", "ICMS Total", "CST", "Data Emissão"]
    df_editado = st.data_editor(
        df_notas[[c for c in colunas_tabela if c in df_notas.columns]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "Selecionar": st.column_config.CheckboxColumn("Selecionar", default=True),
            "Valor Total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
            "ICMS Total": st.column_config.NumberColumn("ICMS Total", format="R$ %.2f"),
        },
    )

    # 4. Botões Reprocessar e Visualizar Resultados
    st.markdown("---")
    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        reprocessar_clicked = st.button("🔄 Reprocessar Selecionadas", type="primary")
    with col_btn2:
        visualizar_clicked = st.button("📊 Visualizar Resultados")

    nota_ids_selecionados: list = []
    if reprocessar_clicked or visualizar_clicked:
        selecionados = df_editado[df_editado["Selecionar"]].index.tolist()
        if not selecionados:
            st.warning("Selecione pelo menos uma nota.")
        else:
            nota_ids_selecionados = [df_notas.loc[i, "_nota_id"] for i in selecionados]

    # 5. Reprocessar (se clicou)
    if reprocessar_clicked and nota_ids_selecionados:
        total_itens = 0
        itens_st_encontrados = 0
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        for idx, nota_id in enumerate(nota_ids_selecionados):
            status_text.text(f"Reprocessando nota {idx + 1}/{len(nota_ids_selecionados)}...")
            progress_bar.progress((idx) / len(nota_ids_selecionados))

            try:
                resp_itens = (
                    supabase.table("itens_nota")
                    .select("id, ncm, cest, cfop")
                    .eq("nota_id", nota_id)
                    .execute()
                )
                itens = resp_itens.data or []
                for item in itens:
                    total_itens += 1
                    ncm = item.get("ncm")
                    cest = item.get("cest")
                    cfop = item.get("cfop")
                    regra = buscar_regra_st(supabase, ncm, cest) if ncm else None
                    st_por_cfop = cfop_indica_st(cfop)
                    sujeito = bool(regra) or st_por_cfop
                    status_st = STATUS_SUJEITO_ST if sujeito else None
                    mva_rem = regra.get("mva_remanescente") if regra else None
                    if status_st:
                        itens_st_encontrados += 1

                    supabase.table("itens_nota").update({
                        "status_st": status_st,
                        "mva_remanescente": float(mva_rem) if mva_rem is not None else None,
                    }).eq("id", item["id"]).execute()
            except Exception as exc:
                st.error(f"Erro ao reprocessar nota {nota_id}: {exc}")

        progress_bar.progress(1.0)
        status_text.empty()

    # Mostrar resultados (após reprocessar ou clicar Visualizar)
    if (reprocessar_clicked or visualizar_clicked) and nota_ids_selecionados:
        st.session_state["auditoria_nota_ids"] = nota_ids_selecionados

    if st.session_state.get("auditoria_nota_ids"):
        nota_ids_para_exibir = st.session_state["auditoria_nota_ids"]
        _exibir_resultados_auditoria(supabase, nota_ids_para_exibir)


def _importar_anexo_ix_upload(supabase: Client, arquivo) -> tuple[int, str]:
    """
    Processa CSV do Anexo IX (sep=';', encoding latin-1).
    Colunas: ncm, descricao, cest, mva (opcional).
    NCM e CEST: só dígitos (remove pontos/espaços).
    """
    import io
    try:
        arquivo.seek(0)
        df = pd.read_csv(io.BytesIO(arquivo.read()), sep=";", encoding="latin-1")
    except Exception as e:
        return 0, f"Erro ao ler CSV: {e}"
    df.columns = df.columns.str.strip().str.lower()
    if "ncm" not in df.columns:
        return 0, "Coluna 'ncm' não encontrada no arquivo."
    # NCM só dígitos (limpeza no ato)
    df["ncm"] = df["ncm"].astype(str).str.replace(r"\D", "", regex=True)
    df = df[df["ncm"].str.len() >= 2]
    df = df[~df["ncm"].isin(["", "nan", "None"])]
    if df.empty:
        return 0, "Nenhum NCM válido no arquivo."
    # CEST: normaliza (só dígitos)
    if "cest" in df.columns:
        df["cest"] = df["cest"].astype(str).str.replace(r"\D", "", regex=True)
    # MVA: decimal (40 -> 0.40)
    if "mva" in df.columns:
        df["mva"] = pd.to_numeric(df["mva"], errors="coerce").fillna(0)
        df["mva_st_interna"] = df["mva"] / 100
        df["mva_remanescente"] = df["mva_st_interna"] * 0.7
    # Descrição: planilha usa "descricao do produto", tabela usa "descricao"
    desc_col = "descricao do produto" if "descricao do produto" in df.columns else "descricao"
    registros = []
    for _, row in df.drop_duplicates(subset=["ncm"]).iterrows():
        ncm = str(row["ncm"]).strip()
        if not ncm:
            continue
        desc = None
        if desc_col in df.columns and pd.notna(row.get(desc_col)):
            desc = str(row[desc_col]).strip()[:500]
        cest = str(row.get("cest", "")).strip() if pd.notna(row.get("cest")) else None
        if cest and len(cest) < 4:
            cest = None
        reg = {
            "ncm": ncm,
            "descricao": desc or "",
            "segmento": "",
            "tipo_base": "MVA",
            "data_inicio_vigencia": datetime.now().strftime("%Y-%m-%d"),
            "versao": 1,
        }
        if cest:
            reg["cest"] = cest
        if "mva_st_interna" in df.columns:
            reg["mva_st_interna"] = float(row.get("mva_st_interna", 0) or 0)
        if "mva_remanescente" in df.columns:
            reg["mva_remanescente"] = float(row.get("mva_remanescente", 0) or 0)
        registros.append(reg)
    if not registros:
        return 0, "Nenhum registro a importar."

    def _mensagem_erro(exc: Exception) -> str:
        if hasattr(exc, "args") and exc.args and isinstance(exc.args[0], dict):
            return exc.args[0].get("message", str(exc))
        return str(exc)

    try:
        # Teste com 1 registro para capturar erro de schema/RLS
        supabase.table("base_normativa_ncm").insert(registros[0:1]).execute()
    except Exception as e:
        return 0, f"Erro ao salvar no banco: {_mensagem_erro(e)}"

    try:
        # Insere o restante (pula o primeiro, já inserido)
        for i in range(1, len(registros), 200):
            lote = registros[i : i + 200]
            supabase.table("base_normativa_ncm").insert(lote).execute()
        return len(registros), f"{len(registros)} NCMs importados com sucesso."
    except Exception as e:
        return 0, f"Erro ao salvar lote: {_mensagem_erro(e)}"


def pagina_base_normativa() -> None:
    """Página Base Normativa (Anexo IX): contador, upload, listagem e teste de busca."""
    global BASE_NORMATIVA_CACHE
    st.header("📚 Base Normativa (Anexo IX)")
    st.caption("NCMs na tabela base_normativa_ncm. Importe a planilha do Anexo IX ou use o script scripts/extrator_anexo_ix.py.")

    supabase = require_supabase()

    # Carrega lista para contador e tabela
    try:
        resp = (
            supabase.table("base_normativa_ncm")
            .select("ncm, descricao")
            .execute()
        )
        registros = resp.data or []
    except Exception as exc:
        st.error(f"Erro ao carregar base normativa: {exc}")
        registros = []

    st.metric("Total de NCMs na Base", len(registros))

    # Upload da planilha Anexo IX (CSV)
    st.subheader("Re-importar Anexo IX")
    arquivo = st.file_uploader(
        "Envie o CSV do Anexo IX (sep=;). Colunas: ncm, descricao do produto, cest, mva",
        type=["csv"],
        key="anexo_ix_csv",
    )
    if arquivo is not None:
        if st.button("Importar para base_normativa_ncm"):
            n, msg = _importar_anexo_ix_upload(supabase, arquivo)
            if n > 0:
                st.success(msg)
                BASE_NORMATIVA_CACHE = None
                st.rerun()
            else:
                st.error(msg)

    # Teste de busca: NCM 8202 (Serrote)
    st.subheader("Teste de busca (Serrote 8202)")
    regra_8202 = buscar_regra_st(supabase, "82021000")  # 8202 ou 82021000
    if regra_8202:
        st.success(f"Match encontrado para o NCM 82021000 através da regra **{regra_8202.get('ncm', '')}**.")
    else:
        st.warning("NCM 8202 (Serrote) não encontrado na base. Importe o Anexo IX e tente novamente.")

    st.markdown("---")

    # Listagem
    if not registros:
        st.info("Nenhum NCM cadastrado. Use o upload acima ou execute: python scripts/extrator_anexo_ix.py")
        return

    # Filtro de busca
    busca = st.text_input(
        "🔍 Buscar NCM",
        placeholder="Ex: 8202, 82021000, 18.06.90",
        help="Pontos e espaços são ignorados na busca.",
    )
    termo_limpo = _sanitizar_ncm(busca) if busca else ""

    if termo_limpo:
        def _match(row: dict) -> bool:
            ncm_limpo = _sanitizar_ncm(row.get("ncm"))
            return termo_limpo in ncm_limpo or ncm_limpo.startswith(termo_limpo)

        lista_exibir = [r for r in registros if _match(r)]
        st.success(f"Encontrados **{len(lista_exibir)}** registro(s) para \"{busca}\".")
    else:
        lista_exibir = registros

    df = pd.DataFrame(lista_exibir)
    st.dataframe(df, use_container_width=True, hide_index=True)


def main() -> None:
    # Inicializa sessão de autenticação
    if "user" not in st.session_state:
        st.session_state["user"] = None
    if "username" not in st.session_state:
        st.session_state["username"] = None

    # Se não autenticado, exibe login
    if not st.session_state.get("user"):
        pagina_login()
        return

    options_base = ["Gestão de Clientes", "Análise de XML", "Painel de Auditoria", "Base Normativa", "Configurações"]
    icons_base = ["house", "shield-check", "bar-chart", "database", "gear"]

    menu_map = {
        "Gestão de Clientes": "clientes",
        "Análise de XML": "xml",
        "Painel de Auditoria": "auditoria",
        "Base Normativa": "base",
        "Configurações": "config",
    }

    with st.sidebar:
        # Logo/título
        logo_path = Path(__file__).resolve().parent / "assets" / "logo.png"
        if logo_path.exists():
            st.image(str(logo_path), use_container_width=True)
        else:
            st.markdown(
                """
                <div style="text-align: center; padding: 20px 0 24px 0; border-bottom: 1px solid #30363d;">
                    <div style="font-size: 2.5rem; font-weight: 700; color: #58A6FF;">📊</div>
                    <div style="font-size: 1.2rem; font-weight: 700; color: #E6EDF3; margin-top: 6px;">ST-Analyzer-PR</div>
                    <div style="font-size: 0.75rem; color: #8B949E;">Análise ICMS-ST • Paraná</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

        menu = option_menu(
            menu_title=None,
            options=options_base,
            icons=icons_base,
            default_index=0,
            styles={
                "container": {"padding": "0", "background-color": "transparent"},
                "icon": {"color": "#58A6FF", "font-size": "1.1rem"},
                "nav-link": {"font-size": "0.95rem", "color": "#8B949E", "padding": "12px 16px"},
                "nav-link-selected": {"background-color": "#1E2129", "color": "#E6EDF3", "border-radius": "8px"},
            },
        )
        menu_key = menu_map.get(menu, "clientes")

        st.markdown("---")
        st.caption(f"Logado como **{st.session_state['user']}**")
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            st.session_state["user"] = None
            st.session_state["username"] = None
            st.session_state.pop("esqueci_senha", None)
            st.rerun()

    if menu_key == "clientes":
        pagina_gestao_clientes()
    elif menu_key == "xml":
        pagina_analise_xml()
    elif menu_key == "auditoria":
        pagina_painel_auditoria()
    elif menu_key == "base":
        pagina_base_normativa()
    elif menu_key == "config":
        pagina_configuracoes()


if __name__ == "__main__":
    main()