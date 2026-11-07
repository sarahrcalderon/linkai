# Fase 6 — Analytics

## Etapa 6.1 — Modelagem e persistência de eventos de acesso

Escopo: domínio e persistência mínima, sem captura em requisições, endpoints,
agregações ou frontend. Arquitetura de Link, contratos Protocol, transação externa,
modelos SQLAlchemy, migrações 0001–0005 e relatórios das Fases 4/5 analisados antes
de implementar. Autenticação, Brevo e redirecionamentos não foram modificados.

### Entidade e minimização

EventoDeAcesso é dataclass frozen/slots, independente de ORM/Pydantic e composta
somente por:

| Campo | Regra |
| --- | --- |
| id | UUID do registro, gerado por padrão; não identifica visitante |
| link_id | UUID obrigatório, referência ao link |
| acessado_em | datetime com fuso obrigatório, normalizado para UTC; relógio UTC por padrão |

Não foi incluída classificação: há um único conceito, tentativa de acesso elegível
conforme política futura da 6.2. Não há resultado de entrega, visitante único ou
conversão inferidos. Se outra classe de evento for necessária, exigir decisão e
migração explícitas em vez de preencher coluna especulativa.

Não há IP completo ou resumido, User-Agent, cookies, tokens, sessão, telefone de
visitante, localização, dispositivo ou fingerprint. Não duplica nome, slug,
WhatsApp, mensagem ou proprietário: associação é somente ao link. As consultas
selecionam só as três colunas do evento, usando o link apenas no filtro de dono.
Construtor rejeita campos extras e slots impedem anexação incidental de atributos.

Os futuros indicadores medirão **acessos registrados**, não pessoas únicas,
conversas iniciadas ou mensagens enviadas. Repetições no mesmo instante são
registros distintos; não há deduplicação de pessoa ou identificador persistente.
Bots, pré-carregamento ou falhas posteriores podem afetar indicadores conforme
a política que será definida na captura, sem inferir conversão.
Minimização não equivale a garantia formal de anonimização: instante exato e link
ainda representam informação de atividade e devem ter controle de acesso.

### Contrato e persistência

RepositorioEventosAcesso define adicionar(evento) e listar_por_link(link_id,
usuario_id, inicio, fim, limite=100, deslocamento=0). Adicionar executa flush, sem
commit, mantendo a unidade de trabalho BancoDados.transacao() existente. Violações
de FK/PK propagam IntegrityError e exigem rollback; não há retries automáticos.

Consulta exige período com fuso e início < fim, intervalo semiaberto **[início, fim)**.
Limite 1–1000, padrão 100; offset 0–1000000. Ordem acessado_em ASC, id ASC,
determinística inclusive para instantes iguais. Normaliza limites para UTC.
Filtro por link e proprietário ocorre em um JOIN SQL, sem carregar Link por
evento, sem consultas N+1. Link inexistente e proprietário incorreto retornam
lista vazia. Futuro caso de uso deve derivar usuario_id da sessão, nunca confiar
em cliente. Nenhuma API de consulta foi criada nesta etapa.

A paginação é offset e não promete snapshot entre chamadas. Não há contagem,
GROUP BY, séries diárias ou agregações implementadas. Índices e instante UTC
permitem implementá-las posteriormente com consultas set-based por proprietário,
sem laço por link/evento ou coluna de dia duplicada. Não foram adicionadas filas,
particionamento ou dependências prematuras.

### Modelo, índices e migração 0006

Tabela eventos_acesso:

- id UUID PRIMARY KEY NOT NULL.
- link_id UUID NOT NULL REFERENCES links(id) ON DELETE CASCADE.
- acessado_em TIMESTAMP WITH TIME ZONE NOT NULL.
- B-tree ix_eventos_link_instante_id(link_id, acessado_em, id): filtro por link,
  intervalo, ordem estável e prefixo útil para contagem futura por link.
- B-tree ix_eventos_acessado_em(acessado_em): recorte temporal global e apoio à
  exclusão por retenção futura. Há custo adicional de escrita deliberado por essa função.

Migração **0006_criar_eventos_acesso.py**, down_revision=0005. Cria somente tabela
e índices; downgrade remove somente eventos_acesso (e seus índices), perdendo os
eventos. Requer backup/consentimento para uso operacional fora dos testes.
Migrações anteriores preservadas. SQLAlchemy metadata e migração foram comparados
pela regressão real de migrações até o novo head.

### Exclusão lógica, física e política inicial de retenção

**Proposta inicial: 90 dias corridos a partir de acessado_em, em UTC.** Esse período
permite tendências recentes e comparação semanal/mensal sem manter histórico bruto
indefinido. Não é afirmação de exigência legal nem autorização para implantar
retenção ilimitada. Antes de iniciar captura, validar a janela com a necessidade
do produto e documentar eventual alteração.

Exclusão lógica do link **não remove eventos imediatamente** e não altera seu
instante/identidade. Histórico continua restrito ao proprietário durante a mesma
janela de 90 dias; a consulta interna pode recuperar eventos de links inativos ou
excluídos logicamente. Isso não restaura o link nem modifica o 404 da API/redirect.
A futura apresentação desse histórico deve ser definida de forma transparente.

Exclusão física administrativa do link remove eventos por CASCADE, evitando órfãos.
Não há operação de remoção física de link na API e ela não foi adicionada. A reserva
de slug após exclusão lógica permanece a da Fase 5. Remoção de conta, reserva de
slug e anonimização operacional precisam de política própria, sem apagar tabelas
às cegas nem enfraquecer controles de propriedade.

Nenhum job, TTL, comando de limpeza, expurgo automático ou método de remoção em
massa foi implementado/executado nesta etapa. A janela proposta **ainda não é
aplicada automaticamente**. Operação futura deve eliminar registros anteriores
ao corte UTC de 90 dias em lotes, com autorização e monitoramento, e tratar
backups/restaurações para não perpetuar ou reintroduzir dados já expirados.
Os testes usam exclusivamente eventos sintéticos em schemas descartáveis.

### Relação com a captura futura

Nenhum import/registro do repositório novo foi adicionado ao caso de uso ou rota
de redirecionamento. GET /r/{slug} continua 302/404/503 conforme a Fase 5, sem inserir
eventos. Não há incremento de contador ou rastreador.
O repositório garante referência ao link, não decide se uma requisição é elegível
ou se o link está ativo no instante de captura. Essa validação/política pertence
à 6.2, inclusive condição de corrida com desativação/exclusão e comportamento
diante de falha de gravação. Não foram introduzidos triggers de captura.

### Arquivos criados e modificados

Criados:

- backend/src/aplicacao/dominio/evento_acesso.py.
- backend/src/aplicacao/dominio/repositorio_eventos_acesso.py.
- backend/src/aplicacao/infraestrutura/repositorio_eventos_acesso.py.
- backend/src/aplicacao/infraestrutura/migracoes/versions/0006_criar_eventos_acesso.py.
- backend/testes/unitarios/teste_evento_acesso.py.
- backend/testes/integracao/teste_eventos_acesso.py.
- docs/relatorios/fase6-analytics.md.

Modificados:

- infraestrutura/modelos.py: mapeamento dos três campos, FK e índices.
- testes/integracao/teste_migracao.py e teste_postgres_migracao.py: novo head e
  presença da tabela no SQL offline.
