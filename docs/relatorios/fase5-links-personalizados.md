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

## Etapa 5.3 — Redirecionamento público para WhatsApp

Analisados roteamento FastAPI, navegação customizada React, Vite e repositório da
5.1. A raiz FastAPI recebe `/r/{slug}`, separada de `/api/links` autenticada. No
frontend não há página ou rota React nova. O middleware Vite encaminha a requisição
antes de ela chegar ao fallback SPA. Não foram modificados autenticação ou Brevo.

### Arquitetura e comportamento

ObterDestinoWhatsApp valida o tamanho bruto (até 64 caracteres) e aplica
normalizar_slug do domínio antes de qualquer consulta. Valores inválidos e
reservados viram LinkNaoEncontrado/404, com mensagem neutra. Consulta apenas
obter_publico_por_slug existente, sem buscar usuário, sessão ou contar cliques.
Revalida disponibilidade no caso de uso por defesa. Rota usa a transação existente
somente como unidade de trabalho, sem dependência de autenticação ou CSRF.

Link ativo não excluído gera 302 e corpo vazio. Ausente, inativo, excluído ou slug
inválido usam o mesmo envelope 404/no-store; indisponibilidade gera o 503 neutro
existente, também no-store. O parâmetro path permite tratar barras codificadas
inválidas e slug vazio com o mesmo 404, sem consultas ou traceback; apenas o formato
canônico de slug é aceito pelo domínio. URI pública documentada continua /r/{slug}.
Leitura não atualiza datas ou registros e não exige usuário verificado do visitante.

Destino é construído exclusivamente como `https://wa.me/` + dígitos do número
normalizado da entidade, removendo somente o `+`. Mensagem não vazia é codificada
por urllib.parse.quote com safe vazio e UTF-8, em um único parâmetro text. Mensagem
null/vazia omite a query; mensagem só de espaços é preservada. Não usa URL enviada
pelo cliente, Host da requisição ou parâmetro arbitrário para construir o destino.

Exemplos fictícios:

| Mensagem | Location |
| --- | --- |
| ausente | https://wa.me/5511999999999 |
| Olá mundo | https://wa.me/5511999999999?text=Ol%C3%A1%20mundo |
| Linha 1 + quebra + Linha 2 | https://wa.me/5511999999999?text=Linha%201%0ALinha%202 |

Emojis são preservados em percent-encoding UTF-8. Ampersand, interrogação, igual,
fragmentos e CR/LF da mensagem são codificados, sem criar parâmetros ou cabeçalhos.
A aplicação não segue o redirecionamento e não chama WhatsApp. Novo slug segue a
regra 5.2: antigo para de resolver, mas pode resolver novo link se for reutilizado.
Slugs vigentes continuam únicos globalmente, inclusive quando excluídos.

### Segurança e privacidade

302: Cache-Control no-store, max-age=0; Referrer-Policy no-referrer e
X-Content-Type-Options nosniff. Sem Set-Cookie, scripts, rastreadores ou analytics.
Nenhum dado de proprietário é retornado. Detalhes internos de falha são ocultados.
Número e mensagem são intencionalmente públicos na URL/Location, incluindo para
quem conhece o slug. Percent-encoding não é criptografia ou anonimização.
Navegador e WhatsApp podem manter a URL em seus históricos; não usar segredos no texto.

Nenhum logger do fluxo escreve número, mensagem, entidade ou Location. SQL usa
hide_parameters já existente. Logs de infraestrutura devem evitar capturar
Location, query strings e payloads; cliente pode inserir dados arbitrários em
uma query, mesmo que ela seja ignorada no destino. Para homologação, iniciar
Uvicorn com --no-access-log; no gateway, desabilitar access log de /r/ ou usar
política revisada sem query/headers sensíveis. Não foi adicionada configuração
global de logging que altere os fluxos de autenticação.

### Roteamento local e futuro deploy

Vite lê VITE_URL_API do ambiente/processo ou .env do frontend, com fallback local
http://localhost:8000. Proxy apenas para prefixo /r/, changeOrigin=true,
followRedirects=false, preservando caminho, status e Location. Valor deve ser o
origin do backend, sem /api no final e sem credenciais. Pode ser qualquer origin
aprovado, não uma constante dependente de localhost. Nenhum segredo vai ao frontend.

