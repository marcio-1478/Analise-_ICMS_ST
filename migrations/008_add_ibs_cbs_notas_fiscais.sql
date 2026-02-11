-- Adiciona totais IBS e CBS em notas_fiscais (Reforma Tributária)
-- Execute no Supabase: SQL Editor → Cole e Execute

ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS ibs_total NUMERIC(15, 4);
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS cbs_total NUMERIC(15, 4);
