# Fase 5 — Links personalizados

## Etapa 5.1 — Modelagem e persistência

Implementação restrita ao domínio, contrato, repositório PostgreSQL e migração.
Arquitetura existente analisada antes das alterações: entidades dataclass,
contratos Protocol, ORM na infraestrutura e transação externa que controla commit.
Nenhuma mudança nos fluxos de autenticação, verificação ou Brevo. Os arquivos
privados de credenciais e o banco da tentativa real de e-mail não foram alterados.

### Entidade e validações

`Link` é dataclass imutável, independente de SQLAlchemy/Pydantic. Datas usam UTC.

| Campo | Regra |
| --- | --- |
| id | UUID gerado por padrão |
| usuario_id | UUID obrigatório; FK para usuários |
| nome | Trim, 2–100 caracteres, sem caracteres Unicode de controle/formatação |
| slug | Trim/lowercase, 3–64 caracteres, segmentos ASCII alfanuméricos separados por hífen |
| numero_whatsapp | `+` seguido de 8–15 dígitos ASCII, primeiro diferente de zero |
| mensagem | Opcional, até 2000 caracteres; sem `<`/`>`; permite newline, CR e tab, recusa outros controles |
| ativo | Booleano, true por padrão |
| criado_em | Timestamp com fuso, normalizado para UTC |
| atualizado_em | Timestamp UTC, não anterior à criação |
| excluido_em | Opcional; exige inativo e criação ≤ exclusão ≤ atualização |

Número aceita entrada com ou sem `+`; remove espaços ASCII, parênteses, pontos e
hífens antes de validar. Não infere país de número nacional e não verifica se o
país/número existe ou possui WhatsApp. Chamadores devem fornecer código do país.
Não há dependência adicional de telefonia. Nome e mensagem são texto; a rejeição
de ângulos é uma política explícita para não aceitar marcação. Renderização futura
ainda deverá escapar texto e codificar parâmetros de URL corretamente.

Slugs reservados: api, admin, login, logout, cadastro, dashboard, verificar-email,
reenviar-codigo, static, assets, docs, redoc, openapi, saude e www. Lista refletida
na migração de forma estática: alterações futuras exigem nova revisão incremental.
Não converte acentos silenciosamente ou aceita caminho, ponto, espaços internos,
hífen inicial/final ou segmentos vazios. Datas de criação/atualização são obrigatórias.
Telefone e mensagem são omitidos do repr da entidade.

### Propriedade, disponibilidade e exclusão

Um usuário pode ter múltiplos links. Unicidade global de slug independe do
proprietário, atividade ou exclusão. `excluir()` produz uma nova entidade inativa
e é idempotente para entidade já excluída. Não há exclusão física no contrato.
`disponivel_para_redirecionamento` expressa apenas uma regra de domínio, sem
implementar serviço ou endpoint de redirecionamento.

`obter_por_id(id, usuario_id)` exige o proprietário e retorna None para outro
usuário; `atualizar(link)` bloqueia a linha e aplica o mesmo filtro. Ausência e
proprietário incorreto resultam no mesmo erro de domínio. Não permite troca de
slug, data original, proprietário ou reversão da exclusão; recusa atualização
com timestamp anterior ao persistido. A futura camada autenticada deverá obter
usuario_id da sessão, nunca confiar no identificador fornecido por cliente.

`obter_publico_por_slug` retorna somente link ativo e não excluído. O repositório
nunca usa esse filtro para decidir se um slug pode ser reutilizado: a constraint
global é a autoridade. A unicidade também protege a corrida entre usuários.

### Persistência e migração

ModeloLink mapeia tabela links. UUID PK, FK usuarios.id ON DELETE RESTRICT, UNIQUE
uq_links_slug, checks de limites, normalização, formatos e coerência temporal.
Índice ix_links_usuario_criado em usuario_id/criado_em; a restrição unique já
mantém índice de slug, evitando índice redundante. Datas são timestamptz.

0005_criar_links.py parte da revisão 0004, sem modificar revisões aplicadas.
Upgrade cria apenas links e seu índice; downgrade remove links. A reversão perde
links e deve ser precedida de backup em qualquer operação persistente real.
Os formatos regex são checks específicos de PostgreSQL; SQLite permanece apenas
na regressão legada e não serve para homologar a nova persistência.

RepositorioLinksSQLAlchemy faz flush, sem commit. Inserção usa savepoint para
traduzir exclusivamente uq_links_slug em SlugJaUtilizado e manter transação externa
utilizável após esse conflito. Outras violações propagam IntegrityError e exigem
rollback. Atualização usa bloqueio de linha e releitura, sem sobrescrever identidade.
RESTRICT evita apagar proprietário e liberar slug por cascata. Políticas futuras
de apagamento/anônimização de contas deverão preservar essa reserva.

