import { apiClient } from "@/api/client";
import type { PaginatedCases } from "@/types/case";

export async function fetchCaseCount(): Promise<number> {
  const response = await apiClient.get<PaginatedCases>("/cases", { params: { page: 1, page_size: 1 } });
  return response.data.total;
}

export async function fetchOpenCaseCount(): Promise<number> {
  const response = await apiClient.get<PaginatedCases>("/cases", {
    params: { page: 1, page_size: 1, status: "OPEN" },
  });
  return response.data.total;
}
