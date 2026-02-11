@echo off
echo ========================================
echo Finalizando Git - Commit e Push
echo ========================================
echo.

REM Remove locks
echo [1/4] Removendo arquivos de lock...
if exist .git\index.lock (
    del /f /q .git\index.lock 2>nul
    echo     Lock removido.
) else (
    echo     Nenhum lock encontrado.
)

if exist .git\config.lock (
    del /f /q .git\config.lock 2>nul
    echo     Config lock removido.
)

timeout /t 2 /nobreak >nul

REM Verifica se ja tem commit
echo.
echo [2/4] Verificando commits existentes...
git log --oneline -1 >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     Commit ja existe!
    git log --oneline -1
) else (
    echo     Criando commit inicial...
    git commit -m "Iniciando projeto Analise ICMS ST"
    if %ERRORLEVEL% EQU 0 (
        echo     Commit criado com sucesso!
    ) else (
        echo     ERRO ao criar commit!
        echo     Tente fechar o Cursor e executar novamente.
        pause
        exit /b 1
    )
)

REM Push
echo.
echo [3/4] Fazendo push para GitHub...
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCESSO! Projeto enviado para GitHub!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERRO no push. Verifique:
    echo ========================================
    echo 1. Se o repositorio existe no GitHub
    echo 2. Se voce tem permissao de escrita
    echo 3. Se precisa configurar autenticacao
    echo    (token ou SSH)
    echo ========================================
)

echo.
pause
