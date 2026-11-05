from typing import Protocol


class ServicoHashSenha(Protocol):
    async def gerar(self, senha: str) -> str: ...