### Arquivos desta etapa

Criados:

- backend/src/aplicacao/dominio/link.py.
- backend/src/aplicacao/dominio/repositorio_links.py.
- backend/src/aplicacao/infraestrutura/repositorio_links.py.
- backend/src/aplicacao/infraestrutura/migracoes/versions/0005_criar_links.py.
- backend/testes/unitarios/teste_link.py.
- backend/testes/integracao/teste_links.py.
- docs/relatorios/fase5-links-personalizados.md.

Modificados:

- backend/src/aplicacao/infraestrutura/modelos.py: adiciona ModeloLink.
- backend/testes/integracao/teste_migracao.py: nova revisão offline e tabela links.
- backend/testes/integracao/teste_postgres_migracao.py: head esperado 0005.
- backend/testes/e2e/ambiente.py: inclui links no TRUNCATE da fixture, necessário
  pela FK; não muda comportamento da API ou autenticação.
- README.md: estado e regras da 5.1.

Alterações anteriores da Fase 4 já presentes no workspace foram preservadas.

### Testes efetivamente executados

PostgreSQL **18.6**, cluster local 127.0.0.1:55432, banco exclusivo linkai_homologacao,
schemas aleatórios migrados de forma real e removidos após cada teste. Nenhum
acesso ao banco linkai_email_homologacao45 e nenhum envio real de e-mail.

- 44 novos casos unitários e 14 PostgreSQL de links: **58 novos testes**.
- Alvos iniciais domínio/migração local: 46 aprovados.
- Alvos PostgreSQL links/migração: 15 aprovados.
- Regressão completa `pytest -q`: **278 aprovados, 1 ignorado**, 1 aviso conhecido
  de depreciação Starlette/httpx. O ignorado é a variante SQLite de concorrência
  anterior; todos os novos testes de concorrência/transações usam PostgreSQL real.
- `ruff check .`: aprovado; `ruff format --check .`: 97 arquivos formatados.
- `git diff --check`: sem erros de whitespace.
- Preparação da fixture E2E executada no banco exclusivo linkai_e2e para validar
  migração e TRUNCATE relacionados. Frontend/navegador não foram alterados/testados.

Cluster PostgreSQL isolado encerrado ao concluir as validações; nenhum processo
de API, worker ou navegador foi iniciado nesta etapa.

Cobertura: normalização, campos e limites, slugs inválidos e reservados, número
inválido, datas, imutabilidade, exclusão lógica, dono único e múltiplos links,
recuperação, atualização por proprietário, recusa de troca de identidade/restauração,
slug indisponível quando inativo ou excluído, transação utilizável após conflito,
FK inexistente, RESTRICT, rollback e constraints por inserção direta no ORM.

Concorrência sincronizada em duas transações/conexões para dois proprietários:
um persistido, um SlugJaUtilizado; contagem final de links igual a um.
Migração **0005 → 0004 → 0005** remove/recria links preservando usuários.
Teste completo de migrações compara o metadata ORM com PostgreSQL após upgrade.

### Execução e pendências para 5.2

Em backend, com ambiente de desenvolvimento instalado e URL_BANCO_TESTE apontando
somente para PostgreSQL dedicado:

```bash
python -m pytest -q
ruff check .
ruff format --check .
python -m pytest testes/unitarios/teste_link.py testes/integracao/teste_links.py -q
```

Para aplicar a nova revisão em ambiente local aprovado, confirme antes URL_BANCO
e execute `alembic upgrade head`. A implementação foi homologada por migrações
nos schemas de teste, sem migrar o banco da tentativa real de e-mail.

5.2 deve definir seus casos de uso/contratos autenticados, paginação/ordenação e
políticas de edição conforme aprovação. Alterações de slug ou remoção física
exigirão decisão explícita sobre reserva permanente; hoje são recusadas pelo
repositório. Autorização autenticada, quotas e políticas de sessão pertencem às
camadas futuras; o contrato de persistência não substitui essas verificações.
Não há endpoint, tela, analytics ou redirecionamento implementado nesta etapa.

Nenhuma credencial alterada, dependência adicionada, chamada Brevo, commit, push
ou deploy. Etapa 5.2 não iniciada; aguarda aprovação do usuário.

## Etapa 5.2 — API de gerenciamento de links personalizados

Implementação restrita a gerenciamento autenticado. Entidade/validações da 5.1
reutilizadas via criação/replace no caso de uso; rotas não contêm regras de link.
Aplicação define DTOs estritos e saídas explícitas, coordena casos de uso e usa o
contrato de repositório. Apresentação valida HTTP/sessão/CSRF e traduz exceções.
Infraestrutura mantém SQL, savepoints, filtros de propriedade e bloqueios.

