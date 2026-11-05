import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Botao } from '../componentes/Botao';
import { CampoTexto } from '../componentes/CampoTexto';
import { Cabecalho } from '../componentes/Cabecalho';
import { GraficoCliques } from '../componentes/GraficoCliques';

describe('Componentes compartilhados', () => {
  it('permite desabilitar o botão', () => {
    render(<Botao disabled>Enviar</Botao>);
    expect(screen.getByRole('button', { name: 'Enviar' })).toBeDisabled();
  });

  it('associa o rótulo ao campo e anuncia erros', () => {
    render(<CampoTexto rotulo="E-mail" identificador="email" erro="E-mail inválido" />);
    expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('E-mail inválido');
  });

  it('permite alternar o tema', () => {
    localStorage.setItem('tema', 'claro');
    render(<Cabecalho />);
    fireEvent.click(screen.getByRole('button', { name: 'Ativar tema escuro' }));
    expect(screen.getByRole('button', { name: 'Ativar tema claro' })).toBeInTheDocument();
  });

  it('identifica explicitamente os dados fictícios', () => {
    render(<GraficoCliques />);
    expect(screen.getByText(/Dados fictícios/)).toBeInTheDocument();
  });
});
