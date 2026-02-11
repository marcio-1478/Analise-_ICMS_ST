@echo off
echo Configurando Git com email e nome corretos...
echo.

REM Configura apenas para este repositorio
git config user.email "marcio@aconcontabilidade.com.br"
git config user.name "Marcio"

echo.
echo Configuracao local concluida!
echo.
echo Tentando configurar globalmente (pode falhar se arquivo estiver bloqueado)...
git config --global user.email "marcio@aconcontabilidade.com.br"
git config --global user.name "Marcio"

echo.
echo Verificando configuracao...
git config --list | findstr "user"

echo.
echo Removendo locks e tentando commit...
if exist .git\index.lock (
    del /f /q .git\index.lock
    timeout /t 2 /nobreak >nul
)

git commit -m "Iniciando projeto Analise ICMS ST"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Commit criado com sucesso!
    echo.
    echo Fazendo push para GitHub...
    git push -u origin main
) else (
    echo.
    echo Erro ao criar commit. Tente fechar o Cursor e executar novamente.
)

echo.
pause
