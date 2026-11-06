# Fase 3 — Etapa 3.1: persistência

## Escopo e diagnóstico

Homologação realizada em 05/11/2026, exclusivamente na Etapa 3.1.
O backend mantém a estrutura FastAPI em `backend/src/aplicacao`, com domínio,
casos de uso, infraestrutura e apresentação. O frontend React/TypeScript da
Fase 2 foi preservado. Cadastro, hash Argon2id, login, sessões, integração de
formulários e envio de e-mail continuam fora desta entrega.

## Ambiente efetivamente observado

- Serviços Windows `postgresql-x64-14` e `postgresql-x64-18` encontrados ativos.
  Os executáveis PostgreSQL não estavam no PATH; foram localizados em
  `C:/Program Files/PostgreSQL/18/bin`.
- Docker CLI instalado, mas daemon indisponível.
- Para não alterar os serviços existentes, foi inicializado outro cluster com
  os binários PostgreSQL 18, autenticação SCRAM-SHA-256 e senha aleatória local.
- Versão confirmada por `SELECT version()`: PostgreSQL **18.6**, 64 bits.
- Instância exclusiva em `127.0.0.1:55432`; banco `linkai_homologacao`, usuário
  `linkai_teste`. Dados, senha e logs em `.postgres-teste/`, ignorada pelo Git.
  Nenhuma credencial foi incorporada a arquivos versionados ou respostas.
- A criação e inicialização do cluster exigiram execução fora do sandbox.
  Os testes do backend conectaram normalmente à instância isolada.

## Resultados observados

| Verificação | Resultado |
| --- | --- |
| Alembic pela CLI no banco dedicado | `upgrade head`, `current`, `downgrade base`, `current`, `upgrade head`, `current` executados com sucesso; revisão final `0001` |
| Migrações automatizadas PostgreSQL | Upgrade, comparação com metadados sem diferenças, downgrade com remoção da tabela, novo upgrade e comparação novamente |
| Inserção e consulta | UUID, campos, valores padrão e datas preservados após commit; consulta por UUID e e-mail normalizado |
| Atualização | Nome, verificação e estado ativo persistidos; `atualizado_em` avançou, `criado_em` permaneceu estável; datas retornadas em UTC |
| E-mail duplicado | Conflito convertido em exceção de domínio; transação continuou utilizável e persistiu outro usuário |
| Concorrência no PostgreSQL | Duas gravações assíncronas com mesmo e-mail: uma criada, uma duplicada; contagem final exatamente 1 |
| Restrição violada | E-mail não normalizado rejeitado; rollback desfez também inserção anterior da mesma transação; nova transação gravou normalmente |
| Rollback de operação composta | Exceção após inserção reverteu a gravação |
| Neon sem credenciais reais | URL fictícia traduzida para asyncpg; parâmetros SSL `require`, `verify-ca`, `verify-full` e `disable` verificados sem conexão; modo desconhecido rejeitado |

A compatibilidade Neon aqui é de configuração do driver. Não foi estabelecida
conexão com Neon nem validado TLS contra um servidor Neon real.
SQLite permanece em testes auxiliares existentes; os resultados de homologação
acima foram efetivamente executados em PostgreSQL, sem substituição por SQLite.

## Qualidade

- Backend: **31 aprovados, 1 ignorado**. O único ignorado é a variante SQLite
  do teste de concorrência; sua variante PostgreSQL passou.
- Execução separada com filtro `-k postgres`: **7 aprovados, 1 ignorado**
  (mesma variante SQLite), 5 desselecionados.
- `ruff check .` e `ruff format --check .`: aprovados.
- Frontend: `npm.cmd run lint`, **5 testes**, `npm.cmd run build`: aprovados.
  O build inclui `tsc -b`. Testes/build foram repetidos fora do sandbox após
  bloqueio de leitura do esbuild; nenhum arquivo de interface foi modificado.
- Permanece aviso de depreciação Starlette/httpx no TestClient existente,
  sem falhas nos testes de saúde.

## Arquivos da etapa e manutenção

- `backend/pyproject.toml`, `.env.exemplo`, `src/aplicacao/configuracao.py`:
  dependências e configuração secreta opcional do banco.
- `src/aplicacao/dominio/usuario.py` e `repositorio_usuarios.py`: entidade,
  normalização, protocolo e exceção de conflito, sem dependência de frameworks.
- `src/aplicacao/infraestrutura/banco.py`, `modelos.py` e
  `repositorio_usuarios.py`: motor assíncrono, transações, tabela e repositório.
- `backend/alembic.ini`, `src/aplicacao/infraestrutura/migracoes/`: revisão 0001,
  configuração e template. Migrações não são executadas na inicialização da API.
- `backend/testes/unitarios/` e `backend/testes/integracao/`: testes da entidade,
  configuração, persistência, concorrência e migrações reais PostgreSQL.
- `.gitignore`, `README.md` e este relatório: isolamento e instruções operacionais.

Caminhos `src/` são relativos a `backend/`. O repositório executa flush; o chamador
controla commit/rollback. O hash é apenas um campo de persistência nesta etapa,
com valores artificiais nas fixtures. Novos usuários permanecem não verificados.
Atualizações via ORM mantêm a data; SQL externo deve atualizar a data explicitamente.

O cluster exclusivo foi encerrado após a homologação; seus dados locais foram
preservados para repetição. Os serviços PostgreSQL preexistentes não foram alterados.
Consulte o README para reiniciar a instância e repetir as verificações.

