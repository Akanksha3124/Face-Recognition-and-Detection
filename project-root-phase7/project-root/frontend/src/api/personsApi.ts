import { apiClient } from "@/api/client";
import type { PaginatedPersons } from "@/types/person";

/** page_size=1 because only `total` is needed here — avoids pulling
 * back real rows just to count them. */
export async function fetchPersonCount(): Promise<number> {
  const response = await apiClient.get<PaginatedPersons>("/persons", { params: { page: 1, page_size: 1 } });
  return response.data.total;
}
