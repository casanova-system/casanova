---
name: production-tracker
description: |
  Rastreamento profissional de producao diaria com controle de horas, dados do
  contratante/contratado, calculo de carga horaria e relatorio completo para
  justificativa de honorarios. Na primeira execucao em novo projeto, coleta dados
  profissionais (empresa contratada, programador, cliente, empresa do cliente).
  Gera relatorio com timestamps, metricas de producao e resumo executivo.
  SEMPRE ATIVA — toda sessao, todo projeto, sem trigger necessario.
author: Duarte System
version: 2.0.0
date: 2026-03-30
---

# Production Tracker v2

Voce DEVE manter um registro detalhado de producao diaria para justificativa
profissional de honorarios. Este registro serve como comprovante de trabalho
entre contratado e contratante.

**Esta skill e SEMPRE ativa. Toda sessao. Todo projeto. Sem trigger.**

---

## 1. Configuracao do Projeto (Primeira Execucao)

Na PRIMEIRA VEZ que esta skill e ativada em um projeto, voce DEVE:

### 1.1 Verificar se existe `.claude/production/project-config.json`

- **Se existir:** carregar configuracoes e prosseguir
- **Se NAO existir:** PERGUNTAR ao programador as seguintes informacoes:

```
Para configurar o controle de producao deste projeto, preciso de algumas informacoes:

1. Qual o nome da sua empresa? (contratada)
2. Qual o seu nome completo? (programador responsavel)
3. Qual o nome do cliente? (pessoa fisica)
4. Qual o nome da empresa do cliente? (contratante)
5. Qual o nome/descricao do projeto?
6. Qual seu valor/hora ou modelo de cobranca? (opcional — para calculo no relatorio)
7. Alguma observacao importante para os relatorios? (opcional)
```

### 1.2 Salvar em `.claude/production/project-config.json`:

```json
{
  "version": "2.0.0",
  "contratada": {
    "empresa": "Nome da empresa do programador",
    "responsavel": "Nome completo do programador",
    "cargo": "Desenvolvedor"
  },
  "contratante": {
    "empresa": "Nome da empresa do cliente",
    "responsavel": "Nome do cliente (pessoa)",
    "projeto": "Nome/descricao do projeto"
  },
  "cobranca": {
    "modelo": "por_hora | por_projeto | mensal",
    "valor_hora": null,
    "moeda": "BRL"
  },
  "observacoes": "",
  "criado_em": "2026-03-30T09:00:00-03:00"
}
```

### 1.3 Se o programador nao quiser responder tudo

Preencher com valores padrão e informar que pode ser atualizado depois com o
comando "atualizar dados do projeto".

---

## 2. Regras Fundamentais

1. **TODA acao significativa deve ser registrada** com timestamp Sao Paulo
2. **O registro e por EXPEDIENTE, nao por dia calendario** — se o trabalho comecar dia 28 e terminar dia 29, tudo fica no log do dia 28
3. **Formato de hora: HH:MM (America/Sao_Paulo)** — sempre converter para BRT/BRST
4. **Linguagem dos registros: PT-BR** — o contratante e brasileiro
5. **Nunca pular registro** — mesmo tarefas pequenas contam como producao
6. **Cada tarefa DEVE ter hora de inicio e hora de fim** — para calculo de duracao
7. **Ao fim, calcular total de horas e justificativa** — indispensavel
8. **HORARIOS DEVEM SER REAIS — NUNCA INVENTAR**
9. **Registrar apenas FATOS — nunca suposicoes**

### 2.1 Regra de Horarios Reais (CRITICA)

**NUNCA estimar, supor ou inventar horarios.** O production-tracker serve para
justificar honorarios — horarios falsos comprometem a credibilidade do relatorio.

Antes de CADA registro de atividade, consultar o horario real:

```bash
python -c "from datetime import datetime; import pytz; tz = pytz.timezone('America/Sao_Paulo'); print(datetime.now(tz).strftime('%H:%M'))"
```

Regras:
- Horario confirmado pelo programador (ex: "comecei as 9") → usar como real
- Horario obtido via comando acima → usar como real
- Horario aproximado (nao verificado) → marcar com (~) antes do horario
- **NUNCA** colocar horario preciso sem te-lo verificado

### 2.2 Regra de Fatos Documentados

O production-tracker registra **acoes que aconteceram**, nao previsoes ou suposicoes.

