import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';

export function operarBanco(operacao: 'preparar' | 'expirar' | 'suspender' | 'restaurar') {
  const python = process.env.E2E_PYTHON || resolve('../backend/.venv/Scripts/python.exe');
  execFileSync(python, ['testes/e2e/ambiente.py', operacao], {
    cwd: resolve('../backend'),
    env: { ...process.env, PYTHONPATH: 'src' },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
}