Commit sugerido para os arquivos da Etapa 3.1:
`feat: estruturar persistencia de usuarios`.
Nenhum commit, push, deploy ou alteração em produção realizado.
Não houve avanço para a Etapa 3.2.

## Etapa 3.2 — Cadastro seguro (05/11/2026)

A seção acima registra a homologação anterior. Nesta entrega foi implementada
exclusivamente a Etapa 3.2; não houve avanço para a 3.3.

### Análise e decisões

A estrutura, a entidade e o repositório da Etapa 3.1 foram revisados antes das
alterações. O domínio continua independente de FastAPI e SQLAlchemy. O índice
único e o savepoint já existentes resolvem duplicatas, inclusive concorrentes;
não foi adicionada consulta prévia que pudesse criar uma condição de corrida.
Não houve mudança de schema nem necessidade de nova migração.

- DTO de entrada validado com Pydantic, sem dependência HTTP ou de banco, e schema
  HTTP derivado. Campos extras são proibidos; senha usa SecretStr e não aparece no repr.
- Caso de uso depende somente do contrato de repositório e da interface de hash.
  Cria entidade ativa, não verificada, sem autenticar.
- Hash Argon2id por argon2-cffi, salt aleatório e parâmetros padrão da biblioteca
  instalada: 64 MiB, 3 iterações e paralelismo 4. Executado em thread com limite
  de dois hashes simultâneos por processo, sem bloquear o event loop.
- Nome: 2–100 caracteres após strip, sem controles. E-mail: até 254 caracteres,
  validado por email-validator sem consulta de entregabilidade e normalizado.
  Senha: 12–128 caracteres, sem truncamento ou strip, sem controles e não composta
  apenas por espaços. Não há exigência artificial de classes de caracteres.
- Resposta `202` idêntica para conta nova ou duplicata, sem identificação da conta,
  senha, hash ou cookie. O hash é calculado em ambos os cenários para reduzir
  diferenças de tempo. A resposta explica a necessidade de verificação futura,
  sem afirmar envio de e-mail. Duplicatas não alteram a conta existente.
- Dependência de transação com `scope="function"`: o commit termina antes de
  enviar a resposta. FastAPI mínimo elevado para 0.121 por esse recurso.
- Erros centralizados e em português: validação 422 sem input/contexto recebido,
  limite do corpo 413, excesso de tentativas 429 com Retry-After, falhas 503 genéricas.
  Consultas usam os parâmetros protegidos e não há log de credenciais na aplicação.
- Middleware limita corpo a 8192 bytes reais, inclusive em chunks, e tentativas
  por endereço ASGI antes da validação/hash. Padrão: 5 em 900 segundos.
  CORS mantém origens explícitas e passa a permitir POST, sem credenciais.

### Arquivos criados

Relativos a `backend/`:

- `src/aplicacao/casos_de_uso/contratos_cadastro.py` — DTO e validações.
- `src/aplicacao/casos_de_uso/servico_hash.py` — protocolo do hash.
- `src/aplicacao/casos_de_uso/cadastrar_usuario.py` — caso de uso.
- `src/aplicacao/infraestrutura/hash_senha.py` — Argon2id.
- `src/aplicacao/apresentacao/schemas_cadastro.py` — entrada/saída HTTP.
- `src/aplicacao/apresentacao/dependencias_cadastro.py` — composição e transação.
- `src/aplicacao/apresentacao/rotas/cadastro.py` — endpoint POST.
- `src/aplicacao/apresentacao/erros.py` — respostas de erro sem dados sensíveis.
- `src/aplicacao/apresentacao/protecao_cadastro.py` — limites de requisição.
- `testes/integracao/teste_cadastro.py` — HTTP, Argon2id e transações em PostgreSQL.
- `testes/unitarios/teste_cadastro.py` — DTO, hash e propagação de falha.
- `testes/unitarios/teste_protecao_cadastro.py` — isolamento e expiração do limite.

### Arquivos modificados

- `backend/pyproject.toml`: dependências, versão mínima FastAPI e importação de testes.
- `backend/.env.exemplo`: variáveis de rate limiting.
- `backend/src/aplicacao/configuracao.py`: limites tipados e validados.
- `backend/src/aplicacao/principal.py`: ciclo de vida do pool, composição, CORS e rota.
- `README.md` e este relatório: instruções, decisões e resultados.

O frontend e as migrações foram preservados. Artefatos egg-info gerados pela
instalação não compõem a implementação e não precisam ser versionados.

### Evidências e qualidade

Instância isolada PostgreSQL 18.6 em `127.0.0.1:55432`, banco
`linkai_homologacao`, reaproveitada sem alterar serviços preexistentes. As fixtures
HTTP aplicam Alembic em schema aleatório por teste e removem esse schema ao terminar.

- **59 testes backend aprovados, 1 ignorado**. O ignorado continua sendo a variante
  SQLite da concorrência; todos os testes PostgreSQL configurados passaram.
- Cadastro válido: conta persistida, nome/e-mail normalizados, hash Argon2id
  verificável, não verificada e ativa; resposta sem senha/hash e sem Set-Cookie.
- Nome/e-mail/senha inválidos, tipos errados, campos ausentes e campos extras
  rejeitados sem persistência ou reflexão de segredos nas mensagens.
- Duplicata com caixa diferente e outra senha: mesma resposta, uma conta persistida
  e senha original preservada.
