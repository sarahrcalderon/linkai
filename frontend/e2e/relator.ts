import type { Reporter, TestCase, TestResult, FullResult } from '@playwright/test/reporter';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

export default class RelatorSeguro implements Reporter {
  private resultados: { teste: string; resultado: string; duracaoMs: number }[] = [];
  onTestEnd(teste: TestCase, resultado: TestResult) {
    this.resultados.push({
      teste: teste.title,
      resultado: resultado.status,
      duracaoMs: resultado.duration,
    });
    process.stdout.write(`${resultado.status}: ${teste.title}\n`);
    for (const erro of resultado.errors) {
      let mensagem = erro.stack || erro.message || 'Falha de teste sem detalhes.';
      for (const segredo of [process.env.E2E_SENHA_FIXTURE, process.env.URL_BANCO_E2E]) {
        if (segredo) mensagem = mensagem.split(segredo).join('[REMOVIDO]');
      }
      mensagem = mensagem
        .replace(/(?:__Host-)?linkai_sessao=[^;\s]+/g, '[COOKIE REMOVIDO]')
        .replace(/\b[a-f0-9]{64}\b/g, '[RESUMO REMOVIDO]');
      process.stdout.write(`${mensagem}\n`);
    }
  }
  onEnd(resultado: FullResult) {
    const pasta = resolve(
      process.env.E2E_PASTA_EVIDENCIAS || '../docs/relatorios/evidencias/fase3',
    );
    mkdirSync(pasta, { recursive: true });
    writeFileSync(
      resolve(pasta, 'resultado-e2e.json'),
      JSON.stringify(
        {
          resultado: resultado.status,
          duracaoMs: resultado.duration,
          testes: this.resultados,
        },
        null,
        2,
      ) + '\n',
    );
    process.stdout.write(`Resultado E2E: ${resultado.status}; ${this.resultados.length} testes.\n`);
  }
}
