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
Desde a Etapa 4.3, configure também VERIFICACAO_SEGREDO e OUTBOX_CHAVE estáveis
antes de usar cadastro/reenvio; veja a seção 4.3. Sem as chaves exigidas, a operação
falha com 503, sem persistir um cadastro parcial. A API não gera chaves temporárias.

| Variável | Uso |
| --- | --- |
| `AMBIENTE` | `desenvolvimento` por padrão |
| `URL_BANCO` | `postgresql+asyncpg://USUARIO:SENHA@localhost:5432/linkai` |
| `ORIGENS_PERMITIDAS` | Lista JSON de origens explícitas; padrão `["http://localhost:5173"]` |
| `CADASTRO_LIMITE_TENTATIVAS` | 5 requisições por IP, por processo |
| `CADASTRO_JANELA_SEGUNDOS` | Janela móvel de 900 segundos |
| `LOGIN_LIMITE_TENTATIVAS` | 10 requisições de login por IP, por processo |
| `LOGIN_JANELA_SEGUNDOS` | Janela móvel de 900 segundos |
| `SESSAO_DURACAO_SEGUNDOS` | Duração fixa: 28800 segundos (8h), entre 60 e 604800 |
| `SESSAO_COOKIE_SEGURO` | Opcional no desenvolvimento; Secure é obrigatório em produção |
| `SESSAO_COOKIE_SAMESITE` | `lax` (padrão), `strict` ou `none` |
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
Cadastro e login agora estão integrados à API na Etapa 3.4, descrita abaixo.

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
O usuário nasce ativo e com `email_verificado=false`. O cadastro não autentica
automaticamente nem cria cookie. Login e sessões estão descritos na Etapa 3.3
abaixo; ainda não há envio de e-mail.

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

## Etapa 3.3 — Login, sessões e logout

| Método | Endpoint | Comportamento |
| --- | --- | --- |
| POST | `/api/autenticacao/login` | E-mail/senha em JSON; `200` somente para conta ativa e verificada |
| GET | `/api/usuarios/me` | `200` com usuário público e CSRF; `401` sem sessão válida |
| POST | `/api/autenticacao/logout` | Revoga sessão, apaga cookie e responde `204` |

O login normaliza o e-mail e verifica Argon2id. E-mail inexistente, senha errada,
conta inativa ou não verificada recebem o mesmo `401`, com código
`credenciais_invalidas` e mensagem `E-mail ou senha inválidos.`. Um hash fictício
é verificado quando a conta não existe para reduzir diferenças de processamento.
O cadastro continua sem liberar acesso. Desde a Etapa 4.3, a confirmação explícita
usa o endpoint descrito adiante; não há atalhos públicos para verificar contas.

Login e logout exigem `Origin` exatamente igual a uma entrada de
`ORIGENS_PERMITIDAS`; ausência ou origem diferente recebe `403`. Isso também
protege contra login CSRF, antes de existir sessão. Para testar pelo Swagger local,
inclua `http://localhost:8000` na lista de origens de desenvolvimento; em CLI,
envie `Origin: http://localhost:5173` explicitamente. O login aceita somente os
campos e-mail e senha, com senha de 1–128 caracteres; campos extras são rejeitados.

Login e `/me` retornam este formato, sem hash de senha ou token de sessão no JSON:

```json
{
  "usuario": {
    "id": "UUID",
    "nome": "Ana",
    "email": "ana@example.com",
    "email_verificado": true
  },
  "csrf": "valor de proteção fornecido pela API"
}
```

O token de sessão usa 32 bytes aleatórios (256 bits) e viaja somente em cookie
HttpOnly. No banco fica apenas SHA-256 do token, com índice único, FK do usuário,
datas UTC, expiração e revogação. SHA-256 é utilizado para resumir tokens aleatórios;
senhas continuam usando Argon2id. O login sempre gera outro token e revoga a sessão
anterior apresentada no cookie, na mesma transação. Outros dispositivos continuam
com suas próprias sessões. Não há renovação automática do prazo.

Em desenvolvimento HTTP, cookie `linkai_sessao`, `Path=/api`, `HttpOnly`,
`SameSite=lax`, expiração e Max-Age. Com Secure habilitado (sempre em produção),
o nome é `__Host-linkai_sessao`, `Path=/`, `Secure`, sem atributo Domain.
O prefixo exige esse caminho e impede cookies Domain equivalentes definidos por
outro subdomínio. O cookie pertence apenas ao host da API.

Para `app.exemplo.com` e `api.exemplo.com` ambos em HTTPS, normalmente `lax`
atende por serem do mesmo site. Em sites distintos, use `none` com Secure/HTTPS;
políticas do navegador para cookies de terceiros ainda podem bloquear o fluxo.
Produção exige `AMBIENTE=producao`, origens HTTPS explícitas, sem curingas.
Configuração insegura é rejeitada ao carregar a aplicação. CORS permite credenciais
e os cabeçalhos Content-Type e X-CSRF-Token apenas para as origens configuradas.

O cliente deve usar `credentials: 'include'`, manter o CSRF retornado em memória
e enviá-lo no cabeçalho `X-CSRF-Token` ao fazer logout. `/me` permite recuperar
esse valor após recarregar a página. Ele é um HMAC-SHA-256 vinculado ao token
da sessão e comparado em tempo constante, sem outro segredo persistido.
CSRF ausente, errado ou de outra sessão recebe `403`, sem revogação ou remoção
do cookie. Sem cookie, logout continua idempotente (`204`, com Origin permitido).
Sessão já revogada ou expirada também pode ser encerrada com o CSRF correspondente.
Nenhum token deve ir para localStorage ou sessionStorage. Respostas de autenticação
usam `Cache-Control: no-store`; não registre cookies ou cabeçalhos CSRF em logs.

Falhas no banco de sessões retornam `503`, sem autenticação alternativa. Falha no
commit do login não entrega cookie; falha no logout não confirma a revogação nem
apaga o cookie. A dependência encerra a transação antes de enviar a resposta.

### Migração, execução e testes da 3.3

Com URL_BANCO configurada para o banco local, execute a partir de `backend`:

```bash
alembic upgrade head
alembic current
uvicorn aplicacao.principal:app --reload --no-proxy-headers
```

Revisão atual: `0002`. Para testar reversão apenas em banco descartável:
`alembic downgrade 0001` remove sessões, preservando usuários;
`alembic upgrade head` recria sessões. Os cookies antigos deixam de funcionar.

