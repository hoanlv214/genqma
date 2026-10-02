import type { QmaRoute } from "@/app/routes";

export interface ConnectProps {
  onNavigate: (route: QmaRoute) => void;
}
