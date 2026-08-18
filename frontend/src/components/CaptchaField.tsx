import type { CaptchaChallenge } from "../core/types";
import { Field } from "./ui";

export function CaptchaField({
  challenge,
  loading,
  error,
  value,
  fieldError,
  onChange,
  onRefresh,
}: {
  challenge: CaptchaChallenge | null;
  loading: boolean;
  error: string | null;
  value: string;
  fieldError?: string;
  onChange: (value: string) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="captcha">
      <div className="captcha-row">
        {loading && <div className="captcha-placeholder">Loading…</div>}
        {!loading && challenge && (
          <img src={challenge.image_data_uri} alt="Captcha challenge" className="captcha-image" />
        )}
        {!loading && !challenge && <div className="captcha-placeholder">{error ?? "Unavailable"}</div>}
        <button type="button" className="btn btn-ghost captcha-refresh" onClick={onRefresh}>
          ↻ New image
        </button>
      </div>
      <Field
        label="Type the characters above"
        name="captcha"
        autoComplete="off"
        autoCapitalize="characters"
        spellCheck={false}
        value={value}
        error={fieldError}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