Em desenvolvimento, backend na porta configurada e npm run dev no frontend;
abrir diretamente http://localhost:5173/r/campanha com fixture de link ativa.
Usar âncora normal/navegação do navegador, não LinkInterno/History API, que apenas
mudaria a página React sem fazer a navegação pública de rede.

Em produção, o bundle estático não inclui o proxy Vite. Duas estratégias válidas:

1. Domínio público/gateway comum: rotear /r/ para FastAPI antes de try_files/index.html.
2. Frontend em domínio estático e API em outro: compartilhar /r/ no domínio do
   backend, ou configurar proxy/edge explícito no domínio público de links.

Exemplo ilustrativo Nginx, não aplicado/deployado, com upstream definido pelo operador:

```nginx
location ^~ /r/ {
    proxy_pass http://linkai_backend;
    proxy_cache off;
    access_log off;
}
location / {
    try_files $uri $uri/ /index.html;
}
```

proxy_pass sem barra final preserva /r/. Não transformar upstream 404 em SPA, não
seguir Location no gateway e não forçar cache de 302/404/503. TLS/origins e proxy
confiável devem seguir a configuração do ambiente; nenhuma publicação foi feita.
Hostings somente estáticos sem proxy devem usar domínio/API público separado.
vite preview não substitui essa configuração de produção.

### Arquivos criados e modificados

Criados:

- backend/src/aplicacao/casos_de_uso/obter_destino_whatsapp.py.
- backend/src/aplicacao/apresentacao/rotas/redirecionamento.py.
- backend/testes/unitarios/teste_destino_whatsapp.py.
- backend/testes/integracao/teste_redirecionamento.py.

Modificados: backend/src/aplicacao/principal.py (registro na raiz),
frontend/vite.config.ts (proxy mínimo), README.md e este relatório.
Sem nova migração, dependência, mudança de modelo, API de gerenciamento,
autenticação, arquivo de credenciais ou código Brevo.

### Validação efetivamente executada

Testes unitários cobrem host fixo, número internacional, codificação de espaços,
acentos/UTF-8, emojis, CR/LF, caracteres de query/fragmento, ausência de mensagem,
slug reservado/inválido e ausência de consulta nesses casos.
Integração PostgreSQL cobre 302/Location/cache/corpo vazio, sem sessão/CSRF,
links inativos/excluídos/ausentes, path inválido sem SQL, tentativa de destino
arbitrário ignorada, renomeação/reutilização e 503 sem revelar erro interno.
Caplog verifica ausência do número e texto nas mensagens da aplicação.

O proxy foi testado de fato com servidor Vite e backend HTTP falso locais em
portas dinâmicas: /r/campanha gerou exatamente uma chamada ao backend e manteve
302/Location/no-store; /login continuou 200 HTML da SPA sem chamada ao backend.
Fetch usou redirect manual. Servidores fechados ao terminar. Nenhuma requisição
a WhatsApp, Brevo ou serviço externo, inclusive durante testes.

Frontend: 46 testes Vitest aprovados, ESLint, Prettier e TypeScript/build aprovados.
Sem alteração de UI; Chromium/E2E de navegador não executados nesta etapa.
PostgreSQL 18.6 isolado, linkai_homologacao, schemas migrados até 0005 e descartados.
Banco da tentativa real de e-mail e outbox anterior não acessados.

Resultados finais: **348 testes backend aprovados, 1 ignorado**, com o aviso
Starlette/httpx já existente. São 39 novos casos (16 unitários e 23 integração).
O ignorado continua a variante SQLite legada de concorrência; as novas validações
transacionais usam PostgreSQL real. Ruff check e format --check aprovados, com
106 arquivos formatados; git diff --check sem erros. Testes direcionados iniciais
de redirecionamento: 35 aprovados antes dos quatro casos adicionais de caminhos/falha.
Formatação inicial corrigida conforme Ruff/Prettier. Nenhuma regressão identificada.
PostgreSQL isolado encerrado ao final; nenhum worker ou processo de servidor ficou ativo.