- ✅ "Lidas 5 transcricoes de reunioes" — FATO (aconteceu)
- ✅ "Criado arquivo docs/analises/etapa-01.md" — FATO (verificavel)
- ❌ "Analise deve levar ~2h" — PREVISAO (nao registrar como atividade)
- ❌ "Sistema provavelmente precisa de X" — SUPOSICAO (nao registrar)

Se uma atividade foi iniciada mas nao concluida, registrar como "Em andamento"
com hora de inicio real. Hora de fim sera preenchida quando concluir.

---

## 3. Regra de Virada de Meia-Noite

O expediente e definido pela DATA DE INICIO:
- Se comecou em 28/03, o log e `2026-03-28.md`
- Se o trabalho continua apos 00:00 (ja e 29/03), entradas continuam no log de 28/03
- Timestamps mostram hora real (ex: `[01:30]` = madrugada do dia seguinte)
- Cabecalho indica: `**Periodo:** 28/03/2026 22:00 — 29/03/2026 02:15`
- O log so "vira" quando o programador ENCERRA e INICIA novo expediente

### Controle de Sessao Ativa

Ao iniciar sessao:
1. Verificar se existe `.claude/production/current-session.txt`
2. Se existir e conter uma data → continuar no log dessa data
3. Se nao existir → criar com data atual e iniciar novo log

Ao encerrar expediente:
1. Preencher metricas finais e calcular horas
2. Gerar PDF
3. **Deletar** `current-session.txt`

---

## 4. Inicio de Sessao: Ler e Continuar

Ao iniciar qualquer sessao:

1. Ler `project-config.json` (dados do contratante/contratado)
2. Ler `.claude/production/YYYY-MM-DD.md` do dia atual (se existir)
3. Se nao existir, criar com o template abaixo
4. Registrar `[HH:MM] Sessao iniciada` na Timeline
5. Ler ultimo log para contexto (se houver sessao anterior no dia)

Se `.claude/production/` nao existir, criar.

### Template do Log Diario

```markdown
# Relatorio de Producao — DD/MM/YYYY (Dia da Semana)

## Dados do Contrato
| Campo | Valor |
|-------|-------|
| **Contratada** | [empresa do programador] |
| **Responsavel Tecnico** | [nome do programador] |
| **Contratante** | [empresa do cliente] |
| **Solicitante** | [nome do cliente] |
| **Projeto** | [nome do projeto] |
| **Data** | DD/MM/YYYY |
| **Periodo** | HH:MM — HH:MM |

---

## Resumo Executivo
> [Preenchido ao final do expediente — 3-5 linhas resumindo entregas e valor gerado]

## Metricas de Producao
| Metrica | Valor |
|---------|-------|
| Inicio do expediente | HH:MM |
| Fim do expediente | HH:MM |
| **Horas trabalhadas** | **Xh XXmin** |
| Commits realizados | N |
| Arquivos criados | N |
| Arquivos modificados | N |
| Linhas adicionadas | +N |
| Linhas removidas | -N |

---

## Detalhamento de Atividades (Timeline)

### [HH:MM — HH:MM] Titulo da Atividade (Xh XXmin)
- **Tipo:** Implementacao | Correcao | Melhoria | Analise | Configuracao | Reuniao
- **Descricao:** O que foi feito
- **Arquivos:** `path/to/file.ts`
- **Resultado:** Concluido | Em andamento | Bloqueado

---

## Registro de Commits
| Hora | Hash | Mensagem |
|------|------|----------|

## Implementacoes Realizadas
- [x] [descricao — concluida]
- [ ] [descricao — em andamento]

## Correcoes Aplicadas (Bug Fixes)
- [x] [descricao do bug e correcao]

## Melhorias Tecnicas (Refactoring/Otimizacao)
- [x] [descricao da melhoria]

## Decisoes Tecnicas Documentadas
| Hora | Decisao | Justificativa |
|------|---------|---------------|

## Problemas Encontrados e Solucoes
| Hora | Problema | Solucao | Tempo gasto |
|------|----------|---------|-------------|

## Pendencias para Proximo Expediente
- [ ] [descricao com prioridade: Alta/Media/Baixa]

---

## Composicao de Horas

| # | Atividade | Inicio | Fim | Duracao | Tipo |
|---|-----------|--------|-----|---------|------|
| 1 | [descricao] | HH:MM | HH:MM | Xh XXmin | Implementacao |
| 2 | [descricao] | HH:MM | HH:MM | Xh XXmin | Correcao |
| | **TOTAL** | | | **Xh XXmin** | |

## Justificativa de Honorarios
> [Preenchido ao final — resumo tecnico do valor entregue, complexidade das
> tarefas, decisoes que economizaram tempo futuro, e qualquer observacao
> relevante para o contratante entender o valor do trabalho realizado]

---

*Relatorio gerado automaticamente por Production Tracker v2 — Duarte System*
*Data de geracao: DD/MM/YYYY HH:MM (America/Sao_Paulo)*
```