- testes/e2e/ambiente.py: inclui eventos_acesso no TRUNCATE da fixture devido à FK.
- frontend/e2e/links-reais.spec.ts: expectativa de revisão muda de 0005 para 0006;
  não é funcionalidade de analytics no frontend.
- README.md: estrutura, privacidade, retenção e resultados atuais.

### Testes efetivamente executados

PostgreSQL **18.6**, cluster local de testes 127.0.0.1:55432, linkai_homologacao,
schemas aleatórios migrados/removidos pelas fixtures. Nenhum banco de produção,
desenvolvimento ou da tentativa real Brevo foi acessado/modificado. Nenhuma chamada
externa, novo cadastro real, captura pública ou envio de e-mail.

| Validação | Resultado |
| --- | --- |
| Alvos iniciais domínio + migração local | 18 aprovados |
| Alvos eventos + migração PostgreSQL | 14 aprovados |
| Regressão completa pytest -q | **377 aprovados, 1 ignorado**, 1 aviso conhecido |
| ruff check . | Aprovado |
| ruff format --check . | 113 arquivos formatados |
| Preparação da fixture E2E | Aprovada em linkai_e2e, tabela nova incluída no TRUNCATE |
| TypeScript dos E2E | Aprovado com expectativa da revisão atualizada |

São **29 novos casos**: 16 unitários, 13 PostgreSQL. O ignorado continua a variante
SQLite legada de concorrência; PostgreSQL é a homologação das novas transações.
Aviso Starlette/httpx existente. Ruff corrigiu imports/formatação iniciais; não há
falha de teste pendente. Frontend/build/navegador não repetidos por ausência de
mudança funcional nesses componentes; somente types dos testes E2E foram verificados.

Cobertura observada:

- Evento válido, UUIDs, UTC com conversão de offset, recusa de datas sem fuso e
  campos pessoais/duplicados não previstos; schema contém exatamente três colunas.
- FK para link inexistente rejeitada; erro e falha após flush fazem rollback.
- Persistência/recuperação, intervalo com início incluído e fim excluído,
  ordenação por instante/UUID e paginação, proprietário errado/link ausente vazios.
- Consulta de vários eventos instrumentada: **uma instrução SQL**, sem N+1.
- Oito transações/conexões concorrentes gravam no mesmo instante: **oito eventos**
  preservados. Um nono UUID novo é aceito; repetir seu UUID falha sem duplicar linha.
- Exclusão lógica preserva evento consultável pelo dono; remoção física de link
  apenas em fixture confirma CASCADE.
- HTTP 302 de link ativo e 404 inexistente deixam tabela de eventos com **zero linhas**.
- **0006 → 0005 → 0006** em PostgreSQL preserva links e recria tabela vazia.
  Regressão completa valida demais reversões e metadata após upgrade.

### Execução e pendências para 6.2

No backend com ambiente de desenvolvimento instalado, URL_BANCO_TESTE deve apontar
somente para PostgreSQL local dedicado:

```bash
python -m pytest -q
ruff check .
ruff format --check .
python -m pytest testes/unitarios/teste_evento_acesso.py testes/integracao/teste_eventos_acesso.py -q
```

Para aplicar head fora dos schemas de teste, confirmar o destino URL_BANCO e obter
autorização para o banco local persistente antes de `alembic upgrade head`.
Não foram migrados bancos de desenvolvimento/produção. A fixture descartável
linkai_e2e foi preparada somente para comprovar compatibilidade de sua limpeza.

6.2 deve definir quando registrar tentativa elegível, política para bots/repetição
sem identificação individual, fonte de tempo, concorrência com alteração de link,
e efeito de indisponibilidade do analytics no redirecionamento. Também deve planejar
operação da retenção antes de coletar dados reais. Agregações, APIs, gráficos,
fingerprinting e geolocalização não foram implementados nem antecipados.

Nenhuma credencial alterada, integração externa, commit, push ou deploy.
PostgreSQL isolado encerrado ao final; API, navegador e worker não foram iniciados
nesta etapa. git diff --check concluído sem erros de whitespace.
Etapa 6.2 não iniciada; aguarda aprovação do usuário.

## Etapa 6.2 — Registro automático de acessos

GET /r/{slug}, caso de uso de destino, sessão SQLAlchemy e repositório da 6.1
inspecionados antes de implementar. Escopo exclusivo de captura mínima; sem API
de métricas, gráficos, frontend, geolocalização, fingerprint ou serviço externo.
Migração permanece 0006; esquema e entidade não foram modificados.

### Estratégia e separação de responsabilidades

ObterDestinoWhatsApp continua retornando str com URL e reutilizando as validações
existentes. Após consulta válida e montagem do destino, cria EventoDeAcesso e
chama o contrato RegistradorAcesso. A composição HTTP fornece RegistrarAcesso,
que coordena prazo e política best effort sem importar SQLAlchemy.
Argumento opcional preserva os consumidores internos de montagem pura de URL;
no endpoint a composição de analytics é sempre fornecida, sem opção do visitante.

ConsultaLinkPublico é contrato segregado do repositório de links. O adaptador
ConsultaLinkPublicoSQLAlchemy abre sua sessão, usa o repositório existente,
encerra a transação e devolve a entidade de domínio já destacada. Só depois é
iniciada PersistenciaEventoSQLAlchemy, com outra sessão/transação, chamando o
repositório da 6.1. O retorno de persistir ocorre somente depois do commit.
Não há compartilhamento de sessão entre consulta e gravação nem commit tardio
em dependência HTTP que transforme falha de analytics em erro da resposta.

Escolha: **registro aguardado antes da resposta**, não BackgroundTasks. Vantagens:
ciclo de vida explícito, evento confirmado ao retornar em condições normais e
nenhuma tarefa órfã/sessão da requisição reutilizada após encerramento. Trade-off:
latência adicional de uma transação por acesso, carga no pool e cancelamento
cooperativo. Não há fila, worker ou garantia de recuperação após queda do processo.

ANALYTICS_PRAZO_SEGUNDOS configurável, padrão 0.5, mínimo 0.01 e máximo 5;
Pydantic recusa infinitos/NaN. asyncio.timeout cobre criação da sessão, aquisição,
flush e commit. Rollback/fechamento precisam finalizar antes de devolver controle;
o prazo é cooperativo e não promete limite rígido de latência em qualquer falha
de driver/sistema. Não há retries internos no caso de uso ou adaptador.

### Política de falhas e validade

Adaptador traduz somente falhas DBAPI, integridade, operacional/conexão, pool e
OSError em FalhaPersistenciaEvento com categoria fechada; não transporta mensagem,
SQL ou parâmetros. SQLAlchemy erros de execução do driver podem incluir schema
ausente/rejeição SQL, classificados como banco. InvalidRequestError, TypeError,
ValueError e demais erros de programação não são capturados por except Exception.
Aplicação trata a falha tipada e TimeoutError, registra aviso neutro e devolve
controle para o 302. CancelledError externo não é engolido ou repetido.

Consulta principal indisponível ainda usa o erro neutro existente (503), pois não
há destino seguro para resolver. Best effort protege a etapa de analytics, não
inventa destino quando não se consegue consultar o link. Nenhum detalhe interno
de analytics é retornado ao visitante.

