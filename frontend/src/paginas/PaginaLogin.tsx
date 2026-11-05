import { EstruturaAcesso } from '../componentes/EstruturaAcesso';
import { Feedback } from '../componentes/Feedback';
import { FormularioAutenticacao } from '../componentes/FormularioAutenticacao';
import { usarAutenticacao } from '../funcionalidades/autenticacao/usarAutenticacao';

export function PaginaLogin() {
  const { mensagem } = usarAutenticacao();
  return (
    <EstruturaAcesso
      titulo="Entre na sua conta"
      descricao="Acesse o Linkai com seu e-mail verificado."
    >
      {mensagem && (
        <div className="mb-5">
          <Feedback mensagem={mensagem} />
        </div>
      )}
      <FormularioAutenticacao cadastro={false} />
    </EstruturaAcesso>
  );
}
