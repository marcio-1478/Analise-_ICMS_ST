-- Adiciona colunas de impostos em itens_nota para análise fiscal
-- ICMS, ICMS-ST, PIS, COFINS, IPI, IBS, CBS (base, alíquota, valor)
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute

-- ICMS
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS icms_bc NUMERIC(15, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS icms_aliq NUMERIC(8, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS icms_valor NUMERIC(15, 4);

-- ICMS-ST (Substituição Tributária)
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS icms_st_bc NUMERIC(15, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS icms_st_aliq NUMERIC(8, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS icms_st_valor NUMERIC(15, 4);

-- PIS
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS pis_bc NUMERIC(15, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS pis_aliq NUMERIC(8, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS pis_valor NUMERIC(15, 4);

-- COFINS
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS cofins_bc NUMERIC(15, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS cofins_aliq NUMERIC(8, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS cofins_valor NUMERIC(15, 4);

-- IPI
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS ipi_bc NUMERIC(15, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS ipi_aliq NUMERIC(8, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS ipi_valor NUMERIC(15, 4);

-- IBS e CBS (Reforma Tributária - para futuras NF-e)
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS ibs_valor NUMERIC(15, 4);
ALTER TABLE itens_nota ADD COLUMN IF NOT EXISTS cbs_valor NUMERIC(15, 4);

-- Totais na nota (notas_fiscais) para análise consolidada
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS icms_bc_total NUMERIC(15, 4);
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS icms_st_total NUMERIC(15, 4);
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS pis_total NUMERIC(15, 4);
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS cofins_total NUMERIC(15, 4);
ALTER TABLE notas_fiscais ADD COLUMN IF NOT EXISTS ipi_total NUMERIC(15, 4);
