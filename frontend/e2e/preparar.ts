import { randomBytes } from 'node:crypto';
import { operarBanco } from './ambiente';

export default function preparar() {
  if (!process.env.URL_BANCO_E2E)
    throw new Error('Configure URL_BANCO_E2E para o banco local linkai_e2e.');
  process.env.E2E_SENHA_FIXTURE = randomBytes(32).toString('base64url');
  operarBanco('restaurar');
  operarBanco('preparar');
}
