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
