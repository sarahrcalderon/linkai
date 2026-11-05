import { ErroHTTP } from '../../servicos/http';
import { servicoAutenticacao } from './servico';
import type { Credenciais, EstadoAutenticacao, SessaoAutenticada } from './tipos';

export class GerenciadorAutenticacao {
  private estado: EstadoAutenticacao = { situacao: 'carregando', usuario: null };
  private csrf = '';
  private ouvintes = new Set<() => void>();
  private consulta: Promise<void> | null = null;
  private inicializado = false;
  private versao = 0;
  private ultimaConsulta = 0;
  private mutacaoPendente = false;

  obterEstado = () => this.estado;
  inscrever = (ouvinte: () => void) => {
    this.ouvintes.add(ouvinte);
    return () => {
      this.ouvintes.delete(ouvinte);
    };
  };

  private atualizar(estado: EstadoAutenticacao) {
    this.estado = estado;
    this.ouvintes.forEach((ouvinte) => ouvinte());
  }

  private autenticar(sessao: SessaoAutenticada) {
    this.csrf = sessao.csrf;
    this.atualizar({ situacao: 'autenticado', usuario: sessao.usuario });
  }

  private limpar(mensagem?: string) {
    this.csrf = '';
    this.atualizar({ situacao: 'nao_autenticado', usuario: null, mensagem });
  }

  iniciar = (): Promise<void> => {
    if (this.inicializado) return this.consulta || Promise.resolve();
    this.inicializado = true;
    return this.revalidar(true);
  };

  revalidar = (forcar = false): Promise<void> => {
    if (this.mutacaoPendente) return Promise.resolve();
    if (this.consulta) return this.consulta;
    if (
      !forcar &&
      (this.estado.situacao !== 'autenticado' || Date.now() - this.ultimaConsulta < 60000)
    ) {
      return Promise.resolve();
    }
    const versao = this.versao;
    if (this.estado.situacao === 'indisponivel')
      this.atualizar({ situacao: 'carregando', usuario: null });
    this.consulta = (async () => {
      try {
        const sessao = await servicoAutenticacao.consultar();
        if (versao === this.versao) this.autenticar(sessao);
      } catch (erro) {
        if (versao !== this.versao) return;
        if (erro instanceof ErroHTTP && erro.status === 401) {
          this.limpar(this.estado.usuario ? 'Sua sessão expirou. Entre novamente.' : undefined);
        } else {
          this.csrf = '';
          this.atualizar({
            situacao: 'indisponivel',
            usuario: null,
            mensagem: erro instanceof Error ? erro.message : 'Não foi possível consultar a sessão.',
          });
        }
      } finally {
        this.ultimaConsulta = Date.now();
        this.consulta = null;
      }
    })();
    return this.consulta;
  };

  entrar = async (credenciais: Credenciais): Promise<void> => {
    if (this.mutacaoPendente) throw new Error('Aguarde a operação em andamento.');
    this.mutacaoPendente = true;
    const versao = ++this.versao;
    try {
      const sessao = await servicoAutenticacao.entrar(credenciais);
      if (versao === this.versao) this.autenticar(sessao);
    } catch (erro) {
      if (versao === this.versao && this.estado.situacao === 'carregando') this.limpar();
      throw erro;
    } finally {
      ++this.versao;
      this.mutacaoPendente = false;
    }
  };

  sair = async (): Promise<void> => {
    if (this.mutacaoPendente) throw new Error('Aguarde a operação em andamento.');
    this.mutacaoPendente = true;
    const versao = ++this.versao;
    try {
      await servicoAutenticacao.sair(this.csrf);
      if (versao === this.versao) this.limpar();
    } catch (erro) {
      if (erro instanceof ErroHTTP && erro.status === 401) {
        this.limpar('Sua sessão expirou. Entre novamente.');
        return;
      }
      throw erro;
    } finally {
      ++this.versao;
      this.mutacaoPendente = false;
    }
  };
}
