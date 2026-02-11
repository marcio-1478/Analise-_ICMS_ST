# Deploy do ST-Analyzer-PR

## Pré-requisitos

- Python 3.10+
- Conta no [Streamlit Community Cloud](https://share.streamlit.io) ou outro provedor

## 1. Dependências

As bibliotecas estão em `requirements.txt`:
- streamlit, pandas, supabase, xmltodict
- streamlit-aggrid, streamlit-option-menu
- reportlab (PDF)
- python-dotenv

## 2. Caminhos

O app usa `Path(__file__).resolve().parent` para imagens e assets — funciona em qualquer servidor.

- Logo: `assets/logo.png` (opcional)
- Coloque `logo.png` em `assets/` para exibir na sidebar

## 3. Segurança — Chaves e Senhas

**Nunca** commite chaves ou senhas no código.

### Supabase (obrigatório)

Configure em **st.secrets** (Streamlit Cloud) ou **.env** (local):

| Variável      | Onde configurar           |
|---------------|---------------------------|
| SUPABASE_URL  | st.secrets ou .env        |
| SUPABASE_KEY  | st.secrets ou .env (service_role) |

### Streamlit Cloud

1. Repositório conectado → **Settings** → **Secrets**
2. Cole (formato TOML):

```toml
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Desenvolvimento local

Crie `.env` na raiz (não commitar):

```
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=eyJ...
```

### Usuários e senhas

- Admin e funcionários: tabela `usuarios` no Supabase (não em código)
- Execute as migrations 009 e 011 no banco

## 4. Comando de execução

```bash
streamlit run app.py
```

O Streamlit Cloud usa `app.py` na raiz automaticamente.
