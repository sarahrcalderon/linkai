from typing import Literal

from pydantic import BaseModel

from aplicacao.casos_de_uso.contratos_cadastro import EntradaCadastro


class CadastroEntradaHTTP(EntradaCadastro):
    pass


class CadastroSaidaHTTP(BaseModel):
    mensagem: Literal[
        "Solicitação recebida. A verificação de e-mail será necessária para acessar a conta."
    ] = "Solicitação recebida. A verificação de e-mail será necessária para acessar a conta."