### Pendências para 5.4

Configurar/validar o domínio público e gateway em infraestrutura aprovada quando
houver autorização de deploy; confirmar logs e regras de cache do provedor real.
Nenhum teste aqui comprova abertura/entrega de mensagem pelo aplicativo WhatsApp:
somente a URL e o redirecionamento HTTP foram homologados.
Interface de gerenciamento, analytics, políticas de slugs antigos e outras fases
não foram implementados. URLs de links devem usar o origin público escolhido,
sem assumir domínio único para frontend/backend.
Etapa 5.4 aguarda aprovação; sem commits, pushes ou deploys.

## Etapa 5.4 — Dashboard de gerenciamento de links

Frontend existente analisado: página privada /dashboard, navegação customizada,
gerenciador de sessão com CSRF em memória, cliente HTTP central, componentes
Botao/CampoTexto/Feedback/Cabecalho e temas por data-tema. Esses padrões foram
reutilizados, sem reconstrução do projeto ou nova biblioteca. Backend e integração
Brevo não foram modificados nesta etapa; alterações anteriores no workspace preservadas.

### Interface e responsabilidades

PaginaDashboard conserva saudação, controles de sessão/logout e layout do Design
System, substituindo o placeholder por MeusLinks. Listagem em cartões, uma coluna
no celular e duas no desktop, mostra nome, URL pública completa quebrável e estado.
Ações explícitas, sem menu escondido: copiar, abrir, editar, ativar/desativar e
excluir. Sem indicadores de cliques ou métricas inventadas.

servico.ts contém tipos de contratos e validação de respostas; usarLinks coordena
carregamento/páginas/erros e descarta resultados de leituras antigas após mudança
ou unmount. FormularioLink controla validação/estado, DTO parcial e dirty state;
MeusLinks coordena ações/diálogos e atualiza a listagem após mutações confirmadas.
Dialogo é componente reutilizável com HTML dialog nativo e foco contido por Tab.

### Fluxos implementados

- Lista: GET /api/links?pagina=N&tamanho=10, com paginação anterior/próxima,
  loading, erro e tentar novamente. Página vazia após exclusão volta para a última
  página válida; criação retorna à primeira página. Estado vazio orienta Criar link.
- Criar: formulário com labels, nome interno, slug, WhatsApp e mensagem opcional.
  Validação de tamanho/formato, nomes reservados, telefone internacional e texto
  sem marcação; backend continua autoridade. Contador da mensagem, orientação de
  código do país e prévia da URL com aviso de confirmação ao salvar.
- Editar: GET /api/links/{id} antes de abrir; PATCH somente das diferenças.
  Mensagem vazia vira null, campo inalterado não é enviado. Ativo é booleano real.
  Aviso exato ao mudar slug: “O endereço anterior deixará de funcionar e poderá
  ser utilizado novamente.”
- Ativar/desativar: PATCH mínimo com ativo; mutex síncrono impede duplicação.
- Excluir: diálogo confirma efeito, exclusão lógica, reserva do slug vigente e
  ausência de desfazer. Cancelar/Escape não excluem; somente Confirmar exclusão
  chama DELETE. Erro permanece no diálogo, com anúncio/foco e possibilidade de tentar.
- Copiar: Clipboard API com feedback anunciado/focado; falha orienta seleção e
  cópia manual da URL visível. Abrir usa âncora normal em nova aba com noopener
  noreferrer; link inativo não oferece abertura habilitada.
- Sucesso: feedback acessível e recarga da lista somente após resposta contratada.
  Não repete mutação automaticamente se a atualização da listagem falhar.

### Sessão e integração

Reutilizado requisitar: credentials include, no-store e timeout. Escritas enviam
X-CSRF-Token; Origin é controlado pelo navegador e deve estar permitido na API.
O gerenciador mantém CSRF privado em memória. Foi adicionada somente a operação
executarAutenticado(callback), exposta pelo hook existente, para usar esse valor
sem criar outra fonte de sessão ou persistir tokens. Trata 401 limpando estado e
mensagem de expiração; guarda versão para resposta antiga não limpar um login novo.
Login, logout, cookies, rotas privadas e contratos backend não foram alterados.

