# Evidências da homologação local — Etapa 3.5

Chromium real via Playwright, API FastAPI e PostgreSQL 18.6 exclusivos de teste.
Resultado final e duração: [resultado-e2e.json](resultado-e2e.json).
Versão do navegador e viewport: [ambiente-navegador.json](ambiente-navegador.json).
Contraste medido: [medidas-layout.json](medidas-layout.json).

As capturas foram feitas sem credenciais preenchidas. A faixa colorida nas imagens
da conta é uma máscara de privacidade sobre o e-mail da fixture, aplicada pelo
Playwright; não faz parte da interface. Não há cookies, tokens ou senha nos artefatos.

| Largura | Tema | Cadastro | Login | Conta |
| --- | --- | --- | --- | --- |
| 375 px | Claro | [Imagem](cadastro-375-claro.png) | [Imagem](login-375-claro.png) | [Imagem](conta-375-claro.png) |
| 375 px | Escuro | [Imagem](cadastro-375-escuro.png) | [Imagem](login-375-escuro.png) | [Imagem](conta-375-escuro.png) |
| 768 px | Claro | [Imagem](cadastro-768-claro.png) | [Imagem](login-768-claro.png) | [Imagem](conta-768-claro.png) |
| 768 px | Escuro | [Imagem](cadastro-768-escuro.png) | [Imagem](login-768-escuro.png) | [Imagem](conta-768-escuro.png) |
| 1440 px | Claro | [Imagem](cadastro-1440-claro.png) | [Imagem](login-1440-claro.png) | [Imagem](conta-1440-claro.png) |
| 1440 px | Escuro | [Imagem](cadastro-1440-escuro.png) | [Imagem](login-1440-escuro.png) | [Imagem](conta-1440-escuro.png) |

O teste verifica largura do documento, caixas dos controles, fonte dos campos,
foco via teclado e contraste do botão principal. As imagens complementam as
asserções; não representam auditoria completa de acessibilidade WCAG.
Sidebar e menu lateral mobile não existem no escopo atual e não foram adicionados.
