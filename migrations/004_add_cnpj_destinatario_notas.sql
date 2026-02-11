-- Adiciona CNPJ do destinatário (só dígitos) em notas_fiscais para re-vinculação.

ALTER TABLE notas_fiscais
ADD COLUMN IF NOT EXISTS cnpj_destinatario TEXT;

-- Re-vincular notas que têm cnpj_destinatario mas cliente_id nulo
-- (execute após rodar 003 e após o app gravar cnpj_destinatario nas novas importações)
UPDATE notas_fiscais n
SET cliente_id = c.id
FROM clientes c
WHERE n.cnpj_destinatario IS NOT NULL
  AND n.cliente_id IS NULL
  AND c.cnpj = n.cnpj_destinatario;
