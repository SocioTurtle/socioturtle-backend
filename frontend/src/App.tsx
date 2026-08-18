import { useEffect, useState } from "react";

import { AuthProvider, useAuth } from "./core/hooks/useAuth";
import type { ApiClient } from "./core/api/client";
import { ActivateScreen } from "./screens/ActivateScreen";
import { AdminScreen } from "./screens/AdminScreen";
import { LoginScreen } from "./screens/LoginScreen";
import { SearchScreen } from "./screens/SearchScreen";
import { SignupScreen } from "./screens/SignupScreen";

type AuthView = "login" | "signup";
type AppView = "search" | "admin";

/** Reads ?invite=… once; the app has no router, so this is the whole of routing. */
function readInviteToken(): string | null {
  if (typeof window === "undefined") return null;
  return new URLSearchParams(window.location.search).get("invite");
}

function Routes({ client }: { client: ApiClient }) {
  const { user, initialising } = useAuth();
  const [authView, setAuthView] = useState<AuthView>("login");
  const [appView, setAppView] = useState<AppView>("search");
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
      {user.is_admin && (
        <nav className="app-nav">
          <button
            className={appView === "search" ? "tab tab-active" : "tab"}
            onClick={() => setAppView("search")}
          >
            Resources
          </button>
          <button
            className={appView === "admin" ? "tab tab-active" : "tab"}
            onClick={() => setAppView("admin")}
          >
            Admin
          </button>
        </nav>
      )}
      {appView === "admin" && user.is_admin ? (
        <AdminScreen client={client} />
      ) : (
        <SearchScreen client={client} />
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
