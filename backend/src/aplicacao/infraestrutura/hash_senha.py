from anyio import CapacityLimiter, to_thread
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError


class HashSenhaArgon2id:
    def __init__(self) -> None:
        self.gerador = PasswordHasher(type=Type.ID)
        self.limitador = CapacityLimiter(2)

    async def gerar(self, senha: str) -> str:
        return await to_thread.run_sync(self.gerador.hash, senha, limiter=self.limitador)

    async def verificar(self, senha_hash: str, senha: str) -> bool:
        try:
            return await to_thread.run_sync(
                self.gerador.verify, senha_hash, senha, limiter=self.limitador
            )
        except (VerificationError, InvalidHashError):
            return False
