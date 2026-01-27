@echo off
echo Removendo pasta .git antiga (se existir)...
if exist .git (
    rmdir /s /q .git
    timeout /t 2 /nobreak >nul
)

echo Inicializando repositorio Git...
git init

echo Adicionando arquivos...
git add .

echo Criando commit inicial...
git commit -m "Iniciando projeto Analise ICMS ST"

echo Configurando branch main...
git branch -M main

echo Adicionando remote origin...
git remote add origin https://github.com/marcio-1478/Analise-_ICMS_ST.git

echo Fazendo push para GitHub...
git push -u origin main

echo.
echo Concluido! Verifique se houve algum erro acima.
pause
