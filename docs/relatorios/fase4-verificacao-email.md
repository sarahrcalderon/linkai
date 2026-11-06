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
