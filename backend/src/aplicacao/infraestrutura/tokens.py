import hashlib
import hmac
import secrets


class TokensSeguros:
    def gerar(self) -> str:
        return secrets.token_urlsafe(32)

    def resumir(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def gerar_csrf(self, token: str) -> str:
        return hmac.new(token.encode("utf-8"), b"linkai-csrf-v1", hashlib.sha256).hexdigest()

    def verificar_csrf(self, token: str, csrf: str) -> bool:
        if len(csrf) != 64 or not csrf.isascii():
            return False
        return hmac.compare_digest(self.gerar_csrf(token), csrf)
