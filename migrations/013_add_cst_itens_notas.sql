-- Adiciona CST (Código de Situação Tributária) para análises fiscais
-- Em itens_nota: CST por item (extraído do bloco ICMS do XML)
-- Em notas_fiscais: CST principal da nota (para exibição no resumo)
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute

ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS cst TEXT;
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS cst_principal TEXT;
