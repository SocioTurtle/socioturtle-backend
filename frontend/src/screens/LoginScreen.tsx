import { useState, type FormEvent } from "react";

import { CaptchaField } from "../components/CaptchaField";
import { Alert, Button, Card, Field } from "../components/ui";
import type { ApiClient } from "../core/api/client";
import { useAuth } from "../core/hooks/useAuth";
import { useCaptcha } from "../core/hooks/useCaptcha";
import { hasErrors, validateLogin, type Errors, type LoginField } from "../core/validation";

export function LoginScreen({
  client,
  onSwitchToSignup,
}: {
  client: ApiClient;
  onSwitchToSignup: () => void;
}) {
  const { login } = useAuth();
  const captcha = useCaptcha(client);

  const [values, setValues] = useState({ identifier: "", password: "", captcha: "" });
  const [errors, setErrors] = useState<Errors<LoginField>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (key: keyof typeof values) => (value: string) =>
    setValues((prev) => ({ ...prev, [key]: value }));

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    const found = validateLogin(values);
    setErrors(found);
    if (hasErrors(found)) return;

    if (!captcha.challenge) {
      setFormError("Captcha is not loaded. Please refresh it and try again.");
      return;
    }

    setSubmitting(true);
    try {
      await login({
        identifier: values.identifier.trim(),
        password: values.password,
        captcha: { challenge_id: captcha.challenge.challenge_id, answer: values.captcha.trim() },
      });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Login failed.");
      // Challenges are single-use, so a failed attempt always needs a fresh one.
      setValues((prev) => ({ ...prev, captcha: "" }));
      void captcha.refresh();
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card className="auth-card">
      <h1>Welcome back</h1>
      <p className="muted">Sign in to manage your saved resources.</p>

      <form onSubmit={handleSubmit} noValidate>
        {formError && <Alert>{formError}</Alert>}

        <Field
          label="Email or username"
          name="identifier"
          autoComplete="username"
          value={values.identifier}
          error={errors.identifier}
          onChange={(e) => set("identifier")(e.target.value)}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="current-password"
          value={values.password}
          error={errors.password}
          onChange={(e) => set("password")(e.target.value)}
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
          Sign in
        </Button>
      </form>

      <p className="muted switch">
        No account?{" "}
        <button type="button" className="link" onClick={onSwitchToSignup}>
          Create one
        </button>
      </p>
    </Card>
  );
}
