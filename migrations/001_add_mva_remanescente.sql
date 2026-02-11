-- Adiciona colunas mva_remanescente e mva_st_interna na tabela base_normativa_ncm
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute

-- mva_st_interna: MVA original em decimal (ex: 0.40 para 40%)
ALTER TABLE base_normativa_ncm
ADD COLUMN IF NOT EXISTS mva_st_interna NUMERIC;

-- mva_remanescente: 70% da MVA (Art. 17, ex: 0.28 para 40% * 0.7)
ALTER TABLE base_normativa_ncm
ADD COLUMN IF NOT EXISTS mva_remanescente NUMERIC;
