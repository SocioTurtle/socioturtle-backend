import { useCallback, useEffect, useState } from "react";

import { Alert, Button, Card } from "../components/ui";
import type { ApiClient } from "../core/api/client";
import { leadApi, newsletterApi } from "../core/api/endpoints";
import type { Lead, LeadList } from "../core/types";

type Tab = "leads" | "newsletter";

export function AdminScreen({ client }: { client: ApiClient }) {
  const [tab, setTab] = useState<Tab>("leads");

  return (
    <div className="admin">
      <div className="tabs" role="tablist">
        <button
          role="tab"
          aria-selected={tab === "leads"}
          className={tab === "leads" ? "tab tab-active" : "tab"}
          onClick={() => setTab("leads")}
        >
          Registrations
        </button>
        <button
          role="tab"
          aria-selected={tab === "newsletter"}
          className={tab === "newsletter" ? "tab tab-active" : "tab"}
          onClick={() => setTab("newsletter")}
        >
          Newsletter
        </button>
      </div>

      {tab === "leads" ? <LeadsPanel client={client} /> : <NewsletterPanel client={client} />}
    </div>
  );
}

function LeadsPanel({ client }: { client: ApiClient }) {
  const [data, setData] = useState<LeadList | null>(null);
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(
        await leadApi(client).list({
          role: role || undefined,
          status: status || undefined,
          q: q.trim() || undefined,
          limit: 200,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load registrations.");
    } finally {
      setLoading(false);
    }
  }, [client, role, status, q]);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 250);
    return () => clearTimeout(timer);
  }, [load]);

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function toggleAll(leads: Lead[]) {
    setSelected((prev) =>
      prev.size === leads.length ? new Set() : new Set(leads.map((l) => l.id)),
    );
  }

  async function invite(payload: { lead_ids?: number[]; all_new?: boolean }) {
    setBusy(true);
    setNotice(null);
    setError(null);
    try {
      const result = await leadApi(client).invite(payload);
      const bits = [`${result.sent} invite${result.sent === 1 ? "" : "s"} sent`];
      if (result.skipped) bits.push(`${result.skipped} skipped`);
      if (result.failed) bits.push(`${result.failed} failed`);
      setNotice(bits.join(", ") + ".");
      if (result.errors.length) setError(result.errors.join(" | "));
      setSelected(new Set());
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send invites.");
    } finally {
      setBusy(false);
    }
  }

  async function exportCsv() {
    try {
      const csv = await client.requestText("/api/leads/export.csv", { auth: true });
      const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = "socioturtle-leads.csv";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed.");
    }
  }

  const leads = data?.items ?? [];
  const counts = data?.counts ?? {};

  return (
    <>
      <div className="stats">
        {[
          ["Total", counts.total],
          ["Students", counts.student],
          ["Mentors", counts.mentor],
          ["Not invited", counts.new],
          ["Invited", counts.invited],
          ["Activated", counts.activated],
          ["Newsletter", counts.newsletter],
        ].map(([label, value]) => (
          <div className="stat" key={String(label)}>
            <span className="stat-value">{value ?? 0}</span>
            <span className="stat-label">{label}</span>
          </div>
        ))}
      </div>

      {error && <Alert>{error}</Alert>}
      {notice && <p className="notice">{notice}</p>}

      <div className="admin-controls">
        <input
          className="input"
          type="search"
          placeholder="Search name, email, organisation…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Search registrations"
        />
        <select className="input" value={role} onChange={(e) => setRole(e.target.value)} aria-label="Filter by role">
          <option value="">All roles</option>
          <option value="student">Students</option>
          <option value="mentor">Mentors</option>
        </select>
        <select className="input" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
          <option value="">All statuses</option>
          <option value="new">Not invited</option>
          <option value="invited">Invited</option>
          <option value="activated">Activated</option>
        </select>
      </div>

      <div className="admin-actions">
        <Button loading={busy} disabled={selected.size === 0} onClick={() => invite({ lead_ids: [...selected] })}>
          Invite selected ({selected.size})
        </Button>
        <Button variant="ghost" loading={busy} onClick={() => invite({ all_new: true })}>
          Invite everyone not yet invited
        </Button>
        <Button variant="ghost" onClick={exportCsv}>
          Export CSV
        </Button>
      </div>

      {loading && leads.length === 0 && <p className="muted">Loading…</p>}

      {leads.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>
                  <input
                    type="checkbox"
                    checked={selected.size === leads.length}
                    onChange={() => toggleAll(leads)}
                    aria-label="Select all"
                  />
                </th>
                <th>Name</th>
                <th>Email</th>
                <th>Role</th>
                <th>Organisation</th>
                <th>News</th>
                <th>Status</th>
                <th>Registered</th>
              </tr>
            </thead>
            <tbody>
              {leads.map((lead) => (
                <tr key={lead.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={selected.has(lead.id)}
                      onChange={() => toggle(lead.id)}
                      aria-label={`Select ${lead.email}`}
                    />
                  </td>
                  <td>{lead.name}</td>
                  <td className="mono">{lead.email}</td>
                  <td>
                    <span className={`role-badge role-badge-${lead.role}`}>{lead.role}</span>
                  </td>
                  <td>{lead.organisation || "—"}</td>
                  <td>{lead.newsletter_opt_in ? "yes" : "—"}</td>
                  <td>
                    <span className={`status status-${lead.status}`}>{lead.status}</span>
                  </td>
                  <td className="muted">{new Date(lead.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && leads.length === 0 && <p className="muted empty">No registrations yet.</p>}
    </>
  );
}

function NewsletterPanel({ client }: { client: ApiClient }) {
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [audience, setAudience] = useState("all");
  const [testTo, setTestTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function send(test: boolean) {
    setError(null);
    setNotice(null);
    if (!subject.trim() || !body.trim()) {
      setError("Subject and body are both required.");
      return;
    }
    if (test && !testTo.trim()) {
      setError("Enter an address to send the test to.");
      return;
    }
    if (
      !test &&
      !window.confirm(`Send "${subject}" to every opted-in ${audience} subscriber? This cannot be undone.`)
    ) {
      return;
    }

    setBusy(true);
    try {
      const result = await newsletterApi(client).send({
        subject: subject.trim(),
        body_markdown: body,
        audience,
        test_to: test ? testTo.trim() : undefined,
      });
      setNotice(
        result.test
          ? `Test sent to ${testTo}.`
          : `Sent to ${result.recipient_count} subscriber${result.recipient_count === 1 ? "" : "s"}` +
            (result.failed_count ? `, ${result.failed_count} failed.` : "."),
      );
      if (!result.test) {
        setSubject("");
        setBody("");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <h2 className="panel-h">Compose this week's issue</h2>
      <p className="muted">
        Markdown is supported. An unsubscribe link is added automatically — you do not need to
        include one.
      </p>

      {error && <Alert>{error}</Alert>}
      {notice && <p className="notice">{notice}</p>}

      <div className="field">
        <label htmlFor="nl-subject">Subject</label>
        <input
          id="nl-subject"
          className="input"
          value={subject}
          onChange={(e) => setSubject(e.target.value)}
          placeholder="SocioTurtle Weekly — 5 projects worth building"
        />
      </div>

      <div className="field">
        <label htmlFor="nl-body">Body (markdown)</label>
        <textarea
          id="nl-body"
          className="input textarea"
          rows={14}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={"## This week\n\n- A link worth reading\n- Another one\n\nSee you next week!"}
        />
      </div>

      <div className="field">
        <label htmlFor="nl-audience">Audience</label>
        <select
          id="nl-audience"
          className="input"
          value={audience}
          onChange={(e) => setAudience(e.target.value)}
        >
          <option value="all">Everyone opted in</option>
          <option value="student">Students only</option>
          <option value="mentor">Mentors only</option>
        </select>
      </div>

      <div className="field">
        <label htmlFor="nl-test">Send a test to</label>
        <input
          id="nl-test"
          className="input"
          type="email"
          value={testTo}
          onChange={(e) => setTestTo(e.target.value)}
          placeholder="you@socioturtle.com"
        />
      </div>

      <div className="admin-actions">
        <Button variant="ghost" loading={busy} onClick={() => send(true)}>
          Send test
        </Button>
        <Button loading={busy} onClick={() => send(false)}>
          Send to subscribers
        </Button>
      </div>
    </Card>
  );
}