- Duas requisições HTTP concorrentes: duas respostas genéricas 202 e contagem
  final igual a um usuário em PostgreSQL real.
- Restrição UNIQUE de teste, adiada até o commit: segunda gravação falhou com
  503, sem resposta antecipada de sucesso; rollback preservou só a primeira conta.
  Novo cadastro distinto funcionou em seguida. Não foi usado mock para provar isso.
- Tentativas inválidas consumiram o limite; a sexta recebeu 429/Retry-After,
  mesmo com X-Forwarded-For forjado; saúde permaneceu operacional.
- Corpo em stream com 8193 bytes rejeitado com 413; JSON malformado recebeu 422
  sem refletir senha; testes de log não encontraram senha/hash.
- Hashes independentes da mesma senha diferiram por salt e foram verificáveis.
- `ruff check .` e `ruff format --check .`: aprovados.
- Frontend: ESLint, **5 testes** e build com TypeScript aprovados.

### Problemas encontrados e limitações

- A primeira coleta Pytest encontrou módulos homônimos entre unitários e integração;
  corrigido com `--import-mode=importlib`.
- Instalação PyPI e execução frontend precisaram de execução autorizada fora do
  sandbox por bloqueios de rede/leitura do esbuild; verificações finais passaram.
- Permanece o aviso de depreciação Starlette/httpx já observado na Etapa 3.1.
- Rate limiting em memória, por processo: reinício limpa o histórico e múltiplos
  workers não compartilham contadores. Antes de escalar, adotar controle compartilhado
  ou na borda. Guarda até 10.000 origens recentes; novas origens recebem bloqueio
  quando a capacidade está esgotada. Proxies devem ser configurados explicitamente
  no servidor; não confiar em cabeçalhos enviados diretamente pelo cliente.
- A resposta uniforme reduz enumeração, sem prometer tempo de resposta constante.
- Sem verificação real de e-mail, login, sessão, envio de e-mail ou integração React.
  As contas permanecem não verificadas até a Fase 4; nenhum atalho público foi criado.
- Neon continua validado apenas quanto à configuração, sem credenciais ou conexão real.

Para testar manualmente, configure URL_BANCO local, execute `alembic upgrade head`,
inicie a API e envie JSON em `/docs` ou POST `/api/autenticacao/cadastro`.
O README contém exemplo completo, códigos HTTP e comandos de homologação.
O cluster de teste foi encerrado após as verificações, com dados locais preservados.

Commit sugerido: `feat: implementar cadastro seguro de usuarios`.
Não foram executados commits, pushes, deploys ou alterações de produção.

## Etapa 3.3 — Login e sessões seguras (05/11/2026)

As seções anteriores mantêm o histórico das etapas 3.1 e 3.2. Esta entrega
implementa exclusivamente a 3.3, após revisão dos contratos, modelos, migrações,
composição da API e testes existentes. Não houve avanço para a 3.4.

### Decisões e implementação

- Domínio: entidade Sessao, contrato de repositório e regras de expiração/revogação,
  sem imports de FastAPI ou SQLAlchemy. Identificadores UUID, datas UTC e hash oculto no repr.
- Aplicação: casos separados para autenticar, consultar usuário autenticado e encerrar
  sessão. Dependem de protocolos de usuários, sessões, hash e tokens.
- Login normaliza o e-mail, verifica Argon2id fora do event loop e rejeita com o
  mesmo 401 senha errada, conta ausente, inativa ou não verificada. Conta ausente
  também executa Argon2id contra hash fictício gerado no ciclo de vida da aplicação.
- Infraestrutura gera 32 bytes aleatórios com secrets, persiste apenas SHA-256 do
  token e deriva o CSRF por HMAC-SHA-256 com o próprio token como chave. Nenhuma
  criptografia própria, token em texto puro no banco ou dependência paga.
- Migração 0002: tabela sessoes, FK com cascade para usuários, índice único do hash,
  índices de usuário/expiração e restrições de tamanho e prazo.
- Cada login bem-sucedido cria novo token. A sessão anterior apresentada pelo
  cliente é revogada na mesma transação; token pré-fixado nunca é reaproveitado.
- Consulta verifica sessão existente, prazo, revogação e estado atual do usuário.
  Retorna somente id, nome, e-mail, email_verificado e o CSRF da sessão, sem senha,
  hash ou token de autenticação no JSON. Todas as respostas sensíveis usam no-store.
- Logout faz UPDATE atômico condicionado à ausência de revogação. É idempotente
  com Origin permitido; se houver token, exige CSRF correspondente mesmo para
  sessões expiradas/revogadas. Cookie é apagado após revogação confirmada.
- Cookies host-only, HttpOnly e com prazo fixo de 8h por padrão. Desenvolvimento
  HTTP usa linkai_sessao em /api. HTTPS/Secure usa __Host-linkai_sessao em /, sem
  Domain, impedindo injeção equivalente por subdomínios. Secure obrigatório em produção.
- SameSite=lax por padrão; none exige Secure. Produção exige origens HTTPS explícitas
  e rejeita curingas. CORS passa a permitir credenciais e X-CSRF-Token.
- Origin explícito e permitido obrigatório para login/logout, inclusive clientes CLI.
  Logout autenticado também valida CSRF, com comparação em tempo constante. O cliente
  futuro deverá manter CSRF em memória e usar credentials: include; /me recupera o valor.
