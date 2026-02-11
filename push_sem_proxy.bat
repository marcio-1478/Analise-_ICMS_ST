@echo off
echo ========================================
echo Push para GitHub - Desabilitando Proxy
echo ========================================
echo.

REM Remove variaveis de ambiente de proxy
set HTTP_PROXY=
set HTTPS_PROXY=
set http_proxy=
set https_proxy=

echo Proxy desabilitado temporariamente.
echo.

REM Tenta push
echo Fazendo push para GitHub...
git -c http.proxy= -c https.proxy= push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo SUCESSO! Push concluido!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ERRO no push. Possiveis solucoes:
    echo ========================================
    echo 1. Verifique sua conexao com a internet
    echo 2. Verifique se o firewall/antivirus esta bloqueando
    echo 3. Tente usar SSH em vez de HTTPS:
    echo    git remote set-url origin git@github.com:marcio-1478/Analise-_ICMS_ST.git
    echo    git push -u origin main
    echo 4. Use o GitHub Desktop como alternativa
    echo ========================================
)

echo.
pause
