"""Diagnóstico por lista permitida: nunca registra corpos, mensagens ou cabeçalhos."""

import logging

import httpx

registrador = logging.getLogger(__name__)
CODIGOS_SEGUROS = frozenset(
    {
        "invalid_parameter",
        "missing_parameter",
        "out_of_range",
        "unauthorized",
        "permission_denied",
        "duplicate_parameter",
        "document_not_found",
        "method_not_allowed",
        "not_acceptable",
        "too_many_requests",
        "internal_error",
    }
)


def registrar_falha(
    resultado: str, resposta: httpx.Response | None = None, categoria: str | None = None
) -> None:
    status = resposta.status_code if resposta is not None else None
    codigo = None
    if resposta is not None:
        try:
            dados = resposta.json()
        except ValueError:
            dados = None
        candidato = dados.get("code") if isinstance(dados, dict) else None
        if isinstance(candidato, str) and candidato in CODIGOS_SEGUROS:
            codigo = candidato
    if categoria is None:
        categoria = {
            400: "dados_invalidos",
            401: "autenticacao",
            403: "permissao",
            429: "limite_requisicoes",
        }.get(status, "provedor" if status is not None and status >= 500 else "resposta_http")
    registrador.warning(
        "envio_email_falhou status_http=%s codigo_provedor=%s categoria=%s resultado=%s",
        status,
        codigo,
        categoria,
        resultado,
        extra={
            "status_http": status,
            "codigo_provedor": codigo,
            "categoria": categoria,
            "resultado": resultado,
        },
    )