Com o PostgreSQL exclusivo iniciado e URL_BANCO_TESTE definida conforme o bloco
PowerShell acima:

```bash
pytest
pytest testes/integracao/teste_autenticacao.py -q
pytest testes/integracao/teste_postgres_migracao.py -q
ruff check .
ruff format --check .
```

Os testes criam usuários verificados somente em fixtures isoladas, exercitam os
endpoints e removem os schemas ao terminar. Para testar login válido nesta etapa,
use essas fixtures; contas criadas pela API continuam recebendo `401` até a Fase 4.
Não há ativação pública nem credenciais de teste incluídas no banco normal.

Homologação 3.3: **103 testes backend aprovados, 1 ignorado**, PostgreSQL 18.6
real, migração `0002 → 0001 → 0002` aprovada e usuários preservados. Login,
expiração, revogação, CSRF, concorrência e falhas de infraestrutura/commit aprovados.
Ruff, ESLint, **5 testes frontend** e build/TypeScript aprovados.

Os limitadores de cadastro e login continuam em memória, independentes, por IP
e processo. Não são adequados como controle global em múltiplas instâncias.
Antes de escalar, adote contadores atômicos compartilhados no PostgreSQL ou em
Valkey/Redis auto-hospedado, além do controle na borda; não exigem licença paga.
Configure corretamente a confiança em proxies para não permitir IP forjado.
Sessões expiradas/revogadas permanecem no banco; limpeza periódica com retenção
definida ainda deve ser planejada. Requisições já autorizadas antes do logout
podem terminar; requisições posteriores à revogação confirmada recebem `401`.

## Etapa 3.4 — Autenticação no React

Páginas `/cadastro`, `/login` e `/dashboard` integradas aos contratos existentes,
com navegação via History API e sem nova dependência de roteamento. A página
inicial mantém o design system e a prévia demonstrativa; o dashboard privado
mostra somente os dados públicos da conta e controles de sessão, sem analytics.

### Configuração local

1. Configure PostgreSQL e `backend/.env` conforme as instruções anteriores.
2. Em `backend`, execute `alembic upgrade head` e
   `uvicorn aplicacao.principal:app --reload --no-proxy-headers`.
3. Copie `frontend/.env.exemplo` para `frontend/.env`. Defina
   `VITE_URL_API=http://localhost:8000`, sem `/api` no final.
4. Em `frontend`, execute `npm install` e `npm run dev`.
5. Acesse http://localhost:5173. Use o mesmo nome de host nos dois serviços;
   não misture `localhost` e `127.0.0.1`.

`VITE_URL_API` é uma configuração pública incorporada ao build Vite. Não coloque
segredos nela. Em produção, configure explicitamente a origem HTTPS da API antes
de executar `npm run build`; não há URL fixa de produção no código.
O servidor de arquivos do frontend precisa devolver `index.html` ao acessar
diretamente `/cadastro`, `/login` ou `/dashboard`, preservando os caminhos da SPA.
Nenhuma configuração de hospedagem ou deploy foi alterada nesta entrega.

`ORIGENS_PERMITIDAS` no backend deve conter exatamente a origem do frontend, por
exemplo `["http://localhost:5173"]`. O navegador envia Origin automaticamente;
o serviço HTTP usa `credentials: 'include'` em todas as chamadas. CORS continua
com origens explícitas e credenciais habilitadas. Não houve mudança de endpoints.
Cookies seguem as regras da Etapa 3.3: HttpOnly, host-only, Secure em produção,
SameSite conforme a relação entre sites e ausência de Domain compartilhado.

### Fluxos e segurança

- Cadastro valida nome, e-mail e senha, mostra erros junto aos campos e bloqueia
  envios simultâneos. Aceita somente o status 202 contratado e, desde a Etapa 4.4,
  direciona para `/verificar-email` com mensagem neutra. Não informa existência
  da conta, não afirma envio de e-mail e não autentica automaticamente.
- Login atualiza o estado apenas depois de 200 com usuário verificado e CSRF válido.
  Respostas 401 permanecem genéricas, incluindo conta não verificada; 429 e falhas
  de rede/serviço recebem feedback acessível. Senhas são limpas ao concluir a requisição.
- A inicialização consulta `/me` uma vez, inclusive em React StrictMode. Usuário
  e CSRF ficam somente em memória. Não há token/credencial em localStorage ou
  sessionStorage; somente a preferência de tema continua no localStorage.
- A área privada fica oculta durante carregamento, ausência de autenticação ou
  indisponibilidade da API. Falha de rede não é interpretada como logout confirmado;
  existe ação para tentar consultar novamente.
- Logout envia `X-CSRF-Token` com o valor do login ou de `/me`. Apenas após 204
  limpa o estado. Falha 403/503 preserva a sessão e apresenta erro; é possível
  atualizar a sessão para recuperar o CSRF caso outra aba tenha trocado o cookie.
- `/me` com 401 remove o acesso e pede novo login. Há revalidação ao retornar
  o foco/visibilidade, limitada a uma vez por minuto, além do botão Atualizar sessão.
  Não há polling em segundo plano nem requisição por renderização.
- Consultas pendentes são deduplicadas e respostas antigas não podem desfazer
  login/logout. A autorização definitiva permanece no backend em cada requisição.
- O cliente aborta chamadas após 15 segundos e não registra credenciais, cookies
  ou CSRF em logs. A proteção do frontend não substitui a autorização da API.

Contas criadas pela API continuam não verificadas. Para exercitar login válido
antes da Fase 4, execute os testes backend, que usam fixtures verificadas isoladas;
não existe atalho público para ativação de conta.

### Validação e limites

```bash
cd frontend
npm run lint
npm run test
npm run build
npm run format:check
```

Etapa 3.4: **29 testes frontend aprovados**, ESLint, TypeScript/build e Prettier
aprovados. Backend preservado: **103 aprovados, 1 ignorado**, com PostgreSQL 18.6
real; Ruff lint e formatação aprovados. Os testes frontend usam respostas HTTP
controladas compatíveis com os contratos, incluindo rejeições e falhas.

Na entrega original da 3.4 ainda não havia homologação em navegador real;
a Etapa 3.5 abaixo registra essa validação. Formulários usam largura fluida,
campos sem largura mínima fixa e controles que quebram linha; acessibilidade e
associação de erros foram verificadas em DOM de teste. As restrições de cookies
de terceiros dos navegadores continuam relevantes em sites distintos.
Uma sessão expirada é reconhecida na próxima consulta; não há encerramento visual
instantâneo por evento do servidor. Validação completa de e-mail continua no backend.
Brevo, verificação real de e-mail, métricas reais e Etapa 3.5 não foram implementados.

