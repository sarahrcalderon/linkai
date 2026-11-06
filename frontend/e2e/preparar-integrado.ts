import preparar from './preparar';

export default async function prepararIntegrado() {
  process.env.E2E_LINKS_REAIS = '1';
  await preparar();
}
