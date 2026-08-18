// Mirrors the Pydantic constraints so the same rules apply on web and native.

import type { Role } from "./types";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const USERNAME_RE = /^[a-zA-Z0-9_.-]+$/;

export type Errors<T extends string> = Partial<Record<T, string>>;

export type SignupField =
  | "email"
  | "username"
  | "password"
  | "confirmPassword"
  | "role"
  | "captcha";

export function validateSignup(values: {
  email: string;
  username: string;
  password: string;
  confirmPassword: string;
  role: Role | null;
  captcha: string;
}): Errors<SignupField> {
  const errors: Errors<SignupField> = {};

  if (values.role !== "student" && values.role !== "mentor")
    errors.role = "Choose whether you are joining as a student or a mentor.";

  if (!values.email.trim()) errors.email = "Email is required.";
  else if (!EMAIL_RE.test(values.email.trim())) errors.email = "Enter a valid email address.";

  const username = values.username.trim();
  if (!username) errors.username = "Username is required.";
  else if (username.length < 3) errors.username = "Must be at least 3 characters.";
  else if (!USERNAME_RE.test(username))
    errors.username = "Only letters, numbers, and . _ - are allowed.";

  if (!values.password) errors.password = "Password is required.";
  else if (values.password.length < 8) errors.password = "Must be at least 8 characters.";

  if (values.confirmPassword !== values.password)
    errors.confirmPassword = "Passwords do not match.";

  if (!values.captcha.trim()) errors.captcha = "Enter the characters shown above.";

  return errors;
}

export type LoginField = "identifier" | "password" | "captcha";

export function validateLogin(values: {
  identifier: string;
  password: string;
  captcha: string;
}): Errors<LoginField> {
  const errors: Errors<LoginField> = {};
  if (!values.identifier.trim()) errors.identifier = "Email or username is required.";
  if (!values.password) errors.password = "Password is required.";
  if (!values.captcha.trim()) errors.captcha = "Enter the characters shown above.";
  return errors;
}

export const hasErrors = (errors: Record<string, unknown>): boolean =>
  Object.keys(errors).length > 0;
