from typing import Annotated

from fastapi import APIRouter, Depends

from aplicacao.apresentacao.dependencias_cadastro import obter_cadastro
from aplicacao.apresentacao.schemas_cadastro import CadastroEntradaHTTP, CadastroSaidaHTTP
from aplicacao.casos_de_uso.cadastrar_usuario import CadastrarUsuario

roteador_cadastro = APIRouter(tags=["Autenticação"])


@roteador_cadastro.post("/autenticacao/cadastro", status_code=202, response_model=CadastroSaidaHTTP)
async def cadastrar_usuario(
    entrada: CadastroEntradaHTTP,
    cadastro: Annotated[CadastrarUsuario, Depends(obter_cadastro, scope="function")],
) -> CadastroSaidaHTTP:
    await cadastro.executar(entrada)
    return CadastroSaidaHTTP()
