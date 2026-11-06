from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from uuid import uuid4

import pytest

from aplicacao.dominio.link import SLUGS_RESERVADOS, Link


def criar(**ajustes):
    dados = dict(
        usuario_id=uuid4(),
        nome=" Campanha ",
        slug=" Minha-Campanha ",
        numero_whatsapp="+55 (11) 99999-9999",
        mensagem="Olá!\nQuero saber mais.",
    )
    return Link(**(dados | ajustes))


def test_link_normalizado_sem_dependencia_do_orm():
    link = criar()
    assert link.nome == "Campanha" and link.slug == "minha-campanha"
    assert link.numero_whatsapp == "+5511999999999"
    assert link.mensagem == "Olá!\nQuero saber mais."
    assert link.disponivel_para_redirecionamento
    assert link.numero_whatsapp not in repr(link) and link.mensagem not in repr(link)
    with pytest.raises(FrozenInstanceError):
        link.slug = "alterado"


@pytest.mark.parametrize(
    "slug", ["", "ab", "a" * 65, "-abc", "abc-", "a--bc", "a/b", "ação", "a.b", "a b"]
)
def test_slug_invalido(slug):
    with pytest.raises(ValueError):
        criar(slug=slug)


@pytest.mark.parametrize("slug", sorted(SLUGS_RESERVADOS))
def test_slug_reservado(slug):
    with pytest.raises(ValueError):
        criar(slug=" " + slug.upper() + " ")


@pytest.mark.parametrize(
    "numero",
    [
        "",
        "+012345678",
        "1234567",
        "1" * 16,
        "+55abc999999999",
        "++5511999999999",
        "５５１１９９９９９９９９９",
        "55/11999999999",
    ],
)
def test_numero_invalido(numero):
    with pytest.raises(ValueError):
        criar(numero_whatsapp=numero)


@pytest.mark.parametrize(
    "ajustes",
    [
        {"nome": "a"},
        {"nome": "a" * 101},
        {"nome": "ab\x00c"},
        {"mensagem": "a" * 2001},
        {"mensagem": "<b>Olá</b>"},
        {"mensagem": "a\x00b"},
        {"ativo": "sim"},
        {"usuario_id": "invalido"},
    ],
)
def test_limites_e_campos_invalidos(ajustes):
    with pytest.raises(ValueError):
        criar(**ajustes)


def test_limites_validos_e_numero_sem_formatacao():
    link = criar(
        nome="a" * 100, slug="a" * 64, mensagem="a" * 2000, numero_whatsapp="123456789012345"
    )
    assert link.numero_whatsapp == "+123456789012345"
    assert criar(mensagem=None).mensagem is None


def test_exclusao_e_inatividade_impedem_disponibilidade():
    link = criar()
    excluido = link.excluir()
    assert excluido.slug == link.slug and not excluido.disponivel_para_redirecionamento
    assert excluido.excluir() is excluido
    assert not replace(link, ativo=False).disponivel_para_redirecionamento
    with pytest.raises(ValueError):
        replace(excluido, ativo=True)
    with pytest.raises(ValueError):
        replace(link, atualizado_em=link.criado_em - timedelta(seconds=1))
    with pytest.raises(ValueError):
        replace(link, criado_em=link.criado_em.replace(tzinfo=None))
