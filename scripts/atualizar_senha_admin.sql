-- Atualiza a senha do usuário admin para SHA256 de "admin123"
-- Execute no Supabase: SQL Editor → Cole e Execute

UPDATE public.usuarios
SET senha = '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'
WHERE usuario = 'admin';

-- Se a tabela tiver RLS ativo, o app precisa usar a chave service_role no .env
-- (Supabase Dashboard > Settings > API > service_role)
