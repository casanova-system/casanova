@echo off
REM ============================================================
REM  Corrige o apontamento de casanova.sistema no arquivo hosts.
REM
REM  O sistema apontava para 10.12.50.99 (servidor desligado).
REM  O servidor correto e 10.12.50.53.
REM
REM  PRECISA RODAR COMO ADMINISTRADOR.
REM ============================================================
setlocal

set HOSTS=%SystemRoot%\System32\drivers\etc\hosts
set IP=10.12.50.53
set NOME=casanova.sistema

net session >nul 2>&1
if not %errorLevel% == 0 (
    echo.
    echo  ERRO: este script precisa ser executado como ADMINISTRADOR.
    echo.
    echo  Clique com o botao direito neste arquivo e escolha
    echo  "Executar como administrador".
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Corrigindo casanova.sistema
echo  ============================================================
echo.
echo  Arquivo: %HOSTS%
echo  Antes:
findstr /I "%NOME%" "%HOSTS%"
echo.

REM Backup do hosts
copy /Y "%HOSTS%" "%HOSTS%.bak" >nul
echo  Backup criado em: %HOSTS%.bak

REM Remove QUALQUER linha antiga com casanova.sistema (ativa)
powershell -NoProfile -Command ^
  "$f = '%HOSTS%';" ^
  "$l = Get-Content $f | Where-Object { $_ -notmatch 'casanova\.sistema' };" ^
  "Set-Content -Path $f -Value $l -Encoding ASCII;"

REM Adiciona a entrada correta
powershell -NoProfile -Command ^
  "Add-Content -Path '%HOSTS%' -Value '`n%IP%    %NOME%' -Encoding ASCII;"

echo.
echo  Depois:
findstr /I "%NOME%" "%HOSTS%"
echo.

REM Limpa o cache de DNS
ipconfig /flushdns >nul
echo  Cache de DNS limpo.

echo.
echo  ============================================================
echo   PRONTO!
echo.
echo   Feche e abra o navegador e acesse:
echo     https://%NOME%/industria/rastreio/
echo.
echo   Se ainda nao abrir, use direto o IP:
echo     https://%IP%/industria/rastreio/
echo  ============================================================
echo.
pause