Ponto de validade: a consulta concluída observou o link ativo e não excluído no
snapshot daquela leitura. Não mantém bloqueio na linha durante a contabilização.
Evento recebe UUID novo e instante UTC do servidor na preparação do registro;
instante é próximo da resolução, não prova de recebimento pelo visitante.

- Link desativado/excluído logicamente depois dessa leitura: redirect já resolvido
  continua 302 e evento pode persistir; próxima requisição resulta 404 sem evento.
- Link removido fisicamente depois da leitura: FK impede evento órfão; falha de
  integridade é best effort e o redirect resolvido permanece 302.
- Mudança de número/mensagem após leitura não altera retroativamente Location
  já resolvido; não há snapshot/lock global entre leitura e analytics.

Não se declara exatamente uma vez. Cada execução elegível tenta uma inserção
com UUID próprio; não há retry que duplique internamente a mesma tentativa.
Requisições repetidas pelo cliente contam como novos acessos. Queda/cancelamento
ou timeout em torno do commit podem deixar evento não confirmado, inclusive já
persistido; não reenviar às cegas. Também pode haver evento sem o cliente receber
o 302 por desconexão posterior. Não mede pessoa única, conversa ou mensagem.

### Observabilidade e privacidade

Logger aplicacao.casos_de_uso.registrar_acesso:

- INFO evento_acesso_registrado somente depois de commit concluído.
- WARNING evento_acesso_nao_confirmado categoria=integridade/conexao/banco/pool/timeout.

Categorias são lista fechada e conteúdo inesperado é substituído por banco.
Sem exc_info, stack, texto de exceção, SQL ou identificadores de evento/link.
Não registra IP, User-Agent, cookie, token, número, mensagem ou URL completa.
Para observar sucessos, configurar logger/handler em INFO desse namespace,
mantendo payload/SQL fora de DEBUG. Avisos permanecem no nível WARNING.
Não havia infraestrutura local de métricas/contador de perdas; não foi criada
uma nova. É possível contar registros de warning operacionalmente, mas não
equivalem a perdas exatas, especialmente em commit indeterminado. Logs também
não são entrega durável garantida de métricas.

Evento e tabela continuam com exatamente UUID, link_id e instante UTC. Nenhum
dado pessoal adicional é coletado. Política proposta de 90 dias continua sem
rotina automática; operação de retenção/backups precisa ser definida antes de
publicação com coleta real. A captura desta homologação ocorreu apenas em fixtures.

### Testes e homologação real PostgreSQL

PostgreSQL 18.6 local isolado, banco linkai_homologacao e schemas temporários
migrados até 0006. A homologação GET usa a aplicação FastAPI real por transporte
ASGI em processo e PostgreSQL real; não é mock de transação, sessão ou persistência.
Não houve abertura de navegador ou serviço externo/WhatsApp/Brevo. Nenhum acesso
ao banco da tentativa de e-mail, desenvolvimento ou produção.

| Cenário | Status | Resultado observado |
| --- | --- | --- |
| Link válido | APROVADO | 302 e um evento mínimo por tentativa confirmada |
| Inexistente/inválido/reservado/inativo/excluído | APROVADO | 404, sem evento |
| Location/cache/cookies/UTF-8 | APROVADO | Regressão do redirecionamento preservada |
| Três GETs controlados | APROVADO | Inicial 0, três 302, final 3 |
| GET após desativação | APROVADO | 404, contagem continua 3 |
| Falha real em flush | APROVADO | Trigger PostgreSQL rejeita INSERT; 302 preservado, zero eventos |
| Falha real em commit | APROVADO | Trigger adiado rejeita commit; rollback completo, 302 preservado |
| Timeout de gravação | APROVADO | Inserção antes do atraso é revertida, sessão encerrada, 302 |
| Acessos concorrentes | APROVADO | Seis GETs 302, seis eventos, seis sessões distintas |
| Desativação/exclusão lógica após leitura | APROVADO | Acesso resolvido 302/evento; próximo 404 |
| Remoção física após leitura | APROVADO | FK falha sem órfão, 302 preservado |
| Encerramento de sessões | APROVADO | Nenhuma transação ativa e checkedout=0 após requisição |
| Uma tentativa/sem retries | APROVADO | Unitários conferem chamada única; concorrência não duplica |
| Erro de programação | APROVADO | TypeError propagado, não classificado como falha best effort |
| Logs sanitizados | APROVADO | Conteúdo privado de erro e UUIDs ausentes; categorias/sucesso verificados |
| Queda completa do banco/rede durante gravação | NÃO EXECUTADO | Falhas SQL reais e timeout injetado cobrem a política local; não foi desligado o banco durante a requisição |
| Entrega de HTTP/WhatsApp ao visitante real | NÃO EXECUTADO | Redirects nunca seguidos; não há garantia dessa entrega |
| Produção, carga sustentada e relógios distribuídos | NÃO EXECUTADO | Escopo local, sem benchmark de tráfego real |

Testes de timeout e barreira de concorrência usam wrappers de teste para atrasar
o repositório real; flush/commit/rollback continuam no PostgreSQL. Mudança de link
entre leitura e gravação é sincronizada no wrapper para tornar a corrida
determinística, usando transações reais distintas. Não é comprovação por mocks.

Resultados executados:

- 8 novos unitários e 12 novos PostgreSQL; 20 casos adicionados.
- Alvos de captura/redirecionamento/eventos: 48 aprovados.
- Regressão completa: **397 aprovados, 1 ignorado**, 1 aviso Starlette/httpx conhecido.
- Ruff check e format --check aprovados, 117 arquivos formatados.
- git diff --check sem erros. Não há falha de teste pendente.
- O ignorado segue a variante SQLite legada; a concorrência nova usa PostgreSQL.
- Frontend/E2E navegador não repetidos: não houve alteração funcional do dashboard.

### Arquivos desta etapa

Criados:

- backend/src/aplicacao/casos_de_uso/registrar_acesso.py: contratos, erro tipado e política best effort.
- backend/src/aplicacao/infraestrutura/registro_acessos.py: ciclos transacionais próprios e tradução de falhas.
- backend/testes/unitarios/teste_registrar_acesso.py.
- backend/testes/integracao/teste_captura_acessos.py.

Modificados: obter_destino_whatsapp.py, domínio/repositorio_links.py (contrato
segregado), rota pública redirecionamento.py (composição), configuracao.py e
backend/.env.exemplo (prazo), teste_eventos_acesso.py (expectativa passa a captura),
README.md e este relatório. Mudanças anteriores da 6.1 no workspace preservadas.
Sem nova migração, dependência, mudança de autenticação/Brevo ou contrato do dashboard.
Nenhum arquivo privado de credenciais foi modificado.

### Limitações e pendências da 6.3

Prazo e transação adicionais impactam latência e pool; validar sob carga antes
de publicação. Best effort permite perda/indeterminação de eventos; não é fila
durável nem coleta auditável de todas as respostas. Não há contador persistente
de perdas ou correlação por visitante. Retenção de 90 dias continua proposta,
sem expurgo automático; definir operação e backups antes de coleta pública.
Agregações, API de métricas, gráficos, usuários únicos e geolocalização não foram
implementados. Nenhuma etapa posterior iniciada; aguarda aprovação.
Sem chamadas externas, envio de e-mail, commit, push ou deploy.
PostgreSQL isolado encerrado ao concluir. Nenhum servidor público, navegador ou
worker foi iniciado nesta etapa.

