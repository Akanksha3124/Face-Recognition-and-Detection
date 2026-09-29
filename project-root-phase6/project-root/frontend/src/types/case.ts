// Mirrors backend/app/schemas/case.py — see the note in types/person.ts.
export interface PaginatedCases {
  items: unknown[];
  total: number;
  page: number;
  page_size: number;
}
