import { useEffect, useRef, useState } from 'react';
import { Botao } from '../../componentes/Botao';
import { Dialogo } from '../../componentes/Dialogo';
import { Feedback } from '../../componentes/Feedback';
import { FormularioLink } from './FormularioLink';
import { servicoLinks, urlPublica, type LinkPersonalizado } from './servico';
import { usarLinks } from './usarLinks';

export function MeusLinks() {
  const lista = usarLinks();
  const [formulario, definirFormulario] = useState<{
    link: LinkPersonalizado | null;
    acionador: HTMLElement;
  } | null>(null);
  const [exclusao, definirExclusao] = useState<LinkPersonalizado | null>(null);
  const [ocupado, definirOcupado] = useState(false);
  const [mensagem, definirMensagem] = useState('');
  const [erro, definirErro] = useState('');
  const [erroExclusao, definirErroExclusao] = useState('');
  const bloqueado = useRef(false);
  const feedback = useRef<HTMLDivElement>(null);
  const feedbackExclusao = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (erroExclusao) feedbackExclusao.current?.focus();
  }, [erroExclusao]);
  useEffect(() => {
    if (mensagem || erro) feedback.current?.focus();
  }, [mensagem, erro]);
  async function executar(acao: () => Promise<void>, sucesso: string, recarregar = true) {
    if (bloqueado.current) return;
    bloqueado.current = true;
    definirOcupado(true);
    definirErro('');
    definirMensagem('');
    try {
      await acao();
      definirMensagem(sucesso);
      if (recarregar) lista.recarregar();
    } catch (falha) {
      definirErro(falha instanceof Error ? falha.message : 'Não foi possível concluir a operação.');
    } finally {
      bloqueado.current = false;
      definirOcupado(false);
    }
  }
  async function editar(link: LinkPersonalizado, acionador: HTMLElement) {
    await executar(
      async () => {
        const atual = await lista.executarAutenticado(() => servicoLinks.consultar(link.id));
        definirFormulario({ link: atual, acionador });
      },
      '',
      false,
    );
  }
  async function copiar(link: LinkPersonalizado) {
    definirErro('');
    definirMensagem('');
    try {
      await navigator.clipboard.writeText(urlPublica(link.slug));
      definirMensagem('URL copiada.');
    } catch {
      definirErro('Não foi possível copiar. Selecione e copie a URL exibida no cartão.');
    }
  }
  async function excluir() {
    if (!exclusao || bloqueado.current) return;
    bloqueado.current = true;
    definirOcupado(true);
    definirErroExclusao('');
    try {
      await lista.executarAutenticado((csrf) => servicoLinks.excluir(exclusao.id, csrf));
      definirExclusao(null);
      definirMensagem('Link excluído. O slug permanece reservado.');
      lista.recarregar();
    } catch (falha) {
      definirErroExclusao(
        falha instanceof Error ? falha.message : 'Não foi possível excluir o link.',
      );
    } finally {
      bloqueado.current = false;
      definirOcupado(false);
    }
  }
  return (
    <section aria-labelledby="titulo-meus-links" className="mt-10 min-w-0">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 id="titulo-meus-links" className="text-3xl font-bold">
            Meus links
          </h2>
          <p className="mt-3 leading-relaxed">
            Crie e organize seus links personalizados para WhatsApp.
          </p>
        </div>
        <Botao
          disabled={ocupado}
          onClick={(evento) => definirFormulario({ link: null, acionador: evento.currentTarget })}
        >
          Criar link
        </Botao>
      </div>
      <Feedback referencia={feedback} mensagem={erro || mensagem} sucesso={Boolean(mensagem)} />
      {lista.carregando ? (
        <p role="status" className="py-8">
          Carregando links…
        </p>
      ) : lista.erro ? (
        <div className="my-6">
          <Feedback mensagem={lista.erro} />
          <Botao variante="secundaria" className="mt-4" onClick={lista.recarregar}>
            Tentar novamente
          </Botao>
        </div>
      ) : lista.dados?.itens.length === 0 ? (
        <div className="my-6 rounded-2xl border border-dashed border-current/25 p-6">
          <h3 className="text-xl font-semibold">Seu primeiro link começa aqui</h3>
          <p className="mt-3 leading-relaxed">
            Use “Criar link” para escolher um endereço e preparar sua conversa no WhatsApp.
          </p>
        </div>
      ) : (
        <>
          <ul className="mt-6 grid min-w-0 gap-5 lg:grid-cols-2">
            {lista.dados?.itens.map((link) => (
              <li
                key={link.id}
                className="min-w-0 rounded-2xl border border-current/15 bg-white p-5 dark:bg-slate-900"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <h3 className="min-w-0 text-xl font-semibold break-words">{link.nome}</h3>
                  <span className="rounded-full border border-current/25 px-3 py-1 text-sm font-medium">
                    {link.ativo ? 'Ativo' : 'Inativo'}
                  </span>
                </div>
                <p className="mt-4 text-sm leading-relaxed break-all select-all">
                  {urlPublica(link.slug)}
                </p>
                <div className="mt-5 flex flex-wrap gap-2" aria-label={`Ações de ${link.nome}`}>
                  <Botao
                    variante="secundaria"
                    disabled={ocupado}
                    onClick={() => void copiar(link)}
                    aria-label={`Copiar URL de ${link.nome}`}
                  >
                    Copiar
                  </Botao>
                  {link.ativo ? (
                    <a
                      href={urlPublica(link.slug)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-h-11 items-center rounded-xl border border-current/20 px-5 py-3 font-semibold hover:bg-current/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
                      aria-label={`Abrir ${link.nome}`}
                    >
                      Abrir
                    </a>
                  ) : (
                    <Botao variante="secundaria" disabled>
                      Abrir
                    </Botao>
                  )}
                  <Botao
                    variante="secundaria"
                    disabled={ocupado}
                    onClick={(evento) => void editar(link, evento.currentTarget)}
                  >
                    Editar
                  </Botao>
                  <Botao
                    variante="secundaria"
                    disabled={ocupado}
                    onClick={() =>
                      void executar(
                        async () => {
                          await lista.executarAutenticado((csrf) =>
                            servicoLinks.atualizar(link.id, { ativo: !link.ativo }, csrf),
                          );
                        },
                        link.ativo ? 'Link desativado.' : 'Link ativado.',
                      )
                    }
                  >
                    {link.ativo ? 'Desativar' : 'Ativar'}
                  </Botao>
                  <Botao
                    variante="secundaria"
                    disabled={ocupado}
                    onClick={() => {
                      definirErroExclusao('');
                      definirExclusao(link);
                    }}
                  >
                    Excluir
                  </Botao>
                </div>
              </li>
            ))}
          </ul>
          {lista.dados && (
            <nav aria-label="Paginação de links" className="mt-6 flex flex-wrap items-center gap-4">
              <Botao
                variante="secundaria"
                disabled={ocupado || lista.pagina <= 1}
                onClick={() => lista.definirPagina(lista.pagina - 1)}
              >
                Anterior
              </Botao>
              <p>
                Página {lista.pagina} de{' '}
                {Math.max(1, Math.ceil(lista.dados.total / lista.dados.tamanho))}
              </p>
              <Botao
                variante="secundaria"
                disabled={ocupado || lista.pagina * lista.dados.tamanho >= lista.dados.total}
                onClick={() => lista.definirPagina(lista.pagina + 1)}
              >
                Próxima
              </Botao>
            </nav>
          )}
        </>
      )}
      {formulario && (
        <FormularioLink
          link={formulario.link}
          focoRetorno={formulario.acionador}
          fechar={() => definirFormulario(null)}
          salvo={() => {
            definirFormulario(null);
            definirErro('');
            definirMensagem(formulario.link ? 'Link atualizado.' : 'Link criado.');
            if (!formulario.link) lista.definirPagina(1);
            lista.recarregar();
          }}
        />
      )}
      {exclusao && (
        <Dialogo
          titulo="Excluir link"
          fechar={() => {
            if (!bloqueado.current) definirExclusao(null);
          }}
        >
          <p className="leading-relaxed break-words">
            Excluir “{exclusao.nome}”? O link deixará de funcionar. A exclusão é lógica, o slug
            vigente permanecerá reservado e a operação não poderá ser desfeita pela interface atual.
          </p>
          <div className="mt-4">
            <Feedback referencia={feedbackExclusao} mensagem={erroExclusao} />
          </div>
          <div className="mt-6 flex flex-wrap gap-3">
            <Botao variante="secundaria" disabled={ocupado} onClick={() => definirExclusao(null)}>
              Cancelar
            </Botao>
            <Botao disabled={ocupado} onClick={() => void excluir()}>
              {ocupado ? 'Excluindo…' : 'Confirmar exclusão'}
            </Botao>
          </div>
        </Dialogo>
      )}
    </section>
  );
}
