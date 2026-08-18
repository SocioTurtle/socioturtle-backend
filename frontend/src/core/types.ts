// Shared contracts between web and future React Native clients.

export type Role = "student" | "mentor";

export const ROLES: { value: Role; label: string; blurb: string }[] = [
  { value: "student", label: "Student", blurb: "Find and save learning resources." },
  { value: "mentor", label: "Mentor", blurb: "Share resources and guide students." },
];

export interface User {
  id: number;
  email: string;
  username: string;
  role: Role;
  is_admin: boolean;
  created_at: string;
}

export type LeadStatus = "new" | "invited" | "activated";

export interface Lead {
  id: number;
  name: string;
  email: string;
  role: Role;
  phone: string;
  organisation: string;
  source: string;
  newsletter_opt_in: boolean;
  status: LeadStatus;
  invited_at: string | null;
  activated_at: string | null;
  created_at: string;
}

export interface LeadList {
  total: number;
  limit: number;
  offset: number;
  counts: Record<string, number>;
  items: Lead[];
}

export interface InviteResult {
  sent: number;
  skipped: number;
  failed: number;
  errors: string[];
}

export interface InviteCheck {
  valid: boolean;
  name: string | null;
  email: string | null;
  role: Role | null;
  reason: string | null;
}

export interface NewsletterResult {
  subject: string;
  audience: string;
  recipient_count: number;
  failed_count: number;
  test: boolean;
}

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface CaptchaChallenge {
  challenge_id: string;
  image_data_uri: string;
  expires_in: number;
}

export interface CaptchaAnswer {
  challenge_id: string;
  answer: string;
}

export interface Resource {
  id: number;
  title: string;
  url: string;
  description: string;
  tags: string[];
  created_at: string;
}

export interface SearchResults {
  query: string;
  total: number;
  limit: number;
  offset: number;
  items: Resource[];
}

export interface SignupPayload {
  email: string;
  username: string;
  password: string;
  role: Role;
  captcha: CaptchaAnswer;
}

export interface LoginPayload {
  identifier: string;
  password: string;
  captcha: CaptchaAnswer;
}