## Etapa 6.3 — API de métricas e estatísticas

Analisados entidade/repositório de eventos, índices, autenticação/Proprietario,
casos de uso/DTOs e tratamento HTTP existentes. Implementação restrita a leitura
agregada; tabela/migração permanecem 0006, sem modificar captura/redirecionamento,
login, cookies, CSRF, Brevo ou dashboard. Nenhuma dependência ou chamada externa.

### Endpoints e contratos

| Endpoint | Parâmetro | Sucesso |
| --- | --- | --- |
| GET /api/links/{id}/estatisticas | dias=7, 30 ou 90; padrão 7 | 200 EstatisticasLinkSaida |
| GET /api/estatisticas/resumo | dias=7, 30 ou 90; padrão 7 | 200 ResumoEstatisticasSaida |

ID é UUID; parâmetro inexistente seleciona 7. Query aceita somente as strings
canônicas 7/30/90; 7.0, valores negativos, outras durações, datas personalizadas
e campos extras são 422. Não aceita usuario_id ou qualquer seletor de proprietário.
Casos de uso também limitam duração, independentemente da validação HTTP.

Resposta individual:

```json
{
  "link_id": "22222222-2222-4222-8222-222222222222",
  "total_acessos": 0,
  "data_inicial": "2026-10-31T00:00:00Z",
  "data_final": "2026-11-06T12:30:00Z",
  "serie_diaria": [
    {"data": "2026-10-31", "acessos": 0},
    {"data": "2026-11-01", "acessos": 0},
    {"data": "2026-11-02", "acessos": 0},
    {"data": "2026-11-03", "acessos": 0},
    {"data": "2026-11-04", "acessos": 0},
    {"data": "2026-11-05", "acessos": 0},
    {"data": "2026-11-06", "acessos": 0}
  ]
}
```

Exemplo ilustrativo de schema, não contador fictício em produção. Resumo contém
os mesmos campos temporais/total/série, troca link_id por links_ativos e
links_inativos. Quantidade de links é seu estado atual, não links criados no
período. Todos os valores reais são calculados dos registros do PostgreSQL.

### Definição temporal UTC

Uma leitura do relógio do servidor por consulta. Converte para UTC, determina
meia-noite do dia atual e subtrai dias-1. Intervalo **[início, agora)** inclui a
primeira fronteira e exclui a final. Dia atual é parcial; à meia-noite seu valor
inicial pode ser zero. Não há inclusão de eventos futuros nem janela móvel N×24h.

Série contém exatamente 7/30/90 datas em ordem crescente, preenchendo dias sem
acesso com zero. Data inicial/final são datetimes UTC; campo data de cada item é
data de calendário UTC. Agrupamento usa explicitamente
CAST(timezone('UTC', acessado_em) AS DATE), independente do timezone da conexão.
Teste alterou a sessão para Pacific/Honolulu e preservou a separação correta dos
dias UTC, inclusive evento com offset -03:00.

### Autorização, cache e privacidade

Reutiliza Proprietario/ConsultarAutenticado e a mesma unidade transacional de
autenticação, sem alterar esses fluxos. Exige sessão válida de usuário ativo e
e-mail verificado. Leituras GET não acrescentam exigência CSRF; escritas existentes
continuam protegidas. Cookies HttpOnly, Origin/CORS e sessão não foram alterados.

SQL sempre filtra usuario_id da sessão. Para consulta individual, condição de
link.id/proprietário/excluido_em IS NULL antecede a agregação; ausência, exclusão
e link de terceiro produzem o mesmo 404/code link_nao_encontrado. Não há consulta
global para distinguir causas. Link inativo próprio é consultável, com seu histórico.

Resumo considera somente links próprios não excluídos, ativos e inativos. Exclusão
lógica conserva histórico na tabela conforme 6.1, mas remove o link e seus eventos
do resumo atual. Estatísticas individuais de excluídos não são expostas por essa API.

Cache-Control **private, no-store** nos sucessos e erros destas rotas, incluindo
401/404/422/503. O helper central de erro recebeu Request opcional apenas para
selecionar essa política contextual; demais rotas mantêm no-store e envelopes
existentes. Validação HTTP contextualizada para dias/UUID, sem refletir input,
proprietário, query desconhecida ou erro SQL. Falhas de infraestrutura são 503
sanitizado, sem contagem falsa em substituição ao erro.

Não retorna eventos individuais, IDs de eventos, proprietário, telefone, mensagem,
IP, User-Agent, cookie, token ou dados de sessão. Mede acessos registrados, sem
inferir quantidade de pessoas, conversas iniciadas ou mensagens enviadas.

### Agregações e consistência

Contrato segregado RepositorioEstatisticas devolve AcessosAgregados/ResumoAgregado,
independentes de ORM. Não reutiliza listar_por_link para contar: isso carregaria
eventos e exigiria paginação/N+1. Infraestrutura usa os modelos/índices da 6.1.
Aplicação monta DTOs explícitos e preenche apenas datas ausentes com zero; não
soma eventos ou estima totais em Python.

Individual: uma instrução SQL, LEFT JOIN de link autorizado com eventos filtrados
no ON por [início,fim). COUNT(evento.id) e GROUP BY dia; SUM(COUNT(...)) OVER ()
calcula o total dos grupos no próprio banco. Link sem evento gera total zero;
link não autorizado não gera linha. Não há consulta separada por existência/dia.

Resumo: uma instrução SQL com subconsulta de contagens atuais de links
(COUNT FILTER ativo/inativo) e outra de eventos autorizados, COUNT/GROUP BY/janela.
LEFT JOIN das subconsultas mantém resultado vazio com contagens/total zero.
Contagem de links não é multiplicada pelos eventos. PostgreSQL retorna no máximo
90 linhas diárias agregadas, não os eventos brutos. Autenticação ainda tem suas
consultas próprias; a afirmação de uma instrução refere-se à agregação.

Cada instrução de agregação usa um snapshot PostgreSQL, mantendo total/série e
contagens do resumo coerentes nesse statement. Sob READ COMMITTED, autenticação
e consultas HTTP diferentes não compartilham snapshot eterno. O corte temporal
é fixado antes de consultar: novos eventos após data_final ficam para outra janela.
Eventos com timestamp anterior ainda em commit podem aparecer numa consulta
posterior. Só eventos persistidos/visíveis entram no cálculo. Best effort pode
perder eventos ou ter resultado indeterminado, sem garantia exatamente uma vez.

Retenção proposta de 90 dias continua sem limpeza automática. Não foi adicionado
cache de contadores ou estimativa em memória; dados fora da janela não entram
nas respostas mesmo que ainda estejam retidos fisicamente.

### Testes e classificação final

PostgreSQL **18.6**, cluster local de testes 127.0.0.1:55432, linkai_homologacao com
schemas aleatórios migrados e removidos pelas fixtures. Sem produção, banco de
desenvolvimento ou banco de e-mail. As contas/sessões são fictícias. Requisições
HTTP usam FastAPI por ASGI e PostgreSQL real, sem mocks nas agregações.

