import secrets

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def segredos_locais_de_teste(monkeypatch):
    # Somente fixtures: nunca criar segredos transitórios na aplicação real.
    monkeypatch.setenv("VERIFICACAO_SEGREDO", secrets.token_urlsafe(32))
    monkeypatch.setenv("OUTBOX_CHAVE", Fernet.generate_key().decode())