## Etapa 3.5 — Homologação final local

Fluxos reais homologados com PostgreSQL 18.6, FastAPI/Uvicorn, Vite e Chromium
headless via Playwright 1.65.0, em ambiente Windows isolado. Banco `linkai_e2e`,
API `http://127.0.0.1:18000`, frontend `http://127.0.0.1:15173`; CORS permite
somente a origem desse frontend. As portas e URLs são exclusivas dos testes.

**Resultado executado:** 10 E2E aprovados; 103 testes backend aprovados e 1 ignorado;
29 testes frontend aprovados; Ruff, ESLint, TypeScript (aplicação e E2E), build e
Prettier aprovados. Evidências: [18 capturas e resultados JSON](docs/relatorios/evidencias/fase3/README.md).
Não há senha, token ou cookie real nos artefatos.

Os E2E cobrem cadastro válido/inválido, 202 uniforme, bloqueio de não verificados,
login verificado por fixture, rejeições genéricas, cookies HttpOnly, CSRF, CORS,
reload, rotas privadas, logout e replay de token revogado, expiração no banco,
falha de conexão, indisponibilidade real do banco, navegação, loading e rate limiting.
Não são respostas de sucesso simuladas: o navegador acessa a API e o PostgreSQL.
A interceptação de rede é usada apenas para provocar falha e atrasar envio no teste
de loading; a resposta bem-sucedida continua vindo do backend real.

Responsividade aprovada nas larguras 375, 768 e 1440 px, em claro/escuro, com
altura de 900 px: sem overflow horizontal, controles com pelo menos 44 px de
altura, fonte de campos de pelo menos 16 px e foco por teclado verificado.
Não há sidebar neste produto; a navegação existente foi preservada.

Correções comprovadas pela homologação:

- Botão principal e CTA: fundo esmeralda mais escuro; contraste de 3,65:1 para
  **5,36:1**, preservando o design system.
- Falhas SQLAlchemy: tratadas antes do middleware CORS devolver a resposta,
  permitindo que o navegador leia o `503` padronizado em vez de um erro genérico
  de conexão. Não houve alteração de endpoint ou relaxamento de origem/CSRF.
- Ferramentas: Vitest atualizado para 4.1.12 e typescript-eslint para 8.72.1,
  removendo os dois avisos críticos reportados durante o diagnóstico.

### Executar os E2E

Requer PostgreSQL local, banco **exclusivo e descartável** chamado `linkai_e2e`,
usuário capaz de migrar tabelas, alterar ALLOW_CONNECTIONS e encerrar suas conexões.
O helper recusa hosts remotos e outros nomes de banco. Cada execução limpa usuários
e sessões desse banco, aplica as migrações e cria uma fixture verificada com senha
aleatória mantida apenas em memória. Não aponta para produção.
Não existe atalho público de verificação de contas; desde a Etapa 4.3, confirmar
exige o código temporário e os controles descritos na seção correspondente.

Para reutilizar o cluster já criado neste workspace, execute da raiz em PowerShell:

```powershell
$binarioPostgres = 'C:/Program Files/PostgreSQL/18/bin'
& "$binarioPostgres/pg_ctl.exe" -D "$PWD/.postgres-teste/dados" -l "$PWD/.postgres-teste/servidor.log" -o '-h 127.0.0.1 -p 55432' -w start
$env:PGPASSWORD = [IO.File]::ReadAllText((Join-Path $PWD '.postgres-teste/senha.secret'))
$bancoExiste = & "$binarioPostgres/psql.exe" -h 127.0.0.1 -p 55432 -U linkai_teste -d postgres -w -tAc "SELECT 1 FROM pg_database WHERE datname='linkai_e2e'"
if ($bancoExiste -ne '1') {
  & "$binarioPostgres/createdb.exe" -h 127.0.0.1 -p 55432 -U linkai_teste linkai_e2e
}
$env:URL_BANCO_E2E = 'postgresql://linkai_teste:' + $env:PGPASSWORD + '@127.0.0.1:55432/linkai_e2e'
Remove-Item Env:PGPASSWORD
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $PWD '.postgres-teste/navegadores'
Set-Location frontend
npm.cmd ci
npx.cmd playwright install chromium --only-shell
npm.cmd run test:e2e:tipos
npm.cmd run test:e2e
Set-Location ..
& "$binarioPostgres/pg_ctl.exe" -D "$PWD/.postgres-teste/dados" -m fast -w stop
Remove-Item Env:URL_BANCO_E2E, Env:PLAYWRIGHT_BROWSERS_PATH
```

Se a instância já estiver iniciada, pule o comando start. Em outro ambiente,
configure URL_BANCO_E2E diretamente no processo com credenciais locais, sem gravá-las
em relatórios. `E2E_PYTHON` permite indicar outro Python do venv (por exemplo no
Linux); o padrão aponta para o venv Windows deste repositório.
Playwright inicia e encerra API/Vite e não reutiliza servidores existentes.
Variáveis normais do backend são sobrescritas somente nos processos de teste;
os limites padrão de cadastro e login permanecem ativos.

O cenário de banco indisponível suspende conexões apenas de `linkai_e2e`, encerra
as conexões desse banco e o restaura em finally. Se a execução for interrompida
externamente, a preparação da próxima execução o restaura antes das fixtures.
Logs brutos ficam somente na pasta ignorada `.postgres-teste/`; o teste procura
credenciais/tokens nesses logs. Traces, vídeo e storageState não são gravados.
O relatório E2E sanitiza mensagens de erro e grava somente resultados e durações.

### Pendências para produção

A Fase 3 está estável no ambiente local e nos cenários executados. Isso não
substitui homologação HTTPS do deploy real: Firefox/WebKit, Secure/SameSite em
browser sob HTTPS e políticas de cookies de terceiros não foram testados nesta rodada.
Continuam pendentes rate limiting compartilhado, retenção/limpeza de sessões e
configuração de proxies confiáveis antes de escalar. Não foi realizada auditoria
WCAG completa nem teste em dispositivos físicos.

Auditoria npm observada: **zero avisos em `npm audit --omit=dev`**. Restam sete
avisos moderados na cadeia de ferramentas de desenvolvimento (minimatch/linter).
Não foi aplicado override incompatível nem `audit fix --force`; acompanhar uma
correção compatível e revalidar antes de ampliar exposição das ferramentas.
Permanece o aviso conhecido Starlette/httpx no TestClient, sem falha da suíte.
Verificação de e-mail e Brevo continuam exclusivamente reservados à Fase 4.

