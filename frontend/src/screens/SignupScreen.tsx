import { useState, type FormEvent } from "react";

import { CaptchaField } from "../components/CaptchaField";
import { RoleSelect } from "../components/RoleSelect";
import { Alert, Button, Card, Field } from "../components/ui";
import type { ApiClient } from "../core/api/client";
import { useAuth } from "../core/hooks/useAuth";
import { useCaptcha } from "../core/hooks/useCaptcha";
import type { Role } from "../core/types";
import { hasErrors, validateSignup, type Errors, type SignupField } from "../core/validation";

export function SignupScreen({
  client,
  onSwitchToLogin,
}: {
  client: ApiClient;
  onSwitchToLogin: () => void;
}) {
  const { signup } = useAuth();
  const captcha = useCaptcha(client);

  const [values, setValues] = useState<{
    email: string;
    username: string;
    password: string;
    confirmPassword: string;
    role: Role | null;
    captcha: string;
  }>({
    email: "",
    username: "",
    password: "",
    confirmPassword: "",
    role: null,
    captcha: "",
  });
  const [errors, setErrors] = useState<Errors<SignupField>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  type TextField = Exclude<keyof typeof values, "role">;
  const set = (key: TextField) => (value: string) =>
    setValues((prev) => ({ ...prev, [key]: value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    const found = validateSignup(values);
    setErrors(found);
    if (hasErrors(found) || values.role === null) return;

    if (!captcha.challenge) {
      setFormError("Captcha is not loaded. Please refresh it and try again.");
      return;
    }

    setSubmitting(true);
    try {
      await signup({
        email: values.email.trim(),
        username: values.username.trim(),
        password: values.password,
        role: values.role,
        captcha: { challenge_id: captcha.challenge.challenge_id, answer: values.captcha.trim() },
      });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Sign up failed.");
      setValues((prev) => ({ ...prev, captcha: "" }));
      void captcha.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="auth-card">
      <h1>Create your account</h1>
      <p className="muted">Save and search links worth keeping.</p>

      <form onSubmit={handleSubmit} noValidate>
        {formError && <Alert>{formError}</Alert>}

        <RoleSelect
          value={values.role}
          error={errors.role}
          onChange={(role) => setValues((prev) => ({ ...prev, role }))}
        />

        <Field
          label="Email"
          name="email"
          type="email"
          autoComplete="email"
          value={values.email}
          error={errors.email}
          onChange={(e) => set("email")(e.target.value)}
        />
        <Field
          label="Username"
          name="username"
          autoComplete="username"
          hint="At least 3 characters; letters, numbers, . _ -"
          value={values.username}
          error={errors.username}
          onChange={(e) => set("username")(e.target.value)}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters"
          value={values.password}
          error={errors.password}
          onChange={(e) => set("password")(e.target.value)}
        />
        <Field
          label="Confirm password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          value={values.confirmPassword}
          error={errors.confirmPassword}
          onChange={(e) => set("confirmPassword")(e.target.value)}
        />
        <CaptchaField
          challenge={captcha.challenge}
          loading={captcha.loading}
          error={captcha.error}
          value={values.captcha}
          fieldError={errors.captcha}
          onChange={set("captcha")}
          onRefresh={captcha.refresh}
        />

        <Button type="submit" loading={submitting}>
          Create account
        </Button>
      </form>

      <p className="muted switch">
        Already registered?{" "}
        <button type="button" className="link" onClick={onSwitchToLogin}>
          Sign in
        </button>
      </p>
    </Card>
  );
}