| Cenário | Status | Evidência |
| --- | --- | --- |
| Link sem/um/múltiplos acessos | APROVADO | Totais 0, 1 e 4 com eventos persistidos |
| Períodos 7/30/90 | APROVADO | Endpoints individuais e resumos, séries com tamanho exato |
| Fronteiras do intervalo | APROVADO | Início incluído, final/agora e futuros excluídos |
| Dias vazios/ordem | APROVADO | Zeros e sequência cronológica |
| Virada UTC/offset/fuso da conexão | APROVADO | Microsegundo anterior e meia-noite em dias distintos |
| Resumo atual ativo/inativo | APROVADO | Counts separados, total sem multiplicar links |
| Excluído e outro proprietário | APROVADO | Fora do resumo e mesmo 404 individual |
| Sessão ausente/expirada e UUID | APROVADO | 401/422 conforme contrato, cache privado |
| Query extra/proprietário/limites | APROVADO | 422 sem refletir valores |
| Privacidade/cache | APROVADO | DTO explícito, private/no-store em sucesso e erros |
| Falha de infraestrutura | APROVADO | Erro de banco injetado, resposta 503 sem detalhes |
| Agregação PostgreSQL/volume | APROVADO | 30000 eventos, uma instrução por resumo e EXPLAIN real |
| Queda física de infraestrutura durante GET | NÃO EXECUTADO | Não foi desligado banco no meio da consulta |
| Produção/carga concorrente prolongada | NÃO EXECUTADO | Benchmark local sintético não comprova capacidade produtiva |
| Frontend/navegador de analytics | NÃO EXECUTADO | Fora da etapa; nenhuma tela criada |

Primeiro ensaio teve falha de descoberta da fixture dependente; corrigida por
importação explícita, conforme padrão existente. Preparação SQL textual também
precisou selecionar search_path do schema descartável, pois schema_translate_map
não reescreve SQL literal; expiração de sessões passou a usar ORM. Esses erros
de preparação não eram falhas da autenticação ou das consultas do produto.
Imports e formatação foram ajustados ao Ruff. Nenhuma falha restante na execução final.

Resultados finais:

- **434 backend aprovados, 1 ignorado**, aviso Starlette/httpx já conhecido.
- 37 novos casos: 12 unitários de aplicação e 25 integrações PostgreSQL.
- Ruff check e format --check aprovados: **123 arquivos formatados**.
- git diff --check sem erros. Não repetidos frontend/build/E2E: nenhuma mudança
  nesses componentes. O ignorado segue a variante SQLite de concorrência legada;
  consultas/agregações/planos desta etapa foram homologados no PostgreSQL real.

### Desempenho observado — sem extrapolação produtiva

Inseridos **30000 eventos sintéticos** por generate_series em um link, distribuídos
em 90 dias. Contexto com quatro links, dois proprietários e estados diferentes.
ANALYZE executado somente na tabela do schema de teste. Medição via perf_counter
em chamada ao repositório e EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) da instrução
real capturada pelo listener. Saída salva sem SQL completo, UUIDs ou dados pessoais.

Última regressão completa observou:

| Janela | Acessos no período | Instruções de agregação | Tempo no repositório | Planejamento EXPLAIN | Execução EXPLAIN |
| --- | --- | --- | --- | --- | --- |
| 7 dias | 2331 | 1 | 6,459 ms | 0,210 ms | 1,273 ms |
| 90 dias | 30000 | 1 | 13,884 ms | 0,309 ms | 10,586 ms |

[Evidência medida](evidencias/fase6/desempenho6.3.json), regenerada pelo teste.
Valores são observações de uma máquina local; variam por cache/execução e não são
SLA, percentis ou capacidade medida da API em produção. Tempos do repositório não
incluem rede HTTP, autenticação, serialização ou carga concorrente.

Plano de 7 dias usou Bitmap Index Scan em ix_eventos_acessado_em e índice existente
de proprietário em links. Plano de 90 dias escolheu Seq Scan dos 30000 eventos,
coerente com selecionar o conjunto inteiro desse ensaio, mais agregação no servidor.
O índice composto por link/instante/UUID permanece disponível para leituras
seletivas individuais. Não foi demonstrado gargalo que justificasse índice extra;
nenhum índice/migração foi criado ou hint de plano forçado.

### Arquivos criados/modificados e próxima etapa

Criados:

- dominio/repositorio_estatisticas.py: contrato e estruturas agregadas.
- casos_de_uso/consultar_estatisticas.py: períodos, DTOs e preenchimento de zeros.
- infraestrutura/repositorio_estatisticas.py: consultas SQL agregadas.
- apresentacao/rotas/estatisticas.py: os dois GET autenticados.
- testes/unitarios/teste_consultar_estatisticas.py.
- testes/integracao/teste_estatisticas.py.
- docs/relatorios/evidencias/fase6/desempenho6.3.json.

Caminhos de código relativos a backend/src/aplicacao; caminhos de testes relativos
a backend. Modificados: principal.py para registro do roteador, apresentacao/erros.py
para validação/cache contextual, README e este relatório. Alterações anteriores
do workspace preservadas; entidade, registro best effort, migrações, autenticação
e Brevo não foram modificados nesta etapa.

Para executar em backend com URL_BANCO_TESTE exclusivamente no PostgreSQL dedicado:

```bash
python -m pytest -q
ruff check .
ruff format --check .
python -m pytest testes/integracao/teste_estatisticas.py -q
```

Consulta manual exige login existente de conta verificada local e cookie de sessão;
GETs não precisam de CSRF e não aceitam proprietário informado pelo consumidor.
Nenhum bypass de autenticação foi adicionado para testar as métricas.

6.4 aguarda aprovação para sua interface/escopo futuro. Permanecem pendentes
validação de produção/TLS, carga representativa multiusuário, planejamento de
retenção/backups e operação das perdas do best effort. Não foram implementados
gráficos, exportação, rastreamento ou serviços externos. Sem chamadas externas,
e-mails, commits, pushes ou deploys; nenhuma etapa posterior iniciada.
PostgreSQL isolado encerrado após a validação. Nenhum navegador, worker ou servidor
público foi iniciado nesta etapa.

## Etapa 6.4 — Dashboard de Analytics

Implementada exclusivamente a interface, preservando backend, autenticação,
Brevo, captura de acessos e redirecionamentos. O dashboard existente ganhou uma
seção de Analytics; o gerenciamento de links permanece no mesmo local.

### Arquivos e componentes

Criados em `frontend/src/funcionalidades/estatisticas/`:

- `servico.ts`: contratos TypeScript, leitura defensiva da resposta e formatação UTC.
- `usarEstatisticas.ts`: integração com `executarAutenticado`, estado de consulta,
  repetição manual e descarte de respostas obsoletas.
- `Analytics.tsx`: resumo, consulta individual, filtros e estados de interface.
- `GraficoAcessos.tsx`: série SVG, consulta diária por controle acessível e tabela.

Modificados:

- `frontend/src/paginas/PaginaDashboard.tsx`: composição da seção e seleção do link.
- `frontend/src/funcionalidades/links/MeusLinks.tsx`: botão de estatísticas nos
  recursos da listagem autenticada e notificação após alterações. Criar, editar,
  ativar, desativar ou excluir um link atualiza o resumo e limpa a seleção anterior.
