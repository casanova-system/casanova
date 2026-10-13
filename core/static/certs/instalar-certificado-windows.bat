@echo off
REM ============================================================
REM  Instala o certificado da CA local da Casanova Esquadrias
REM  no Windows, para o navegador confiar no HTTPS do sistema.
REM
REM  Uso: clique com o botao direito -> "Executar como administrador"
REM  (ou execute normalmente: instala so para o seu usuario)
REM ============================================================
setlocal

set CERT=%~dp0casanova-ca.crt

if not exist "%CERT%" (
    echo.
    echo  ERRO: arquivo casanova-ca.crt nao encontrado nesta pasta.
    echo  Coloque este .bat junto com o certificado.
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Casanova Esquadrias - Instalacao do Certificado
echo  ============================================================
echo.
echo  Certificado: %CERT%
echo.

net session >nul 2>&1
if %errorLevel% == 0 (
    echo  Modo ADMINISTRADOR: instalando para TODOS os usuarios deste PC.
    certutil -addstore ROOT "%CERT%"
) else (
    echo  Modo USUARIO: instalando apenas para voce.
    echo  ^(Para todos os usuarios, execute como Administrador^)
    certutil -user -addstore ROOT "%CERT%"
)

echo.
echo  ============================================================
echo   Pronto! Feche e abra o navegador novamente.
echo   Acesse: https://10.12.50.53/industria/producao/
echo  ============================================================
echo.
pause
