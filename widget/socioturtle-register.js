/*!
 * SocioTurtle quick-registration widget.
 *
 * Drop-in for a static site (GitHub Pages) — no build step, no framework, and no
 * dependency on the host page's CSS. All styles are injected under an `st-`
 * prefix so they cannot collide with Tailwind or anything else on the page.
 *
 *   <div id="socioturtle-register"></div>
 *   <script src="/socioturtle-register.js"
 *           data-api="https://api.socioturtle.com"
 *           data-modal-delay="20000"></script>
 *
 * Options (data-* attributes on the script tag):
 *   data-api           API base URL                      (required)
 *   data-mount         inline container selector         (default #socioturtle-register)
 *   data-modal         "on" | "off"                      (default on)
 *   data-modal-delay   ms before the popup appears       (default 20000)
 *   data-source        attribution label stored per lead (default website)
 */
(function () {
  "use strict";

  var script = document.currentScript;
  var CFG = {
    api: (script.getAttribute("data-api") || "").replace(/\/$/, ""),
    mount: script.getAttribute("data-mount") || "#socioturtle-register",
    modal: (script.getAttribute("data-modal") || "on") !== "off",
    modalDelay: parseInt(script.getAttribute("data-modal-delay") || "20000", 10),
    source: script.getAttribute("data-source") || "website",
  };

  var DONE_KEY = "st.registered";
  var SNOOZE_KEY = "st.modal.snoozed";
  var SNOOZE_DAYS = 30;

  if (!CFG.api) {
    console.error("[socioturtle] data-api is required on the script tag");
    return;
  }

  /* ---------------------------------------------------------------- styles */

  var CSS = [
    ".st-card{background:#fff;border:1px solid #dfe3ec;border-radius:12px;padding:22px;",
    "font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;color:#16192a;",
    "line-height:1.5;box-sizing:border-box;max-width:520px;width:100%;}",
    ".st-card *,.st-card *:before,.st-card *:after{box-sizing:border-box;}",
    ".st-h{font-size:1.25rem;font-weight:700;margin:0 0 4px;}",
    ".st-sub{font-size:.88rem;color:#6b7284;margin:0 0 16px;}",
    ".st-roles{display:flex;gap:10px;margin-bottom:12px;}",
    ".st-role{flex:1;border:1px solid #dfe3ec;border-radius:8px;padding:10px 12px;cursor:pointer;",
    "text-align:left;background:#fff;font:inherit;color:inherit;}",
    ".st-role:hover{border-color:#b9c0d6;}",
    ".st-role[aria-pressed='true']{border-color:#4c5fd7;background:#eef0fb;}",
    ".st-role b{display:block;font-size:.92rem;}",
    ".st-role span{display:block;font-size:.74rem;color:#6b7284;}",
    ".st-row{display:flex;gap:10px;}",
    ".st-row>*{flex:1;min-width:0;}",
    ".st-f{margin-bottom:10px;}",
    ".st-f label{display:block;font-size:.8rem;font-weight:600;margin-bottom:4px;}",
    ".st-f input{width:100%;padding:9px 11px;border:1px solid #dfe3ec;border-radius:8px;",
    "font-size:.92rem;font-family:inherit;color:#16192a;background:#fff;}",
    ".st-f input:focus-visible{outline:2px solid #4c5fd7;outline-offset:1px;}",
    ".st-f input.st-bad{border-color:#c0392b;}",
    ".st-f-highlight{background:#f3f4fd;border:1px solid #c7cdf5;border-radius:10px;",
    "padding:10px 12px 4px;box-shadow:0 0 0 3px rgba(76,95,215,.12);}",
    ".st-f-highlight label{color:#3543b3;}",
    ".st-f-highlight input{border-color:#4c5fd7;}",
    ".st-row-inline{display:flex;gap:8px;}",
    ".st-row-inline input{flex:1;min-width:0;}",
    ".st-otp-btn{flex:none;background:#4c5fd7;color:#fff;border:none;border-radius:8px;",
    "padding:9px 12px;font-size:.82rem;font-weight:600;cursor:pointer;font-family:inherit;",
    "white-space:nowrap;}",
    ".st-otp-btn:disabled{opacity:.6;cursor:not-allowed;}",
    ".st-ok-mini{display:block;font-size:.74rem;color:#1a7f4b;margin-top:4px;}",
    ".st-hint{display:block;font-size:.74rem;color:#6b7284;margin-top:4px;}",
    ".st-otp-row{margin-top:10px;}",
    ".st-err{display:block;font-size:.74rem;color:#c0392b;margin-top:3px;}",
    ".st-link{background:none;border:none;padding:0;color:#4c5fd7;font:inherit;font-size:.78rem;",
    "cursor:pointer;text-decoration:underline;}",
    ".st-check{display:flex;gap:8px;align-items:flex-start;font-size:.8rem;color:#6b7284;margin:12px 0;}",
    ".st-check input{margin-top:2px;flex:none;}",
    ".st-btn{width:100%;background:#4c5fd7;color:#fff;border:none;border-radius:8px;padding:11px 16px;",
    "font-size:.95rem;font-weight:600;cursor:pointer;font-family:inherit;}",
    ".st-btn:disabled{opacity:.6;cursor:not-allowed;}",
    ".st-alert{background:#fdecea;border:1px solid #f5c6c0;color:#922b21;padding:9px 11px;",
    "border-radius:8px;font-size:.84rem;margin-bottom:12px;}",
    ".st-ok{text-align:center;padding:16px 0;}",
    ".st-ok .st-tick{font-size:2rem;line-height:1;}",
    ".st-fine{font-size:.72rem;color:#8b91a1;margin:10px 0 0;text-align:center;}",
    ".st-ov{position:fixed;inset:0;background:rgba(16,19,42,.55);display:flex;align-items:center;",
    "justify-content:center;padding:16px;z-index:99999;overflow-y:auto;}",
    ".st-ov .st-card{position:relative;margin:auto;}",
    ".st-x{position:absolute;top:10px;right:12px;background:none;border:none;font-size:1.4rem;",
    "line-height:1;color:#6b7284;cursor:pointer;padding:4px 8px;}",
    "@media(max-width:480px){.st-roles{flex-direction:column;}.st-row{flex-direction:column;gap:0;}}",
  ].join("");

  function injectStyles() {
    if (document.getElementById("st-styles")) return;
    var el = document.createElement("style");
    el.id = "st-styles";
    el.textContent = CSS;
    document.head.appendChild(el);
  }

  /* ------------------------------------------------------------- utilities */

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function store(key, value) {
    try {
      value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value);
    } catch (e) {
      /* private browsing — degrade quietly */
    }
  }

  function read(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function hasRegistered() {
    return read(DONE_KEY) === "1";
  }

  function snoozed() {
    var until = parseInt(read(SNOOZE_KEY) || "0", 10);
    return until > Date.now();
  }

  function snooze() {
    store(SNOOZE_KEY, String(Date.now() + SNOOZE_DAYS * 864e5));
  }

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  /* ---------------------------------------------------------------- widget */

  function createForm(container, opts) {
    var role = null;
    var busy = false;
    var otpBusy = false;
    var emailVerifyToken = null;
    var verifiedEmail = null;

    container.className = "st-card";
    container.innerHTML = [
      opts.dismissible ? '<button class="st-x" type="button" aria-label="Close">&times;</button>' : "",
      '<h2 class="st-h">Get early access</h2>',
      '<p class="st-sub">Join SocioTurtle as a student, mentor, or employer. We will email you an invitation.</p>',
      '<div class="st-alert" data-alert hidden></div>',
      '<div class="st-roles" role="group" aria-label="Register as">',
      '<button type="button" class="st-role" data-role="student" aria-pressed="false">',
      "<b>Student</b><span>Build skills, get verified, get hired.</span></button>",
      '<button type="button" class="st-role" data-role="mentor" aria-pressed="false">',
      "<b>Mentor</b><span>Guide learners and verify portfolios.</span></button>",
      '<button type="button" class="st-role" data-role="employer" aria-pressed="false">',
      "<b>Employer</b><span>Discover talent, hire with confidence.</span></button>",
      "</div>",
      '<span class="st-err" data-err-role hidden></span>',
      '<form novalidate>',
      '<div class="st-f"><label for="st-name">Full name</label>',
      '<input id="st-name" name="name" autocomplete="name">',
      '<span class="st-err" data-err-name hidden></span></div>',
      '<div class="st-f st-f-highlight"><label for="st-email">Email</label>',
      '<div class="st-row-inline"><input id="st-email" name="email" type="email" autocomplete="email">',
      '<button type="button" class="st-otp-btn" data-otp-send>Send code</button></div>',
      '<span class="st-err" data-err-email hidden></span>',
      '<span class="st-ok-mini" data-email-verified hidden>✓ Email verified</span>',
      '<div class="st-otp-row" data-otp-row hidden>',
      '<label for="st-otp">Verification code</label>',
      '<div class="st-row-inline"><input id="st-otp" name="otp" inputmode="numeric" pattern="[0-9]*" maxlength="6" placeholder="6-digit code">',
      '<button type="button" class="st-otp-btn" data-otp-verify>Verify</button></div>',
      '<span class="st-err" data-err-otp hidden></span>',
      '<span class="st-hint" data-otp-hint></span>',
      "</div>",
      "</div>",
      '<div class="st-row">',
      '<div class="st-f"><label for="st-phone">Phone <span style="font-weight:400;color:#8b91a1;">(optional)</span></label>',
      '<input id="st-phone" name="phone" autocomplete="tel"></div>',
      '<div class="st-f"><label for="st-org">College / company <span style="font-weight:400;color:#8b91a1;">(optional)</span></label>',
      '<input id="st-org" name="organisation" autocomplete="organization"></div>',
      "</div>",
      '<label class="st-check"><input type="checkbox" name="news">',
      "<span>Email me the weekly SocioTurtle newsletter. You can unsubscribe any time.</span></label>",
      '<button type="submit" class="st-btn">Register</button>',
      '<p class="st-fine">We will never email you a password.</p>',
      "</form>",
    ].join("");

    var form = container.querySelector("form");
    var alertBox = container.querySelector("[data-alert]");
    var closeBtn = container.querySelector(".st-x");

    if (closeBtn) closeBtn.addEventListener("click", opts.onClose);

    function setErr(field, message) {
      var el = container.querySelector("[data-err-" + field + "]");
      var input = form && form.elements[field === "role" ? "name" : field];
      if (el) {
        el.textContent = message || "";
        el.hidden = !message;
      }
      if (field !== "role" && input && input.classList) {
        input.classList.toggle("st-bad", !!message);
      }
    }

    function clearErrors() {
      ["role", "name", "email", "otp"].forEach(function (f) {
        setErr(f, "");
      });
      alertBox.hidden = true;
    }

    function showAlert(message) {
      alertBox.textContent = message;
      alertBox.hidden = false;
    }

    container.querySelectorAll(".st-role").forEach(function (button) {
      button.addEventListener("click", function () {
        role = button.getAttribute("data-role");
        container.querySelectorAll(".st-role").forEach(function (other) {
          other.setAttribute("aria-pressed", String(other === button));
        });
        setErr("role", "");
      });
    });

    var emailVerifiedBadge = container.querySelector("[data-email-verified]");
    var otpRow = container.querySelector("[data-otp-row]");
    var otpHint = container.querySelector("[data-otp-hint]");
    var otpSendBtn = container.querySelector("[data-otp-send]");
    var otpVerifyBtn = container.querySelector("[data-otp-verify]");

    function markEmailUnverified() {
      emailVerifyToken = null;
      verifiedEmail = null;
      emailVerifiedBadge.hidden = true;
    }

    form.elements.email.addEventListener("input", function () {
      var current = form.elements.email.value.trim();
      if (verifiedEmail && current !== verifiedEmail) markEmailUnverified();
    });

    otpSendBtn.addEventListener("click", function () {
      if (otpBusy) return;
      var email = form.elements.email.value.trim();
      setErr("email", "");

      if (!email || !EMAIL_RE.test(email)) {
        setErr("email", "Enter a valid email address.");
        return;
      }

      otpBusy = true;
      otpSendBtn.disabled = true;
      otpSendBtn.textContent = "Sending…";

      fetch(CFG.api + "/api/leads/otp/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var detail = result.body && result.body.detail;
            if (typeof detail !== "string") detail = "Could not send a code. Please try again.";
            setErr("email", detail);
            return;
          }
          markEmailUnverified();
          setErr("otp", "");
          otpRow.hidden = false;
          otpHint.textContent = "Code sent to " + email + ". It expires in a few minutes.";
          form.elements.otp.focus();
        })
        .catch(function () {
          setErr("email", "Could not reach the server. Please check your connection and try again.");
        })
        .finally(function () {
          otpBusy = false;
          otpSendBtn.disabled = false;
          otpSendBtn.textContent = "Send code";
        });
    });

    otpVerifyBtn.addEventListener("click", function () {
      if (otpBusy) return;
      var email = form.elements.email.value.trim();
      var code = form.elements.otp.value.trim();
      setErr("otp", "");

      if (!code) {
        setErr("otp", "Enter the 6-digit code sent to your email.");
        return;
      }

      otpBusy = true;
      otpVerifyBtn.disabled = true;
      otpVerifyBtn.textContent = "Verifying…";

      fetch(CFG.api + "/api/leads/otp/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email, code: code }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var detail = result.body && result.body.detail;
            if (typeof detail !== "string") detail = "Incorrect code. Please try again.";
            setErr("otp", detail);
            return;
          }
          emailVerifyToken = result.body.verify_token;
          verifiedEmail = email;
          emailVerifiedBadge.hidden = false;
          otpRow.hidden = true;
          form.elements.otp.value = "";
        })
        .catch(function () {
          setErr("otp", "Could not reach the server. Please check your connection and try again.");
        })
        .finally(function () {
          otpBusy = false;
          otpVerifyBtn.disabled = false;
          otpVerifyBtn.textContent = "Verify";
        });
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (busy) return;
      clearErrors();

      var name = form.elements.name.value.trim();
      var email = form.elements.email.value.trim();
      var bad = false;

      if (!role) {
        setErr("role", "Choose student, mentor, or employer.");
        bad = true;
      }
      if (!name) {
        setErr("name", "Please tell us your name.");
        bad = true;
      }
      if (!email) {
        setErr("email", "Email is required.");
        bad = true;
      } else if (!EMAIL_RE.test(email)) {
        setErr("email", "Enter a valid email address.");
        bad = true;
      } else if (!emailVerifyToken || verifiedEmail !== email) {
        setErr("email", "Please verify your email address first.");
        bad = true;
      }
      if (bad) return;

      busy = true;
      var submit = form.querySelector(".st-btn");
      submit.disabled = true;
      submit.textContent = "Registering…";

      fetch(CFG.api + "/api/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name,
          email: email,
          role: role,
          phone: form.elements.phone.value.trim(),
          organisation: form.elements.organisation.value.trim(),
          newsletter_opt_in: form.elements.news.checked,
          source: CFG.source,
          email_verify_token: emailVerifyToken,
        }),
      })
        .then(function (response) {
          return response.json().then(function (body) {
            return { ok: response.ok, body: body };
          });
        })
        .then(function (result) {
          if (!result.ok) {
            var detail = result.body && result.body.detail;
            if (typeof detail !== "string") detail = "Something went wrong. Please try again.";
            showAlert(detail);
            return;
          }
          store(DONE_KEY, "1");
          container.innerHTML =
            '<div class="st-ok"><div class="st-tick">🎉</div>' +
            "<h2 class='st-h'>You're on the list</h2>" +
            '<p class="st-sub">Thanks, ' +
            esc(name.split(" ")[0]) +
            ". We'll email <b>" +
            esc(email) +
            "</b> with your invitation soon.</p></div>";
          if (opts.onSuccess) opts.onSuccess();
        })
        .catch(function () {
          showAlert("Could not reach the server. Please check your connection and try again.");
        })
        .finally(function () {
          busy = false;
          submit.disabled = false;
          submit.textContent = "Register";
        });
    });
  }

  /* ------------------------------------------------------------------ boot */

  function mountInline() {
    var host = document.querySelector(CFG.mount);
    if (!host) return;
    createForm(host, { dismissible: false });
  }

  function openModal() {
    if (document.querySelector(".st-ov")) return;

    var overlay = document.createElement("div");
    overlay.className = "st-ov";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    var card = document.createElement("div");
    overlay.appendChild(card);
    document.body.appendChild(overlay);

    function close() {
      snooze();
      overlay.remove();
      document.removeEventListener("keydown", onKey);
    }
    function onKey(event) {
      if (event.key === "Escape") close();
    }

    overlay.addEventListener("click", function (event) {
      if (event.target === overlay) close();
    });
    document.addEventListener("keydown", onKey);

    createForm(card, {
      dismissible: true,
      onClose: close,
      onSuccess: function () {
        setTimeout(function () {
          overlay.remove();
        }, 2600);
      },
    });
  }

  function scheduleModal() {
    if (!CFG.modal || hasRegistered() || snoozed()) return;
    setTimeout(function () {
      if (!hasRegistered()) openModal();
    }, CFG.modalDelay);
  }

  function start() {
    injectStyles();
    mountInline();
    scheduleModal();
    window.SocioTurtleRegister = { open: openModal };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
