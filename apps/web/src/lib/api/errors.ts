/**
 * FastAPI error envelope → user-readable message.
 *
 * FastAPI returns either `{ detail: string }` (HTTPException) or
 * `{ detail: ValidationError[] }` (422). Anything else (proxy errors,
 * plain-text 500s) degrades to a status-line message.
 */

type ValidationItem = { loc?: (string | number)[]; msg?: string };

export class ApiError extends Error {
  readonly status: number;
  readonly service: string;

  constructor(service: string, status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.service = service;
  }
}

export function detailToMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.length > 0) return detail;
  if (Array.isArray(detail)) {
    const parts = (detail as ValidationItem[])
      .map((item) => {
        // drop only the leading location segment ("query"/"body"/"path") —
        // a field may legitimately be named "query"
        const loc = item.loc ?? [];
        const head = loc[0];
        const fieldPath = (
          head === "query" || head === "body" || head === "path" ? loc.slice(1) : loc
        ).join(".");
        return fieldPath ? `${fieldPath}: ${item.msg ?? "invalid"}` : (item.msg ?? "invalid");
      })
      .filter(Boolean);
    if (parts.length > 0) return parts.join("; ");
  }
  return `Request failed with status ${status}`;
}

export function toApiError(service: string, status: number, body: unknown): ApiError {
  const detail =
    body && typeof body === "object" && "detail" in body
      ? (body as { detail: unknown }).detail
      : undefined;
  return new ApiError(service, status, detailToMessage(detail, status));
}
