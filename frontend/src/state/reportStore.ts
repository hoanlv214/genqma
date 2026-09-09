import { useMemo, useState } from "react";
import type { PaidReport } from "../types/qma";

export function useReportStore() {
  const [report, setReport] = useState<PaidReport | null>(null);
  const [loading, setLoading] = useState(false);

  return useMemo(() => ({
    report,
    setReport,
    loading,
    setLoading,
    clearReport() {
      setReport(null);
    },
  }), [loading, report]);
}