Nenhum usuario_id/id/datas administrativos são enviados em criação. Serviço valida
status esperados (201/200/204) e respostas explícitas; 409 informa slug indisponível.
401 retorna ao login, 403 orienta revalidar, falha de rede não simula sucesso.
Não há armazenamento de sessão/CSRF em localStorage/sessionStorage; somente tema
continua persistido pelo mecanismo existente.

### URL pública, segurança e alterações não salvas

VITE_URL_PUBLICA_LINKS opcional define o origin público que atende /r/; fallback
é window.location.origin, correto no Vite com proxy da 5.3. Somente HTTP/HTTPS sem
credenciais embutidas; caminho fixo /r/ com slug codificado. Configuração é pública
e não deve receber segredo. Deploy separado exige origin apropriado, não implica
que /r/ esteja servido pelo domínio do frontend estático.

Telefone/texto aparecem somente no formulário autorizado; renderização React usa
texto, sem HTML injetado. O aviso lembra que serão visíveis no destino público.
Nenhum fetch externo, pré-abertura ou pré-carregamento do WhatsApp. E2E não clica
âncora Abrir nem navega para serviços externos. Cópia usa somente URL pública.

Cancelar/Escape com dados alterados abre confirmação inline de descarte no próprio
diálogo; sem alterações fecha diretamente. Clique fora não descarta; durante envio
não há fechamento por Escape/cancelar. beforeunload protege saída/recarga quando
o navegador permitir. Não usa alert()/confirm() como solução principal.
O guard de beforeunload não é um bloqueador geral de toda navegação History API;
rotas de formulário não foram criadas, e a navegação atrás do modal fica inerte.

### Acessibilidade, responsividade e temas

Diálogo nomeado por aria-labelledby, foco inicial em controle, contenção explícita
do primeiro/último controle para Tab/Shift+Tab, Escape tratado, retorno ao acionador.
Erros por campo usam aria-invalid/aria-describedby e foco no primeiro inválido;
Feedback usa alert/status e foco quando aplicável. Estado busy e desabilitação
impedem cliques/submit repetidos. Exclusão inicia no botão Cancelar.

320, 375, 768, 1024 e 1440 px, altura 900, temas claro e escuro: dez combinações
verificadas no Chromium. Sem overflow no documento e nos diálogos, URLs longas
quebram sem expandir cartões; formulários têm scroll vertical interno e ficam
dentro da viewport. Campos ≥16 px e botões ≥44 px. Não foram criadas métricas,
menus ou barras laterais adicionais.

Contrastes medidos no formulário/validação: texto 17,04:1 claro e 18,40:1 escuro;
botão 5,36:1; erro 4,56:1 claro e 6,98:1 escuro. Todos os elementos medidos
superaram 4,5:1; não se declara auditoria WCAG completa ou leitor de tela real.
Capturas mobile claro e formulário escuro foram também inspecionadas visualmente.

### Arquivos criados e modificados nesta etapa

Criados:

- frontend/src/componentes/Dialogo.tsx.
- frontend/src/funcionalidades/links/servico.ts.
- frontend/src/funcionalidades/links/usarLinks.ts.
- frontend/src/funcionalidades/links/FormularioLink.tsx.
- frontend/src/funcionalidades/links/MeusLinks.tsx.
- frontend/src/testes/Links.test.tsx.
- frontend/e2e/links.spec.ts.
- Evidências em docs/relatorios/evidencias/fase5/dashboard5.4.

Modificados: PaginaDashboard.tsx, gerenciador.ts/usarAutenticacao.ts para a operação
encapsulada, .env.exemplo do frontend (somente configuração pública opcional),
Autenticacao.test.tsx para responder lista vazia simulada sem interferir nos testes
de sessão anteriores, README.md e este relatório. Nenhum arquivo privado alterado.

### Testes efetivamente executados

