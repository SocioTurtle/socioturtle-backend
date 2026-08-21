import { useEffect, useState } from "react";

import { AuthProvider, useAuth } from "./core/hooks/useAuth";
import type { ApiClient } from "./core/api/client";
import { Button } from "./components/ui";
import { ActivateScreen } from "./screens/ActivateScreen";
import { AdminScreen } from "./screens/AdminScreen";
import { Dashboard } from "./screens/Dashboard";
import { LoginScreen } from "./screens/LoginScreen";
import { SearchScreen } from "./screens/SearchScreen";
import { SignupScreen } from "./screens/SignupScreen";

type AuthView = "login" | "signup";
type AppView = "dashboard" | "resources" | "admin";

/** Reads ?invite=… once; the app has no router, so this is the whole of routing. */
function readInviteToken(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("invite");
}

function Routes({ client }: { client: ApiClient }) {
  const { user, initialising, logout } = useAuth();
  const [authView, setAuthView] = useState<AuthView>("login");
  const [appView, setAppView] = useState<AppView>("dashboard");
  const [inviteToken, setInviteToken] = useState<string | null>(readInviteToken);

  // Strip the token from the address bar so it is not left in history or copied
  // into a shared link.
  useEffect(() => {
    if (inviteToken) {
      window.history.replaceState({}, "", window.location.pathname);
    }
  }, [inviteToken]);

  if (initialising) return <p className="muted centered">Loading…</p>;

  if (inviteToken) {
    return (
      <ActivateScreen client={client} token={inviteToken} onDone={() => setInviteToken(null)} />
    );
  }

  if (!user) {
    return authView === "login" ? (
      <LoginScreen client={client} onSwitchToSignup={() => setAuthView("signup")} />
    ) : (
      <SignupScreen client={client} onSwitchToLogin={() => setAuthView("login")} />
    );
  }

  return (
    <>
      {/* Nav only renders once a user is logged in — logged-out visitors
          above never reach this branch, so there's no separate check needed. */}
      <nav className="app-nav">
        <div className="app-nav-tabs">
          <button
            className={appView === "dashboard" ? "tab tab-active" : "tab"}
            onClick={() => setAppView("dashboard")}
          >
            Dashboard
          </button>
          <button
            className={appView === "resources" ? "tab tab-active" : "tab"}
            onClick={() => setAppView("resources")}
          >
            Resources
          </button>
          {user.is_admin && (
            <button
              className={appView === "admin" ? "tab tab-active" : "tab"}
              onClick={() => setAppView("admin")}
            >
              Admin
            </button>
          )}
        </div>
        <div className="app-nav-user">
          <span className="muted">{user.username}</span>
          <Button variant="ghost" onClick={() => void logout()}>
            Sign out
          </Button>
        </div>
      </nav>
      {appView === "admin" && user.is_admin ? (
        <AdminScreen client={client} />
      ) : appView === "resources" ? (
        <SearchScreen client={client} />
      ) : (
        <Dashboard onGoToResources={() => setAppView("resources")} />
      )}
    </>
  );
}

export default function App({ client }: { client: ApiClient }) {
  return (
    <AuthProvider client={client}>
      <main className="app">
        <Routes client={client} />
      </main>
    </AuthProvider>
  );
}
