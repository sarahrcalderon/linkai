# Linkai

Monorepositório com backend FastAPI e frontend React, TypeScript e Tailwind CSS.

## Requisitos

- Python 3.12+
- Node.js 22+

## Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn aplicacao.principal:app --reload
pytest
ruff check .
ruff format --check .
```

API: http://localhost:8000/api/saude

## Frontend

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test
npm run build
```

Site: http://localhost:5173

## Segurança e escopo

Esta fase implementa apenas a fundação, um endpoint de saúde e a interface inicial. Cadastro, login, e-mails, links e métricas serão implementados nas próximas fases. Nenhuma credencial deve ser versionada.

## Commits sugeridos

1. `chore: criar estrutura inicial do monorepositorio`
2. `feat: adicionar api e endpoint de saude`
3. `feat: adicionar interface inicial responsiva`
4. `test: configurar verificacoes de qualidade`

Execute e valide cada etapa antes de registrar o commit. Os arquivos deste pacote não foram commitados automaticamente.

## Fase 2 — Interface

Componentes reutilizáveis, temas claro/escuro, prévia responsiva do dashboard e testes de interface. Os números exibidos são fictícios. Consulte `docs/arquitetura/fase2-design-system.md`.


## Fase 3 ? Etapa 3.1: persist?ncia

SQLAlchemy ass?ncrono, driver asyncpg e Alembic. A estrutura permanece em
`backend/src/aplicacao`: dom?nio independente, infraestrutura de persist?ncia,
casos de uso e apresenta??o. O frontend da Fase 2 permanece intacto.

### PostgreSQL local e Neon

Use PostgreSQL 16+ e um banco dedicado chamado `linkai`, com um usu?rio local
que tenha permiss?o de criar tabelas e ?ndices. Instale as depend?ncias com
`pip install -e ".[dev]"` dentro de `backend`.

Copie `backend/.env.exemplo` para `backend/.env` e preencha apenas localmente:

- `AMBIENTE`: `desenvolvimento` (padr?o).
- `ORIGENS_PERMITIDAS`: lista JSON de origens expl?citas.
- `URL_BANCO`: `postgresql+asyncpg://USUARIO:SENHA@localhost:5432/linkai`.
  Caracteres especiais nas credenciais devem ser codificados para URL.
- Neon Free: use a URL PostgreSQL fornecida pelo painel, com `?sslmode=require`.
  O adaptador traduz `sslmode` para asyncpg; `verify-full` tamb?m ? suportado.
  Prefira conex?o direta para migra??es. N?o coloque credenciais em comandos
  compartilhados, capturas, relat?rios ou arquivos versionados.
- `URL_BANCO_TESTE`: opcional, vari?vel do processo para um PostgreSQL dedicado
  aos testes. O usu?rio precisa criar/remover schemas; cada teste isola e remove
  seu pr?prio schema aleat?rio. Nunca aponte para produ??o.

Execute a partir de `backend`:

```bash
alembic upgrade head
alembic current
uvicorn aplicacao.principal:app --reload
```

Para reverter a primeira migra??o em banco de desenvolvimento descart?vel:
`alembic downgrade base` (remove a tabela e seus dados).
N?o h? cria??o autom?tica de tabelas na inicializa??o da API.
O endpoint `GET /api/saude` permanece independente da conex?o com o banco.

### Valida??o

```bash
cd backend
pytest
pytest testes/unitarios
pytest testes/integracao
ruff check .
ruff format --check .
```

Os testes padr?o usam SQLite tempor?rio e n?o exigem servi?o externo. Com
`URL_BANCO_TESTE`, a su?te tamb?m executa persist?ncia e concorr?ncia em PostgreSQL.
SQLite n?o substitui homologa??o PostgreSQL. A su?te verifica avan?o/revers?o
Alembic em SQLite e gera??o de SQL PostgreSQL sem conex?o.
O teste de concorr?ncia real exige PostgreSQL.

O frontend continua sendo executado com `npm run dev`; valide com
`npm run lint`, `npm run test` e `npm run build` (inclui TypeScript).
No PowerShell com restri??o ao arquivo npm.ps1, use `npm.cmd`.

### Limites desta entrega

N?o h? cadastro, hash de senhas, login ou sess?o nesta etapa. `senha_hash` ?
somente um campo de persist?ncia, oculto na representa??o da entidade; os testes
usam valores artificiais. Apenas a futura Etapa 3.2 receber? senhas e produzir?
hash Argon2id. O dom?nio normaliza e limita campos; valida??o completa de e-mail
ser? acrescentada no cadastro. Novos usu?rios t?m `email_verificado=false`.
O reposit?rio executa flush; o chamador controla commit/rollback da transa??o.
`BancoDados.transacao()` fornece esse contexto e `encerrar()` libera o pool.

Pr?ximas etapas: 3.2 cadastro, 3.3 autentica??o e sess?es, 3.4 integra??o React,
3.5 homologa??o e contratos de e-mail. Na Fase 4: verifica??o real de e-mail e
integra??o Brevo por abstra??o. Vari?veis futuras previstas: `BREVO_API_KEY`,
`EMAIL_REMETENTE`, `NOME_REMETENTE` e `URL_PUBLICA_FRONTEND`; ainda n?o s?o lidas.

Relatório e agrupamento dos arquivos: [Fase 3](docs/relatorios/fase3-autenticacao.md).

## Homologação PostgreSQL da Etapa 3.1

Homologada em PostgreSQL 18.6 local: migrações de avanço/reversão/avanço,
inserção, consulta, atualização, concorrência, unicidade e rollback.
Backend: 31 testes aprovados e 1 ignorado (variante SQLite da concorrência).
A variante PostgreSQL passou. Ruff, frontend lint, 5 testes e build passaram.
Não foi feita conexão real com Neon; sua configuração SSL foi testada sem rede.

Foi criado um cluster exclusivo, sem alterar os serviços PostgreSQL existentes.
Ele fica desligado após a validação. Para repetir no PowerShell, a partir da raiz
do repositório, sob o usuário que criou o cluster:

```powershell
$binarioPostgres = 'C:/Program Files/PostgreSQL/18/bin'
& "$binarioPostgres/pg_ctl.exe" -D "$PWD/.postgres-teste/dados" -l "$PWD/.postgres-teste/servidor.log" -o '-h 127.0.0.1 -p 55432' -w start
$senhaHomologacao = [IO.File]::ReadAllText((Join-Path $PWD '.postgres-teste/senha.secret'))
$env:URL_BANCO_TESTE = 'postgresql://linkai_teste:' + $senhaHomologacao + '@127.0.0.1:55432/linkai_homologacao'
$env:URL_BANCO = $env:URL_BANCO_TESTE
Set-Location backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic current
# Somente neste banco exclusivo: downgrade remove a tabela de usuários.
.venv/Scripts/python.exe -m alembic downgrade base
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/ruff.exe check .
.venv/Scripts/ruff.exe format --check .
Set-Location ..
& "$binarioPostgres/pg_ctl.exe" -D "$PWD/.postgres-teste/dados" -m fast -w stop
Remove-Item Env:URL_BANCO_TESTE, Env:URL_BANCO
$senhaHomologacao = $null
```

O diretório `.postgres-teste/` contém dados e credencial temporária e está
ignorado no Git. Em outra máquina, crie um banco dedicado e forneça sua conexão
por `URL_BANCO_TESTE`; o teste de migrações PostgreSQL e os demais testes usam
schemas aleatórios, removidos ao final. Não use banco de produção.
