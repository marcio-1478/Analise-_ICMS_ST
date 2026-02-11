@echo off
echo ========================================
echo Push para GitHub - Removendo Proxy
echo ========================================
echo.

REM Remove todas as variaveis de proxy
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=
set NO_PROXY=
set no_proxy=

echo Variaveis de proxy removidas.
echo.

REM Verifica se o commit existe
git log --oneline -1 >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERRO: Nenhum commit encontrado!
    echo Execute: git commit -m "Iniciando projeto Analise ICMS ST"
    pause
    exit /b 1
)

echo Commit encontrado:
git log --oneline -1
echo.

REM Tenta push sem proxy
echo Fazendo push para GitHub (sem proxy)...
git -c http.proxy= -c https.proxy= push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCESSO! Push concluido!
    echo ========================================
    echo.
    echo Verifique em: https://github.com/marcio-1478/Analise-_ICMS_ST
) else (
    echo.
    echo ========================================
    echo ERRO no push. Tente:
    echo ========================================
    echo 1. Verificar conexao com internet
    echo 2. Desativar VPN/proxy temporariamente
    echo 3. Verificar firewall/antivirus
    echo 4. Usar GitHub Desktop como alternativa
    echo ========================================
)

echo.
pause