### Endpoints e contratos

| Método/rota | Sucesso | Entrada |
| --- | --- | --- |
| POST /api/links | 201 | nome, slug, numero_whatsapp, mensagem opcional |
| GET /api/links | 200 | pagina=1, tamanho=20 na query |
| GET /api/links/{id} | 200 | UUID |
| PATCH /api/links/{id} | 200 | Campos alteráveis presentes |
| DELETE /api/links/{id} | 204 sem corpo | UUID |

Exemplo de corpo de criação, sem campos de propriedade:

```json
{
  "nome": "Campanha",
  "slug": "campanha",
  "numero_whatsapp": "+5511999999999",
  "mensagem": "Olá! Quero saber mais."
}
```

DTO LinkSaida explicita id, nome, slug, numero_whatsapp, mensagem, ativo, criado_em
e atualizado_em. Não expõe proprietário, exclusão interna, sessão, hash ou estado
de persistência. Datas são timestamps com fuso, UUID é string na representação JSON.
Todos os DTOs de entrada rejeitam campos extras, tipos incompatíveis e administrativos.

Listagem retorna `{itens, total, pagina, tamanho}`. Página entre 1 e 1000000;
tamanho entre 1 e 100, padrão 20. Filtros obrigatórios: proprietário da sessão e
excluido_em IS NULL. Inclui links inativos para gerenciamento. Ordem determinística
criado_em DESC, id DESC. Usa offset/limit: inserções/exclusões entre páginas podem
deslocar itens; não é um snapshot consistente entre requisições. Total e itens são
consultados na mesma transação READ COMMITTED, sem prometer snapshot entre statements.

PATCH permite nome, slug, numero_whatsapp, mensagem e ativo. exclude_unset preserva
campos ausentes; mensagem=null limpa, demais campos não aceitam null; objeto vazio
é 422. Ativo deve ser booleano real. Data de atualização vem do servidor. Leitura
sob bloqueio antecede a composição da alteração, evitando perder campos de outro
PATCH concorrente. Não aceita usuario_id, id, datas nem excluido_em.

DELETE marca inativo/excluido_em e conserva o registro/slug. Depois, detalhe,
PATCH e DELETE retornam 404, e o item não participa da listagem. O repositório
também recusa trocar slug de registro excluído, protegendo a reserva terminal.

### Alteração explícita da decisão de slug da 5.1

A 5.2 autoriza PATCH de slug; foi removida a proibição anterior de editar slug
de link não excluído. Normalização, reservados, formato e unicidade continuam
valendo; conflito de inserção ou atualização gera SlugJaUtilizado/409 via savepoint.
O teste anterior de identidade passou a verificar imutabilidade da data de criação.

**Ao renomear, o slug antigo fica livre.** Não há tabela de aliases/histórico.
Essa liberação difere de exclusão: o slug vigente de link excluído continua reservado.
Antes de publicar redirecionamento, confirmar a política de antigos endereços,
pois terceiros poderão escolher um slug liberado por renomeação. Nenhum redirect
ou alias foi implementado nesta etapa e não foi necessária nova migração.

### Autenticação, autorização e transação

Reutilizados ConsultarAutenticado, ler_token, validar_origem e TokensSeguros:
sessão existente, não expirada/revogada, usuário ativo e e-mail verificado. Não foi
adicionado token alternativo, novo cookie ou atalho de verificação/login.
O proprietário é obtido exclusivamente desse resultado, nunca do corpo/query.
Todas as consultas e escritas privadas filtram id e usuario_id. Recurso ausente,
excluído e de outro proprietário têm a mesma resposta 404, sem consulta global
para decidir mensagens e sem revelar existência.

POST/PATCH/DELETE exigem Origin configurado e X-CSRF-Token válido com comparação
segura existente. Leituras não exigem CSRF. Cookies/contratos de autenticação são
preservados. A adaptação mínima de CORS acrescenta métodos PATCH/DELETE à lista
permitida para que o navegador consiga executar os novos endpoints; origens e
cabeçalhos explícitos não foram ampliados.

Dependências reutilizam a mesma transação com escopo function e commit antes da
resposta. Falha adiada até COMMIT reverte e retorna 503, sem 201 antecipado.
Atualizações/exclusões bloqueiam a linha; savepoint trata conflitos de slug sem
persistir alterações parciais. O caso de uso não faz commit e as rotas não usam SQL.

ProtecaoCorpoLinks limita POST/PATCH/DELETE a **16384 bytes reais**, sem depender
de Content-Length e inclusive em chunks. Nenhum corpo/token é registrado.
Cache-Control no-store em respostas de sucesso e erros. Sem novas dependências.

