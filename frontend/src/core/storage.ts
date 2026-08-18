/**
 * Token persistence is the one thing web and React Native genuinely differ on.
 * Everything else in core/ stays platform-free by depending on this interface;
 * a native app supplies an AsyncStorage/SecureStore implementation instead.
 */
export interface TokenStorage {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
}

export const ACCESS_TOKEN_KEY = "st.access_token";
export const REFRESH_TOKEN_KEY = "st.refresh_token";

export const memoryStorage = (): TokenStorage => {
  const store = new Map<string, string>();
  return {
    async get(key) {
      return store.get(key) ?? null;
    },
    async set(key, value) {
      store.set(key, value);
    },
    async remove(key) {
      store.delete(key);
    },
  };
};

export const webStorage = (): TokenStorage => {
  if (typeof localStorage === "undefined") return memoryStorage();
  return {
    async get(key) {
      return localStorage.getItem(key);
    },
    async set(key, value) {
      localStorage.setItem(key, value);
    },
    async remove(key) {
      localStorage.removeItem(key);
    },
  };
};
