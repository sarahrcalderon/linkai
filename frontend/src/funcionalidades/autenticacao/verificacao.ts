import { ErroHTTP, requisitar } from '../../servicos/http';

const intervaloConfigurado = Number(import.meta.env.VITE_VERIFICACAO_INTERVALO_REENVIO || 60);
export const intervaloReenvio =
  Number.isFinite(intervaloConfigurado) && intervaloConfigurado > 0
    ? Math.ceil(intervaloConfigurado)
    : 60;

// Contexto transitório: nunca vai para URL, histórico ou armazenamento do navegador.
export const contextoVerificacao = { email: '', reenviarEm: 0 };

function validarMensagem(dados: unknown): void {
  if (
    !dados ||
    typeof dados !== 'object' ||
    !('mensagem' in dados) ||
    typeof dados.mensagem !== 'string'
  ) {
    throw new Error('Resposta inesperada da API. Tente novamente.');
  }
}

export const servicoVerificacao = {
  async confirmar(email: string, codigo: string): Promise<void> {
    try {
      validarMensagem(
        await requisitar('/api/autenticacao/verificar-email', 200, {
          method: 'POST',
          body: JSON.stringify({ email, codigo }),
        }),
      );
    } catch (erro) {
      if (erro instanceof ErroHTTP && erro.status === 400) {
        throw new ErroHTTP(
          400,
          'Código inválido ou indisponível. Confira os dados ou solicite outro código.',
        );
      }
      throw erro;
    }
  },
  async reenviar(email: string): Promise<void> {
    validarMensagem(
      await requisitar('/api/autenticacao/reenviar-codigo', 202, {
        method: 'POST',
        body: JSON.stringify({ email }),
      }),
    );
  },
};