## Etapa 4.1 — Estrutura interna de verificação de e-mail

Domínio e infraestrutura para desafios temporários de seis dígitos, com uso único,
limite de tentativas e reenvio controlado. **Sem novas rotas ou telas, geração no
cadastro ou envio real.** Os endpoints da Fase 3 mantêm seus contratos; contas
recém-cadastradas continuam bloqueadas até verificação.

Código gerado por `secrets.randbelow`, persistido somente como HMAC-SHA-256,
vinculado ao usuário e ao UUID do desafio. Confirmação usa comparação segura.
O segredo do servidor impede enumeração offline do espaço numérico a partir do
banco isoladamente. Não registre o código nem o segredo em logs.

| Variável | Padrão/uso |
| --- | --- |
| `VERIFICACAO_SEGREDO` | Sem padrão; segredo aleatório com pelo menos 32 bytes UTF-8 |
| `VERIFICACAO_VALIDADE_SEGUNDOS` | 600 (10 minutos) |
| `VERIFICACAO_LIMITE_TENTATIVAS` | 5 erros por desafio |
| `VERIFICACAO_INTERVALO_REENVIO` | 60 segundos entre emissões |
| `VERIFICACAO_LIMITE_ENVIOS` | 5 emissões por janela |
| `VERIFICACAO_JANELA_ENVIOS` | 3600 segundos |

O segredo é necessário somente para instanciar o novo serviço interno, não para
iniciar a API existente. Gere-o com fonte criptográfica, como `secrets.token_urlsafe(32)`,
e configure apenas no ambiente/gerenciador de segredos. Não use uma senha humana,
placeholder ou chave das fixtures. Os processos devem compartilhar o mesmo segredo.
Rotação invalida códigos pendentes; ainda não há versionamento de chaves.

`criar_verificacao_email(banco, configuracao)` compõe o serviço `VerificarEmail`.
Contratos internos: `gerar_desafio(usuario_id)`, `confirmar(usuario_id, codigo)` e
`invalidar(usuario_id)`. Geração também prepara o reenvio. `DesafioGerado` é um
DTO interno com código protegido por SecretStr, destinado ao futuro serviço de
entrega, nunca a uma resposta HTTP. `ServicoEnvioEmail` é somente uma interface.
O adaptador desse contrato está descrito na Etapa 4.2 abaixo, sem credenciais reais no código.

As operações bloqueiam a linha do usuário em uma transação. O consumo e a alteração
de `email_verificado` são atômicos; tentativa incorreta é persistida, mesmo retornando
falso. Reenvio invalida os códigos anteriores e evita repetir números recentes.
O índice parcial impede dois desafios pendentes do mesmo usuário. Limites de emissão
usam histórico no PostgreSQL, incluindo desafios já invalidados; não remova esse
histórico antes do fim da janela. A futura camada HTTP deverá preservar respostas
uniformes para solicitação/reenvio, sem revelar a existência de contas.

Migração corrente: **0003**. No backend, com banco local configurado:

```bash
alembic upgrade head
alembic current
pytest
pytest testes/unitarios/teste_verificacao_email.py testes/integracao/teste_verificacao_email.py -q
ruff check .
ruff format --check .
```

`alembic downgrade 0002` remove os desafios, preservando usuários e sessões;
use apenas em banco descartável. `alembic upgrade head` recria a estrutura.
Não há alteração automática do estado dos usuários durante a migração.

Validação 4.1 em PostgreSQL 18.6 real: **127 testes backend aprovados, 1 ignorado**;
Ruff aprovado. Frontend: **29 testes**, ESLint e build/TypeScript aprovados.
Também foram reexecutados os **10 E2E Chromium da Fase 3**, todos aprovados.
O teste ignorado continua sendo a variante SQLite de concorrência da Fase 3.
Concorrência, índice único, falha no commit e rollback da verificação foram
homologados em PostgreSQL, sem substituição por mocks.

Pendências para a próxima etapa: composição com solicitação pública protegida,
adaptador de envio pelo contrato, entrega após commit, retentativas, respostas
uniformes e experiência de confirmação. Não avance automaticamente para essas
funcionalidades. Relatório e arquivos: [Etapa 4.1](docs/relatorios/fase4-verificacao-email.md).

## Etapa 4.2 — Adaptador Brevo

Adaptador opcional de infraestrutura para `ServicoEnvioEmail`, sem ativação no
cadastro/login, sem endpoints ou telas novas. A API continua criando contas não
verificadas; importar ou iniciar a aplicação não exige configuração Brevo.

