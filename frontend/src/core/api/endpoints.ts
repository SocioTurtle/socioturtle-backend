import type { ApiClient } from "./client";
import type {
  CaptchaChallenge,
  InviteCheck,
  InviteResult,
  LeadList,
  LoginPayload,
  NewsletterResult,
  Resource,
  SearchResults,
  SignupPayload,
  TokenPair,
  User,
} from "../types";

export const authApi = (client: ApiClient) => ({
  captcha: () => client.request<CaptchaChallenge>("/api/auth/captcha"),

  signup: (payload: SignupPayload) =>
    client.request<TokenPair>("/api/auth/signup", { method: "POST", body: payload }),

  login: (payload: LoginPayload) =>
    client.request<TokenPair>("/api/auth/login", { method: "POST", body: payload }),

  me: () => client.request<User>("/api/auth/me", { auth: true }),
});

export interface SearchParams {
  q?: string;
  tag?: string;
  limit?: number;
  offset?: number;
}

export interface LeadFilters {
  role?: string;
  status?: string;
  q?: string;
  limit?: number;
  offset?: number;
}

export const leadApi = (client: ApiClient) => ({
  list: (filters: LeadFilters) =>
    client.request<LeadList>("/api/leads", { query: { ...filters }, auth: true }),

  invite: (body: { lead_ids?: number[]; all_new?: boolean; resend?: boolean }) =>
    client.request<InviteResult>("/api/leads/invite", { method: "POST", body, auth: true }),
});

export const inviteApi = (client: ApiClient) => ({
  check: (token: string) => client.request<InviteCheck>(`/api/invites/${token}`),

  activate: (body: { token: string; username: string; password: string }) =>
    client.request<TokenPair>("/api/invites/activate", { method: "POST", body }),
});

export const newsletterApi = (client: ApiClient) => ({
  send: (body: {
    subject: string;
    body_markdown: string;
    audience: string;
    test_to?: string;
  }) =>
    client.request<NewsletterResult>("/api/newsletter/send", {
      method: "POST",
      body,
      auth: true,
    }),
});

export const resourceApi = (client: ApiClient) => ({
  search: (params: SearchParams) =>
    client.request<SearchResults>("/api/resources/search", { query: { ...params } }),

  create: (payload: { title: string; url: string; description?: string; tags?: string[] }) =>
    client.request<Resource>("/api/resources", { method: "POST", body: payload, auth: true }),
});
