from typing import Literal

from pydantic import BaseModel

from aplicacao.casos_de_uso.solicitacoes_email import EntradaConfirmacao, EntradaReenvio


class ReenvioEntradaHTTP(EntradaReenvio):
    pass


class ConfirmacaoEntradaHTTP(EntradaConfirmacao):
    pass


class ReenvioSaidaHTTP(BaseModel):
    mensagem: Literal["Solicitação recebida. Se aplicável, um código será enviado."] = (
        "Solicitação recebida. Se aplicável, um código será enviado."
    )


class ConfirmacaoSaidaHTTP(BaseModel):
    mensagem: Literal["E-mail verificado. Entre na sua conta para continuar."] = (
        "E-mail verificado. Entre na sua conta para continuar."
    )
