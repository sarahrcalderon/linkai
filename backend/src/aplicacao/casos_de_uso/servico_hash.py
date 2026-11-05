from typing import Protocol


class ServicoHashSenha(Protocol):
    async def gerar(self, senha: str) -> str: ...

    async def verificar(self, senha_hash: str, senha: str) -> bool: ...
