import type { QmaRoute } from "@/app/routes";

export interface HomeProps {
  onNavigate: (route: QmaRoute) => void;
}
