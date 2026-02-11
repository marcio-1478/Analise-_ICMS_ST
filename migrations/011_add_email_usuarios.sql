-- Adiciona coluna email na tabela usuarios
-- Execute no Supabase: SQL Editor → Cole e Execute

ALTER TABLE public.usuarios ADD COLUMN IF NOT EXISTS email TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email ON public.usuarios(email) WHERE email IS NOT NULL;
