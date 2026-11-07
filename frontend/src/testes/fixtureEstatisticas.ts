// Dados exclusivamente de teste, nunca importados pela aplicação.
export function fixtureEstatisticas(dias = 7) {
  return {
    total_acessos: 0,
    links_ativos: 0,
    links_inativos: 0,
    data_inicial: '2026-01-01T00:00:00Z',
    data_final: new Date(Date.UTC(2026, 0, dias, 12)).toISOString(),
    serie_diaria: Array.from({ length: dias }, (_, i) => ({
      data: new Date(Date.UTC(2026, 0, i + 1)).toISOString().slice(0, 10),
      acessos: 0,
    })),
  };
}
