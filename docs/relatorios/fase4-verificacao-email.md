# Fase 4 — Etapa 4.1: estrutura de verificação de e-mail

Entrega de 06/11/2026. Exclusivamente contratos, domínio, persistência e serviço
interno; não há novas rotas, telas, envio real, credenciais Brevo ou avanço para 4.2.

## Diagnóstico e arquitetura

Revisados os contratos de cadastro/login, entidade de usuário, sessão opaca,
SQLAlchemy assíncrono, transações, migrações e testes da Fase 3 antes das alterações.
O cadastro permanece criando contas não verificadas, sem gerar desafio ou autenticar.
O login permanece bloqueado até que uma confirmação válida seja persistida.

- Domínio independente: VerificacaoEmail e RepositorioVerificacoes. UUIDs, datas UTC,
  codigo_hash oculto no repr, utilização, invalidação e contador de erros.
- Aplicação: VerificarEmail gera/reenvia, confirma e invalida desafios através dos
  contratos criptográficos e de uma unidade transacional; não importa ORM/FastAPI.
- Infraestrutura: HMAC, repositório SQLAlchemy, unidade de trabalho e factory explícita
  criar_verificacao_email. Cada operação abre uma transação e bloqueia o usuário com
  SELECT FOR UPDATE. Todos os repositórios dessa unidade usam a mesma AsyncSession.
- ServicoEnvioEmail é somente um Protocol. Não há implementação ou chamada de envio.
  DesafioGerado é DTO interno com SecretStr, não um schema HTTP; JSON/repr não mostram
  o código. O valor real fica em memória apenas para futura entrega confiável.

## Política e segurança

- secrets.randbelow gera seis dígitos, preservando zeros iniciais.
- HMAC-SHA-256 com segredo do servidor de pelo menos 32 bytes UTF-8. O resumo
  inclui contexto de protocolo, usuário e UUID do desafio, impedindo troca entre desafios.
  Conferência usa hmac.compare_digest, sem hash simples de espaço numérico pequeno.
- Segredo sem valor padrão e exigido apenas para instanciar o novo serviço.
  A API existente continua funcionando sem essa configuração. SecretStr, repr=False
  e ocultação de inputs em erros de configuração evitam exposição acidental.
- Padrões: validade 600s, cinco tentativas incorretas, intervalo de reenvio 60s,
  cinco emissões por janela móvel de 3600s. Limite de tentativas é persistido por desafio.
- Erros de código, inclusive formato inválido, consomem tentativa se o desafio
  estiver disponível. A quinta falha invalida o desafio. Retorno normal confirma
  o contador; não há exceção de negócio que desfaça tentativas incorretas.
- Reenvio e confirmação serializam pelo usuário; a invalidação dos anteriores e
  a inserção do novo são atômicas. Índice parcial único limita um desafio pendente
  (não usado e não invalidado), mesmo que já expirado, por usuário.
- Números já utilizados em desafios da janela recente não são sorteados novamente.
  Até vinte sorteios são tentados; falha preserva o desafio anterior por rollback.
  A janela de exclusão cobre o maior prazo entre validade e janela de emissões.
- Na confirmação, consumo e email_verificado=true são gravados na mesma transação.
  Somente um confirmador concorrente tem sucesso; reutilização retorna falso.
- Usuários ausentes, inativos ou já verificados não recebem novo desafio. Falhas
  de confirmação retornam o mesmo booleano interno. Não há resposta/status HTTP novo
  capaz de revelar existência de conta; uma futura camada HTTP deverá manter respostas
  uniformes de solicitação/reenvio e nunca serializar o resultado interno com o código.
- Persistência contém somente HMAC, referência ao usuário e metadados mínimos;
  sem código, destinatário duplicado, IP ou credencial de provedor.

## Arquivos

Criados, relativos a backend/:

- src/aplicacao/dominio/verificacao_email.py e repositorio_verificacoes.py.
- src/aplicacao/casos_de_uso/contratos_verificacao.py e verificar_email.py.
- src/aplicacao/infraestrutura/codigos_verificacao.py, repositorio_verificacoes.py
  e transacoes_verificacao.py.
- src/aplicacao/infraestrutura/migracoes/versions/0003_criar_verificacoes_email.py.
- testes/unitarios/teste_verificacao_email.py e testes/integracao/teste_verificacao_email.py.

Modificados:

- backend/src/aplicacao/configuracao.py e backend/.env.exemplo: parâmetros opcionais.
- backend/src/aplicacao/infraestrutura/modelos.py: modelo, FK, índices e restrições.
- backend/src/aplicacao/infraestrutura/repositorio_usuarios.py: bloqueio e atualização
  para confirmação, sem alterar consultas/cadastro existentes.
