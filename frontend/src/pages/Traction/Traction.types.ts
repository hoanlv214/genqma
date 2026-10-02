import type { QmaRoute } from "@/app/routes";

export interface TractionProps {
  onNavigate: (route: QmaRoute) => void;
}
