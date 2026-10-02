import React, { useEffect, useRef } from "react";
import "../../styles/styles.css";
import { cn } from "../../utils/cn";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  children: React.ReactNode;
  maxWidth?: number | string;
  className?: string;
  showCloseButton?: boolean;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  maxWidth = 480,
  className = "",
  showCloseButton = true,
}: ModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    const prevActiveElement = document.activeElement as HTMLElement | null;

    // Focus panel on open for screen readers
    panelRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      prevActiveElement?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="modal-backdrop open"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
      role="presentation"
    >
      <div
        ref={panelRef}
        className={cn("modal-panel w-full max-w-lg", className)}
        role="dialog"
        aria-modal="true"
        tabIndex={-1}
      >
        {(title || showCloseButton) && (
          <div className="modal-header">
            {title ? <span className="modal-title">{title}</span> : <div />}
            {showCloseButton && (
              <button
                type="button"
                className="icon-button"
                onClick={onClose}
                aria-label="Close modal"
              >
                ✕
              </button>
            )}
          </div>
        )}
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}
