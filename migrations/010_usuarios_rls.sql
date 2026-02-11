-- Se o login não funcionar, pode ser RLS bloqueando a leitura de usuarios.
-- Opção 1: Desabilitar RLS na tabela usuarios (mais simples)
ALTER TABLE public.usuarios DISABLE ROW LEVEL SECURITY;

-- Opção 2 (alternativa): Use a chave service_role no .env do app
-- (Supabase Dashboard > Settings > API > service_role - secret)
-- A service_role ignora o RLS e não precisa desta migration.