- O middleware existente foi parametrizado por caminho para aplicar ao login um
  limitador independente, preservando o cadastro. Padrão login: 10 tentativas por
  IP/900 segundos e corpo de até 8192 bytes, antes de validação/hash.
- Dependência de transação com escopo de função confirma commit antes de enviar
  qualquer cookie. Falha de infraestrutura/commit recebe 503 genérico, sem fallback.

### Arquivos criados

Relativos a `backend/`:

- `src/aplicacao/dominio/sessao.py` e `repositorio_sessoes.py`.
- `src/aplicacao/casos_de_uso/contratos_autenticacao.py`, `servico_tokens.py`,
  `autenticar_usuario.py`, `consultar_autenticado.py` e `encerrar_sessao.py`.
- `src/aplicacao/infraestrutura/tokens.py` e `repositorio_sessoes.py`.
- `src/aplicacao/infraestrutura/migracoes/versions/0002_criar_sessoes.py`.
- `src/aplicacao/apresentacao/cookies_sessao.py`, `dependencias_autenticacao.py`,
  `schemas_autenticacao.py` e `rotas/autenticacao.py`.
- `testes/integracao/teste_autenticacao.py`.
- `testes/unitarios/teste_sessao.py` e `teste_configuracao_sessao.py`.

### Arquivos modificados

- `backend/src/aplicacao/configuracao.py`: limites, prazo, cookies e validação de origens.
- `backend/src/aplicacao/principal.py`: composição, ciclo de vida, middleware e CORS.
- `backend/src/aplicacao/casos_de_uso/servico_hash.py` e
  `infraestrutura/hash_senha.py`: contrato e implementação de verificação Argon2id.
- `backend/src/aplicacao/infraestrutura/modelos.py`: modelo da sessão.
- `backend/src/aplicacao/apresentacao/erros.py`: 401/403 padronizados, no-store e validação de login.
- `backend/src/aplicacao/apresentacao/protecao_cadastro.py`: seleção do caminho protegido.
- `backend/testes/integracao/teste_migracao.py` e `teste_postgres_migracao.py`:
  revisão 0002, reversão e preservação de usuários na reversão exclusiva da 3.3.
- `backend/.env.exemplo`, `README.md` e este relatório.

Nenhum arquivo frontend foi alterado. Não foram adicionadas dependências nesta etapa.

### Homologação observada em PostgreSQL 18.6

Reutilizada a instância exclusiva em 127.0.0.1:55432, banco linkai_homologacao,
sem alterar os serviços PostgreSQL preexistentes. Integrações aplicam Alembic em
schemas aleatórios e os removem ao final. Usuários verificados existem somente
em fixtures controladas; não há endpoint de ativação.

| Cenário | Resultado efetivamente observado |
| --- | --- |
| Migração pela CLI | upgrade head → current 0002 → downgrade 0001 → current 0001 → upgrade head → current 0002 |
| Migração automatizada | Metadados equivalentes; reversão 0002→0001 preserva usuário, remove sessões; novo avanço preserva usuário; também validada reversão completa e recriação |
| Login válido | 200, sessão persistida, cookie com prazo e HttpOnly; /me retorna mesmo usuário e CSRF |
| Falhas de credenciais/estado | Senha errada, e-mail inexistente, não verificado e inativo recebem exatamente a mesma resposta 401; zero sessões criadas |
| Cadastro seguido de login | Cadastro permanece 202, não verificado; login rejeitado com 401 |
| Armazenamento e logs | Apenas hash do token persistido; senha/hash/token não aparecem no JSON nem nos logs capturados, inclusive em falhas |
| Sessões inválidas | Token ausente, inexistente, malformado, expirado ou revogado recebem 401; alteração posterior do estado do usuário também bloqueia /me |
| Logout | 204, revogação persistida e cookie Max-Age=0; repetição segura; replay do token revogado recebe 401 |
| CSRF | Valor ausente, errado ou de outra sessão e Origin não permitido recebem 403, sem revogar nem apagar cookie |
| CORS/Origin | Preflight permite credenciais/cabeçalho CSRF para origem explícita; origem maliciosa ou ausente não consegue fazer login |
| Força bruta | Limite configurado de 3 na fixture bloqueia quarta tentativa com 429/Retry-After; cadastro mantém contador independente |
| Produção | Secure, HttpOnly, SameSite=none, prefixo __Host-, Path=/ e ausência de Domain comprovados no cookie de login/logout |
| Fixação/rotação | Token fornecido previamente não é aceito como novo token; novo login revoga o anterior, que passa a receber 401 |
| Concorrência | Dois logins simultâneos criam tokens distintos; dois logouts simultâneos da mesma sessão têm sucesso e somente essa sessão é revogada |
| Falha no commit | UNIQUE adiado até o commit rejeita segundo login com 503 e sem Set-Cookie; rollback preserva a sessão anterior ativa |
| Falha de revogação | Restrição de banco rejeita UPDATE com 503, sem apagar cookie nem afirmar revogação; sessão permanece utilizável |
| Infraestrutura indisponível | Renomear tabela de sessões faz login, /me e logout retornarem 503, sem cookies/segredos; após restauração, a sessão anterior funciona |
| Validação/limites | Campos extras, ausentes, e-mail inválido e senha acima do limite rejeitados; login com corpo de 8193 bytes recebe 413 |

### Validações finais

- `pytest`: **103 aprovados, 1 ignorado**. O ignorado continua sendo a variante
  SQLite de concorrência da 3.1; a correspondente PostgreSQL e todos os novos
  testes de sessões foram executados em PostgreSQL real.
