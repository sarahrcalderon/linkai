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
