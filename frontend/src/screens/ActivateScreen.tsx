import { useEffect, useState, type FormEvent } from "react";

import { Alert, Button, Card, Field } from "../components/ui";
import type { ApiClient } from "../core/api/client";
import { inviteApi } from "../core/api/endpoints";
import { useAuth } from "../core/hooks/useAuth";
import type { InviteCheck } from "../core/types";

/** Landing page for the one-time link sent in the invite email. */
export function ActivateScreen({
  client,
  token,
  onDone,
}: {
  client: ApiClient;
  token: string;
  onDone: () => void;
}) {
  const { refreshUser } = useAuth();
  const [check, setCheck] = useState<InviteCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState({ username: "", password: "", confirmPassword: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await inviteApi(client).check(token);
        if (!cancelled) setCheck(result);
      } catch {
        if (!cancelled) {
          setCheck({
            valid: false,
            name: null,
            email: null,
            role: null,
            reason: "We could not verify this invitation. Please try the link again.",
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [client, token]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    const found: Record<string, string> = {};
    const username = values.username.trim();
    if (!username) found.username = "Choose a username.";
    else if (username.length < 3) found.username = "Must be at least 3 characters.";
    else if (!/^[a-zA-Z0-9_.-]+$/.test(username))
      found.username = "Only letters, numbers, and . _ - are allowed.";
    if (!values.password) found.password = "Choose a password.";
    else if (values.password.length < 8) found.password = "Must be at least 8 characters.";
    if (values.confirmPassword !== values.password)
      found.confirmPassword = "Passwords do not match.";

    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      const tokens = await inviteApi(client).activate({
        token,
        username,
        password: values.password,
      });
      await client.saveTokens(tokens);
      await refreshUser();
      onDone();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not activate your account.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <p className="muted centered">Checking your invitation…</p>;

  if (!check?.valid) {
    return (
      <Card className="auth-card">
        <h1>Invitation not valid</h1>
        <p className="muted">{check?.reason ?? "This link cannot be used."}</p>
        <p className="muted switch">
          <button type="button" className="link" onClick={onDone}>
            Go to sign in
          </button>
        </p>
      </Card>
    );
  }

  return (
    <Card className="auth-card">
      <h1>Welcome, {check.name?.split(" ")[0] ?? "there"}</h1>
      <p className="muted">
        Setting up your SocioTurtle account for {check.email}. Choose a username and password to
        finish.
      </p>

      <form onSubmit={handleSubmit} noValidate>
        {formError && <Alert>{formError}</Alert>}

        <Field
          label="Username"
          name="username"
          autoComplete="username"
          hint="At least 3 characters; letters, numbers, . _ -"
          value={values.username}
          error={errors.username}
          onChange={(e) => setValues((p) => ({ ...p, username: e.target.value }))}
        />
        <Field
          label="Password"
          name="password"
          type="password"
          autoComplete="new-password"
          hint="At least 8 characters"
          value={values.password}
          error={errors.password}
          onChange={(e) => setValues((p) => ({ ...p, password: e.target.value }))}
        />
        <Field
          label="Confirm password"
          name="confirmPassword"
          type="password"
          autoComplete="new-password"
          value={values.confirmPassword}
          error={errors.confirmPassword}
          onChange={(e) => setValues((p) => ({ ...p, confirmPassword: e.target.value }))}
        />

        <Button type="submit" loading={submitting}>
          Activate my account
        </Button>
      </form>
    </Card>
  );
}