- `ruff check .` e `ruff format --check .`: aprovados.
- Frontend: ESLint, **5 testes** e build/TypeScript aprovados.
- Permanece o aviso de depreciação Starlette/httpx do TestClient existente.
- Frontend precisou da repetição autorizada fora do sandbox por bloqueio de leitura
  do esbuild. O PostgreSQL isolado também foi iniciado fora do sandbox e encerrado
  depois dos testes. Nenhuma falha ficou pendente na suíte.

### Configuração, limites e pendências

Variáveis novas documentadas no README e .env.exemplo: LOGIN_LIMITE_TENTATIVAS,
LOGIN_JANELA_SEGUNDOS, SESSAO_DURACAO_SEGUNDOS, SESSAO_COOKIE_SEGURO e
SESSAO_COOKIE_SAMESITE. AMBIENTE aceita desenvolvimento, teste e producao.
Produção exige HTTPS nas origens e não permite Secure=false. O endereço do proxy
confiável deve ser configurado no servidor, sem aceitar X-Forwarded-For de qualquer origem.

O rate limiting continua em memória, por IP/processo e com reinício do histórico
ao reiniciar a aplicação. Não é adequado como limite global de múltiplos workers.
Antes de escalar, usar contadores atômicos no PostgreSQL ou Valkey/Redis auto-hospedado,
mais limitação na borda; nenhuma dessas alternativas exige serviço pago.
Respostas genéricas e hash fictício reduzem enumeração, sem garantir tempo constante.
Sessões têm prazo fixo; limpeza periódica dos registros antigos e retenção ainda
precisam de planejamento. Requisições já autorizadas podem terminar durante logout;
após a revogação confirmada, novas consultas rejeitam o token.

Em sites distintos, SameSite=None/Secure ainda depende de políticas de cookies de
terceiros do navegador. Não houve teste em browser nem integração frontend nesta etapa.
Neon continua sem conexão real, somente compatibilidade de configuração já validada.
Verificação por e-mail, Brevo, dashboard real, links e Etapa 3.4 não foram implementados.

Para reproduzir: iniciar banco exclusivo, definir URL_BANCO/URL_BANCO_TESTE,
executar `alembic upgrade head`, iniciar Uvicorn e rodar `pytest`, Ruff e comandos
frontend. O README contém os comandos completos e o contrato HTTP/CSRF.

Commit sugerido: `feat: implementar autenticacao e sessoes`.
Nenhum commit, push, deploy ou alteração em produção foi realizado.

## Etapa 3.4 — Integração de autenticação com React (05/11/2026)

### Análise e escopo

Revisados o frontend React/TypeScript/Vite, componentes e temas da Fase 2,
contratos de cadastro/login/logout/me, CORS e CSRF da Etapa 3.3 antes das alterações.
O frontend tinha somente página inicial, componentes e cinco testes, sem rotas
ou estado de autenticação. A API já atendia ao fluxo e não precisou de alteração.
A implementação ficou exclusivamente na 3.4, sem publicação, Brevo, dashboard
analítico, Etapa 3.5 ou Fase 4.

### Arquitetura e comportamento

- `servicos/http.ts`: fetch central com credentials include, URL por VITE_URL_API,
  limite de 15s, verificação de status esperado, erros tipados e mensagens de rede.
- `funcionalidades/autenticacao/`: tipos, serviço dos quatro endpoints, validações,
  gerenciador de sessão, contexto, provedor e hooks. Senha não é guardada no estado
  da aplicação; o formulário lê FormData e limpa o campo após a requisição.
- O gerenciador mantém usuário e CSRF exclusivamente em memória, consulta /me ao
  iniciar e deduplica consultas, inclusive durante StrictMode. Distingue carregando,
  autenticado, não autenticado e indisponível. A API continua autorizando cada chamada.
- Versões de operações ignoram consultas antigas após login/logout; mutações são
  bloqueadas enquanto outra está pendente. Consultas não começam durante mutações.
- Revalidação no retorno à aba/foco é limitada a uma por minuto, somente se havia
  autenticação confirmada. Botão Atualizar sessão força consulta. Não há polling.
- `navegacao/`: quatro caminhos com History API, links internos preservando abertura
  em outra aba, rota privada, redirecionamento e página não encontrada. Sem nova dependência.
- `Aplicacao.tsx` contém somente composição. Páginas e componentes guardam responsabilidades
  próprias, com layout e feedback reutilizáveis. O dashboard privado mostra somente conta
  e controles de sessão. A prévia pública com dados fictícios foi preservada.
- Cadastro aceita somente 202 e apresenta a mensagem uniforme da API; não consulta
  existência de conta, não autentica nem simula envio de e-mail.
- Login valida o contrato de sucesso em runtime, inclusive email_verificado=true
  e CSRF hexadecimal de 64 caracteres. HTTP rejeitado nunca vira sessão autenticada.
- Logout inclui o CSRF no cabeçalho, sem lê-lo de cookies ou gravá-lo em storage.
  Falhas de logout preservam a sessão; 401 em consulta encerra o estado local.
- Labels, autocomplete, senha mascarada, erros associados com aria-describedby,
  aria-invalid, feedback de status/alerta, foco, loading e bloqueio síncrono de envios.
  Layout com largura fluida, campos min-width:0 e controles com quebra de linha.

### Arquivos criados

Relativos a `frontend/`:

