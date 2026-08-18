import { Alert, Button, Card } from "../components/ui";
import type { ApiClient } from "../core/api/client";
import { useAuth } from "../core/hooks/useAuth";
import { useSearch } from "../core/hooks/useSearch";

export function SearchScreen({ client }: { client: ApiClient }) {
  const { user, logout } = useAuth();
  const search = useSearch(client);

  return (
    <div className="search-screen">
      <header className="topbar">
        <div>
          <h1>Socioturtle</h1>
          <p className="muted">Search saved resources</p>
        </div>
        <div className="topbar-actions">
          {user ? (
            <>
              <span className="muted">{user.username}</span>
              <span className={`role-badge role-badge-${user.role}`}>{user.role}</span>
              <Button variant="ghost" onClick={() => void logout()}>
                Sign out
              </Button>
            </>
          ) : (
            <span className="muted">Browsing as guest</span>
          )}
        </div>
      </header>

      <div className="search-controls">
        <input
          className="input search-input"
          type="search"
          placeholder="Search titles, descriptions, tags, URLs…"
          value={search.query}
          onChange={(e) => search.setQuery(e.target.value)}
          aria-label="Search resources"
        />
        {search.tag && (
          <button type="button" className="chip chip-active" onClick={() => search.setTag(null)}>
            {search.tag} ✕
          </button>
        )}
      </div>

      {search.error && <Alert>{search.error}</Alert>}

      <p className="muted result-count" aria-live="polite">
        {search.loading && search.items.length === 0
          ? "Searching…"
          : `${search.total} result${search.total === 1 ? "" : "s"}`}
      </p>

      <ul className="results">
        {search.items.map((resource) => (
          <li key={resource.id}>
            <Card>
              <a href={resource.url} target="_blank" rel="noreferrer noopener" className="result-title">
                {resource.title}
              </a>
              <p className="result-url">{resource.url}</p>
              {resource.description && <p>{resource.description}</p>}
              <div className="tags">
                {resource.tags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    className="chip"
                    onClick={() => search.setTag(tag)}
                  >
                    {tag}
                  </button>
                ))}
              </div>
            </Card>
          </li>
        ))}
      </ul>

      {!search.loading && search.items.length === 0 && (
        <p className="muted empty">No resources matched your search.</p>
      )}

      {search.hasMore && (
        <Button variant="ghost" loading={search.loading} onClick={search.loadMore}>
          Load more
        </Button>
      )}
    </div>
  );
}
