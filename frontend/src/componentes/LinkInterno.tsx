import type { AnchorHTMLAttributes } from 'react';
import { navegar } from '../navegacao/usarNavegacao';

export function LinkInterno({
  href = '/',
  children,
  ...propriedades
}: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      {...propriedades}
      href={href}
      onClick={(evento) => {
        if (
          evento.button === 0 &&
          !evento.ctrlKey &&
          !evento.metaKey &&
          !evento.shiftKey &&
          !evento.altKey
        ) {
          evento.preventDefault();
          navegar(href);
        }
      }}
    >
      {children}
    </a>
  );
}
