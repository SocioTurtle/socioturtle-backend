import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiClient } from "../api/client";
import { resourceApi } from "../api/endpoints";
import type { Resource } from "../types";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 300;

export function useSearch(client: ApiClient) {
  const [query, setQuery] = useState("");
  const [tag, setTag] = useState<string | null>(null);
  const [items, setItems] = useState<Resource[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Guards against a slow early request overwriting a newer result set.
  const requestId = useRef(0);

  const run = useCallback(
    async (nextOffset: number, append: boolean) => {
      const id = ++requestId.current;
      setLoading(true);
      setError(null);
      try {
        const results = await resourceApi(client).search({
          q: query.trim(),
          tag: tag ?? undefined,
          limit: PAGE_SIZE,
          offset: nextOffset,
        });
        if (id !== requestId.current) return;
        setItems((prev) => (append ? [...prev, ...results.items] : results.items));
        setTotal(results.total);
        setOffset(nextOffset);
      } catch (err) {
        if (id !== requestId.current) return;
        setError(err instanceof Error ? err.message : "Search failed.");
        if (!append) setItems([]);
      } finally {
        if (id === requestId.current) setLoading(false);
      }
    },
    [client, query, tag],
  );

  useEffect(() => {
    const timer = setTimeout(() => void run(0, false), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [run]);

  const loadMore = useCallback(() => {
    if (!loading && items.length < total) void run(offset + PAGE_SIZE, true);
  }, [loading, items.length, total, offset, run]);

  return {
    query,
    setQuery,
    tag,
    setTag,
    items,
    total,
    loading,
    error,
    loadMore,
    hasMore: items.length < total,
  };
}
