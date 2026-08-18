# Registration widget for socioturtle.com

A self-contained lead-capture form for the marketing site. No build step, no
framework, and no dependency on the host page's CSS — every style is injected
under an `st-` prefix so it cannot collide with Tailwind.

## Install

socioturtle.com is served from GitHub Pages (repo `supriyakokate92.github.io`),
so "deploying" the widget means committing two things to that repo.

**1. Copy the script** into the site repo root, next to `index.html`:

```
socioturtle-register.js
```

**2. Add a mount point** wherever the inline form should appear in `index.html`
— the hero section is the usual spot:

```html
<div id="socioturtle-register"></div>
```

**3. Add the script tag** just before `</body>`:

```html
<script
  src="/socioturtle-register.js"
  data-api="https://api.socioturtle.com"
  data-modal-delay="20000"
></script>
```

That is the whole integration. The widget renders the inline card immediately and
shows the popup after the delay.

## Options

All configured as `data-*` attributes on the script tag.

| Attribute | Default | Meaning |
| --- | --- | --- |
| `data-api` | *(required)* | Base URL of the API |
| `data-mount` | `#socioturtle-register` | Selector for the inline card |
| `data-modal` | `on` | `off` disables the popup entirely |
| `data-modal-delay` | `20000` | Milliseconds before the popup appears |
| `data-source` | `website` | Attribution label stored on each lead |

Use `data-source` to tell campaigns apart — e.g. `data-source="instagram-bio"` on
a landing page — and the value shows up in the CSV export.

## Opening the popup from your own button

The widget exposes one global:

```html
<button onclick="SocioTurtleRegister.open()">Register</button>
```

## Popup behaviour

The popup is deliberately restrained, because an aggressive one costs more traffic
than it captures:

- never shown to someone who already registered (`localStorage`)
- dismissing it snoozes the popup for 30 days
- closes on Escape, on the ✕, or on a click outside
- never shown twice in one page view

## Before it works in production

CORS is the thing that catches people out. The API must list the marketing site
as an allowed origin or the browser silently blocks every request:

```
CORS_ORIGINS=["https://www.socioturtle.com","https://socioturtle.com"]
```

Include both the apex and `www` — they are different origins to a browser.

## Local testing

```bash
cd widget && python3 -m http.server 8080
```

Open http://localhost:8080/demo.html with the API running on port 8000. The demo
page mimics the real site's header and hero so the widget can be checked in
context. `demo.html` is for local use only — do not copy it to the site repo.