---

## 5. Durante o Trabalho: Registro Continuo

Registre na timeline TODA acao significativa com timestamp e TIPO:

### O que registrar (com hora de inicio e fim):
- Inicio/fim de cada tarefa ou feature
- Cada commit (hash curto + mensagem)
- Decisoes tecnicas tomadas (qual tecnologia, por que)
- Problemas encontrados e como foram resolvidos
- Instalacoes de dependencias
- Configuracoes de infraestrutura
- Testes executados e resultados
- Deploys realizados
- Revisoes de codigo
- Reunioes ou alinhamentos
- Analise e pesquisa (tempo investido em estudo tambem e produtivo)

### O que NAO registrar:
- Leitura silenciosa de arquivos (a menos que gere insight importante)
- Tentativas de busca que nao levaram a nada
- Detalhes internos de prompt/skill

### Formato de entrada na timeline:

```markdown
### [HH:MM — HH:MM] Descricao curta da atividade (Xh XXmin)
- **Tipo:** Implementacao
- **Descricao:** Detalhes relevantes
- **Arquivos:** `path/to/file.ts`, `path/to/other.ts`
- **Resultado:** Concluido
```

### Importante: Registrar INICIO de cada atividade

Quando iniciar uma atividade, registrar imediatamente com hora de inicio.
Quando finalizar, atualizar com hora de fim e duracao.
Se nao souber a hora exata de fim, estimar com base no contexto.

---

## 6. Encerramento do Expediente: Gerar Relatorio

Quando o programador indicar que esta encerrando (ou pedir relatorio):

### 6.1 Coletar metricas do git:
```bash
# Commits do dia
git log --since="YYYY-MM-DDT00:00:00" --until="YYYY-MM-DDT23:59:59" --oneline
# Estatisticas
git diff --stat HEAD~N  # onde N = numero de commits do dia
```

### 6.2 Preencher secoes finais:
1. **Resumo Executivo** — 3-5 linhas objetivas sobre entregas e valor
2. **Metricas de Producao** — calcular horas, commits, linhas
3. **Composicao de Horas** — tabela detalhada com cada atividade e duracao
4. **Justificativa de Honorarios** — explicacao tecnica do valor entregue
5. **Classificar atividades** — marcar concluidas com [x], pendentes com [ ]
6. **Proximos Passos** — listar pendencias com prioridade

### 6.3 Gerar PDF de producao:
```bash
# Opcao 1: pandoc
pandoc .claude/production/YYYY-MM-DD.md -o .claude/production/YYYY-MM-DD.pdf \
  --pdf-engine=wkhtmltopdf \
  -V geometry:margin=2cm \
  -V mainfont="Arial" \
  -V fontsize=11pt

# Opcao 2: md-to-pdf via npx
npx md-to-pdf .claude/production/YYYY-MM-DD.md \
  --config-file .claude/production/pdf-config.json

# Opcao 3: informar programador se nenhum disponivel
```

### 6.4 Informar o programador:
- Onde o PDF foi salvo
- Total de horas trabalhadas
- Quantidade de entregas
- Pendencias para o proximo dia

---

## 7. Configuracao de PDF (criar na primeira vez)

Salvar em `.claude/production/pdf-config.json`:

