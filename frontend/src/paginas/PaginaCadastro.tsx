import { EstruturaAcesso } from '../componentes/EstruturaAcesso';
import { FormularioAutenticacao } from '../componentes/FormularioAutenticacao';

export function PaginaCadastro() {
  return (
    <EstruturaAcesso
      titulo="Crie sua conta"
      descricao="Organize seu acesso ao Linkai com segurança."
    >
      <FormularioAutenticacao cadastro />
    </EstruturaAcesso>
  );
}
