import { useCallback, useEffect, useState } from "react";

import type { ApiClient } from "../api/client";
import { authApi } from "../api/endpoints";
import type { CaptchaChallenge } from "../types";

export function useCaptcha(client: ApiClient) {
  const [challenge, setChallenge] = useState<CaptchaChallenge | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setChallenge(await authApi(client).captcha());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load captcha.");
      setChallenge(null);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { challenge, loading, error, refresh };
}
