-- Tabela de usuários para autenticação
-- Execute no Supabase: SQL Editor → Cole e Execute
-- Senha padrão: admin / admin123 (hash abaixo). Altere após primeiro login.

CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para busca rápida por username
CREATE INDEX IF NOT EXISTS idx_usuarios_username ON usuarios(username);

-- Usuário padrão (senha: admin123) — ALTERE A SENHA EM PRODUÇÃO
-- Hash: SHA256 de senha + salt "st_analyzer_salt"
INSERT INTO usuarios (username, password_hash)
VALUES (
    'admin',
    '91f879c90f864ba2ab51d70b2891b7ee404336ad4fe3cf324bc6b70a6f1dcc8f'
)
ON CONFLICT (username) DO NOTHING;
