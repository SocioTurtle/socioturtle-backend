import { ROLES, type Role } from "../core/types";

export function RoleSelect({
  value,
  error,
  onChange,
}: {
  value: Role | null;
  error?: string;
  onChange: (role: Role) => void;
}) {
  return (
    <fieldset className="role-select">
      <legend>I am joining as</legend>
      <div className="role-options">
        {ROLES.map((role) => (
          <label
            key={role.value}
            className={value === role.value ? "role-option role-option-active" : "role-option"}
          >
            <input
              type="radio"
              name="role"
              value={role.value}
              checked={value === role.value}
              onChange={() => onChange(role.value)}
            />
            <span className="role-label">{role.label}</span>
            <span className="role-blurb">{role.blurb}</span>
          </label>
        ))}
      </div>
      {error && (
        <span className="error" role="alert">
          {error}
        </span>
      )}
    </fieldset>
  );
}
