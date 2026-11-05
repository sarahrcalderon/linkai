import React from 'react';
import ReactDOM from 'react-dom/client';
import { PaginaInicial } from './paginas/PaginaInicial';
import './estilos/globais.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <PaginaInicial />
  </React.StrictMode>,
);
