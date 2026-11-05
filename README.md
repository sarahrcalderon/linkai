# Linkai

Monorepositório com backend FastAPI e frontend React, TypeScript e Tailwind CSS.

## Requisitos

- Python 3.12+.
- Node.js 22+.
- PostgreSQL 16+; etapas 3.1 e 3.2 homologadas em PostgreSQL 18.6 local.

## Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
```

Copie `.env.exemplo` para `.env`, configure um PostgreSQL local dedicado chamado
`linkai`, e preencha a conexão somente no arquivo local ignorado pelo Git.
O usuário do banco precisa criar tabelas e índices para aplicar migrações.

| Variável | Uso |
| --- | --- |
| `AMBIENTE` | `desenvolvimento` por padrão |
| `URL_BANCO` | `postgresql+asyncpg://USUARIO:SENHA@localhost:5432/linkai` |
| `ORIGENS_PERMITIDAS` | Lista JSON de origens explícitas; padrão `["http://localhost:5173"]` |
| `CADASTRO_LIMITE_TENTATIVAS` | 5 requisições por IP, por processo |
| `CADASTRO_JANELA_SEGUNDOS` | Janela móvel de 900 segundos |
| `URL_BANCO_TESTE` | Variável do processo, apontando para PostgreSQL exclusivo de testes |

Codifique caracteres especiais nas credenciais da URL. Neon Free: use a URL
PostgreSQL fornecida pelo painel com `?sslmode=require`; `verify-full` também
é suportado. Prefira conexão direta para migrações. A configuração Neon foi
testada sem rede; não foi feita homologação contra uma conta Neon real.

```bash
alembic upgrade head
alembic current
uvicorn aplicacao.principal:app --reload --no-proxy-headers
```

Não há criação automática de tabelas ao iniciar a API. `alembic downgrade base`
remove a tabela e seus dados: execute somente em banco descartável.
API: http://localhost:8000; documentação interativa: http://localhost:8000/docs.

## Frontend e Fase 2

```bash
cd frontend
npm install
npm run dev
npm run lint
npm run test
npm run build
```

Site: http://localhost:5173. No PowerShell, use `npm.cmd` se `npm.ps1` estiver
bloqueado pela política de execução. O build inclui a checagem TypeScript.
Componentes reutilizáveis, temas claro/escuro e prévia responsiva permanecem
preservados. Os números exibidos são fictícios. Consulte o
[design system](docs/arquitetura/fase2-design-system.md).
O formulário de cadastro no frontend fica para a etapa de integração React.

## Etapa 3.2 — Cadastro seguro

| Método | Endpoint | Resultado |
| --- | --- | --- |
| GET | `/api/saude` | Funcionamento da API, independente do banco |
| POST | `/api/autenticacao/cadastro` | Recebe nome, e-mail e senha em JSON |

O cadastro exige nome com 2–100 caracteres após remover espaços nas bordas,
e-mail válido com até 254 caracteres e senha com 12–128 caracteres.
O e-mail é normalizado para minúsculas. Senhas não são aparadas nem truncadas;
valores só com espaços e caracteres de controle são rejeitados. Nome também
rejeita controles. Campos desconhecidos, tipos incorretos e campos ausentes
são rejeitados; o cliente não pode definir estado ativo nem verificação de e-mail.
O corpo completo tem limite de 8192 bytes, inclusive em envio por chunks.

Senhas recebem hash Argon2id com salt aleatório, pela biblioteca argon2-cffi,
fora do event loop, com no máximo dois hashes simultâneos por processo.
O usuário nasce ativo e com `email_verificado=false`. Não há autenticação
automática, cookies, login, sessões ou envio de e-mail nesta etapa.

Para testar, inicie o banco e a API, abra `/docs` e envie o cadastro. Exemplo
de corpo com dados fictícios, somente para teste local:

```json
{
  "nome": "Ana Silva",
  "email": "ana@example.com",
  "senha": "Frase longa de teste!"
}
```

A resposta é `202` com apenas:

```json
{
  "mensagem": "Solicitação recebida. A verificação de e-mail será necessária para acessar a conta."
}
```

A conta é persistida antes da resposta. E-mails duplicados recebem a mesma
resposta, também após cálculo de hash, para reduzir enumeração. Não há atualização
da conta ou troca de senha em tentativas duplicadas. O índice único resolve
cadastros concorrentes. A resposta não afirma que foi enviado um e-mail.

Erros usam `{"erro":{"codigo":"...","mensagem":"..."}}`; validação inclui
uma lista `campos`, sem ecoar valores recebidos. Códigos HTTP:

