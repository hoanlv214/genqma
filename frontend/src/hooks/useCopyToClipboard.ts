import { useState, useCallback } from "react";

export function useCopyToClipboard(resetDelayMs = 2000) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(
    async (text: string) => {
      if (!text) return false;
      try {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), resetDelayMs);
        return true;
      } catch (err) {
        console.warn("Failed to copy text to clipboard:", err);
        setCopied(false);
        return false;
      }
    },
    [resetDelayMs],
  );

  return { copied, copy };
}
