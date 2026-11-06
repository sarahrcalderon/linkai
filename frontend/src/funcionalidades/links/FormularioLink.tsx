import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Botao } from '../../componentes/Botao';
import { CampoTexto } from '../../componentes/CampoTexto';
import { Dialogo } from '../../componentes/Dialogo';
import { Feedback } from '../../componentes/Feedback';
import { ErroHTTP } from '../../servicos/http';
import {
  servicoLinks,
  urlPublica,
  type AlteracoesLink,
  type DadosLink,
  type LinkPersonalizado,
} from './servico';
import { usarAutenticacao } from '../autenticacao/usarAutenticacao';

type Campos = {
  nome: string;
  slug: string;
  numero_whatsapp: string;
  mensagem: string;
  ativo: boolean;
};
const reservados = [
  'api',
  'admin',
  'login',
  'logout',
  'cadastro',
  'dashboard',
  'verificar-email',
  'reenviar-codigo',
  'static',
  'assets',
  'docs',
  'redoc',
  'openapi',
  'saude',
  'www',
];
function validar(dados: Campos): Record<string, string> {
  const erros: Record<string, string> = {};
  if (
    Array.from(dados.nome.trim()).length < 2 ||
    Array.from(dados.nome.trim()).length > 100 ||
    /[\p{C}]/u.test(dados.nome.trim())
  )
    erros.nome = 'Informe um nome com 2 a 100 caracteres, sem controles.';
  const slug = dados.slug.trim().toLowerCase();
  if (slug.length < 3 || slug.length > 64 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug))
    erros.slug = 'Use 3 a 64 letras sem acentos, números e hífens entre segmentos.';
  else if (reservados.includes(slug)) erros.slug = 'Este slug é reservado. Escolha outro.';
  if (!/^\+?[1-9][0-9]{7,14}$/.test(dados.numero_whatsapp.trim().replace(/[ ().-]/g, '')))
    erros.numero_whatsapp =
      'Informe o código do país e 8 a 15 dígitos. Exemplo: +55 (11) 99999-9999.';
  if (
    Array.from(dados.mensagem).length > 2000 ||
    /[<>]/.test(dados.mensagem) ||
    /[^\P{C}\n\r\t]/u.test(dados.mensagem)
  )
    erros.mensagem = 'Use até 2000 caracteres de texto, sem HTML ou controles inválidos.';
  return erros;
}

