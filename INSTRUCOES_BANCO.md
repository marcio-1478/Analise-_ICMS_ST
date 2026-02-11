# Instruções para Criar as Tabelas no Supabase

## Passo a Passo

1. Acesse o painel do Supabase (https://app.supabase.com)
2. Selecione seu projeto
3. Vá em **SQL Editor** no menu lateral
4. Clique em **New Query**
5. Cole o conteúdo do arquivo `schema.sql` e execute

## Estrutura das Tabelas

### `notas_fiscais`
- `id` (UUID, Primary Key)
- `numero_nfe` (TEXT, UNIQUE) - Número da nota fiscal
- `cliente_id` (UUID, Foreign Key para `clientes`)
- `valor_total` (NUMERIC) - Valor total da nota
- `icms_total` (NUMERIC) - Valor total do ICMS
- `data_importacao` (TIMESTAMP) - Data/hora da importação

### `itens_nota`
- `id` (UUID, Primary Key)
- `nota_id` (UUID, Foreign Key para `notas_fiscais`)
- `codigo_produto` (TEXT)
- `descricao` (TEXT)
- `ncm` (TEXT)
- `cest` (TEXT)
- `cfop` (TEXT)
- `valor_unitario` (NUMERIC)
- `valor_total` (NUMERIC)

## Funcionalidades Implementadas

- ✅ Criação automática das tabelas via SQL
- ✅ Salvamento automático de notas e itens após processamento
- ✅ Verificação de duplicidade (não salva a mesma nota duas vezes)
- ✅ Relacionamento entre notas e clientes
- ✅ Relacionamento entre notas e itens (com CASCADE)

## Observações

- A coluna `numero_nfe` tem constraint UNIQUE para evitar duplicatas
- O sistema verifica duplicidade antes de inserir
- Se uma nota já existir, será exibida uma mensagem informativa
- Os itens são salvos automaticamente junto com a nota

## Migrações (CNPJ e notas)

1. **003_normalizar_cnpj_clientes.sql** — Normaliza o CNPJ em `clientes` (apenas dígitos). Execute primeiro para que a consulta por CNPJ do XML (ex: 23420405000184) encontre o cliente.
2. **004_add_cnpj_destinatario_notas.sql** — Adiciona `cnpj_destinatario` em `notas_fiscais` e re-vincula notas que já tiverem esse campo preenchido e `cliente_id` nulo.

## Autenticação (Login)

O sistema exige login para acessar o painel. Duas opções:

### Opção A: st.secrets (Streamlit)

1. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml`
2. Configure `[auth]` com `salt` e `users` (username = hash da senha)
3. Para gerar hash: `python -c "import hashlib; print(hashlib.sha256(('sua_senha' + 'st_analyzer_salt').encode()).hexdigest())"`

### Opção B: Tabela no Supabase

1. Execute **009_create_usuarios.sql** no SQL Editor do Supabase
2. Execute **011_add_email_usuarios.sql** para habilitar e-mail e cadastro de funcionários
3. Usuário padrão: `admin` / senha: `admin123` — altere em produção
5. **Se o login não funcionar:**
   - Use a chave **service_role** (não anon) no `.env`: `SUPABASE_KEY=eyJ...` (Settings > API no Supabase)
   - Ou execute **010_usuarios_rls.sql** para desabilitar RLS em usuarios
   - Ou rode `python scripts/configurar_senha_admin.py` para atualizar a senha