| Verificação | Resultado |
| --- | --- |
| npm run test | 62 aprovados: 46 anteriores e 16 novos cenários |
| npm run lint | Aprovado |
| npm run test:e2e:tipos | Aprovado |
| npm run build | TypeScript e Vite aprovados |
| npm run format:check | Aprovado |
| npm run test:e2e | 17 aprovados no Chromium real, incluindo 3 novos |

Novos unitários/integrados de DOM usam fetch simulado para lista, vazio, criação,
validação/foco, 409, PATCH mínimo/limpeza null, aviso/dirty state, estado ativo,
exclusão/cancelamento, clipboard/falha, sessão expirada, rede/retry, paginação,
envio duplicado, diálogo/Escape e temas. Polyfill de dialog no JSDOM não comprova
focus trap nativo; essa verificação foi feita de fato no Chromium.

Novos E2E: CRUD de interface com API simulada e assert de CSRF, contenção de
Tab/Escape/descarte e layouts/contrastes nos dez cenários. O primeiro ensaio de
teclado falhou ao usar só o comportamento nativo no Shift+Tab; adicionada contenção
explícita e a suíte completa repetida com 17 aprovações. Os 14 E2E anteriores
continuam verificando autenticação real em PostgreSQL e verificação de interface.
CRUD de links com backend real via navegador ainda não foi homologado nesta etapa.

Playwright iniciou API/Vite locais; PostgreSQL 18.6 exclusivo linkai_e2e, sem contas
ou dados de produção. Nenhum worker, conta real de e-mail, chave Brevo ou serviço
externo foi usado. Backend não foi alterado e pytest/Ruff não foram repetidos;
os 348/1 da 5.3 são histórico anterior, não execução desta etapa.
Build inicial bloqueado pelo sandbox/esbuild, repetido fora do sandbox com aprovação.
Sem novas dependências ou migrações.
API/Vite encerrados pelo Playwright e PostgreSQL isolado encerrado ao final.

Evidências sem credenciais/códigos de verificação, com campos de fixture mascarados:

- [Resultado E2E](evidencias/fase5/dashboard5.4/resultado-e2e.json).
- [Medições](evidencias/fase5/dashboard5.4/dashboard-layout.json).
- [Lista mobile claro](evidencias/fase5/dashboard5.4/lista-320-claro.png).
- [Formulário mobile escuro](evidencias/fase5/dashboard5.4/formulario-375-escuro.png).
- [Validação desktop claro](evidencias/fase5/dashboard5.4/validacao-1440-claro.png).

### Execução local e pendências para 5.5

API configurada/migrada conforme 5.2 e frontend com VITE_URL_API para seu origin;
configure VITE_URL_PUBLICA_LINKS somente se o domínio público diferir. Em frontend,
npm install e npm run dev; faça login com usuário verificado do ambiente local e
abra /dashboard. Para regressão isolada, use os comandos da tabela e as variáveis
URL_BANCO_E2E/PLAYWRIGHT_BROWSERS_PATH já documentadas nas homologações anteriores.
Não iniciar worker nem enviar e-mails para criar fixtures.

Pendências: homologação do novo CRUD de UI contra backend real no navegador,
leitores de tela/dispositivos físicos/outros navegadores, revisão do domínio público
e política de navegação com alterações não salvas antes de ampliar as rotas.
Sem dashboard de analytics ou contagem de cliques. Abertura real de WhatsApp e
entrega de e-mail permanecem fora da validação. Etapa 5.5 não iniciada.
Sem commits, pushes ou deploys; aguarda aprovação do usuário.

## Etapa 5.5 — Homologação integrada com backend real

Homologação restrita ao ambiente local. Inspecionados README, relatórios,
configurações Playwright/Vite, rotas/serviços, migrações até 0005 e fixture de
autenticação. Não foram usados credenciais Brevo, contas reais, produção ou
chamadas externas. Nenhuma nova funcionalidade de negócio ou dependência.

### Ambiente e isolamento

- PostgreSQL 18.6 em 127.0.0.1:55432. E2E usa exclusivamente linkai_e2e;
  regressão pytest usa linkai_homologacao com schemas temporários. Nenhum acesso
  ao banco da tentativa de e-mail linkai_email_homologacao45 ou a desenvolvimento/produção.
