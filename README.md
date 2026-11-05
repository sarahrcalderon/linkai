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
O cadastro continua sem liberar acesso; não há endpoint para verificar e-mails.

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
  envios simultâneos. Aceita somente o status 202 contratado e mostra a mensagem
  uniforme de que a verificação de e-mail será necessária. Não informa existência
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

Não foi realizada homologação ponta a ponta em navegador com cookies reais nem
medição visual de overflow em dispositivos. Formulários usam largura fluida,
campos sem largura mínima fixa e controles que quebram linha; acessibilidade e
associação de erros foram verificadas em DOM de teste. As restrições de cookies
de terceiros dos navegadores continuam relevantes em sites distintos.
Uma sessão expirada é reconhecida na próxima consulta; não há encerramento visual
instantâneo por evento do servidor. Validação completa de e-mail continua no backend.
Brevo, verificação real de e-mail, métricas reais e Etapa 3.5 não foram implementados.

## Arquitetura e próximas etapas

Em `backend/src/aplicacao`: domínio independente, contratos e casos de uso,
infraestrutura assíncrona e apresentação HTTP. O repositório executa flush;
`BancoDados.transacao()` controla commit/rollback. O endpoint mantém a transação
em dependência com escopo de função para concluir o commit antes de enviar a resposta.
Não foram necessárias novas migrações na Etapa 3.2.

Etapa 3.4 concluída no escopo acima. Etapa 3.5 não iniciada.
Fase 4: verificação real de e-mail e integração Brevo por abstração.
Variáveis futuras previstas, ainda não utilizadas: `BREVO_API_KEY`, `EMAIL_REMETENTE`,
`NOME_REMETENTE` e `URL_PUBLICA_FRONTEND`. Links e analytics também ficam fora do escopo.

Resultados e arquivos: [relatório da Fase 3](docs/relatorios/fase3-autenticacao.md).
Commit sugerido para a Etapa 3.4: `feat: integrar autenticacao ao frontend`.
Nenhum commit, push ou deploy foi executado automaticamente.
