-- Cruzamento duplo (CEST + NCM): adiciona coluna CEST em base_normativa_ncm
-- CEST é mais específico; permite match exato quando o item informa CEST no XML
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute
--
-- Após rodar: python scripts/extrator_anexo_ix.py (para carregar CEST)

-- 1. Adiciona coluna cest em base_normativa_ncm (permite armazenar CEST na mesma linha)
ALTER TABLE base_normativa_ncm
ADD COLUMN IF NOT EXISTS cest TEXT;

-- 2. Índice para busca rápida por CEST
CREATE INDEX IF NOT EXISTS idx_base_normativa_cest ON base_normativa_ncm (cest)
WHERE cest IS NOT NULL;
