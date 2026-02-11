-- Adiciona data de emissão da NF-e em notas_fiscais para filtro por data de emissão
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute
--
-- As novas importações preencherão automaticamente. Para notas antigas:
-- UPDATE notas_fiscais SET data_emissao = data_importacao::date WHERE data_emissao IS NULL;

ALTER TABLE notas_fiscais
ADD COLUMN IF NOT EXISTS data_emissao DATE;

-- Preenche notas antigas com data_importacao como fallback
UPDATE notas_fiscais
SET data_emissao = data_importacao::date
WHERE data_emissao IS NULL;

CREATE INDEX IF NOT EXISTS idx_notas_fiscais_data_emissao ON notas_fiscais (data_emissao);