- `frontend/src/testes/Autenticacao.test.tsx` e `Links.test.tsx`: fixtures adaptadas
  à consulta adicional de resumo, preservando as asserções dos fluxos existentes.
- `frontend/package.json`: comando `test:e2e:analytics`, sem novas dependências.
- Este relatório. Arquivos de cache TypeScript são regenerados pelo build.

Criados também `frontend/src/testes/Analytics.test.tsx`,
`frontend/src/testes/fixtureEstatisticas.ts`, `frontend/e2e/analytics.spec.ts`,
`frontend/playwright.analytics.config.ts` e as evidências em
`docs/relatorios/evidencias/fase6/dashboard6.4/`.

### Contratos e comportamento

Consome exclusivamente `GET /api/estatisticas/resumo?dias=7|30|90` e
`GET /api/links/{id}/estatisticas?dias=7|30|90`. O padrão é 7 dias. Os campos
`total_acessos`, `links_ativos` e `links_inativos` vêm da API; nenhum total é
calculado a partir da página de links ou da série. Respostas incompletas,
contagens inválidas, série de tamanho inesperado ou identificador de link
divergente produzem erro, sem fabricar indicadores. Dados sintéticos existem
somente nos testes.

A consulta individual parte do botão de um link retornado pela listagem
autenticada, incluindo links inativos. Não há seletor de proprietário, IDs livres
ou listagem adicional para Analytics. Links excluídos não são disponibilizados
pela listagem. Um 403/404 remove os indicadores e apresenta “Link indisponível”.
A autorização definitiva permanece no backend.

Reutiliza cookies e `cache: no-store` do cliente HTTP, além do gerenciador de
sessão existente: 401 encerra a sessão e leva ao login. GET não acrescenta CSRF;
as mutações existentes mantêm sua proteção. Não persiste métricas em storage.

As datas da série são interpretadas explicitamente em UTC, inclusive no texto
dos detalhes e na tabela. A interface mostra o instante final fornecido pela API,
indica que o dia atual está parcial e não redefine os limites pelo fuso local.
Trocar período ou link oculta imediatamente os dados anteriores; efeitos
desativados não podem substituir a consulta atual. O início da consulta é
adiado por um microtask para evitar a execução duplicada do efeito de Analytics
na montagem em StrictMode. Não há polling ou retentativa automática; “Tentar
novamente” inicia uma consulta manual. Requisições já iniciadas continuam até
conclusão ou timeout do cliente HTTP, mas resultados obsoletos são descartados.

### Indicadores, gráfico e acessibilidade

Resumo exibe acessos registrados no período e quantidades atuais de links ativos
e inativos. A visão individual exibe nome, URL pública textual, total e série;
o botão de retorno restaura o resumo. Selecionar uma visão move o foco ao título.

O gráfico usa SVG nativo, sem biblioteca adicional: são no máximo 90 pontos,
sem animação ou interação complexa que justifique uma dependência. Apresenta
escala inteira, rótulos temporais HTML legíveis mesmo em 320 px e cores existentes
do Design System. O detalhe diário persistente funciona como consulta acessível
dos valores: o controle de faixa funciona por toque e setas do teclado, com
`aria-valuetext`, descrição e atualização anunciada. Não depende de hover.
Uma tabela expansível apresenta todos os dias, inclusive zeros, com cabeçalhos
e legenda. O gráfico não é a única fonte de informação.

Estados presentes: carregando com `aria-busy`/status, vazio com zeros e orientação
para criar links quando aplicável, erro com alerta e repetição manual, dados com
indicadores e série. O aviso explica que acessos registrados não correspondem a
visitantes únicos, conversas iniciadas ou mensagens enviadas.

### Validação observada

Ambiente: Windows local, React 19, TypeScript, Vite e Playwright existentes no
projeto. API inteiramente simulada nos testes desta etapa. Nenhum backend,
PostgreSQL, worker ou serviço externo foi iniciado/acessado para a validação.

| Verificação | Resultado |
| --- | --- |
| Vitest completo | 75 testes aprovados, em 8 arquivos |
| Playwright com Chrome local (motor Chromium), API simulada | 15 testes aprovados |
| ESLint | Aprovado |
| TypeScript da aplicação/build e tipos E2E | Aprovados |
| Prettier do frontend | Aprovado |
| Build de produção Vite | Aprovado |

Vitest cobre resumo, zeros, carregamento, períodos 30/90, corrida entre respostas,
consulta individual, 403/404, rede e repetição, contrato 401, leitura acessível da
série, tabela, UTC e resposta incompleta. A regressão de autenticação e CRUD de
links foi executada junto aos novos testes.

Os 15 E2E cobrem dez combinações de 320/375/768/1024/1440 px com temas claro e
escuro, além de seleção individual/retorno sem consulta adicional da listagem,
rede e repetição, sessão expirada, resposta atrasada e link indisponível.
Todas as larguras tiveram `scrollWidth <= innerWidth`. Foram verificados controle
de período com altura mínima de 44 px, foco visível, navegação por setas, valores
acessíveis e tabela com 90 dias. A preferência de tema foi preservada.

As dez capturas `analytics-{largura}-{tema}.png` e os dez arquivos
`layout-{largura}-{tema}.json` estão na pasta de evidências. Os JSON registram
largura, conteúdo, tema e contraste calculado no navegador para título e linha
do gráfico contra o fundo. Exemplo de 320 px claro: título 17,04:1 e linha
5,13:1, acima dos limites verificados de 4,5:1 e 3:1, respectivamente.
As capturas de 320 px claro e 1440 px escuro também foram inspecionadas visualmente.
Isso não substitui auditoria completa de acessibilidade ou teste com leitor de tela.

Problemas encontrados e resolvidos na validação: as fixtures antigas não
previam o resumo e geravam falhas artificiais/alertas adicionais; agora têm uma
resposta de métricas dedicada. Seletores dos novos testes foram delimitados aos
cards, pois a tabela repete legitimamente os totais. A listagem preexistente
executa dois efeitos na montagem em StrictMode; o E2E compara a contagem antes e
depois da seleção para comprovar que Analytics não acrescenta consulta à lista.
O Chromium empacotado do Playwright não estava instalado; foi reutilizado o
Chrome local com `E2E_CANAL=chrome`, sem download ou chamada externa.
PowerShell bloqueia `npm.ps1`; foi utilizado `npm.cmd`, sem mudar essa política.
Build/testes Vite e navegador precisaram executar fora do sandbox por restrições
de acesso do esbuild, mediante autorização da ferramenta.

### Execução e limites

Em `frontend`:

```powershell
npm.cmd run test
npm.cmd run lint
npm.cmd run test:e2e:tipos
npm.cmd run format:check
npm.cmd run build
$env:E2E_CANAL = 'chrome' # opcional: Chrome já instalado
npm.cmd run test:e2e:analytics
```

Sem `E2E_CANAL`, usa o Chromium padrão previamente instalado do Playwright.
O executor específico inicia somente Vite em 127.0.0.1:15174 e intercepta a API;
não exige credenciais ou banco. O servidor temporário foi encerrado ao final.
Não foi afirmada integração real com PostgreSQL nesta etapa, nem repetida a
homologação integrada das etapas anteriores. Os testes E2E antigos dependentes
do backend/banco não foram executados nesta entrega.