- `.env.exemplo`, `.prettierignore`, `src/vite-env.d.ts` e `src/Aplicacao.tsx`.
- `src/servicos/http.ts`.
- `src/funcionalidades/autenticacao/tipos.ts`, `servico.ts`, `gerenciador.ts`,
  `contexto.ts`, `ProvedorAutenticacao.tsx`, `usarAutenticacao.ts`,
  `validacao.ts` e `usarFormularioAutenticacao.ts`.
- `src/navegacao/usarNavegacao.ts` e `RotasAplicacao.tsx`.
- `src/componentes/EstruturaAcesso.tsx`, `Feedback.tsx`, `FormularioAutenticacao.tsx`
  e `LinkInterno.tsx`.
- `src/paginas/PaginaCadastro.tsx`, `PaginaLogin.tsx` e `PaginaDashboard.tsx`.
- `src/testes/Autenticacao.test.tsx`, `GerenciadorAutenticacao.test.ts` e
  `ServicoHTTP.test.ts`.

### Arquivos modificados

- `frontend/src/principal.tsx`: composição da aplicação.
- `frontend/src/paginas/PaginaInicial.tsx`: links funcionais para cadastro/login.
- `frontend/src/componentes/Cabecalho.tsx`: navegação ao início da aplicação.
- `frontend/src/estilos/globais.css`: campos fluidos e foco de links.
- `frontend/src/testes/configuracao.ts`: cleanup explícito entre testes.
- `frontend/.prettierrc.json`, `src/componentes/Botao.tsx`, `CampoTexto.tsx`,
  `GraficoCliques.tsx`, `src/funcionalidades/tema/usarTema.ts` e os três arquivos
  tsconfig JSON: somente formatação para atender ao Prettier já configurado.
- `README.md` e este relatório: fluxos, ambiente, contratos, validação e limitações.

Nenhuma dependência, endpoint, migração ou implementação backend foi alterada.
Artefatos gerados de TypeScript não fazem parte da entrega.

### Testes e resultados observados

- Frontend: **29 testes aprovados** em cinco arquivos, incluindo os cinco existentes.
- Cadastro válido normalizado e 202 sem autenticar; validação acessível e foco;
  envio simultâneo bloqueado; loading; falha de rede; erros HTTP por campo.
- Login válido redireciona; senha inválida e conta não verificada têm rejeição
  genérica; resposta de sucesso malformada ou com conta não verificada é recusada;
  429 apresentado sem simular acesso.
- Inicialização única em StrictMode; dashboard não aparece antes da confirmação;
  visitante redirecionado; indisponibilidade com nova tentativa; sessão expirada
  remove a área privada; logout envia cookies/CSRF, limpa após 204 e preserva após 503.
- Consulta tardia não restaura sessão após logout; consultas durante mutação não
  são disparadas; inicialização tardia não desfaz login; rejeição durante consulta
  inicial não deixa carregamento permanente; deduplicação e intervalo de foco verificados.
- Serviço HTTP rejeita outro 2xx no lugar do 202, JSON inválido e aborta em 15s.
- Tema alternado e preservado; storage contém somente tema, sem CSRF ou credenciais.
- ESLint, `npm run build` (inclui TypeScript) e `npm run format:check`: aprovados.
- Backend com URL_BANCO_TESTE em PostgreSQL **18.6** real: **103 aprovados, 1 ignorado**,
  preservando cadastro, sessões, migrações e transações. O ignorado permanece a
  variante SQLite da concorrência da 3.1. `ruff check .` e `ruff format --check .` aprovados.

### Problemas encontrados e limites

- Hooks precisam do prefixo use para o ESLint; implementação usa esse prefixo e
  exporta os nomes portugueses usar*, seguindo o padrão do hook de tema existente.
- Prettier existente apontou arquivos antigos sem formatação e tentou incluir dist.
  Adicionado ignore de artefatos e aplicada somente formatação nos arquivos antigos.
- O teste de timeout encontrou DOMException que não satisfazia instanceof Error
  no ambiente de testes. A detecção agora usa o sinal de aborto do controlador.
- Corrigida a condição de corrida que poderia restaurar o estado local por /me
  tardio após logout; há testes para esse comportamento.
- Testes/build frontend exigiram execução autorizada fora do sandbox por bloqueio
  de leitura do esbuild. Permanece o aviso backend Starlette/httpx já conhecido.
- Não houve navegador automatizado disponível para homologação real de cookies,
  navegação ou medidas de overflow em celulares/tablets. Testes DOM não comprovam
  geometria visual ou políticas SameSite/third-party dos navegadores.
- As integrações frontend usam mocks HTTP controlados, não uma sessão de browser
  ligada ao PostgreSQL. O backend foi revalidado separadamente no banco real.
- Sessão expirada é reconhecida na próxima consulta; não há evento de expiração
  instantâneo vindo do servidor. Validação definitiva de entrada fica no backend.
- Rate limiting compartilhado, limpeza de sessões e verificação de e-mail continuam
  com as limitações documentadas nas etapas anteriores.

### Operação

O README contém comandos de backend/frontend, teste e variáveis. VITE_URL_API
recebe a origem da API sem /api e é pública, definida no build. ORIGENS_PERMITIDAS
deve incluir a origem exata do frontend; não misturar localhost/127.0.0.1.
Cookie permanece host-only/HttpOnly/Secure conforme ambiente e SameSite conforme
o deploy. CSRF é recebido no login/me e devolvido no header do logout.
Hospedagem estática deve redirecionar caminhos da SPA para index.html; nenhuma
configuração de deploy foi modificada. A instância PostgreSQL de testes foi
encerrada após a validação, preservando dados locais e serviços preexistentes.

