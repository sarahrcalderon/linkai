import hashlib
import hmac
import secrets
from uuid import UUID

from pydantic import SecretStr


class CodigosVerificacaoHMAC:
    def __init__(self, segredo: SecretStr) -> None:
        if len(segredo.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("Configure um segredo de verificação com pelo menos 32 bytes.")
        self._segredo = segredo

    def gerar(self) -> str:
        return f"{secrets.randbelow(1000000):06d}"

    def resumir(self, codigo: str, desafio_id: UUID, usuario_id: UUID) -> str:
        mensagem = f"linkai-email-v1:{usuario_id}:{desafio_id}:{codigo}".encode()
        return hmac.new(
            self._segredo.get_secret_value().encode(), mensagem, hashlib.sha256
        ).hexdigest()

    def conferir(self, codigo: str, resumo: str, desafio_id: UUID, usuario_id: UUID) -> bool:
        if len(codigo) != 6 or not codigo.isascii() or not codigo.isdecimal():
            return False
        return hmac.compare_digest(self.resumir(codigo, desafio_id, usuario_id), resumo)