- backend/testes/integracao/teste_migracao.py e teste_postgres_migracao.py: revisão 0003,
  comparação de metadados, reversão exclusiva da 4.1 preservando usuários e sessões.
- backend/testes/e2e/ambiente.py: inclusão da nova tabela na limpeza do banco E2E
  exclusivo, exigida pela FK ao aplicar a migração 0003.
- README.md, este relatório e resultado sanitizado da regressão E2E em
  docs/relatorios/evidencias/fase4/resultado-regressao-e2e.json.

Nenhuma dependência, implementação frontend, endpoint ou credencial Brevo foi adicionada.

## Execução e evidências PostgreSQL

PostgreSQL 18.6 local em 127.0.0.1:55432, bancos isolados linkai_homologacao e
linkai_e2e. Integrações usam schemas aleatórios, migração real e remoção ao final.
Nenhum banco de produção foi acessado. O cluster foi encerrado depois da validação.

Resultados executados:

| Verificação | Resultado |
| --- | --- |
| Pytest completo | **127 aprovados, 1 ignorado** |
| Novos testes | 10 unitários e 14 integrações PostgreSQL |
| Ruff check / format --check | Aprovados |
| Frontend ESLint | Aprovado |
| Frontend Vitest | **29 aprovados** |
| Frontend build/TypeScript | Aprovado |
| Regressão Chromium existente | **10 E2E aprovados** com migração 0003 |
| Alembic pela CLI | **0003 (head) → 0002 → 0003 (head)** |

O teste ignorado permanece a variante SQLite da concorrência da Fase 3; sua
variante PostgreSQL passou. SQLite não substituiu a homologação desta etapa.

Evidências dos novos testes reais:

- Código/HMAC persistido, UTC/prazo, DTO/repr/JSON e logs sem código em claro.
- Código correto usado uma vez; expiração exata e quinto erro bloqueiam confirmação.
- Emissões concorrentes produzem somente um desafio; oito erros concorrentes
  persistem exatamente cinco falhas, sem perda de incremento.
- Duas confirmações concorrentes retornam um sucesso e uma rejeição, com um único consumo.
- Reenvio respeita intervalo e janela de emissões e invalida anteriores. Colisão
  forçada de número é recusada; sorteio indisponível não invalida o desafio anterior.
- Restrição PostgreSQL rejeita dois desafios pendentes, mesmo contornando o serviço.
- Falha de CHECK no usuário reverte tanto consumo quanto alteração do e-mail.
- Trigger PostgreSQL adiado até o COMMIT força falha depois dos writes: ambos
  são revertidos. Removida a falha controlada, o mesmo código confirma normalmente.
- Login continua rejeitando o usuário enquanto o código não for confirmado.
- Migração reversível 0003→0002 preserva usuário e tabela de sessões; avanço e
  comparação de metadados passam. Também passou reversão completa/recriação.

Não foram usados mocks para provar concorrência, transações, índices ou rollback.
Mocks pontuais apenas controlam sorteios para testes determinísticos de colisão.

Um teste antigo procurava a palavra “segredo” no repr da configuração e confundiu
o nome do novo campo com vazamento. O campo foi excluído do repr e a asserção antiga
foi preservada. Continua o aviso Starlette/httpx do TestClient, sem falha da suíte.

## Operação e limites

Variáveis VERIFICACAO_SEGREDO, VERIFICACAO_VALIDADE_SEGUNDOS,
VERIFICACAO_LIMITE_TENTATIVAS, VERIFICACAO_INTERVALO_REENVIO,
VERIFICACAO_LIMITE_ENVIOS e VERIFICACAO_JANELA_ENVIOS estão documentadas no README.
Configure um segredo aleatório forte no ambiente, compartilhado entre processos;
não copie os valores artificiais das fixtures para uso real.

Não há geração automática no cadastro, endpoint de confirmação/reenvio, tela,
envio real, credenciais ou SDK Brevo. As contas públicas continuam não verificadas.
O serviço interno deve ser usado pela futura composição da aplicação, não exposto
como endpoint administrativo. O resultado só é entregue ao chamador após commit.

Para a integração futura: implementar adaptador de envio pelo Protocol, configuração
segura do provedor, tratamento de falhas/retentativas e estratégia de entrega após
commit sem persistir código em claro. Não acoplar transação PostgreSQL a uma chamada
de rede longa. Manter respostas HTTP uniformes, limite por IP e os limites por usuário
já persistidos. Nenhuma dessas funcionalidades foi implementada nesta etapa.

Rotação do segredo invalida os códigos existentes; versionamento de chaves ainda
não foi implementado. Retenção não deve remover histórico dentro da janela de
emissões. Antes de futura alteração de e-mail, invalidar desafios do endereço anterior.
Garantias concorrentes dependem do uso da unidade transacional fornecida e PostgreSQL
com isolamento padrão READ COMMITTED; escrita externa deve respeitar os mesmos bloqueios.

