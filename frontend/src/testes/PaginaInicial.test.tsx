import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PaginaInicial } from '../paginas/PaginaInicial';

describe('Página inicial', () => {
  it('apresenta a proposta da plataforma', () => {
    render(<PaginaInicial />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('links inteligentes');
  });
});