- FastAPI real em 127.0.0.1:18000; React/Vite real em 127.0.0.1:15173;
  Chromium 158.0.8127.18. As duas suítes E2E usam portas iguais, sequencialmente,
  reiniciando a API para evitar interferência dos limites sem relaxar proteções.
- Fixture local existente aplica migrações e limpa somente o banco linkai_e2e,
  protegido por checagem de host/nome. A suíte real cria duas contas fictícias
  verificadas por script de teste; senha aleatória por execução, hash Argon2id.
  Não há endpoint/bypass de verificação adicionado à aplicação.
- Login pela interface real em ambas as contas, com cookie HttpOnly, SameSite=Lax
  e path=/api, Secure=false apenas no HTTP local. Origin explícito local;
  CSRF normal da sessão. Segredos HMAC/Fernet de teste em memória, sem Brevo.
- APIs, modelos, domínio, CORS, rate limiting e integração Brevo não alterados.
  Arquivos privados de credenciais não modificados.

### Estratégia de teste real e evidência SQL

Nova configuração playwright.integrado.config.ts reutiliza o harness existente,
seleciona só links-reais.spec.ts e usa preparação própria para a segunda conta.
A configuração anterior ignora esse arquivo e continua executando os 17 cenários
antigos. Não executar em paralelo: cada preparação limpa dados exclusivamente fictícios.

GET/POST/PATCH/DELETE de negócio não têm respostas simuladas na suíte real.
O navegador faz login e usa o serviço real. Helper consultar_link.py abre
transação PostgreSQL READ ONLY, checa registros por UUID e devolve somente
booleans de correspondência de campos/exclusão, sem imprimir telefone, mensagem,
senha, cookies ou tokens. Também consulta versão do servidor/revisão Alembic.

Asserções SQL independentes ocorreram após criação, edição de nome/slug/número/
texto, limpeza null, desativação, reativação, cancelamento de exclusão e exclusão.
Confirmam registro persistido, não apenas estado React ou resposta HTTP otimista.
Consulta real confirmou PostgreSQL 18.6 e revisão 0005.

As duas únicas intervenções de rede na suíte real foram atraso com route.continue
para observar loading e route.abort para simular desconexão. Não substituem
respostas de negócio. Após liberar/remover a intervenção, a resposta e a recuperação
vieram do backend real. Atraso/falha de rede são explicitamente simulações.
As requisições públicas /r/ usam maxRedirects=0, incluindo contexto anônimo sem
cookies; somente status/Location são inspecionados, nunca WhatsApp.

### Cenários e classificação final

