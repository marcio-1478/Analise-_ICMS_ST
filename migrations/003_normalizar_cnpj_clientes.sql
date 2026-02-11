-- Normaliza CNPJ na tabela clientes (apenas dígitos)
-- Execute no Supabase SQL Editor. Assim 23.420.405/0001-84 vira 23420405000184
-- e a consulta por CNPJ do XML (23420405000184) encontra o cliente.

UPDATE clientes
SET cnpj = regexp_replace(cnpj, '[^0-9]', '', 'g')
WHERE cnpj IS NOT NULL
  AND cnpj != regexp_replace(cnpj, '[^0-9]', '', 'g');
