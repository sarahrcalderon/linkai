import { ProvedorAutenticacao } from './funcionalidades/autenticacao/ProvedorAutenticacao';
import { RotasAplicacao } from './navegacao/RotasAplicacao';

export function Aplicacao() {
  return (
    <ProvedorAutenticacao>
      <RotasAplicacao />
    </ProvedorAutenticacao>
  );
}