| Cenário | Status | Evidência realmente executada |
| --- | --- | --- |
| Login autorizado | APROVADO | Interface real, contas fictícias e senha da fixture |
| Persistência após reload/dashboard | APROVADO | Cookie existente e /me/links reais após recarga |
| Não autenticado em rota privada | APROVADO | Retorno ao login após sessão expirada/acesso a dashboard |
| Revalidação de sessão | APROVADO | Botão Atualizar sessão, /me real; não promete extensão do prazo |
| Cookie HttpOnly/CSRF | APROVADO | Atributos do cookie, invisibilidade a document.cookie, escritas reais |
| CSRF ausente/inválido | APROVADO | PATCH real retorna 403 sem mutação |
| Origin inválido | APROVADO | Requisição local com Origin hostil retorna 403 |
| Criação e exibição | APROVADO | Formulário, POST 201, cartão e consulta SQL |
| Slug duplicado | APROVADO | POST real recusado, erro próximo ao slug no formulário |
| Listagem/paginação/ordem | APROVADO | 11 links reais, páginas 1/2 e sequência de IDs do backend |
| Isolamento entre usuários/IDOR | APROVADO | Segundo login, lista vazia e GET/PATCH/DELETE alheios retornam 404 |
| Editar nome/slug/número/mensagem | APROVADO | PATCH pela interface e valores comparados via SQL |
| Limpar mensagem | APROVADO | Campo apagado, null no PostgreSQL e Location sem text |
| Desativar/reativar | APROVADO | Interface, SQL e 404 público quando inativo |
| Cancelar exclusão | APROVADO | Diálogo cancelado; SQL sem exclusão |
| Exclusão lógica/reserva do slug | APROVADO | Sai da lista, linha inativa/excluída e novo POST do slug retorna 409 |
| 302 público e domínio fixo | APROVADO | Vite → FastAPI reais, Location https://wa.me, maxRedirects=0 |
| Texto UTF-8/emoji/quebra/espaços | APROVADO | Decodificação de Location corresponde à mensagem persistida |
| Sem autenticação no redirect | APROVADO | Contexto anônimo recebe 302 do link ativo |
| Inativo/excluído/inexistente | APROVADO | 404 no endpoint público, sem Location/cookie |
| Renomeação | APROVADO | Endereço antigo 404 e novo 302 |
| Payload administrativo inválido | APROVADO | POST real com usuario_id recebe 422 sanitizado |
| Sessão expirada | APROVADO | Fixture expira sessões, /me retorna ao login e bloqueia dashboard |
| Logs sem credenciais | APROVADO | Assert de ausência da senha, CSRF e valores de cookies nos logs locais |
| Copiar URL | APROVADO | Clipboard real no Chromium, sem abrir destino |
| Diálogo/teclado/foco | APROVADO | Tab/Shift+Tab contidos, Escape e retorno ao botão Editar |
| Layout/temas | APROVADO | Dez combinações com dados da API/PostgreSQL reais |
| Loading | APROVADO | Atraso controlado, resposta real liberada depois |
| Falha de rede/retry | APROVADO | Abort controlado, remoção da falha e recarga da API real |
| Logout | APROVADO | Botão Sair real retorna ao formulário de login |
| Abertura do aplicativo WhatsApp | NÃO EXECUTADO | Intencionalmente fora do escopo; redirects não seguidos |
| Envio/recebimento Brevo | NÃO EXECUTADO | Nenhum worker, envio ou chamada autenticada Brevo |
| Produção/HTTPS/outros navegadores | NÃO EXECUTADO | Ambiente exclusivamente local HTTP/Chromium |
| Leitor de tela/dispositivo físico | NÃO EXECUTADO | Não há infraestrutura desses dispositivos nesta execução |

Nenhum cenário crítico de CRUD/autenticação/redirecionamento permaneceu sem
validação real no escopo local. Isso não homologa produção ou a entrega de e-mail
pendente da Fase 4. A aprovação se limita às condições acima.

### Falhas encontradas e correções mínimas

| Falha no primeiro ensaio | Status inicial | Correção e status final |
| --- | --- | --- |
| Comparação SQL de UTF-8 no Windows | REPROVADO | Helper executado com PYTHONUTF8=1; APROVADO |
| Retorno de foco após editar | REPROVADO | Preservado acionador antes do GET/desabilitação; APROVADO |

A primeira comparação falhou porque o processo Python lia JSON UTF-8 de stdin
com a codificação padrão Windows; não era corrupção no banco. O helper passou a
usar UTF-8 explícito. A falha de foco era real: o botão ficava desabilitado durante
GET assíncrono antes de Dialogo capturar document.activeElement. MeusLinks agora
captura o elemento no clique e o passa por FormularioLink a Dialogo. O componente
reutilizável devolve foco a esse elemento ao fechar. A asserção E2E que falhou foi
mantida e passou nas dez combinações, sem remover proteção ou mascarar a falha.

### UX, responsividade e evidências

320, 375, 768, 1024 e 1440 px, altura 900, temas claro e escuro. Lista real sem
overflow horizontal; formulários dentro da viewport, scroll vertical próprio,
campos ≥16 px, botões ≥44 px, URLs longas quebráveis, validação com foco e
confirmação de exclusão. Medições de contraste: texto 17,04:1 claro/18,40:1 escuro,
botão 5,36:1, erro 4,56:1 claro/6,98:1 escuro. Esses elementos superam 4,5:1;
não se declara auditoria WCAG completa. Capturas de celular claro e formulário
desktop escuro também inspecionadas visualmente.

