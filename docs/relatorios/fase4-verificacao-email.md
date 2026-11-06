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