```json
{
  "stylesheet": [],
  "body_class": [],
  "css": "body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 11pt; line-height: 1.6; color: #1a1a1a; } h1 { color: #0f172a; border-bottom: 3px solid #1e40af; padding-bottom: 10px; font-size: 18pt; } h2 { color: #1e3a5f; margin-top: 28px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; } h3 { color: #334155; margin-top: 16px; } table { width: 100%; border-collapse: collapse; margin: 12px 0; } th, td { border: 1px solid #cbd5e1; padding: 10px 12px; text-align: left; } th { background-color: #1e40af; color: white; font-weight: 600; } tr:nth-child(even) { background-color: #f8fafc; } blockquote { border-left: 4px solid #1e40af; padding: 12px 16px; background: #f0f4ff; margin: 16px 0; font-style: italic; } code { background: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 10pt; } strong { color: #0f172a; } .footer { margin-top: 40px; padding-top: 12px; border-top: 2px solid #1e40af; font-size: 9pt; color: #64748b; text-align: center; }",
  "pdf_options": {
    "format": "A4",
    "margin": { "top": "20mm", "bottom": "25mm", "left": "20mm", "right": "20mm" },
    "printBackground": true,
    "displayHeaderFooter": true,
    "headerTemplate": "<div style='font-size:8pt; color:#64748b; width:100%; text-align:center; padding:5px 20mm;'>Relatorio de Producao — Confidencial</div>",
    "footerTemplate": "<div style='font-size:8pt; color:#64748b; width:100%; text-align:center; padding:5px 20mm;'>Pagina <span class='pageNumber'></span> de <span class='totalPages'></span></div>"
  },
  "marked_options": { "headerIds": true }
}
```

---

## 8. Comandos do Programador

| Comando / Frase | Acao |
|---|---|
| "relatorio de producao" / "gerar relatorio" | Finalizar e gerar PDF do dia |
| "resumo do dia" | Mostrar timeline resumida sem gerar PDF |
| "o que fizemos hoje?" | Listar atividades do dia |
| "encerrar expediente" | Finalizar metricas + gerar PDF + listar pendencias |
| "producao da semana" | Compilar logs dos ultimos 7 dias |
| "producao do mes" | Compilar logs do mes atual |
| "atualizar dados do projeto" | Reconfigurar project-config.json |
| "composicao de horas" | Mostrar tabela detalhada de horas por atividade |

---

## 9. Estrutura de Arquivos

```
.claude/
└── production/
    ├── project-config.json      ← dados contratante/contratado (1x por projeto)
    ├── pdf-config.json          ← config visual do PDF (1x)
    ├── current-session.txt      ← data do expediente ativo
    ├── 2026-03-30.md            ← log do dia
    ├── 2026-03-30.pdf           ← PDF gerado
    └── weekly/
        └── 2026-W14.md          ← compilado semanal (sob demanda)
```

---

## 10. Integracao com Outras Skills

- **napkin**: Referenciar erros/aprendizados do dia no relatorio
- **architecture-decision-records**: Incluir ADRs na secao "Decisoes Tecnicas"
- **commit-commands**: Registrar commits automaticamente na timeline
- **memory**: Registrar memorias salvas como "Decisao documentada"
- **timeline-report** (claude-mem): Complementar com timeline detalhada
- **gsd**: Integrar progresso de fases no relatorio de producao

---

## 11. Relatorio Semanal/Mensal

Quando solicitado "producao da semana" ou "producao do mes":

### Template de Compilado

```markdown
# Relatorio de Producao — Semana/Mes [periodo]

## Dados do Contrato
[Mesmos dados do project-config.json]

## Resumo do Periodo
| Metrica | Valor |
|---------|-------|
| Dias trabalhados | N |
| Horas totais | Xh XXmin |
| Media diaria | Xh XXmin |
| Commits totais | N |
| Features entregues | N |
| Bugs corrigidos | N |

## Composicao de Horas por Dia
| Data | Inicio | Fim | Horas | Principais entregas |
|------|--------|-----|-------|---------------------|

## Entregas do Periodo
[Lista consolidada de todas as implementacoes]

## Valor Entregue
> [Resumo executivo do periodo — impacto das entregas, valor para o negocio]
```

---

## 12. Exemplo de Timeline Real

```markdown
### [09:15 — 09:25] Sessao iniciada e contexto (10min)
- **Tipo:** Configuracao
- **Descricao:** Abertura do projeto, leitura de contexto, alinhamento de prioridades
- **Resultado:** Concluido

### [09:25 — 10:30] Setup de ambiente e instalacao de skills (1h 05min)
- **Tipo:** Configuracao
- **Descricao:** Inventario de ferramentas, instalacao de 5 pacotes de skills, configuracao do MCP
- **Arquivos:** `.claude/skills/`, `.mcp.json`
- **Resultado:** Concluido — 24 novas skills disponiveis

### [10:30 — 12:00] Analise e documentacao do sistema existente (1h 30min)
- **Tipo:** Analise
- **Descricao:** Mapeamento de workflows n8n, documentacao de endpoints Z-API, pesquisa consolidada
- **Arquivos:** `docs/engenhario-sdr/pesquisa-consolidada.md`
- **Resultado:** Concluido
```
