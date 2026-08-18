import {
  ACCESS_TOKEN_KEY,
  REFRESH_TOKEN_KEY,
  type TokenStorage,
} from "../storage";
import type { TokenPair } from "../types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | undefined | null>;
  auth?: boolean;
}

/**
 * Uses only `fetch`, so the same client runs unchanged under React Native.
 * The base URL is injected rather than read from import.meta so native builds
 * can point at an absolute host.
 */
export class ApiClient {
  private refreshInFlight: Promise<string | null> | null = null;

  constructor(
    private readonly baseUrl: string,
    private readonly storage: TokenStorage,
    private readonly onAuthExpired?: () => void,
  ) {}

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const response = await this.perform(path, options);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  /** For endpoints that return a file rather than JSON (e.g. the CSV export). */
  async requestText(path: string, options: RequestOptions = {}): Promise<string> {
    const response = await this.perform(path, options);
    return await response.text();
  }

  private async perform(path: string, options: RequestOptions): Promise<Response> {
    const { method = "GET", body, query, auth = false } = options;

    let response = await this.send(path, method, body, query, auth);

    if (response.status === 401 && auth) {
      const token = await this.refreshAccessToken();
      if (token) {
        response = await this.send(path, method, body, query, auth);
      } else {
        this.onAuthExpired?.();
      }
    }

    if (!response.ok) {
      throw new ApiError(response.status, await extractMessage(response));
    }
    return response;
  }

  private async send(
    path: string,
    method: string,
    body: unknown,
    query: RequestOptions["query"],
    auth: boolean,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth) {
      const token = await this.storage.get(ACCESS_TOKEN_KEY);
      if (token) headers.Authorization = `Bearer ${token}`;
    }

    return fetch(`${this.baseUrl}${path}${buildQuery(query)}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }

  /** Collapses concurrent 401s into a single refresh call. */
  private refreshAccessToken(): Promise<string | null> {
    if (!this.refreshInFlight) {
      this.refreshInFlight = this.doRefresh().finally(() => {
        this.refreshInFlight = null;
      });
    }
    return this.refreshInFlight;
  }

  private async doRefresh(): Promise<string | null> {
    const refreshToken = await this.storage.get(REFRESH_TOKEN_KEY);
    if (!refreshToken) return null;

    const response = await fetch(`${this.baseUrl}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!response.ok) {
      await this.clearTokens();
      return null;
    }

    const tokens = (await response.json()) as TokenPair;
    await this.saveTokens(tokens);
    return tokens.access_token;
  }

  async saveTokens(tokens: TokenPair): Promise<void> {
    await this.storage.set(ACCESS_TOKEN_KEY, tokens.access_token);
    await this.storage.set(REFRESH_TOKEN_KEY, tokens.refresh_token);
  }

  async clearTokens(): Promise<void> {
    await this.storage.remove(ACCESS_TOKEN_KEY);
    await this.storage.remove(REFRESH_TOKEN_KEY);
  }

  async hasSession(): Promise<boolean> {
    return (await this.storage.get(ACCESS_TOKEN_KEY)) !== null;
  }
}

function buildQuery(query: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      params.set(key, String(value));
    }
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

async function extractMessage(response: Response): Promise<string> {
  try {
    const body = await response.json();
    const detail = body?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d: { msg?: string }) => d.msg ?? "Invalid value").join(", ");
    }
  } catch {
    // Fall through to the generic message below.
  }
  return `Request failed (${response.status})`;
}