export function FormularioLink({
  link,
  fechar,
  salvo,
  focoRetorno,
}: {
  link: LinkPersonalizado | null;
  fechar: () => void;
  salvo: () => void;
  focoRetorno?: HTMLElement | null;
}) {
  const { executarAutenticado } = usarAutenticacao();
  const inicial: Campos = {
    nome: link?.nome || '',
    slug: link?.slug || '',
    numero_whatsapp: link?.numero_whatsapp || '',
    mensagem: link?.mensagem || '',
    ativo: link?.ativo ?? true,
  };
  const [campos, definirCampos] = useState(inicial);
  const [erros, definirErros] = useState<Record<string, string>>({});
  const [erro, definirErro] = useState('');
  const [enviando, definirEnviando] = useState(false);
  const [descartar, definirDescartar] = useState(false);
  const bloqueado = useRef(false);
  const formulario = useRef<HTMLFormElement>(null);
  const feedback = useRef<HTMLDivElement>(null);
  const alterado = Object.keys(inicial).some(
    (c) => campos[c as keyof Campos] !== inicial[c as keyof Campos],
  );
  useEffect(() => {
    if (!alterado) return;
    const proteger = (evento: BeforeUnloadEvent) => {
      evento.preventDefault();
      evento.returnValue = '';
    };
    window.addEventListener('beforeunload', proteger);
    return () => window.removeEventListener('beforeunload', proteger);
  }, [alterado]);
  useEffect(() => {
    if (erro) feedback.current?.focus();
  }, [erro]);
  function cancelar() {
    if (bloqueado.current) return;
    if (alterado) definirDescartar(true);
    else fechar();
  }
  function mudar(campo: keyof Campos, valor: string | boolean) {
    definirCampos((c) => ({ ...c, [campo]: valor }));
  }
  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    if (bloqueado.current) return;
    const falhas = validar(campos);
    definirErros(falhas);
    definirErro('');
    const primeiro = Object.keys(falhas)[0];
    if (primeiro) {
      (formulario.current?.elements.namedItem(primeiro) as HTMLElement)?.focus();
      return;
    }
    const dados: DadosLink = {
      nome: campos.nome.trim(),
      slug: campos.slug.trim().toLowerCase(),
      numero_whatsapp: campos.numero_whatsapp.trim(),
      mensagem: campos.mensagem === '' ? null : campos.mensagem,
    };
    const alteracoes: AlteracoesLink = {};
    if (link) {
      for (const campo of ['nome', 'slug', 'numero_whatsapp', 'mensagem'] as const) {
        if (dados[campo] !== link[campo]) Object.assign(alteracoes, { [campo]: dados[campo] });
      }
      if (campos.ativo !== link.ativo) alteracoes.ativo = campos.ativo;
      if (!Object.keys(alteracoes).length) {
        fechar();
        return;
      }
    }
    bloqueado.current = true;
    definirDescartar(false);
    definirEnviando(true);
    try {
      await executarAutenticado((csrf) =>
        link ? servicoLinks.atualizar(link.id, alteracoes, csrf) : servicoLinks.criar(dados, csrf),
      );
      salvo();
    } catch (falha) {
      if (falha instanceof ErroHTTP && falha.status === 409) definirErros({ slug: falha.message });
      definirErro(falha instanceof Error ? falha.message : 'Não foi possível salvar o link.');
    } finally {
      bloqueado.current = false;
      definirEnviando(false);
    }
  }
  return (
    <Dialogo
      titulo={link ? 'Editar link' : 'Criar link'}
      fechar={cancelar}
      focoRetorno={focoRetorno}
    >
      <form
        ref={formulario}
        onSubmit={(evento) => void enviar(evento)}
        noValidate
        aria-label={link ? 'Editar link' : 'Criar link'}
        aria-busy={enviando}
        className="flex min-w-0 flex-col gap-5"
      >
        <CampoTexto
          identificador="link-nome"
          name="nome"
          rotulo="Nome interno"
          required
          maxLength={100}
          value={campos.nome}
          onChange={(e) => mudar('nome', e.target.value)}
          disabled={enviando}
          erro={erros.nome}
        />
        <CampoTexto
          identificador="link-slug"
          name="slug"
          rotulo="Slug personalizado"
          required
          maxLength={64}
          autoCapitalize="none"
          spellCheck={false}
          value={campos.slug}
          onChange={(e) => mudar('slug', e.target.value)}
          disabled={enviando}
          erro={erros.slug}
        />
        <p className="text-sm leading-relaxed break-all">
          Prévia: {urlPublica(campos.slug.trim().toLowerCase())}
          <br />A disponibilidade será confirmada ao salvar.
        </p>
        {link && campos.slug.trim().toLowerCase() !== link.slug && (
          <p
            role="status"
            className="rounded-xl border border-current/25 p-3 text-sm leading-relaxed"
          >
            O endereço anterior deixará de funcionar e poderá ser utilizado novamente.
          </p>
        )}
        <CampoTexto
          identificador="link-numero"
          name="numero_whatsapp"
          rotulo="Número de WhatsApp"
          type="tel"
          autoComplete="tel"
          required
          value={campos.numero_whatsapp}
          onChange={(e) => mudar('numero_whatsapp', e.target.value)}
          disabled={enviando}
          erro={erros.numero_whatsapp}
        />
        <p className="text-sm leading-relaxed">
          Inclua o código do país, como +55 para o Brasil. O número e a mensagem serão visíveis no
          destino público.
        </p>
        <div className="flex flex-col gap-2">
          <label htmlFor="link-mensagem" className="text-sm font-semibold">
            Mensagem predefinida (opcional)
          </label>
          <textarea
            id="link-mensagem"
            name="mensagem"
            rows={4}
            value={campos.mensagem}
            onChange={(e) => mudar('mensagem', e.target.value)}
            disabled={enviando}
            aria-invalid={Boolean(erros.mensagem)}
            aria-describedby={
              erros.mensagem ? 'mensagem-erro mensagem-contador' : 'mensagem-contador'
            }
            className="w-full min-w-0 rounded-xl border border-current/20 bg-transparent p-3 text-base focus-visible:outline-2 focus-visible:outline-emerald-500"
          />
          <p id="mensagem-contador" className="text-sm">
            {Array.from(campos.mensagem).length}/2000 caracteres
          </p>
          {erros.mensagem && (
            <p id="mensagem-erro" role="alert" className="text-sm text-red-700 dark:text-red-300">
              {erros.mensagem}
            </p>
          )}
        </div>
        {link && (
          <label className="flex min-h-11 items-center gap-3">
            <input
              type="checkbox"
              className="!w-auto"
              checked={campos.ativo}
              onChange={(e) => mudar('ativo', e.target.checked)}
              disabled={enviando}
            />
            Link ativo
          </label>
        )}
        <Feedback referencia={feedback} mensagem={erro} />
        {descartar && (
          <div role="alert" className="rounded-xl border border-current/25 p-4">
            <p>Descartar as alterações não salvas?</p>
            <div className="mt-3 flex flex-wrap gap-3">
              <Botao type="button" onClick={fechar}>
                Descartar alterações
              </Botao>
              <Botao type="button" variante="secundaria" onClick={() => definirDescartar(false)}>
                Continuar editando
              </Botao>
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-3">
          <Botao type="submit" disabled={enviando}>
            {enviando ? 'Salvando…' : 'Salvar link'}
          </Botao>
          <Botao type="button" variante="secundaria" disabled={enviando} onClick={cancelar}>
            Cancelar
          </Botao>
        </div>
      </form>
    </Dialogo>
  );
}