Comandos a partir de backend, com URL_BANCO/URL_BANCO_TESTE locais configuradas:

```bash
alembic upgrade head
alembic current
pytest
pytest testes/unitarios/teste_verificacao_email.py testes/integracao/teste_verificacao_email.py -q
ruff check .
ruff format --check .
```

Frontend permanece executado/testado pelos comandos npm do README. Nenhuma tela nova.

Commit sugerido: `feat: estruturar verificacao de email`.
Não houve avanço para a Etapa 4.2, commits, pushes, deploys ou alterações em produção.

## Etapa 4.2 — Adaptador de envio Brevo (06/11/2026)

### Escopo e decisões

Revisados o Protocol ServicoEnvioEmail, DTO DesafioGerado, transações de verificação,
configuração e dependências antes das alterações. O contrato de retorno None foi
preservado. Nenhuma entidade/caso de uso chama a API Brevo; a implementação está
isolada em infraestrutura/brevo. Não foi alterado cadastro/login, endpoint ou tela.
Nenhuma conta foi criada, plano contratado ou e-mail real enviado.

Foi consultada a documentação primária de [envio transacional](https://developers.brevo.com/reference/send-transac-email)
e [idempotência](https://developers.brevo.com/docs/heterogenous-versions-batch-emails).
HTTPX assíncrono já existia no ambiente de testes e passou a dependência de runtime,
sem adicionar SDK. Endpoint HTTPS fixo, TLS padrão, trust_env=False na factory e
follow_redirects=False para evitar encaminhar credenciais a outra origem.

ConfiguracaoBrevo é separada da configuração geral. Só a ativação explícita da
factory exige chave/remetente. Validação protege a chave contra espaços/controles,
oculta inputs em erros e exclui chave/endereço do repr. Testes com adaptador falso
não exigem configuração Brevo; a API existente continua iniciando sem ela.

O template tem assunto solicitado, saudação neutra, identificação Linkai, código,
prazo absoluto UTC e aviso para ignorar mensagem não solicitada. HTML com tabela
fluida, estilos inline, fonte de 16 px, sem JavaScript ou imagens externas; alternativa
em texto simples. Nome/código/prazo são escapados no HTML. Corpos ficam protegidos
por SecretStr na representação interna, sem senha, sessão ou dados desnecessários.

### Retentativas e resultado

- Padrão de 3 tentativas, timeout HTTP por operação de até 10s e orçamento total
  de 20s por chamada. Prazo restante do código também limita novas tentativas.
- Falhas anteriores ao envio (ConnectError/ConnectTimeout/PoolTimeout) permitem
  nova conexão com backoff limitado. Nenhum transporte com retries extras é configurado.
- 429 respeita Retry-After em segundos ou data HTTP. Ausente/inválido usa backoff.
  Espera maior que o orçamento interrompe a chamada, sem reenviar antes do permitido.
- 4xx permanentes, incluindo chave inválida 401/403: sem repetição.
- 5xx/408, erros de leitura/escrita e resposta ambígua: indeterminado e sem retentativa.
  É uma escolha conservadora para não duplicar uma operação possivelmente aceita.
- Somente 201 com messageId não vazio confirma aceitação. 201 incompleto, JSON
  inválido, 200/202/redirect, duplicate_parameter e 409 não confirmam envio.
- Payload e UUID em headers.idempotencyKey são estáveis em toda tentativa.
  A documentação de idempotência descreve batch e TTL de 30 minutos. Não se presume
  garantia comprovada para este adaptador; duplicatas manuais/concorrentes permanecem
  possíveis. Não existe controle durável de envios nem garantia exactly-once nesta etapa.
- O retorno None representa somente aceitação pela API, não entrega no destinatário.
  O identificador não é persistido e não há webhook de entrega.

As exceções de aplicação são permanentes, temporárias, indeterminadas ou de
configuração, com mensagens neutras. Não carregam respostas ou destinatários em
atributos próprios. O adaptador não faz logging de payload/chaves/código.
Ele não abre transação PostgreSQL; a futura composição deverá chamar o envio após
o serviço de geração devolver o desafio, quando o commit já terminou.

### Arquivos

Criados, relativos a backend/:

- src/aplicacao/casos_de_uso/erros_envio_email.py — falhas independentes de provedor.
- src/aplicacao/infraestrutura/brevo/__init__.py.
- src/aplicacao/infraestrutura/brevo/configuracao.py — configuração opcional.
- src/aplicacao/infraestrutura/brevo/template.py — HTML e texto.
- src/aplicacao/infraestrutura/brevo/envio.py — HTTPS e política de falhas.
- src/aplicacao/infraestrutura/brevo/fabrica.py — ciclo de vida do cliente.
- testes/unitarios/teste_envio_brevo.py — transporte HTTP simulado, sem rede externa.

Modificados: backend/pyproject.toml, backend/.env.exemplo, README.md e este relatório.
Adicionada evidência sanitizada da regressão em
evidencias/fase4/resultado-regressao-e2e-brevo.json. Nenhuma migração nova.

### Validações observadas

- Pytest completo com PostgreSQL **18.6** na regressão: **173 aprovados, 1 ignorado**.
  O ignorado permanece a variante SQLite de concorrência da Fase 3, não a integração real.
- **46 testes novos** cobrem payload, 201, contrato 4.1, template/escape, configuração
  ausente/inválida, timeout, conexão, 429, 500/503, 400/401/403, orçamentos, resposta
  incompleta, duplicata indeterminada, estabilidade de payload e ausência de segredos.
- Retry-After enorme não é truncado nem ignorado; 429 persistente encerra após três
  tentativas. Orçamento total cancela resposta tardia sem confirmar sucesso.
- Logs do teste de payload foram capturados em DEBUG, sem chave, código, destinatário
  ou conteúdo. Erros simulados com segredos no corpo não os expõem nas mensagens.
- Ruff check e format --check aprovados.
- Frontend: ESLint, **29 testes**, build/TypeScript aprovados.
- Regressão E2E Chromium existente: **10 aprovados**, sem ativar o adaptador ou
  realizar envio externo. [Resultado](evidencias/fase4/resultado-regressao-e2e-brevo.json).
- Permanece aviso Starlette/httpx no TestClient; nenhuma falha de teste pendente.

Todos os testes de envio usam MockTransport; isso não comprova integração em conta
real nem entrega. PostgreSQL e Chromium foram usados apenas na regressão existente.
Não foram utilizadas credenciais reais ou consumida cota de e-mail durante pytest.
O cluster isolado foi desligado após os testes. Não houve acesso a produção.

### Configuração, plano gratuito e pendências

Variáveis: BREVO_API_KEY, BREVO_EMAIL_REMETENTE, BREVO_NOME_REMETENTE,
BREVO_TIMEOUT_SEGUNDOS, BREVO_LIMITE_TENTATIVAS e BREVO_TEMPO_TOTAL_SEGUNDOS.
O .env.exemplo contém só placeholders comentados e parâmetros seguros; o README
contém comandos de instalação/teste, política de falhas e orientação de composição.

Para operação futura, cadastrar e validar o remetente no painel e autenticar o
domínio conforme os registros fornecidos. [Guia do remetente](https://help.brevo.com/hc/en-us/articles/208836149-Create-a-new-sender-From-name-and-From-email)
e [guia de domínio](https://help.brevo.com/hc/en-us/articles/12163873383186-Authenticate-your-domain-with-Brevo-Brevo-code-DKIM-DMARC).
O plano [Free consultado](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans)
oferece 300 envios/dia sem acumulação. Nenhum recurso pago, compra de créditos,
IP dedicado, fila externa ou trial foi configurado; monitoramento da cota é operacional.

Pendências 4.3: composição após commit; controle durável para envios concorrentes
e reconciliação de resultados incertos; estratégia de entrega/retentativas sem
guardar código em claro; tratamento público uniforme; confirmação/reenvio públicos
somente quando autorizados. Não repetir cegamente uma falha indeterminada.
Ainda falta homologação autorizada com remetente real e clientes de e-mail.
Não há evidência de entrega real, proteção durável contra duplicatas entre chamadas
ou renderização efetiva em Gmail/Outlook nesta entrega.

Commit sugerido: `feat: integrar envio de emails com brevo`.
Sem avanço para endpoints, frontend ou Etapa 4.3. Nenhum commit, push ou deploy.

## Etapa 4.3 — Cadastro, confirmação e reenvio (06/11/2026)

### Diagnóstico e decisões

Inspecionados cadastro, contratos, transações de verificação, SQLAlchemy, limites,
composição FastAPI e Brevo antes das alterações. A API ainda não gerava desafios
ou intenções; o envio era um adaptador opcional. Não havia outbox/worker durável.

O cadastro público mantém 202 e corpo anteriores. Composição injeta geração de
desafio e agendamento na mesma AsyncSession: usuário, HMAC e envelope cifrado
são commitados juntos. Duplicata não gera intenção, mesmo não verificada; reenvio
é explícito. Falha de persistência/commit retorna 503 sem cadastro parcial.
Nenhuma sessão é criada no cadastro ou confirmação.

Novos contratos:

| Endpoint | Entrada | Saída |
| --- | --- | --- |
| POST /api/autenticacao/verificar-email | email normalizado, codigo string de 6 dígitos ASCII | 200 e mensagem de confirmação; 400 genérico para incorreto/expirado/usado/conta indisponível |
| POST /api/autenticacao/reenviar-codigo | email normalizado | 202 neutro para existente/inexistente/verificado/cooldown |

Erros de validação são 422, limite 429/Retry-After e banco indisponível 503.
Mensagens não refletem códigos ou existência de contas; confirmação válida prova
posse do código, sem autenticar. O contador de erros é commitado mesmo na resposta 400.
Confirmações concorrentes têm um sucesso; reutilização é recusada.
Validade, tentativas e controles de reenvio da 4.1 foram preservados.

### Outbox

Migração 0004 cria outbox_email e limites_requisicoes, com PK/FK, índices para
reserva/prazo e restrições de estados/contadores. Nenhum código em claro na outbox:
Fernet da biblioteca cryptography protege destinatário e DTO, com autenticação e
vínculo do UUID do desafio no envelope. Uma intenção por desafio, pela PK/FK.
HMAC e cifra usam chaves diferentes, somente no ambiente. Nenhuma criptografia própria.

O domínio define a reserva/contrato; aplicação ProcessarEmails coordena envio por
Protocol. Infraestrutura implementa persistência/leases, cifra e CLI. Nenhuma
entidade importa aplicação, FastAPI ou SQLAlchemy. O cadastro usa uma porta assíncrona,
e o serviço de verificação recebe um agendador abstrato no contexto transacional.

Reserva com SKIP LOCKED é commitada; preflight com bloqueio do usuário valida
estado atual, desafio e token de posse e marca envio_iniciado_em, também commitado.
Não há transação aberta enquanto o serviço externo é chamado. O resultado é gravado
em outra transação, condicionado à posse. Estado/posse impedem ack de worker obsoleto.

- pendente → processando → enviada/falha/indeterminada/cancelada.
- Temporário conhecido → pendente com backoff limitado e Retry-After preservado.
- Lease expirado antes do início → retomável; depois do início → indeterminada.
- Cancelamento durante envio → indeterminada, sem repetição.
- Verificação usada, expirada, inválida ou usuário já verificado/inativo → cancelada.
- Envelope removido em todo estado terminal. Logs não recebem conteúdo, código,
  credenciais, resposta externa ou endereço do destinatário.

Aceitação Brevo não prova entrega. A marcação anterior ao HTTPS deixa uma janela
de incerteza deliberada: queda ali pode não ter enviado nada, mas não se repete
automaticamente. Queda após aceitação antes do ack também não repete. Não há
garantia de exactly-once/at-least-once; prioriza-se evitar duplicação cega.
E-mails já em voo podem chegar com código invalidado por reenvio, sem poder confirmar.

### Segurança e configuração

HMAC VERIFICACAO_SEGREDO passa a ser necessário ao limitador persistente de
cadastro/login/confirmar/reenvio. OUTBOX_CHAVE, Fernet estável, é exigida para
cadastro/reenvio e worker; confirmação não depende da cifra ou do Brevo.
Não há fallback de chaves efêmeras na aplicação: configuração ausente falha segura.
Fixtures fornecem chaves aleatórias por teste, e o E2E usa somente chaves efêmeras
nos processos de homologação, sem persistir valores em arquivos versionados.

Contadores PostgreSQL por IP/rota usam HMAC e UPSERT atômico, commitado antes de
processar o corpo, incluindo requisições inválidas. Operam entre processos;
limitador em memória permanece como proteção complementar. Origem HTTP presente
e não permitida é rejeitada; CORS explícito, cookies e CSRF existentes foram preservados.
Login/logout mantêm sua exigência de Origin. Rotas públicas não exigem cookie.

Novos parâmetros: OUTBOX_CHAVE, OUTBOX_LEASE_SEGUNDOS=120,
OUTBOX_LIMITE_TENTATIVAS=5, OUTBOX_INTERVALO_WORKER=1 e
VERIFICACAO_LIMITE_REQUISICOES=20 por 15 minutos. Limites de cadastro/login preservados.
Lease precisa superar o orçamento HTTPS + 15s. Worker reutiliza BREVO_* da 4.2.
Backoff é 30s exponencial, limitado a 900s; respeita esperas maiores do provedor
ou encerra se o código expirar. No máximo cinco ciclos por mensagem, por padrão.

### Execução e interrupção

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn aplicacao.principal:app --reload --no-proxy-headers
```

Em outro terminal com o mesmo banco/chaves e BREVO_* configurado:

```bash
python -m aplicacao.infraestrutura.worker_emails
```

Esse comando pode enviar e-mails reais quando configurado. Não foi executado com
Brevo real durante os testes. Ctrl+C/SIGINT e SIGTERM solicitado deixam de consumir
e aguardam operação corrente; encerramento forçado é tratado pelo lease na retomada.
Sinais são configurados pela CLI; testes cobrem cancelamento/leases, não um processo
real habilitado com credenciais Brevo. Perda/rotação da chave pode impedir a leitura
de pendências; operação deve preservar chaves ou solicitar novos desafios.

### Validações observadas

PostgreSQL **18.6**, bancos locais exclusivos linkai_homologacao e linkai_e2e.
Fixtures usam migrações reais/schemas isolados; nenhum banco de produção.

- **196 testes backend aprovados, 1 ignorado**. O ignorado permanece a variante
  SQLite de concorrência da Fase 3; os novos testes transacionais são PostgreSQL.
- 23 testes novos: 20 casos PostgreSQL e 3 unitários de cifra/chave.
- Cadastro novo/duplicado/concorrente: 202 uniforme, um usuário/desafio/intenção.
- Confirmação válida/inválida/expirada/usada; cinco erros persistidos; login
  bloqueado antes e permitido após confirmação explícita, sem cookie automático.
- Reenvio inexistente e existente: mesma resposta; cooldown e três reenvios
  concorrentes criam somente um novo desafio e cancelam a intenção anterior.
- Falha na inserção da outbox reverte tudo; trigger adiado até o COMMIT também
  reverte usuário, desafio e intenção e não devolve sucesso antecipado.
- Duas instâncias compartilham o limite persistente. Origem hostil não enfileira.
- Dois workers reais sobre PostgreSQL processam a mesma intenção uma única vez.
- Interrupção antes/depois de início simula lease expirado no banco; retomada ou
  indeterminação corretas e ack antigo sem efeito. Cancelamento não reenvia.
- Sender falso consulta pg_stat_activity durante envio: nenhuma conexão idle in
  transaction. Conteúdo removido após terminal; cifra adulterada/trocada de registro recusada.
- Brevo via MockTransport: 201 aceito, 400 terminal, 503 indeterminado, 429 reprogramado.
  Retry-After de 80s foi respeitado; limite de ciclos encerra e remove conteúdo.
- Ruff check e format --check aprovados.
- Frontend: **29 testes**, ESLint, build/TypeScript e Prettier aprovados; tipos E2E aprovados.
- **10 E2E Chromium existentes aprovados**, sem iniciar worker ou realizar envio externo.
- Alembic pela CLI: **0004 (head) → 0003 → 0004 (head)**. Teste automatizado
  preserva desafio/usuário ao reverter somente 0004 e compara metadados após recriar.
- Permanece aviso de depreciação Starlette/httpx; nenhuma falha de teste pendente.

Testes de Brevo usam somente mocks; não comprovam entrega. Nenhum e-mail real foi
enviado ou credencial real usada. API/Vite e cluster local foram encerrados ao final.
Resultado sanitizado: [regressão E2E](evidencias/fase4/resultado-regressao-e2e-4.3.json).

### Arquivos

Criados em backend/src/aplicacao:

- dominio/entrega_email.py.
- casos_de_uso/contratos_entrega.py, processar_emails.py e solicitacoes_email.py.
- infraestrutura/agendador_email.py, cifra_outbox.py, composicao_verificacao.py,
  limite_persistente.py, repositorio_entregas.py e worker_emails.py.
- infraestrutura/migracoes/versions/0004_criar_outbox.py.
- apresentacao/protecao_persistente.py, schemas_verificacao.py e rotas/verificacao_email.py.

Modificados no backend: configuração, modelos, repositório de usuários para
releitura sob bloqueio, cadastro e suas dependências, contexto/serviço de verificação,
registro de rotas/middlewares e validação de erros. Exceção temporária e adaptador
Brevo propagam Retry-After numérico ao worker, sem detalhes sensíveis.
pyproject.toml adiciona cryptography; .env.exemplo documenta parâmetros.

Testes: novo conftest.py, teste_fluxo_email.py e teste_cifra_outbox.py; migrações e
fixture E2E ajustadas para novas tabelas. frontend/playwright.config.ts recebe
somente chaves de teste; nenhuma interface React foi alterada. README e este
relatório atualizados, com JSON sanitizado da regressão.

### Limites e Etapa 4.4

Ainda não há interface React para confirmar/reenviar, reconciliação automática de
indeterminadas, webhook de entrega ou homologação autorizada em conta Brevo real.
Retenção de outbox/contadores e rotação de chaves precisam de operação planejada.
Não remover histórico de verificações dentro da janela nem reenviar manualmente
mensagens indeterminadas às cegas. Logs operacionais são neutros; o estado da fila
é consultável por contagens, sem expor destinatários/códigos.

O fluxo está homologado localmente nos cenários executados, sem garantia de entrega
real. Pendências de HTTPS/outros navegadores/dispositivos e auditoria de ferramentas
das fases anteriores continuam válidas. Etapa 4.4 não iniciada.

Commit sugerido: `feat: implementar confirmacao de email`.
Nenhum commit, push, deploy ou alteração em produção foi realizado.

## Etapa 4.4 — Experiência frontend de verificação de e-mail

Homologação local em 06/11/2026. Esta seção complementa os registros históricos
anteriores: a interface de confirmação/reenvio agora está implementada. Escopo
restrito a frontend, testes e documentação; backend, endpoints, outbox, worker,
migrações, autenticação, CORS e CSRF foram preservados.

### Fluxo e contratos utilizados

- Cadastro aceita somente HTTP 202, limpa senha e navega para `/verificar-email`.
  E-mail normalizado e prazo inicial ficam somente em memória, sem URL/history state.
  A mensagem condiciona instruções à elegibilidade; não afirma conta criada ou envio.
- Rota pública independente da sessão, disponível por acesso direto ou reload.
  Sem contexto em memória, solicita e-mail novamente; o código inicia vazio.
- Confirmação: POST `/api/autenticacao/verificar-email`, JSON email/codigo.
  Somente 200 permite sucesso; 400 produz uma única mensagem neutra para código
  incorreto/expirado/usado/indisponível e limpa o campo. 422 associa erros conhecidos;
  429 e indisponibilidade/rede usam o tratamento central HTTP existente.
- Sucesso limpa código/e-mail em memória, orienta login e fornece link. Nenhum
  login automático ou manipulação de cookies foi acrescentado.
- Reenvio: POST `/api/autenticacao/reenviar-codigo`, JSON email, exige 202.
  Mensagem neutra sem promessa de entrega imediata; código anterior é limpo no sucesso.
  Erros de rede liberam nova tentativa. Mutex síncrono no hook impede requisições
  simultâneas entre confirmar e reenviar, além dos botões/campos desabilitados.

### Decisões de arquitetura e UX

Serviço de verificação separado valida contratos de resposta e mapeia o 400
específico; hook cuida do estado/validação, cooldown e envio; página apenas compõe
os componentes existentes. Não foram adicionadas bibliotecas. Campo único de texto
com inputMode numeric, autocomplete one-time-code, seis dígitos ASCII e colagem
completa evita a complexidade de seis campos. CampoTexto, Botao, Feedback,
EstruturaAcesso e LinkInterno preservam os temas e Design System existentes.

Erros próximos aos campos usam aria-invalid/aria-describedby, com foco no primeiro
campo inválido. Feedback recebe foco; formulário indica aria-busy. O timer pode
ser consultado, mas não anuncia cada segundo; uma região de status anuncia a
liberação. A navegação mantém título e foco no h1 e as rotas privadas existentes.

VITE_VERIFICACAO_INTERVALO_REENVIO padrão 60 deve acompanhar
VERIFICACAO_INTERVALO_REENVIO. O contrato 202 não oferece prazo; usa-se o valor
documentado. O cliente HTTP interpreta Retry-After numérico ou data se acessível.
CORS existente não expõe esse cabeçalho para origens distintas; nesse caso usa-se
o intervalo configurado, sem alterar o backend nesta etapa. Recarregar perde o
contador local, enquanto cooldown, janela e rate limiting PostgreSQL permanecem
autoritativos. Não há tentativa de tornar o contador frontend proteção definitiva.

### Arquivos criados e modificados

Criados:

- frontend/src/paginas/PaginaVerificacaoEmail.tsx.
- frontend/src/funcionalidades/autenticacao/verificacao.ts e usarVerificacaoEmail.ts.
- frontend/src/testes/VerificacaoEmail.test.tsx.
- frontend/e2e/verificacao-email.spec.ts.
- Evidências sanitizadas em evidencias/fase4/interface4.4, sem códigos/credenciais.

Modificados:

- frontend/src/funcionalidades/autenticacao/usarFormularioAutenticacao.ts: contexto
  transitório e navegação após 202.
- frontend/src/navegacao/RotasAplicacao.tsx: rota pública e título.
- frontend/src/servicos/http.ts: campo codigo e Retry-After opcional no erro.
- frontend/.env.exemplo: intervalo de reenvio documentado.
- frontend/src/testes/Autenticacao.test.tsx e frontend/e2e/autenticacao.spec.ts:
  expectativas atualizadas para o novo redirecionamento, preservando regressões.
- frontend/e2e/relator.ts: destino de evidências configurável por
  E2E_PASTA_EVIDENCIAS, evitando sobrescrever homologações anteriores.
- README.md e este relatório.

### Testes efetivamente executados

| Verificação | Resultado |
| --- | --- |
| npm run test | 46 aprovados, incluindo 17 novos casos de verificação |
| npm run lint | Aprovado |
| npm run build | TypeScript e Vite aprovados |
| npm run format:check | Aprovado |
| npm run test:e2e:tipos | Aprovado |
| npm run test:e2e | 14 aprovados no Chromium real, 10 existentes e 4 novos |
| pytest -q | 196 aprovados, 1 ignorado, PostgreSQL 18.6 real |
| ruff check . | Aprovado |
| ruff format --check . | 86 arquivos formatados |

O ignorado permanece a variante de concorrência SQLite anterior; os testes de
concorrência/transações PostgreSQL foram executados. Aviso conhecido de depreciação
Starlette/httpx permanece. API/Vite usaram bancos locais exclusivos linkai_e2e e
linkai_homologacao; nenhum banco de produção. Chaves de teste geradas em memória.
Worker não iniciado, sem chamadas ou envio de e-mails reais. Os novos E2E usam
respostas simuladas dos endpoints; não comprovam entrega nem substituem os testes
backend reais de confirmação/concorrência da regressão.

Testes cobrem redirecionamento 202, campos vazios/formatos inválidos, e-mail
normalizado, confirmação, códigos incorretos/expirados/usados com mesmo retorno,
loading e bloqueio de duplicatas, reenvio/cooldown, Retry-After, falhas de rede,
limpeza de dados, ausência de armazenamento, login, reload, teclado e temas.
Chromium validou colagem completa pela área de transferência, navegação por Tab e
Enter, recuperação após reload, erro/rede/loading e reenvio. Testes anteriores
continuam verificando cookies HttpOnly, CSRF, CORS, logout/revogação e falha do banco.

Primeira execução E2E identificou erro de codificação em uma mensagem esperada
no teste adaptado; corrigido e a suíte completa repetida com 14 aprovações.
O comando npm.ps1 foi bloqueado pela política do PowerShell; usou-se npm.cmd.
Esbuild exigiu execução aprovada fora do sandbox. PostgreSQL foi iniciado em
127.0.0.1:55432, pois a porta padrão estava indisponível; não foi reconfigurada.
API/Vite foram encerrados pelo Playwright e o cluster isolado foi encerrado após
as validações. As capturas mobile claro e desktop escuro também foram inspecionadas visualmente.

### Evidências de responsividade e acessibilidade

Chromium 158.0.8127.18, larguras 375, 768 e 1440, altura 900, temas claro/escuro.
As seis combinações apresentaram ausência de overflow, campos com fonte ≥16 px,
alvos de campos/botões ≥44 px e foco visível no código por teclado.
Contrastes medidos: botão 5,36:1; texto principal 17,04:1 claro/18,40:1 escuro;
link 5,13:1 claro/10,40:1 escuro. Todos esses elementos superam WCAG AA de 4,5:1.
Não se declara auditoria WCAG completa ou teste com leitor de tela real.

- [Resultado E2E](evidencias/fase4/interface4.4/resultado-e2e.json).
- [Medições de verificação](evidencias/fase4/interface4.4/verificacao-layout.json).
- [Celular claro](evidencias/fase4/interface4.4/verificacao-375-claro.png).
- [Celular escuro](evidencias/fase4/interface4.4/verificacao-375-escuro.png).
- [Tablet claro](evidencias/fase4/interface4.4/verificacao-768-claro.png).
- [Desktop escuro](evidencias/fase4/interface4.4/verificacao-1440-escuro.png).

### Execução local, limites e Etapa 4.5

Inicie PostgreSQL/API conforme a seção 4.3 do README, com chaves estáveis e
alembic upgrade head. Em frontend, copie .env.exemplo para .env, alinhe URL e
intervalo ao backend, execute npm install e npm run dev. Abra /cadastro ou
/verificar-email; após reload informe o e-mail novamente. Login só ocorre pela
tela própria depois da confirmação explícita.

Para regressão: execute os comandos da tabela, com URL_BANCO_TESTE e URL_BANCO_E2E
apontando para bancos locais exclusivos. PLAYWRIGHT_BROWSERS_PATH pode apontar
para a instalação local de Chromium. Configure E2E_PASTA_EVIDENCIAS para preservar
os registros anteriores. Não iniciar worker nos testes automatizados.

Testar entrega real exige conta/configuração Brevo autorizada e execução explícita
do worker, que envia e-mails reais. Isso não foi realizado. Permanecem pendentes
para planejamento da 4.5: entrega ponta a ponta autorizada, HTTPS, navegadores e
dispositivos adicionais, leitores de tela reais e acompanhamento operacional.
Limites/rotação/reconciliação descritos na 4.3 continuam válidos. A API permanece
autoridade de segurança quando o estado em memória é perdido.

Nenhuma migração, endpoint ou funcionalidade da Etapa 4.5 foi implementada.
Nenhum commit, push ou deploy foi realizado.
Commit sugerido: `feat: criar fluxo de verificacao de email`.
