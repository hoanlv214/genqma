import type { ReactNode } from "react";

export function ModalShell({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <section className="modal-panel" role="dialog" aria-modal="true" aria-label={title} onClick={(event) => event.stopPropagation()}>
        <header className="modal-header">
          <h2>{title}</h2>
          <button type="button" onClick={onClose}>x</button>
        </header>
        {children}
      </section>
    </div>
  );
}
