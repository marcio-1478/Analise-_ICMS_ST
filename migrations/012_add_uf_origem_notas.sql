-- Adiciona UF do emitente (origem da mercadoria) em notas_fiscais para auditoria de ST
-- Necessário para classificar CFOP 6.1xx: fora do PR = antecipação pendente (ST na entrada pelo destinatário)
-- Execute no Supabase: app.supabase.com → SQL Editor → New Query → Cole e Execute

ALTER TABLE notas_fiscais
ADD COLUMN IF NOT EXISTS uf_origem TEXT;
