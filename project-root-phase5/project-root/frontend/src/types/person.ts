// Mirrors backend/app/schemas/person.py — only the fields the dashboard
// stat cards need for now (a full Person type lands with the Phase 10
// persons/cases UI).
export interface PaginatedPersons {
  items: unknown[];
  total: number;
  page: number;
  page_size: number;
}