- `422`: `dados_invalidos`.
- `413`: `corpo_excedido`.
- `429`: `limite_excedido`, com cabeçalho `Retry-After`.
- `503`: `servico_indisponivel`, incluindo falha de banco ou commit.

Tentativas inválidas também consomem o limite. O middleware usa o endereço do
cliente ASGI, sem ler `X-Forwarded-For` diretamente. Ao usar proxy, configure
o servidor para confiar apenas nos proxies conhecidos; em execução direta,
o comando acima desabilita essa interpretação. Não habilite confiança irrestrita.
O limitador é em memória: reinicia com o processo e não é compartilhado entre
workers. Uma implantação com múltiplos processos precisa de limitação compartilhada
ou na borda. Até 10.000 IPs com tentativas recentes ficam na memória; ao atingir
esse limite, novas origens são temporariamente bloqueadas. Nenhuma credencial
deve ser registrada em logs, capturas, comandos compartilhados ou arquivos versionados.

## Testes e homologação

```bash
cd backend
pytest
pytest testes/unitarios
pytest testes/integracao
ruff check .
ruff format --check .
```

Defina `URL_BANCO_TESTE` no processo antes de executar. As integrações de cadastro,
concorrência, commit e rollback usam PostgreSQL real e schemas aleatórios, removidos
ao final. O usuário precisa criar/remover schemas. Sem essa variável, os testes
PostgreSQL são ignorados; isso não comprova homologação. SQLite permanece somente
como cobertura auxiliar de persistência da Etapa 3.1, sem substituir PostgreSQL.

Resultado da Etapa 3.2: **59 testes backend aprovados, 1 ignorado** (variante
SQLite da concorrência), Ruff aprovado; **5 testes frontend**, lint e
build/TypeScript aprovados. O cadastro concorrente persistiu exatamente uma conta;
uma restrição adiada até o commit comprovou `503`, rollback e recuperação.

O cluster de homologação local já criado fica desligado após os testes. Para
reutilizá-lo, execute da raiz no PowerShell, sob o usuário que o criou:

```powershell
$binarioPostgres = 'C:/Program Files/PostgreSQL/18/bin'
& "$binarioPostgres/pg_ctl.exe" -D "$PWD/.postgres-teste/dados" -l "$PWD/.postgres-teste/servidor.log" -o '-h 127.0.0.1 -p 55432' -w start
$senhaHomologacao = [IO.File]::ReadAllText((Join-Path $PWD '.postgres-teste/senha.secret'))
$env:URL_BANCO_TESTE = 'postgresql://linkai_teste:' + $senhaHomologacao + '@127.0.0.1:55432/linkai_homologacao'
Set-Location backend
.venv/Scripts/python.exe -m pytest -q
Set-Location ..
& "$binarioPostgres/pg_ctl.exe" -D "$PWD/.postgres-teste/dados" -m fast -w stop
Remove-Item Env:URL_BANCO_TESTE
$senhaHomologacao = $null
```

Para testar a API manualmente nesse mesmo banco, defina também `URL_BANCO` com
o valor de `URL_BANCO_TESTE` antes de iniciar o Uvicorn. Aplique `alembic upgrade head`
a partir de `backend`. Use somente esse banco exclusivo, nunca produção.
Dados, logs e senha aleatória ficam em `.postgres-teste/`, ignorada pelo Git.
Não é necessário modificar os serviços PostgreSQL existentes.

## Arquitetura e próximas etapas

Em `backend/src/aplicacao`: domínio independente, contratos e casos de uso,
infraestrutura assíncrona e apresentação HTTP. O repositório executa flush;
`BancoDados.transacao()` controla commit/rollback. O endpoint mantém a transação
em dependência com escopo de função para concluir o commit antes de enviar a resposta.
Não foram necessárias novas migrações na Etapa 3.2.

Próximas entregas: Etapa 3.3, autenticação e sessões; integração React em etapa
posterior. Fase 4: verificação real de e-mail e integração Brevo por abstração.
Variáveis futuras previstas, ainda não utilizadas: `BREVO_API_KEY`, `EMAIL_REMETENTE`,
`NOME_REMETENTE` e `URL_PUBLICA_FRONTEND`. Links e analytics também ficam fora do escopo.

Resultados e arquivos: [relatório da Fase 3](docs/relatorios/fase3-autenticacao.md).
Commit sugerido: `feat: implementar cadastro seguro de usuarios`.
Nenhum commit, push ou deploy foi executado automaticamente.
