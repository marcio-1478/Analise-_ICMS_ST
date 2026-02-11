-- Adiciona colunas status_st e mva_remanescente na tabela itens_nota
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute

-- status_st: Status ST do item (ex: '⚠️ SUJEITO A ST (PR)' ou NULL)
ALTER TABLE itens_nota
ADD COLUMN IF NOT EXISTS status_st TEXT;

-- mva_remanescente: MVA remanescente (70% Art. 17) em decimal
ALTER TABLE itens_nota
ADD COLUMN IF NOT EXISTS mva_remanescente NUMERIC;
