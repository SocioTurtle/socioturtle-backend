import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Button({
  variant = "primary",
  loading = false,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost";
  loading?: boolean;
}) {
  return (
    <button
      {...props}
      disabled={props.disabled || loading}
      className={`btn btn-${variant} ${props.className ?? ""}`}
    >
      {loading ? "Please wait…" : children}
    </button>
  );
}

export function Field({
  label,
  error,
  hint,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
  hint?: string;
}) {
  const id = props.id ?? props.name;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        {...props}
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
        className={error ? "input input-error" : "input"}
      />
      {hint && !error && <span className="hint">{hint}</span>}
      {error && (
        <span className="error" id={`${id}-error`} role="alert">
          {error}
        </span>
      )}
    </div>
  );
}

export function Alert({ children }: { children: ReactNode }) {
  return (
    <div className="alert" role="alert">
      {children}
    </div>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`card ${className}`}>{children}</div>;
}