Pendências para 6.5, após aprovação: homologação integrada com API/PostgreSQL
isolados, dados e períodos reais, revisão complementar de acessibilidade com
leitor de tela e validação operacional. Não foram adicionados endpoints,
migrações, exportação, geolocalização, retenção automática ou rastreamento.
Sem chamadas externas, e-mails, alterações de credenciais, commits, pushes ou
deploys. Nenhuma etapa posterior iniciada.

## Etapa 6.5 — Homologação integrada do Analytics

### Ambiente, isolamento e escopo

Homologação local em 06/11/2026, com PostgreSQL **18.6**, FastAPI/Uvicorn,
React/Vite e Chrome **156.0.8078.80** via Playwright (motor Chromium).
Reutilizados o cluster `.postgres-teste/dados` e os executores da Fase 5.
PostgreSQL em `127.0.0.1:55432`, banco exclusivo `linkai_e2e` para navegador e
`linkai_homologacao` com schemas descartáveis para pytest. A conexão dos helpers
recusa host não local e qualquer banco diferente de `linkai_e2e`.
Nenhum banco de produção, desenvolvimento ou de homologação do Brevo foi usado.

Backend em `127.0.0.1:18000`, frontend em `127.0.0.1:15173`, CORS com origem
explícita. Usuários fictícios verificados foram criados pelo mecanismo local
existente, com senha transitória gerada no setup e hash Argon2id. Login pelo
navegador e sessões reais, sem bypass público. Cookies HttpOnly/SameSite e
CSRF/Origin foram preservados. Secure permanece conforme o contrato local HTTP;
produção HTTPS não foi validada. Segredos de teste gerados pelo executor, sem
copiar credenciais de Brevo. Nenhum worker de e-mail foi iniciado.

Migrações até **0006**, confirmadas na conexão PostgreSQL real pelo teste de
metadados existente. A regressão executou upgrade/downgrade/upgrade e comparação
com o metadata em schema isolado. Nenhuma migração ou índice novo nesta etapa.

### Arquivos criados e modificados nesta etapa

- Criado `backend/testes/e2e/analytics.py`: fixture histórica, SQL independente
  somente leitura para conferência e injeção/restauração de falha controlada.
  É ferramenta local de testes, nunca importada pela API pública.
- Criado `frontend/e2e/analytics-reais.spec.ts`: três cenários integrados amplos.
- Modificado `frontend/playwright.integrado.config.ts`: inclui Analytics real
  junto aos três testes integrados existentes de links.
- Modificado `frontend/playwright.config.ts`: exclusão de `*-reais.spec.ts` da
  suíte geral e seleção opcional de navegador local com `E2E_CANAL`.
- Modificado `frontend/e2e/links-reais.spec.ts`: preparação isolada antes de cada
  teste, evitando dependência dos dados deixados por outra suíte.
- Modificado `frontend/e2e/links.spec.ts`: fixture de resumo para os testes que
  simulam sessão/listagem; evita consultar a API real sem a sessão simulada.
- Este relatório e evidências em `evidencias/fase6/integrada6.5/` e
  `evidencias/fase6/regressao6.5/`. A regressão também regenerou
  `evidencias/fase6/desempenho6.3.json` com medições novas do ensaio existente.

Alterações de etapas anteriores no workspace preservadas. Não foi necessária
correção no código de produção, nos contratos, na autenticação, no Brevo ou nos
redirecionamentos.

### Cenários reais e classificação

| Cenário | Classificação | Evidência observada |
| --- | --- | --- |
| Usuário local, login e criação de link pelo dashboard | APROVADO | Link confirmado no PostgreSQL; sessão real |
| Estatísticas iniciais | APROVADO | API, SQL e interface com zero eventos |
| Três GETs públicos sem seguir redirecionamento | APROVADO | Três respostas 302; destino wa.me inspecionado sem navegação |
| Registro best effort e atualização do dashboard | APROVADO | Poll SQL com prazo de 10 s confirmou três eventos; total três após reload |
| Gráfico, tooltip e tabela com dados reais | APROVADO | Série da API conferida por SQL; tabela e detalhe diário mostraram três |
| Períodos 7, 30 e 90 dias | APROVADO | Totais 6, 10 e 10 na fixture histórica; séries com 7, 30 e 90 datas |
| UTC, meia-noite e fronteiras | APROVADO | Eventos reais no banco antes/no início, antes/na meia-noite UTC; eventos antigos e futuros excluídos |
| Links ativos, inativos, excluídos e sem acessos | APROVADO | Resumo com dois ativos/um inativo; excluído fora do resumo e consulta 404; sem acessos com zero |
| Múltiplos links e usuários | APROVADO | Resumo e consultas individuais comparados com SQL por proprietário |
| Sessão ausente/expirada | APROVADO | 401 privado; expiração controlada no banco e retorno do navegador ao login |
| IDOR | APROVADO | Link de outro usuário e UUID inexistente retornaram 404 com mesmo corpo |
| Cache-Control | APROVADO | private, no-store em estatísticas 200/401/404 |
| CSRF/Origin | APROVADO | Escrita sem token ou com origem inválida: 403; com ambos corretos: 201 |
| Minimização de dados e logs | APROVADO | Campos exatos dos DTOs; logs da API sem senha transitória, cookies, token CSRF, telefone ou hashes nos padrões verificados |
| Falha real de gravação de Analytics | APROVADO | Trigger temporário rejeitou três INSERTs; três 302 e nenhum evento adicional |
| Contabilização somente de eventos persistidos | APROVADO | Dashboard/API/SQL permaneceram em 23 durante as falhas |
| Concorrência controlada | APROVADO | Vinte GETs simultâneos: vinte 302 e vinte novos eventos confirmados |
| Ausência de N+1 na agregação | APROVADO | Teste real existente com listener SQL confirmou uma instrução agregada por consulta, inclusive 30 mil eventos |
| Cinco larguras e dois temas | APROVADO | Dez combinações reais sem overflow; screenshots e medidas locais |
| Foco, teclado, tooltip e alternativa tabular | APROVADO | Tab do período ao controle, foco visível, Home/setas, tabela e foco ao selecionar link |
| Loading e erro de transporte | APROVADO | Atraso da requisição e falha de rede injetados; recuperação consulta a API real |
| Virada real do relógio durante a execução | NÃO EXECUTADO | Fronteiras foram exercitadas por timestamps controlados; relógio global não alterado |
| Produção, HTTPS/TLS, carga sustentada e leitor de tela | NÃO EXECUTADO | Fora deste ensaio local |

Os cenários críticos de negócio acima não usam respostas HTTP simuladas.
A guarda de rede permite somente destinos locais. Os GETs públicos usam
`maxRedirects: 0`, inclusive passando pelo proxy Vite. Não houve navegação para
WhatsApp, chamada ao Brevo ou envio de e-mail.

### Conferência SQL e limites temporais

O helper abre transação `READ ONLY` nas operações de conferência. A consulta
independente une eventos, links e usuários; filtra proprietário, exclusão lógica
e `[data_inicial, data_final)` retornado pela API; agrupa por
`(acessado_em AT TIME ZONE 'UTC')::date`. Compara cada data da série, incluindo
zeros, total e contagens de estados. Consultas individuais acrescentam `link_id`.
Nenhum registro pessoal é retornado pelo helper de conferência.

