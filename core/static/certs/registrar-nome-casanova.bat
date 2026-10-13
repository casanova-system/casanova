@echo off
REM ============================================================
REM  Registra o nome do sistema Casanova no arquivo hosts do Windows.
REM
REM  Cria as entradas:
REM     casanova.abra.local  -> 10.12.50.53
REM     casanova.sistema     -> 10.12.50.53
REM
REM  PRECISA RODAR COMO ADMINISTRADOR
REM  (clique com o botao direito -> Executar como administrador)
REM ============================================================
setlocal

set HOSTS=%SystemRoot%\System32\drivers\etc\hosts
set IP=10.12.50.53

net session >nul 2>&1
if not %errorLevel% == 0 (
    echo.
    echo  ============================================================
    echo   ERRO: precisa ser executado como ADMINISTRADOR
    echo.
    echo   Clique com o botao direito neste arquivo e escolha:
    echo      "Executar como administrador"
    echo  ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Casanova Esquadrias - Nome do sistema
echo  ============================================================
echo.
echo  Arquivo: %HOSTS%
echo  Servidor: %IP%
echo.

echo  --- Entradas ANTES ---
findstr /I "casanova" "%HOSTS%" 2>nul
if errorlevel 1 echo    (nenhuma)
echo.

REM Backup com data
for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set D=%%d%%b%%c
copy /Y "%HOSTS%" "%HOSTS%.bak_%D%" >nul
echo  Backup: %HOSTS%.bak_%D%

REM Remove entradas antigas de casanova (inclui o apontamento errado para .99)
powershell -NoProfile -Command ^
  "$f='%HOSTS%'; $l = Get-Content $f -ErrorAction SilentlyContinue | Where-Object { $_ -notmatch 'casanova' }; Set-Content -Path $f -Value $l -Encoding ASCII;"

REM Adiciona as entradas corretas
powershell -NoProfile -Command ^
  "Add-Content -Path '%HOSTS%' -Value '`n%IP%    casanova.abra.local' -Encoding ASCII; Add-Content -Path '%HOSTS%' -Value '%IP%    casanova.sistema' -Encoding ASCII;"

echo.
echo  --- Entradas DEPOIS ---
findstr /I "casanova" "%HOSTS%"
echo.

ipconfig /flushdns >nul
echo  Cache de DNS limpo.
echo.

echo  ============================================================
echo   PRONTO! Acesse no navegador:
echo.
echo      https://casanova.abra.local/industria/rastreio/
echo      https://casanova.sistema/industria/rastreio/
echo.
echo   Se o aviso de certificado aparecer, aceite uma vez
echo   (Avançado - Continuar) ou instale a CA em /certificado/
echo  ============================================================
echo.
pause
