export type Role = "SUPER_ADMIN" | "ADMIN" | "TEACHER" | "STUDENT" | "PARENT";
export type User = {
  id: number;
  username: string;
  full_name: string;
  role: Role;
  email: string;
  phone: string;
  must_change_password: boolean;
  route: string;
};
export type Branding = {
  name: string;
  platform: boolean;
  primary_color?: string;
  has_logo?: boolean;
  csrfToken: string;
};
export type Row = Record<string, unknown> & { id: number };
export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};
let csrf = "";
let refreshing: Promise<void> | null = null;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function errorText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.map(errorText).join(" ");
  if (value && typeof value === "object")
    return Object.entries(value)
      .map(
        ([key, message]) =>
          `${key === "detail" ? "" : `${key}: `}${errorText(message)}`,
      )
      .join(" ");
  return "Unable to complete this request.";
}

export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
  retry = true,
): Promise<T> {
  if (!path.startsWith("/api/")) throw new Error("API path must be local.");
  if (method !== "GET" && !csrf) await context();
  const headers: Record<string, string> = {};
  if (method !== "GET") headers["X-CSRFToken"] = csrf;
  if (data !== undefined && !(data instanceof FormData))
    headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method,
    headers,
    credentials: "same-origin",
    cache: "no-store",
    body:
      data === undefined
        ? undefined
        : data instanceof FormData
          ? data
          : JSON.stringify(data),
  });
  if (
    response.status === 401 &&
    retry &&
    (!path.startsWith("/api/auth/") || path === "/api/auth/me/")
  ) {
    refreshing ??= api("/api/auth/refresh/", "POST", {}, false)
      .then(() => {})
      .finally(() => {
        refreshing = null;
      });
    try {
      await refreshing;
    } catch {
      window.location.assign("/login");
      throw new ApiError(401, "Please sign in again.");
    }
    return api<T>(path, method, data, false);
  }
  const result = await response
    .json()
    .catch(() => ({ detail: "The request could not be completed." }));
  if (!response.ok) throw new ApiError(response.status, errorText(result));
  if (result.csrfToken) csrf = result.csrfToken;
  return result as T;
}

export function context() {
  return api<Branding>("/api/auth/context/");
}
export function message(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
}
export async function allRows(path: string): Promise<Row[]> {
  const rows: Row[] = [];
  let next: string | null = path;
  while (next) {
    const page: Page<Row> = await api<Page<Row>>(next);
    rows.push(...page.results);
    next = page.next
      ? new URL(page.next, window.location.origin).pathname +
        new URL(page.next, window.location.origin).search
      : null;
  }
  return rows;
}
