@echo off
REM ============================================================
REM  Casanova Esquadrias - Registra o nome do sistema no Windows
REM
REM  Cria as entradas no arquivo hosts:
REM     casanova.abra.local  -> 10.12.50.53
REM     casanova.sistema     -> 10.12.50.53
REM
REM  PRECISA RODAR COMO ADMINISTRADOR
REM  (clique com o botao direito -> Executar como administrador)
REM ============================================================
setlocal

set IP=10.12.50.53
set HOSTS=%SystemRoot%\System32\drivers\etc\hosts
set TMPHOSTS=%TEMP%\hosts_casanova.txt

net session >nul 2>&1
if not %errorLevel% == 0 (
    echo.
    echo  ============================================================
    echo   ERRO: precisa ser executado como ADMINISTRADOR
    echo.
    echo   Clique com o botao DIREITO neste arquivo e escolha:
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
echo  Servidor: %IP%
echo  Arquivo : %HOSTS%
echo.

echo  --- ANTES ---
findstr /I "casanova" "%HOSTS%" 2>nul
if errorlevel 1 echo    (nenhuma entrada)
echo.

REM Backup do arquivo original
copy /Y "%HOSTS%" "%HOSTS%.bak" >nul
echo  Backup criado: %HOSTS%.bak

REM Monta o novo arquivo: mantem tudo, menos linhas com "casanova"
findstr /I /V "casanova" "%HOSTS%" > "%TMPHOSTS%"

REM Acrescenta as entradas corretas (sem escape especial)
echo.>> "%TMPHOSTS%"
echo # Casanova Esquadrias - sistema de gestao>> "%TMPHOSTS%"
echo %IP%    casanova.abra.local>> "%TMPHOSTS%"
echo %IP%    casanova.sistema>> "%TMPHOSTS%"

REM Substitui o arquivo (robocopy funciona mesmo com o arquivo em uso)
copy /Y "%TMPHOSTS%" "%HOSTS%" >nul
del "%TMPHOSTS%" 2>nul

echo.
echo  --- DEPOIS ---
findstr /I "casanova" "%HOSTS%"
echo.

ipconfig /flushdns >nul
echo  Cache de DNS limpo.
echo.

echo  ============================================================
echo   PRONTO! Acesse no navegador:
echo.
echo      https://casanova.abra.local/industria/rastreio/
echo.
echo   Se aparecer aviso de certificado, aceite uma vez
echo   ou instale a CA em: https://%IP%/certificado/
echo  ============================================================
echo.
pause
