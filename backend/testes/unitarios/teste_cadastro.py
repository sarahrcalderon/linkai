import pytest
from argon2 import PasswordHasher, Type, extract_parameters
from pydantic import ValidationError

from aplicacao.casos_de_uso.cadastrar_usuario import CadastrarUsuario
from aplicacao.casos_de_uso.contratos_cadastro import EntradaCadastro
from aplicacao.infraestrutura.hash_senha import HashSenhaArgon2id


async def test_hash_argon2id_com_salt_aleatorio():
    servico = HashSenhaArgon2id()
    senha = "frase longa de teste"
    primeiro = await servico.gerar(senha)
    segundo = await servico.gerar(senha)
    assert primeiro != segundo
    parametros = extract_parameters(primeiro)
    assert parametros.type == Type.ID
    assert parametros.memory_cost >= 19456 and parametros.time_cost >= 2
    assert PasswordHasher().verify(primeiro, senha)


def test_dto_oculta_senha_e_normaliza():
    entrada = EntradaCadastro(nome=" Ana ", email=" ANA@EXAMPLE.COM ", senha="frase longa secreta")
    assert entrada.nome == "Ana" and entrada.email == "ana@example.com"
    assert "frase longa secreta" not in repr(entrada)
    assert "frase longa secreta" not in entrada.model_dump_json()


def test_dto_nao_reflete_valores_em_excecoes():
    with pytest.raises(ValidationError) as erro:
        EntradaCadastro(nome="Ana", email="segredo-invalido", senha="senha-curta")
    assert "segredo-invalido" not in str(erro.value)
    assert "senha-curta" not in str(erro.value)


async def test_caso_de_uso_propaga_falha_de_persistencia():
    class RepositorioComFalha:
        async def adicionar(self, usuario):
            raise RuntimeError("falha controlada")

    caso = CadastrarUsuario(RepositorioComFalha(), HashSenhaArgon2id())
    with pytest.raises(RuntimeError, match="falha controlada"):
        await caso.executar(
            EntradaCadastro(nome="Ana", email="ana@example.com", senha="frase longa de teste")
        )
