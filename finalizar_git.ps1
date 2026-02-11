# Script para finalizar o commit e push do Git
# Execute este script no PowerShell como Administrador

Write-Host "Finalizando configuracao do Git..." -ForegroundColor Yellow

# Remove locks
Write-Host "Removendo arquivos de lock..." -ForegroundColor Cyan
if (Test-Path ".git\index.lock") {
    Remove-Item ".git\index.lock" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

if (Test-Path ".git\config.lock") {
    Remove-Item ".git\config.lock" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Verifica se há commits
$hasCommits = git log --oneline -1 2>$null
if (-not $hasCommits) {
    Write-Host "Criando commit inicial..." -ForegroundColor Cyan
    git commit -m "Iniciando projeto Analise ICMS ST"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Erro ao criar commit. Tente fechar o Cursor e executar novamente." -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "Commit ja existe: $hasCommits" -ForegroundColor Green
}

# Faz push
Write-Host "Fazendo push para GitHub..." -ForegroundColor Cyan
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSUCESSO! Projeto enviado para o GitHub!" -ForegroundColor Green
} else {
    Write-Host "`nErro no push. Verifique:" -ForegroundColor Red
    Write-Host "1. Se o repositorio existe no GitHub" -ForegroundColor Yellow
    Write-Host "2. Se voce tem permissao de escrita" -ForegroundColor Yellow
    Write-Host "3. Se precisa configurar autenticacao (token ou SSH)" -ForegroundColor Yellow
}

Write-Host "`nPressione qualquer tecla para sair..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
