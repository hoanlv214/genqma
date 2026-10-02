import type { ReactNode } from "react";
import type { QmaRoute } from "../app/routes";

/** Standard API Response envelope */
export interface ApiResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
  detail?: string;
  message?: string;
}

/** Paginated collection */
export interface PaginatedResponse<T = unknown> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

/** Standard pagination query parameters */
export interface PaginationParams {
  page?: number;
  limit?: number;
  offset?: number;
}

/** Component base props */
export interface BaseProps {
  className?: string;
  children?: ReactNode;
}

/** State for async data loading */
export interface AsyncState<T = unknown> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

/** Standard user roles */
export type UserRole = "admin" | "creator" | "buyer" | "provider" | "operator";

/** Navigation item definition */
export interface NavItem {
  id: QmaRoute;
  label: string;
  icon?: ReactNode;
  badge?: string | number;
  disabled?: boolean;
}
