# Instruções para Criar as Tabelas no Supabase

## Passo a Passo

1. Acesse o painel do Supabase (https://app.supabase.com)
2. Selecione seu projeto
3. Vá em **SQL Editor** no menu lateral
4. Clique em **New Query**
5. Cole o conteúdo do arquivo `schema.sql` e execute

## Estrutura das Tabelas

### `notas_fiscais`
- `id` (UUID, Primary Key)
- `numero_nfe` (TEXT, UNIQUE) - Número da nota fiscal
- `cliente_id` (UUID, Foreign Key para `clientes`)
- `valor_total` (NUMERIC) - Valor total da nota
- `icms_total` (NUMERIC) - Valor total do ICMS
- `data_importacao` (TIMESTAMP) - Data/hora da importação

### `itens_nota`
- `id` (UUID, Primary Key)
- `nota_id` (UUID, Foreign Key para `notas_fiscais`)
- `codigo_produto` (TEXT)
- `descricao` (TEXT)
- `ncm` (TEXT)
- `cest` (TEXT)
- `cfop` (TEXT)
- `valor_unitario` (NUMERIC)
- `valor_total` (NUMERIC)

## Funcionalidades Implementadas

- ✅ Criação automática das tabelas via SQL
- ✅ Salvamento automático de notas e itens após processamento
- ✅ Verificação de duplicidade (não salva a mesma nota duas vezes)
- ✅ Relacionamento entre notas e clientes
- ✅ Relacionamento entre notas e itens (com CASCADE)

## Observações

- A coluna `numero_nfe` tem constraint UNIQUE para evitar duplicatas
- O sistema verifica duplicidade antes de inserir
- Se uma nota já existir, será exibida uma mensagem informativa
- Os itens são salvos automaticamente junto com a nota
