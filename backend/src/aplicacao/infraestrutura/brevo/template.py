from dataclasses import dataclass, field
from datetime import UTC
from html import escape

from pydantic import SecretStr

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.casos_de_uso.erros_envio_email import EnvioEmailPermanente


@dataclass(frozen=True)
class MensagemVerificacao:
    assunto: str
    html: SecretStr = field(repr=False)
    texto: SecretStr = field(repr=False)


def montar_template(desafio: DesafioGerado, nome_remetente: str) -> MensagemVerificacao:
    codigo = desafio.codigo.get_secret_value()
    if (
        len(codigo) != 6
        or not codigo.isascii()
        or not codigo.isdecimal()
        or desafio.expira_em.tzinfo is None
    ):
        raise EnvioEmailPermanente()
    prazo = desafio.expira_em.astimezone(UTC).strftime("%d/%m/%Y às %H:%M UTC")
    nome_html, codigo_html, prazo_html = map(escape, (nome_remetente, codigo, prazo))
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="margin:0;background:#f8fafc;font-family:Arial,sans-serif;color:#0f172a">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">
<table role="presentation" width="100%" cellpadding="24" cellspacing="0"
style="max-width:520px;background:#ffffff;border:1px solid #cbd5e1">
<tr><td style="font-size:24px;font-weight:bold;color:#047857">{nome_html}</td></tr>
<tr><td style="font-size:16px;line-height:1.6">Olá,<br>
Para confirmar seu e-mail no Linkai, utilize este código:
<p style="font-size:32px;font-weight:bold;letter-spacing:6px;color:#047857">{codigo_html}</p>
<p>Este código expira em {prazo_html} e pode ser utilizado uma única vez.</p>
<p>Se você não solicitou o cadastro, ignore esta mensagem.</p>
</td></tr></table></td></tr></table></body></html>"""
    texto = (
        f"{nome_remetente}\n\nOlá,\nPara confirmar seu e-mail no Linkai, utilize o código: "
        f"{codigo}\nEste código expira em {prazo} e pode ser utilizado uma única vez.\n"
        "Se você não solicitou o cadastro, ignore esta mensagem."
    )
    return MensagemVerificacao("Confirme seu e-mail — Linkai", SecretStr(html), SecretStr(texto))