Commit sugerido: `feat: integrar autenticacao ao frontend`.
Nenhum commit, push, deploy ou alteração em produção foi realizado.
Não houve avanço para a Etapa 3.5 ou Fase 4.

## Etapa 3.5 — Homologação e estabilização (05/11/2026)

### Diagnóstico e ambiente

Código de frontend, contratos da API, cookies, CORS, tratamento de erros, fixtures,
migrações e configurações foram revisados antes das alterações. O repositório
estava sem alterações locais. Não havia Playwright nem Chromium instalados no
frontend; foram preparados para esta homologação, sem publicação ou serviços pagos.

- Windows, Node 24.21.0, Python do venv existente e PostgreSQL **18.6** confirmado
  por consulta SQL. Cluster isolado em 127.0.0.1:55432, sem tocar nos serviços existentes.
- Banco exclusivo **linkai_e2e**, distinto de linkai_homologacao usado na regressão.
  Migração corrente 0002. Fixture verificada criada diretamente no banco exclusivo,
  com senha aleatória mantida em memória e sem endpoint público de ativação.
- FastAPI/Uvicorn em 127.0.0.1:18000 e React/Vite em 127.0.0.1:15173. Processos
  iniciados pelo Playwright e encerrados ao terminar; sem reutilizar serviços existentes.
- CORS permite somente http://127.0.0.1:15173, com credenciais. Cookies HTTP locais
  HttpOnly, SameSite=Lax, Path=/api e host-only. AMBIENTE=teste. Secure continua
  obrigatório no modo de produção; nenhuma proteção foi removida.
- Limites normais ativos: cadastro 5/900s e login 10/900s, sem zerar ou aumentar
  limites para passar a suíte. Os E2E usam um worker e cenários sequenciais.
- Playwright **1.65.0**, Chromium headless **158.0.8127.18**, realmente executado.
  Viewports 375, 768 e 1440 px, altura de 900 px, temas claro e escuro.

### Resultados efetivamente executados

| Verificação | Resultado |
| --- | --- |
| E2E Chromium | **10 testes aprovados**, cobrindo os 15 cenários de autenticação solicitados |
| Pytest com PostgreSQL real | **103 aprovados, 1 ignorado**; apenas a variante SQLite da concorrência já documentada |
| Ruff | check e format --check aprovados |
| Frontend Vitest | **29 aprovados**, com Vitest 4.1.12 |
| ESLint | Aprovado |
| TypeScript | Build da aplicação e `test:e2e:tipos` aprovados |
| Vite build | Aprovado |
| Prettier | format:check aprovado |
| Auditoria npm de produção | `npm audit --omit=dev --json`: **zero avisos** |

Os E2E não substituem o servidor por respostas de sucesso simuladas. API e banco
são reais. Interceptação é usada somente para abortar conexão e para atrasar o
envio no teste de loading, continuando a requisição real depois do atraso.

### Cobertura no navegador

1. Cadastro inválido associa erro aos três campos e foca o primeiro, sem envio.
2. Cadastro válido e duplicado recebem 202 e mensagem idêntica, sem revelar existência
   da conta, criar sessão ou afirmar envio de e-mail. Campo de senha limpo depois.
3. Conta recém-cadastrada, credenciais incorretas e conta inexistente não entram;
   respostas permanecem genéricas e o navegador fica no login.
4. Fixture verificada faz login real; JSON contém apenas usuário público e CSRF,
   sem senha/hash/token de autenticação. Cache-Control no-store confirmado.
5. Cookie obtido no contexto Chromium confirma HttpOnly, host, Path, SameSite e
   prazo. Não há credenciais/CSRF em localStorage/sessionStorage; só tema é persistido.
6. Reload mantém sessão. Logout sem CSRF recebe 403; logout pela interface envia
   o cabeçalho e recebe 204. Cookie removido; replay do token em memória recebe 401.
7. Preflight de origem maliciosa rejeitado sem Access-Control-Allow-Origin;
   Chromium bloqueia leitura de fetch originado de documento em origem opaca.
8. Acesso privado sem sessão redireciona; links, histórico e retorno ao início funcionam.
9. Expiração provocada diretamente na sessão PostgreSQL remove o acesso e pede login.
10. Falha de conexão tem feedback sem exibir dados privados. Suspensão real das
    conexões de linkai_e2e e encerramento de seus backends provoca 503; restauração
    em finally permite confirmar a mesma sessão novamente.
11. Loading desabilita o envio e campos; rate limiting continua devolvendo 429.
12. Logs efetivos da API foram varridos: senha de fixture, URL com credencial,
    cookie e resumos/tokens não foram encontrados. Logs brutos ficam ignorados.

### UX, responsividade e evidências

Nas três larguras, cadastro, login e conta foram exercitados nos dois temas:
sem overflow horizontal, controles com altura mínima de 44 px, fonte de campos
de pelo menos 16 px e foco visível por navegação Tab entre e-mail e senha.
As telas preservam cabeçalho, tipografia, cartões, estados e espaçamentos existentes.
Sidebar/menu lateral não existem no escopo atual: marcados como não aplicáveis,
sem criar componentes de negócio novos. Navegação existente permanece funcional.

