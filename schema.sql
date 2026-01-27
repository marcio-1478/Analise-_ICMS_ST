-- Criação das tabelas para o ST-Analyzer-PR

-- Tabela de notas fiscais
CREATE TABLE IF NOT EXISTS notas_fiscais (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    numero_nfe TEXT NOT NULL UNIQUE,
    cliente_id UUID REFERENCES clientes(id),
    valor_total NUMERIC(15, 2) NOT NULL DEFAULT 0,
    icms_total NUMERIC(15, 2) NOT NULL DEFAULT 0,
    data_importacao TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tabela de itens da nota
CREATE TABLE IF NOT EXISTS itens_nota (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nota_id UUID REFERENCES notas_fiscais(id) ON DELETE CASCADE,
    codigo_produto TEXT,
    descricao TEXT,
    ncm TEXT,
    cest TEXT,
    cfop TEXT,
    valor_unitario NUMERIC(15, 4) DEFAULT 0,
    valor_total NUMERIC(15, 2) DEFAULT 0
);

-- Índices para melhorar performance
CREATE INDEX IF NOT EXISTS idx_notas_fiscais_numero ON notas_fiscais(numero_nfe);
CREATE INDEX IF NOT EXISTS idx_notas_fiscais_cliente ON notas_fiscais(cliente_id);
CREATE INDEX IF NOT EXISTS idx_itens_nota_nota ON itens_nota(nota_id);