A fixture histórica contém links ativo, inativo, excluído, sem acessos e de outro
proprietário. Para cada link com eventos, inclui 100 dias atrás, fronteira de
30 dias, um microssegundo antes e exatamente no início dos 7 dias, um microssegundo
antes e exatamente na meia-noite UTC atual, além de um evento futuro. Somente
ativo/inativo não excluídos do proprietário compõem seu resumo. A tabela diária
de cada período e os totais de links individuais foram comparados com o SQL.
`periodos-sql-seguranca.json` registra as séries efetivamente observadas, sem
sessões, cookies ou tokens.

### Falha de persistência e concorrência

Instalado temporariamente no banco dedicado um trigger restrito ao UUID do link
do teste, que rejeita INSERT com SQLSTATE 23514. Não substitui a persistência por
mock, não altera a leitura do link nem enfraquece segurança. O trigger e sua
função são removidos em `finally`.

No ensaio, **26 requisições recebidas e 26 respostas 302**, com **23 eventos
persistidos**: três acessos iniciais, vinte concorrentes e três gravações
rejeitadas. Três avisos sanitizados de categoria `integridade` foram observados;
o contador não cresceu na espera adicional de 750 ms. A inspeção do caso de uso
também confirma ausência de laço de retentativas. Esse intervalo de observação
não é uma garantia sobre cargas ou falhas futuras.

`fluxo-concorrencia.json` contém os tempos observados pelo cliente. Na execução
integrada final, GETs iniciais ficaram entre **12,71 e 22,92 ms**; os vinte
simultâneos ficaram entre **28,21 e 198,74 ms**. Incluem cliente e proxy local;
não medem isoladamente o tempo de commit e não são percentis ou SLA. Cada evento
efetivamente persistido foi contabilizado, sem prometer registrar todo acesso.

O ensaio SQL de 30 mil eventos foi repetido pela regressão backend: uma instrução
agregada por resumo, com 7,745 ms no repositório para 7 dias e 11,600 ms para 90
dias; EXPLAIN executou em 1,573/10,244 ms, respectivamente. O plano seletivo usou
índice temporal; a janela integral usou Seq Scan. Sem evidência que justificasse
alterar índices. Os números novos estão no artefato regenerado da Etapa 6.3;
os números da seção anterior são o registro histórico daquela execução.

### UX, evidências e cenários simulados

`ux-real.json` registra navegador e dez medições de 320/375/768/1024/1440 px nos
temas claro e escuro. Em todas, `scrollWidth <= innerWidth`. Contraste medido do
título/fundo: **17,04:1 claro e 18,40:1 escuro**; linha/fundo: **5,13:1 e 13,24:1**.
Isso cobre esses elementos, sem representar auditoria integral de WCAG.
As dez capturas `real-{largura}-{tema}.png` mostram indicadores, filtro, gráfico,
detalhe acessível e tabela com dados da API real. A captura de 320 px claro foi
também inspecionada visualmente.

Loading foi exercitado atrasando somente o envio da requisição, liberada para
a API real; erro foi exercitado abortando a conexão, seguido de repetição real.
Essas duas condições são **falhas/atrasos de transporte simulados**, não mocks de
resposta de negócio. A falha de gravação é injeção de erro dentro do PostgreSQL.
Os E2E de Analytics da Etapa 6.4 e de interface de links continuam explicitamente
com API simulada na suíte geral; não são evidência do fluxo integrado.

### Regressão, correções e conclusão

Regressão backend: **434 aprovados, 1 ignorado**, em 57,48 s, com um aviso
preexistente de depreciação Starlette/httpx. Ruff check aprovado; Ruff format
check aprovado em 124 arquivos. Frontend: **75 testes aprovados**, TypeScript da
aplicação e E2E, ESLint, Prettier e build Vite aprovados.

Executor integrado: **6 testes aprovados**, três novos de Analytics e três reais
de links da Fase 5. Relatório sanitizado em
`evidencias/fase6/integrada6.5/resultado-e2e.json`. A suíte geral tem relatório
separado em `evidencias/fase6/regressao6.5/resultado-e2e.json`: **32 aprovados**,
incluindo os 15 testes simulados de Analytics, testes reais de autenticação e
os testes existentes de interface de links/verificação. Ao todo, **38 E2E
aprovados**, com classificação real/simulada preservada por suíte/cenário.

Na primeira execução, três cenários falharam por preparação de testes:
foco programático após interação por mouse não ativa necessariamente
`:focus-visible`, e fixtures históricas de Analytics contaminavam testes antigos
que pressupunham listagem vazia. Corrigidos com Tab real e preparação por teste.
A suíte simulada de links recebeu resposta de resumo própria para sua sessão
simulada. Nenhuma proteção ou asserção de negócio foi retirada para aprovar.
As seis execuções integradas seguintes passaram.

O PostgreSQL inicialmente não abriu o socket padrão; foi iniciado com IPv4 e
porta de testes explícitos, sem alterar arquivos de credenciais ou configuração
persistente. O Chrome instalado foi reutilizado sem download. Os comandos com
processos de navegador/esbuild e conexão local precisaram de execução autorizada
fora do sandbox. Evidências não contêm credenciais, cookies ou tokens reais.

Para reproduzir, configure somente `URL_BANCO_E2E` para o banco local exclusivo
`linkai_e2e` e `URL_BANCO_TESTE` para o banco dedicado de pytest. O setup E2E
restaura e **limpa as tabelas desse banco de testes**; não o aponte para dados a
preservar. Em frontend:

```powershell
$env:E2E_CANAL = 'chrome'
$env:E2E_PASTA_EVIDENCIAS = '../docs/relatorios/evidencias/fase6/integrada6.5'
npm.cmd run test:e2e:integrado
$env:E2E_PASTA_EVIDENCIAS = '../docs/relatorios/evidencias/fase6/regressao6.5'
npm.cmd run test:e2e
npm.cmd run test
npm.cmd run lint
npm.cmd run test:e2e:tipos
npm.cmd run format:check
npm.cmd run build
```

Em backend, com a URL de teste isolada: `python -m pytest -q`, `ruff check .`
e `ruff format --check .`. Não há segredo ou senha fixa a copiar deste relatório.

Pendências operacionais: produção HTTPS, carga sustentada representativa,
monitoramento das perdas best effort, retenção/backups e auditoria complementar
com leitor de tela. Não foram implementadas métricas novas, exportação, retenção
automática, fingerprinting ou rastreamento. Nenhum commit, push, deploy ou avanço
de etapa.

Conclusão: **homologação integrada local da Etapa 6.5 APROVADA**. Todos os fluxos
críticos solicitados foram validados com API/PostgreSQL reais; as limitações de
produção e acessibilidade complementar acima não são apresentadas como testes
executados. PostgreSQL, Uvicorn e Vite encerrados, com portas 55432/18000/15173
e 15174 livres. Conferência final: PostgreSQL 18.6, revisão 0006 e nenhum trigger
ou função `falha_analytics_e2e` remanescente. Aguardar aprovação antes de avançar.