Usa HTTPX assíncrono em HTTPS, TLS padrão, sem proxies de ambiente ou redirecionamentos,
no endpoint transacional oficial. A chave vai apenas no cabeçalho `api-key`.
HTML e texto simples são gerados localmente, sem scripts ou imagens externas,
com código em destaque, expiração absoluta em UTC e aviso para ignorar cadastro
não solicitado. Conteúdo dinâmico do HTML é escapado.
Contrato consultado: [API transacional Brevo](https://developers.brevo.com/reference/send-transac-email).

### Configuração e remetente

Somente ao entrar em `criar_envio_brevo()` as configurações obrigatórias são lidas
e validadas. O arquivo existente é `backend/.env.exemplo`; copie os parâmetros
necessários para o ambiente local, nunca valores reais para o repositório.

| Variável | Uso |
| --- | --- |
| `BREVO_API_KEY` | Obrigatória; chave de API HTTPS, SecretStr, não chave SMTP |
| `BREVO_EMAIL_REMETENTE` | Obrigatório; endereço validado no Brevo |
| `BREVO_NOME_REMETENTE` | Nome exibido; padrão Linkai |
| `BREVO_TIMEOUT_SEGUNDOS` | Até 10s por operação de I/O por tentativa, limitado pelo orçamento restante |
| `BREVO_LIMITE_TENTATIVAS` | Até 3 tentativas no total por chamada |
| `BREVO_TEMPO_TOTAL_SEGUNDOS` | Orçamento total padrão de 20s, incluindo esperas |

Na conta Free, cadastre o nome/endereço em configurações de remetentes. Se solicitado,
confirme o código enviado ao endereço do remetente; autentique o domínio com os
registros fornecidos pelo painel. Isso não foi feito automaticamente nesta entrega.
Siga as instruções oficiais de [criação do remetente](https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email)
e [autenticação de domínio](https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC).

O plano Free consultado em 06/11/2026 permite 300 envios diários, sem acumular
a sobra para o dia seguinte. O adaptador não compra créditos, não altera plano
nem usa recursos de IP dedicado. Manter a conta no Free e acompanhar a cota é
responsabilidade da operação. Nenhum e-mail real foi enviado nesta etapa.
Fonte: [planos Brevo](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans).

### Aceitação, falhas e duplicação

O método retorna `None` somente após **201 com messageId não vazio**, indicando
aceitação pela API, nunca entrega na caixa de entrada. Não há webhook, consulta
de entrega, persistência do messageId ou rastreamento nesta etapa.

| Ocorrência | Política |
| --- | --- |
| ConnectError, ConnectTimeout, PoolTimeout | Retentativa limitada, backoff 0,5s e 1s no padrão; nenhuma requisição enviada |
| 429 | Respeita Retry-After em segundos ou data HTTP; ausente/inválido usa backoff |
| Retry-After além do prazo/código expirado | Interrompe; não encurta a espera para reenviar antes do permitido |
| 400/401/403 e outros 4xx permanentes | Não repete; exceção permanente neutra |
| 5xx, 408, timeout de leitura/escrita, desconexão após envio | Resultado indeterminado; sem repetição automática |
| 201 sem JSON/messageId válido, 200/202 ou redirecionamento | Resultado indeterminado; não declara aceitação nem segue redirect |
| duplicate_parameter ou 409 | Indeterminado, não tratado como comprovante de envio |
| Orçamento total esgotado durante operação | Indeterminado; não dispara nova tentativa |

O mesmo payload e UUID do desafio em `headers.idempotencyKey` são mantidos nas
retentativas. O guia Brevo documenta janela de 30 minutos para idempotência em
batch; isso é defesa adicional, não garantia de entrega única validada aqui.
Não repetimos resultados ambíguos para depender dessa proteção.
Fonte: [idempotência Brevo](https://developers.brevo.com/docs/heterogenous-versions-batch-emails).
Chamadas manuais repetidas, concorrentes ou depois dessa janela ainda podem duplicar
envios; a composição futura precisa de controle durável de solicitações e reconciliação.

A factory é um contexto assíncrono e fecha o cliente ao sair. O adaptador não abre
transações de banco. A composição futura deve aguardar `gerar_desafio()` terminar
(commit concluído) **antes** de chamar `enviar_verificacao()`; não executar HTTP dentro
de `banco.transacao()`. Nunca registrar chave, código, conteúdo integral, destinatário
completo ou detalhes HTTP do provedor. Erros de aplicação são neutros e não carregam
corpos de resposta; mantenha desabilitado logging de payload/cabeçalhos por instrumentação externa.

### Testes e próximos passos

```bash
cd backend
pip install -e ".[dev]"
pytest testes/unitarios/teste_envio_brevo.py -q
pytest
ruff check .
ruff format --check .
```

HTTPX passou de dependência apenas de testes para runtime; nenhum SDK Brevo foi
adicionado. Os testes de envio usam exclusivamente MockTransport e chaves/dados
artificiais, nunca conexão ao Brevo. **173 testes backend aprovados, 1 ignorado**,
incluindo 46 novos; **29 frontend** e **10 E2E Chromium** aprovados. Ruff, ESLint e
build/TypeScript aprovados, com PostgreSQL 18.6 na regressão das etapas anteriores.

Mocks comprovam payload e política de falhas, não entrega real. Falta validar conta
Free/remetente reais e renderização em clientes de e-mail em uma homologação autorizada.
Etapa 4.3: composição após commit, controle durável de envios/reconciliação e política
pública de solicitação/confirmação/reenvio, preservando não enumeração. Não há filas
externas, endpoints ou frontend novos nesta entrega.
Detalhes: [relatório da Fase 4](docs/relatorios/fase4-verificacao-email.md).

## Etapa 4.3 — Cadastro, confirmação e outbox transacional

Os contratos anteriores continuam válidos. O cadastro 202 agora persiste usuário
não verificado, desafio HMAC e intenção de envio **na mesma transação**, sem chamar
Brevo ou criar sessão. Duplicatas recebem o mesmo 202 e não geram outro desafio ou
e-mail, inclusive quando a conta já está verificada. Use o endpoint próprio para reenvio.

| Método e rota | Entrada JSON | Resultado |
| --- | --- | --- |
| POST `/api/autenticacao/verificar-email` | `email`, `codigo` (string de seis dígitos ASCII) | 200 se confirmado; 400 genérico para código incorreto, expirado, usado ou conta indisponível |
| POST `/api/autenticacao/reenviar-codigo` | `email` | 202 uniforme para conta existente, inexistente, já verificada ou cooldown |

Sucesso de confirmação: `{"mensagem":"E-mail verificado. Entre na sua conta para continuar."}`.
Erro: `{"erro":{"codigo":"verificacao_invalida","mensagem":"Código inválido ou indisponível."}}`.
Reenvio: `{"mensagem":"Solicitação recebida. Se aplicável, um código será enviado."}`.
Não há cookie/sessão automática; após confirmar, faça login normalmente.
Campos inválidos recebem 422 sem refletir valores. Excesso de requisições recebe
429/Retry-After; indisponibilidade do banco retorna 503 sem confirmação parcial.
As respostas usam no-store. Confirmações concorrentes têm apenas um sucesso.

O limite de cinco erros, validade de dez minutos, cooldown de sessenta segundos
e cinco emissões por hora continuam configuráveis. O reenvio invalida os desafios
anteriores e cancela intenções antigas ainda não iniciadas. Um e-mail já em voo
pode chegar com código antigo, que não poderá confirmar a conta.

### Chaves e configuração

Mantenha duas chaves independentes, estáveis e fora do Git:

- `VERIFICACAO_SEGREDO`: aleatório, pelo menos 32 bytes, para HMAC e pseudonimização
  dos contadores de requisição. Também necessário ao limitador persistente de login.
- `OUTBOX_CHAVE`: chave Fernet, necessária para cadastro/reenvio e para o worker.
  A confirmação precisa somente do segredo HMAC e do banco, não do cliente Brevo.

Para gerar valores locais em memória, sem exibir no terminal, a partir de backend:

```powershell
$env:VERIFICACAO_SEGREDO = & .venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
$env:OUTBOX_CHAVE = & .venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Gere uma vez e guarde no gerenciador de segredos/ambiente privado usado pelos
processos. Não regenere em cada reinício. API e worker devem receber a mesma chave
Fernet; perder ou trocar a chave com mensagens pendentes impede sua leitura.
Rotação com múltiplas chaves ainda não foi implementada. Não copie as chaves das fixtures.

| Variável | Padrão |
| --- | --- |
| `OUTBOX_LEASE_SEGUNDOS` | 120; mínimo 90 e maior que orçamento HTTPS + 15s |
| `OUTBOX_LIMITE_TENTATIVAS` | 5 ciclos de processamento |
| `OUTBOX_INTERVALO_WORKER` | 1s quando não há trabalho |
| `VERIFICACAO_LIMITE_REQUISICOES` | 20 requisições por IP/rota em 15 minutos |

### Outbox e worker

Migração **0004** cria `outbox_email` e `limites_requisicoes`. A outbox mantém
destinatário, código e DTO exclusivamente em envelope Fernet autenticado, vinculado
ao UUID do desafio. Estados: pendente, processando, enviada, falha, indeterminada
e cancelada. O envelope é removido ao chegar a estado terminal.

Reservas usam SELECT FOR UPDATE SKIP LOCKED, token de posse e prazo. Antes do HTTPS,
outra transação verifica usuário/desafio e marca o início do envio. Ambas terminam
antes da chamada externa. Ao retornar, o token impede uma resposta de worker antigo
de sobrescrever o estado de outro proprietário.

- Queda antes de marcar início: lease expirado permite retomar com segurança.
- Queda/cancelamento depois da marcação: fica indeterminada, sem reenvio automático.
- Erro permanente: falha terminal. Aceitação Brevo: enviada, **sem comprovar entrega**.
- Erro temporário conhecido: backoff de 30s, 60s, 120s etc., limitado a 900s, até
  cinco ciclos por padrão e sempre antes da expiração. Retry-After maior é respeitado;
  se exceder a validade, não há nova tentativa.

Não há promessa de exactly-once ou entrega garantida. Uma queda entre a marcação e
o HTTPS pode deixar resultado indeterminado mesmo sem envio. Se Brevo aceitou e o
processo caiu antes do registro, a outbox também fica indeterminada. A recuperação
prioriza não reenviar às cegas; o usuário pode solicitar novo desafio após os controles.

Execute em terminais separados, com URL_BANCO e chaves compartilhadas:

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn aplicacao.principal:app --reload --no-proxy-headers
```

No terminal do worker, configure também BREVO_* conforme a Etapa 4.2:

```bash
cd backend
python -m aplicacao.infraestrutura.worker_emails
```

**O worker configurado com Brevo real envia e-mails reais.** Não o inicie em testes
automatizados; estes usam adaptadores falsos ou MockTransport. API não exige chave
Brevo nem inicia worker. Para parar, use Ctrl+C (SIGINT), ou SIGTERM em sistemas
que o entregam: o loop deixa de reservar e aguarda a operação corrente finalizar.
Encerramento forçado usa a recuperação por lease na próxima execução.

### Proteção persistente e operação

Cadastro, login, confirmação e reenvio têm contador PostgreSQL atômico por IP/rota,
independente da transação de negócio. Ele contabiliza também dados inválidos e
continua funcionando entre processos/reinícios. IP fica somente como HMAC; o
limitador em memória permanece como barreira adicional. Cadastro/login usam os
limites já configurados; confirmação/reenvio usam o novo limite acima.
Origin presente e não autorizado é rejeitado antes do processamento. Clientes
não browser podem omitir Origin nas rotas públicas; login/logout mantêm suas
exigências anteriores. Cookies, CSRF de logout e CORS explícito foram preservados.

Monitoramento local sem dados sensíveis:

```sql
SELECT estado, count(*) FROM outbox_email GROUP BY estado;
```

Falhas são guardadas somente por categoria neutra. Defina retenção para registros
terminais e contadores antigos; não apague histórico de verificações dentro da janela
de emissões. Mantenha relógios UTC sincronizados e as chaves protegidas e recuperáveis.
Falha ao decifrar deixa a mensagem em falha, sem conteúdo nem envio; solicite um
novo desafio depois de corrigir a configuração, sem reenfileirar a mensagem às cegas.

### Validação e pendências

**196 testes backend aprovados, 1 ignorado**, em PostgreSQL 18.6 real; **29 frontend**
e **10 E2E Chromium** aprovados. Ruff, ESLint, TypeScript/build e Prettier aprovados.
Migração executada como `0004 → 0003 → 0004`, com teste de preservação dos desafios
anteriores na reversão. Testes incluem workers concorrentes, lease/fencing, cancelamento,
rollback até no commit, Brevo simulado, conteúdo cifrado, não enumeração e limites
compartilhados entre duas instâncias. Nenhum e-mail real foi enviado na validação.

Para executar testes: `pytest`, `ruff check .` e `ruff format --check .` no backend;
`npm run lint`, `npm run test` e `npm run build` no frontend. PostgreSQL de testes
usa URL_BANCO_TESTE; comandos E2E continuam na seção 3.5.

O fluxo React foi implementado na Etapa 4.4, descrita abaixo. Homologação autorizada de
entrega real e operação de monitoramento/reconciliação permanecem pendentes. Retenção e rotação de chaves
continuam exigindo planejamento; não há telas administrativas, webhook ou reconciliação
automática de mensagens indeterminadas. Relatório: [Fase 4](docs/relatorios/fase4-verificacao-email.md).

## Etapa 4.4 — Interface de verificação de e-mail

Após cadastro HTTP 202, o frontend abre a rota pública `/verificar-email`, sem
presumir criação de conta ou entrega. E-mail e prazo inicial são transportados
somente em memória; senha é limpa. O código nunca é colocado na URL, histórico,
localStorage ou sessionStorage. Após reload, informe novamente o e-mail.

A tela reutiliza o Design System, temas e layout de login/cadastro. Campo único
de seis dígitos ASCII aceita colagem e `autocomplete="one-time-code"`; teclado
numérico é sugerido no celular. Há erros associados aos campos, foco no erro ou
feedback, carregamento e bloqueio de operações simultâneas. Confirmação usa
`POST /api/autenticacao/verificar-email`: 200 mostra sucesso e link para login;
400 trata igualmente código incorreto, expirado, utilizado ou conta indisponível.
Não cria sessão nem manipula cookies.

Reenvio usa `POST /api/autenticacao/reenviar-codigo`, aceita somente 202 e informa
que endereços elegíveis receberão instruções, sem prometer entrega imediata.
A contagem regressiva é consultável pelo leitor de tela, sem anunciar cada segundo;
a disponibilidade é anunciada uma vez. O backend continua aplicando os limites reais.

Configure `VITE_VERIFICACAO_INTERVALO_REENVIO=60` em `frontend/.env`, alinhado a
`VERIFICACAO_INTERVALO_REENVIO` do backend. O endpoint 202 não expõe cooldown;
o cliente usa o valor documentado. Se `Retry-After` estiver acessível em uma resposta
429, respeita esse prazo; caso contrário, usa o intervalo configurado. O CORS atual
não expõe esse cabeçalho em origens distintas. Reload perde o contador local;
isso não remove o limite PostgreSQL. Não houve mudança de endpoints, CORS ou worker.

Para testar localmente:

1. Configure e inicie PostgreSQL/API com as chaves estáveis e migrações da seção 4.3.
2. Em `frontend`, copie `.env.exemplo` para `.env`, ajuste a URL e o intervalo;
   execute `npm install` e `npm run dev`.
3. Abra `/cadastro` e envie dados válidos. Confira a navegação para `/verificar-email`;
   reload permite preencher o endereço novamente. Login segue bloqueado antes da confirmação.
4. Para confirmar com código recebido, o worker exige configuração Brevo válida
   e seu início causa envio real. A regressão automatizada não inicia o worker;
   os novos testes frontend/E2E usam mocks. Não consulte nem exponha códigos da outbox.

Validação desta etapa: **46 testes frontend**, **14 E2E Chromium** (10 existentes
adaptados ao redirecionamento e 4 novos), **196 backend aprovados e 1 ignorado**,
PostgreSQL 18.6 real. ESLint, build/TypeScript, tipos E2E, Prettier e Ruff aprovados.
Responsividade em 375/768/1440 px e temas claro/escuro: sem overflow, campos ≥16 px,
alvos ≥44 px, foco visível; contraste de botão, texto principal e link ≥4,5:1.
Essas medições não equivalem a auditoria completa de acessibilidade.
[Evidências](docs/relatorios/evidencias/fase4/interface4.4/verificacao-layout.json) e
[relatório da etapa](docs/relatorios/fase4-verificacao-email.md).

Pendências para a Etapa 4.5: homologação autorizada da entrega real, leitores de tela,
HTTPS, outros navegadores/dispositivos e operação/monitoramento conforme planejamento.
A etapa 4.5 não foi iniciada. Nenhuma nova dependência ou migração foi necessária.

## Etapa 4.5 — Homologação local e envio real pendente

**A Fase 4 ainda não está homologada para entrega real.** Em 06/11/2026 foram
executados 207 testes backend aprovados e 1 ignorado, 46 frontend e 14 E2E Chromium.
Ruff, ESLint, Prettier, tipos E2E e build/TypeScript aprovados. Simulações não
comprovam aceitação pelo Brevo nem recebimento pelo destinatário.

O diagnóstico inicial não encontrou backend/.env ou as variáveis URL_BANCO,
VERIFICACAO_SEGREDO, OUTBOX_CHAVE, BREVO_API_KEY e BREVO_EMAIL_REMETENTE no processo.
Configuracao e ConfiguracaoBrevo leem .env **relativo ao diretório corrente**;
inicie API e worker a partir de backend, ou carregue explicitamente o arquivo local.
Não imprima os valores nem envie credenciais/códigos pelo chat.

Foi preparado um banco **novo e vazio**, linkai_email_homologacao45, no cluster
local PostgreSQL 18.6, 127.0.0.1:55432, com migração 0004. A configuração privada
.postgres-teste/homologacao45.env está ignorada pelo Git e contém URL local, chaves
de homologação estáveis e CORS para http://127.0.0.1:15173. Não contém credenciais
Brevo nem destinatário. O cluster foi encerrado após os testes; preserve as chaves
ao reiniciar. Arquivo ignorado não substitui controle de acesso/cofre de segredos.

Para concluir a configuração **somente nesse arquivo privado**, informe:

- BREVO_API_KEY: chave válida configurada localmente, nunca no repositório/relatório.
- BREVO_EMAIL_REMETENTE: remetente autorizado na conta Brevo. Validação sintática
  local não comprova autorização do provedor; ainda não verificada.
- BREVO_NOME_REMETENTE: opcional, padrão Linkai.
- HOMOLOGACAO_DESTINATARIO: um endereço de teste sob seu controle, escolhido por você.

Antes de qualquer envio, é necessária autorização explícita para esse destinatário
e **uma única mensagem de cadastro**. Reenvio real exige autorização adicional.
Não iniciar o worker contínuo sobre filas anteriores. O executor de homologação
isolado em testes/homologacao/envio_controlado.py faz apenas diagnóstico por padrão:

```powershell
cd backend
.venv/Scripts/python.exe -c "from dotenv import load_dotenv; import runpy; load_dotenv('../.postgres-teste/homologacao45.env', override=True); runpy.run_module('testes.homologacao.envio_controlado', run_name='__main__')"
```

Somente após autorização, o mesmo comando com `--autorizar-envio-real` permite
uma execução curta. Exige AMBIENTE=teste, banco local com nome exclusivo e versão
18.6, exatamente um usuário do destinatário permitido e uma intenção pendente,
com zero tentativas. A allowlist também é conferida imediatamente antes do envio.
O adaptador usa limite de uma tentativa HTTPS; o processo não entra em loop.
Filas antigas, resultados indeterminados e mensagens já tentadas são recusados.
Ctrl+C interrompe; cancelamento após início usa o tratamento indeterminado existente.
Não repetir o comando sem revisar o estado e obter autorização.

Para preparar a interface após reiniciar o cluster, sem iniciar envios:

```powershell
cd backend
.venv/Scripts/python.exe -m uvicorn aplicacao.principal:app --env-file ../.postgres-teste/homologacao45.env --host 127.0.0.1 --port 18000 --no-proxy-headers
```

Em outro terminal, frontend: configure VITE_URL_API=http://127.0.0.1:18000 e execute
`npm run dev -- --host 127.0.0.1 --port 15173 --strictPort`. Cadastre o destinatário
apenas na sessão autorizada; a API sozinha apenas enfileira, sem enviar.
Após aceitação pela API Brevo, peça confirmação de recebimento ao destinatário.
Ele deve inserir o código diretamente na interface local, sem logs/chat/relatório.
Depois, valide confirmação e login; resposta 201 não equivale a entrega.

Pendências para lançamento público: entrega real confirmada, operação de retenção
e limpeza de sessões expiradas, rotação planejada/recuperação das chaves, monitoramento
da fila e resultados indeterminados, HTTPS e navegadores/leitores de tela adicionais.
Sessões expiradas já são recusadas, mas não há limpeza periódica automática.
O conteúdo cifrado é removido em estados terminais; linhas/históricos permanecem.
Nenhuma limpeza ou rotação destrutiva foi executada nesta etapa.

[Relatório e plano de autorização](docs/relatorios/fase4-verificacao-email.md).
[Resultado Chromium](docs/relatorios/evidencias/fase4/homologacao4.5/resultado-e2e.json).

## Etapa 5.1 — Domínio e persistência de links personalizados

Entidade `Link` independente do ORM, contrato `RepositorioLinks`, implementação
SQLAlchemy/PostgreSQL e migração incremental **0005**, reversível até 0004.
Não foram adicionados endpoints, telas, redirecionamento ou analytics.

- UUID do link e do proprietário; nome interno com 2–100 caracteres.
- Slug global com 3–64 caracteres, trim/lowercase, letras ASCII/números e hífens
  entre segmentos; nomes reservados são recusados no domínio e no PostgreSQL.
- WhatsApp normalizado como `+` e 8–15 dígitos, incluindo código do país;
  remove espaços, parênteses, pontos e hífens. Validação estrutural, sem comprovar
  atribuição do número, existência da conta WhatsApp ou validade do país.
- Mensagem opcional de até 2000 caracteres, texto sem `<`/`>` e controles inválidos.
- Estado ativo, datas UTC com fuso e exclusão lógica (`excluido_em`).

Slug permanece reservado mesmo inativo/excluído. O repositório não oferece exclusão
física, troca de proprietário nem restauração de exclusão lógica. Na 5.1 o slug
era imutável; a 5.2 permite alterá-lo explicitamente, conforme descrito abaixo. Consultas
privadas exigem UUID do proprietário; consulta pública só retorna ativo não excluído.
A FK RESTRICT impede exclusão física do proprietário com links e preserva a reserva.
Futuras políticas de remoção de conta devem respeitar essa decisão.

PostgreSQL impõe unicidade global, FK, limites, formato do slug/número, reserva e
coerência de datas/exclusão. Índice por proprietário/data apoia consultas futuras.
Savepoint traduz somente conflito da restrição de slug; commit/rollback permanecem
na unidade de trabalho externa, sem chamadas HTTP.

Validação executada em PostgreSQL 18.6 isolado: **278 testes backend aprovados,
1 ignorado**, Ruff check/format aprovados. Concorrência de dois proprietários pelo
mesmo slug persistiu apenas um link. Migração 0005 → 0004 → 0005 validada, preservando
usuários; reversão remove a tabela de links e exige backup antes de uso operacional.
[Arquivos, decisões e resultados](docs/relatorios/fase5-links-personalizados.md).
Etapa 5.2 aguarda aprovação; credenciais, autenticação e Brevo não foram alterados.

## Etapa 5.2 — API autenticada de gerenciamento de links

| Método | Endpoint | Resultado |
| --- | --- | --- |
| POST | `/api/links` | 201 após commit |
| GET | `/api/links?pagina=1&tamanho=20` | Itens próprios, total e paginação |
| GET | `/api/links/{id}` | Detalhes próprios |
| PATCH | `/api/links/{id}` | Atualização parcial |
| DELETE | `/api/links/{id}` | Exclusão lógica, 204 |

Todos exigem sessão válida de usuário ativo com e-mail verificado. Escritas exigem
Origin permitido e X-CSRF-Token do mecanismo existente. Proprietário vem somente
da sessão; campos extras/administrativos são recusados. POST recebe nome, slug,
numero_whatsapp e mensagem opcional. PATCH permite esses campos e ativo; apenas
mensagem aceita null para limpeza explícita. Objeto vazio no PATCH é recusado.

Respostas de link contêm id, nome, slug, numero_whatsapp, mensagem, ativo, criado_em
e atualizado_em. Listagem: itens, total, pagina e tamanho; tamanho 1–100, padrão 20,
página 1–1000000; ordem criado_em DESC/id DESC, incluindo inativos e excluindo
excluídos. Paginação offset não promete snapshot entre requisições concorrentes.

Slug pode mudar por PATCH; o **slug anterior fica disponível**, sem alias/reserva
histórica ou redirecionamento. Exclusão lógica conserva permanentemente o slug
vigente, inclusive contra alteração posterior pelo repositório. Avaliar política
de históricos antes de publicar redirecionamento em uma etapa futura.

UUID/payload inválido: 422; ausência de sessão: 401; CSRF/Origin inválido: 403;
recurso inexistente, excluído ou de outro usuário: mesmo 404; slug indisponível:
409. Escritas limitadas a 16384 bytes reais, inclusive em chunks (413).
Erros usam o envelope existente e respostas no-store. CORS preserva origens explícitas
e acrescenta PATCH/DELETE para suportar os novos métodos, sem alterar cookies.

Validação: **309 testes backend aprovados, 1 ignorado**, PostgreSQL 18.6 real;
Ruff check e format aprovados. Detalhes no
[relatório da Fase 5](docs/relatorios/fase5-links-personalizados.md).
Não há nova migração, interface React, redirecionamento, analytics ou integração
externa nesta etapa. Etapa 5.3 aguarda aprovação.

## Arquitetura e próximas etapas

Em `backend/src/aplicacao`: domínio independente, contratos e casos de uso,
infraestrutura assíncrona e apresentação HTTP. O repositório executa flush;
`BancoDados.transacao()` controla commit/rollback. O endpoint mantém a transação
em dependência com escopo de função para concluir o commit antes de enviar a resposta.
Não foram necessárias novas migrações na Etapa 3.2.

Etapas 3.1–3.5 concluídas no escopo de autenticação e homologação local acima.
Fase 4: verificação real de e-mail e integração Brevo por abstração.
O adaptador usa as variáveis BREVO_* descritas acima. `URL_PUBLICA_FRONTEND` permanece
reservada a necessidades futuras. A Etapa 5.1 implementa modelagem/persistência e
a 5.2 acrescenta APIs de gestão. Interface, redirecionamento e analytics permanecem pendentes.

Resultados e arquivos: [relatório da Fase 3](docs/relatorios/fase3-autenticacao.md).
Commit sugerido para a Etapa 4.5: `test: homologar verificacao de email`.
Nenhum commit, push ou deploy foi executado automaticamente.