### Respostas de erro

| Status | Código |
| --- | --- |
| 401 | sessao_invalida |
| 403 | csrf_invalido |
| 404 | link_nao_encontrado |
| 409 | slug_indisponivel |
| 413 | corpo_excedido |
| 422 | dados_invalidos |
| 503 | servico_indisponivel |

Envelope `{erro: {codigo, mensagem}}`; erros de estrutura/tipos podem incluir
campos conhecidos com mensagens sanitizadas. Validação semântica do domínio usa
mensagem genérica, sem refletir input, nomes administrativos, dados SQL ou valores.
Validações de sessão e payload seguem o pipeline FastAPI existente; não se promete
precedência 401 para todo payload malformado ou corpo que exceda o limite.

### Arquivos desta etapa

Criados:

- backend/src/aplicacao/casos_de_uso/gerenciar_links.py: DTOs/casos de uso.
- backend/src/aplicacao/apresentacao/rotas/links.py: rotas/composição e sessão/CSRF.
- backend/src/aplicacao/apresentacao/protecao_links.py: limite de corpo.
- backend/testes/unitarios/teste_gerenciar_links.py.
- backend/testes/integracao/teste_api_links.py.

Modificados:

- dominio/repositorio_links.py: consulta com bloqueio e listagem paginada.
- infraestrutura/repositorio_links.py: paginação, alteração de slug e conflito na atualização.
- apresentacao/erros.py: erros de links e validação HTTP contextualizada.
- principal.py: registro das rotas/middleware e métodos CORS necessários.
- testes/integracao/teste_links.py: decisão de slug editável e reserva após exclusão.
- README.md e este relatório.

Nenhum arquivo de credenciais, código Brevo, migração aplicada ou frontend alterado
nesta etapa. Alterações anteriores já existentes no workspace foram preservadas.

### Validação, limitações e Etapa 5.3

Testes novos cobrem criação, rejeição de campos administrativos/tipos/dados, DTOs,
propriedade, listagem/paginação, UUID inválido, consulta, PATCH parcial, null,
ativação/desativação, exclusão, não autenticado, IDOR em leitura/escrita/exclusão,
CSRF ausente/inválido, Origin hostil, tamanho em chunks, concorrência de slug,
conflito em PATCH, PATCH concorrente em campos distintos, CORS e rollback no commit.
Fixtures usam usuários verificados/sessões gerados somente em schemas de teste;
nenhum envio ou verificação pública foi necessário para criar essas fixtures.

PostgreSQL 18.6 local isolado, banco linkai_homologacao, schemas aleatórios migrados
até 0005 e removidos após os testes. O banco da tentativa real Brevo não foi acessado.
Testes de concorrência/transação não usam mocks para comprovar integridade.
Os unitários usam AsyncMock somente para validar coordenação e contratos da aplicação.

Resultados efetivamente executados:

- Testes direcionados iniciais de API e repositório PostgreSQL: 34 aprovados.
- Novos unitários da aplicação: 10 aprovados.
- Regressão completa final: **309 aprovados, 1 ignorado**, 1 aviso conhecido
  Starlette/httpx, em PostgreSQL real. Foram adicionados 31 casos (21 integração,
  10 unitários); o ignorado continua a variante SQLite de concorrência legada.
- Ruff check: aprovado; Ruff format --check: 102 arquivos formatados.
- git diff --check: sem erros de whitespace.

Problemas resolvidos: decisão anterior de slug imutável adaptada ao PATCH autorizado;
proteção do slug terminal reforçada; bloqueio antecipado evita perda de campos em
PATCH concorrente; CORS agora permite preflight dos métodos novos. Teste de trigger
adiado até commit confirmou 503 e zero links persistidos após falha, sem 201 falso.
Imports/formatação iniciais ajustados ao padrão Ruff. Nenhuma falha de teste restante.
PostgreSQL isolado encerrado ao concluir; nenhum worker ou servidor público iniciado.

Sem interface React, redirect /r/{slug}, analytics, quotas ou serviços pagos.
Paginação por cursor, histórico de slugs e políticas de quotas ficam sujeitos a
decisão posterior; não são garantias implícitas desta implementação.
Frontend/E2E navegador não executados nesta etapa, pois não houve alteração de UI.
Etapa 5.3 não iniciada. Para testar: em backend, com URL_BANCO_TESTE no PostgreSQL
dedicado, execute pytest, ruff check . e ruff format --check . conforme seção 5.1.
Uso manual exige login existente de usuário verificado em ambiente local e cookie
de sessão/CSRF obtidos pelo contrato de autenticação, sem inserir tokens no código.

Nenhum commit, push, deploy, chamada Brevo ou avanço de fase. Aguarda aprovação.