Capturas têm campos de fixture mascarados; não contêm credenciais ou códigos.

- [Três cenários reais](evidencias/fase5/integrada5.5/resultado-e2e.json).
- [Medições reais](evidencias/fase5/integrada5.5/layout-real.json).
- [Lista real 320 claro](evidencias/fase5/integrada5.5/lista-real-320-claro.png).
- [Formulário real 1440 escuro](evidencias/fase5/integrada5.5/formulario-real-1440-escuro.png).
- [Regressão anterior](evidencias/fase5/integrada5.5/regressao/resultado-e2e.json).

### Validações finais executadas

| Comando | Resultado |
| --- | --- |
| pytest -q | 348 aprovados, 1 ignorado, 1 aviso Starlette/httpx conhecido |
| ruff check . | Aprovado |
| ruff format --check . | 107 arquivos formatados |
| npm run test | 62 aprovados |
| npm run test:e2e | 17 anteriores aprovados, incluindo mocks identificados da 5.4 |
| npm run test:e2e:integrado | 3 novos cenários reais aprovados |
| npm run test:e2e:tipos | Aprovado, incluindo ambas as configurações |
| npm run lint | Aprovado |
| npm run format:check | Aprovado |
| npm run build | TypeScript/Vite aprovados |

O teste ignorado segue sendo a variante de concorrência SQLite legada; testes
PostgreSQL foram executados, incluindo verificação/reversão/recriação de migrações
e comparação do metadata até 0005. Nenhuma migração nova.
As duas suítes E2E foram executadas com API reiniciada entre elas, em diretórios
de evidência diferentes. Não se somam os mocks como prova de CRUD real: a prova
integrada é a nova suíte, com persistência verificada diretamente.

### Arquivos desta etapa e reprodução

Criados:

- backend/testes/e2e/consultar_link.py: consultas somente leitura com saída sanitizada.
- frontend/e2e/links-reais.spec.ts: cenários integrados sem respostas de negócio simuladas.
- frontend/e2e/preparar-integrado.ts: ativa segunda conta fictícia na fixture.
- frontend/playwright.integrado.config.ts: suíte isolada reutilizando harness existente.
- Evidências em docs/relatorios/evidencias/fase5/integrada5.5.

Modificados:

- backend/testes/e2e/ambiente.py: segunda conta opcional apenas no script de testes.
- frontend/playwright.config.ts: exclui a suíte real da execução legada compartilhada.
- frontend/package.json e tsconfig.e2e.json: comando e typecheck da nova configuração.
- Dialogo.tsx, FormularioLink.tsx e MeusLinks.tsx: correção mínima de foco assíncrono.
- README.md e este relatório. Alterações anteriores do workspace preservadas.

Com URL_BANCO_E2E no banco de testes local exclusivo e Chromium disponível, em frontend:

```bash
npm run test:e2e:integrado
npm run test:e2e
```

Configure E2E_PASTA_EVIDENCIAS separadamente para cada execução. Playwright inicia
e encerra API/Vite nas portas 18000/15173; não deve haver servidores existentes
nessas portas. Executar apenas sobre a fixture descartável linkai_e2e, nunca sobre
base com dados pessoais. O PostgreSQL deve estar iniciado; não executar worker.
Regressão backend usa URL_BANCO_TESTE e comandos documentados nas etapas anteriores.

### Conclusão e limites

APROVADA a integração local da Fase 5 nos cenários críticos executados com API e
PostgreSQL reais. Ainda não foram homologados produção/TLS, diferentes navegadores,
leitores de tela ou abertura efetiva do aplicativo WhatsApp. Entrega real Brevo
continua pendente em seu relatório específico e não foi contornada aqui.
Sem nova funcionalidade, analytics, serviço pago, commit, push ou deploy.
Nenhuma etapa posterior iniciada; aguarda aprovação do usuário.
Ao concluir, API/Vite encerrados pelo Playwright e PostgreSQL isolado encerrado
com pg_ctl. Verificação das portas 15173/18000/55432 sem listeners remanescentes.