Foram produzidas **18 capturas** e resultados JSON, sem credenciais preenchidas,
cookies ou tokens. O e-mail da fixture na tela de conta foi mascarado. Foram
inspecionadas visualmente capturas representativas de celular, tablet e desktop.
O contraste do botão principal medido pelo Chromium ficou em **5,36:1** em todas
as combinações; o valor anterior observado era 3,65:1.

- [Índice das evidências](evidencias/fase3/README.md).
- [Resultados dos testes](evidencias/fase3/resultado-e2e.json).
- [Navegador e viewports](evidencias/fase3/ambiente-navegador.json).
- [Medições de contraste](evidencias/fase3/medidas-layout.json).

Traces, vídeos e storageState não foram gravados. O relator sanitiza erros e
grava somente nomes dos cenários, resultado e duração; artefatos temporários
Playwright são descartados. Os JSON não contêm cabeçalhos nem corpos de login.

### Problemas encontrados e correções

- **Contraste:** texto branco no botão esmeralda 600 teve 3,65:1. O botão reutilizável
  e o CTA passaram para esmeralda 700/hover 800, atingindo 5,36:1, sem redesenho.
- **Erro de banco e CORS:** o handler genérico de Exception era executado fora do
  CORS, então o navegador não conseguia ler o 503 de falha SQLAlchemy. Registrado
  também um handler específico para SQLAlchemyError, tratado no ExceptionMiddleware.
  Resposta passa pelo CORS normal; adicionado teste de regressão dos cabeçalhos.
  O E2E com banco indisponível passou depois da correção.
- **Teste de cookie:** a consulta inicial usou a raiz da API, fora de Path=/api.
  Corrigido somente o caminho de consulta do teste; política do cookie preservada.
- **Ferramentas de desenvolvimento:** npm reportou dois avisos críticos na cadeia
  Vitest/tinypool. Atualizados Vitest para 4.1.12 e typescript-eslint para 8.72.1,
  após confirmar compatibilidade com Node/Vite e reexecutar a regressão.
- **Coleta de testes:** Vitest agora inclui explicitamente src/testes/**/*.test.*,
  separando os specs Playwright da suíte DOM. E2E tem configuração TypeScript própria.
- Instalações, Chromium, API/Vite e execução E2E precisaram de execução autorizada
  fora do sandbox por restrições de rede/processos. Não houve contorno de permissões.

### Arquivos criados/modificados

Criados:

- `backend/testes/e2e/ambiente.py`: helper CLI exclusivo para banco E2E local,
  migração, fixture, expiração e suspensão/restauração de conexões.
- `frontend/playwright.config.ts`, `frontend/tsconfig.e2e.json`.
- `frontend/e2e/ambiente.ts`, `preparar.ts`, `autenticacao.spec.ts` e `relator.ts`.
- `docs/relatorios/evidencias/fase3/`: índice, capturas e JSON sanitizados.

Modificados:

- `backend/src/aplicacao/apresentacao/erros.py` e
  `backend/testes/integracao/teste_autenticacao.py`: correção/regressão de CORS no 503.
- `frontend/src/componentes/Botao.tsx` e `frontend/src/paginas/PaginaInicial.tsx`: contraste.
- `frontend/package.json` e `package-lock.json`: Playwright, ferramentas corrigidas e scripts.
- `frontend/vite.config.ts`, `eslint.config.js`, `.prettierignore` e `.gitignore`:
  separação das suítes e exclusão de artefatos temporários.
- `README.md` e este relatório: reprodução, ambiente, resultados e limites.

Nenhum endpoint foi alterado, nenhum mecanismo público de ativação foi criado
e não houve nova funcionalidade de negócio.

### Pendências e conclusão

Fase 3 **estável no ambiente local e nos cenários executados**, com correções
verificadas em navegador real e regressão aprovada. Não equivale a liberação
de produção ou certificação completa de segurança/acessibilidade.

- HTTPS real do deploy, Secure/SameSite em navegador sob TLS, cookies de terceiros,
  Firefox/WebKit e dispositivos físicos ainda precisam de homologação própria.
  Política de cookie de produção continua coberta pelos testes backend existentes.
- Rate limiting compartilhado antes de múltiplos processos, retenção/limpeza de
  sessões e configuração de proxies confiáveis permanecem pendentes.
- Auditoria completa npm ainda apresenta **sete avisos moderados** nas ferramentas
  de desenvolvimento, na cadeia minimatch/linter. Auditoria omitindo dev retornou
  zero. Não foi aplicado override incompatível nem audit fix --force.
- Permanece aviso Starlette/httpx no TestClient. Nenhuma falha de teste pendente.
- A medição de contraste cobre o botão principal e a inspeção visual dos temas;
  não foi realizada auditoria WCAG completa.
- Verificação de e-mail, Brevo e demais funcionalidades da Fase 4 não foram implementadas.

O README contém os comandos de preparação do banco exclusivo, instalação do
Chromium, variáveis e execução. O helper recusa hosts remotos ou banco diferente
de linkai_e2e e limpa os dados somente desse banco. A senha da fixture é gerada
em memória. A preparação restaura o banco caso um teste anterior tenha sido interrompido.
API/Vite foram encerrados pelo Playwright e o cluster isolado foi desligado após
a homologação; dados locais foram preservados. Produção não foi acessada.

Commit sugerido: `test: homologar fluxo de autenticacao`.
Nenhum commit, push ou deploy realizado. Não houve avanço para a Fase 4.
