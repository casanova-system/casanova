# Script para atualizar servidor de produção via SCP
# Requer: OpenSSH Client instalado no Windows (já vem no Windows 10/11)

$servidor = "10.12.50.53"
$usuario = "casanova"
$destinoBase = "/home/casanova/Custo_de_Frete_CASANOVA"
$origemBase = "C:/Users/kauan.silva/Projects/projeto_vidros"

$arquivos = @(
    "core/views/op_manual.py",
    "core/views/ordem_producao.py",
    "core/templates/core/industria/editar_op_manual.html",
    "core/templates/core/industria/lista_op.html"
)

Write-Host "=== Atualizando servidor $servidor ===" -ForegroundColor Cyan

foreach ($arquivo in $arquivos) {
    $origem = Join-Path $origemBase $arquivo
    $destino = "${usuario}@${servidor}:${destinoBase}/${arquivo}"
    
    if (Test-Path $origem) {
        Write-Host "Enviando: $arquivo" -ForegroundColor Yellow
        scp $origem $destino
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  OK" -ForegroundColor Green
        } else {
            Write-Host "  FALHOU" -ForegroundColor Red
        }
    } else {
        Write-Host "  Arquivo não encontrado localmente: $origem" -ForegroundColor Red
    }
}

Write-Host "`n=== Reiniciando serviços no servidor ===" -ForegroundColor Cyan
ssh $usuario@$servidor "sudo systemctl restart casanova; sudo systemctl restart nginx"

Write-Host "`n=== Verificando status ===" -ForegroundColor Cyan
ssh $usuario@$servidor "sudo systemctl status casanova --no-pager -l"

Write-Host "`nDeploy concluido!" -ForegroundColor Green
Read-Host "Pressione Enter para sair"