import { Info } from "lucide-react";
import "./InfoHint.css";

interface InfoHintProps {
  /** Full explanation shown in the hover/focus tooltip. */
  text: string;
  /** Optional accessible label; defaults to text. */
  label?: string;
  /** Visual size of the icon. Defaults to 12. */
  size?: number;
}

/**
 * A quiet inline help affordance: a Lucide Info icon that reveals a tooltip
 * on hover or keyboard focus. Use it to move long explanatory copy out of
 * dense data surfaces without losing the information.
 */
export function InfoHint({ text, label, size = 12 }: InfoHintProps) {
  return (
    <span
      className="info-hint"
      tabIndex={0}
      role="note"
      aria-label={label ?? text}
    >
      <Info size={size} strokeWidth={2} aria-hidden="true" />
      <span className="info-hint__tip" role="tooltip">
        {text}
      </span>
    </span>
  );
}

export default InfoHint;
