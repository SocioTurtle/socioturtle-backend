"""HTML email bodies.

Styles are inlined because most mail clients discard <style> blocks, and the
layout stays single-column so it survives Gmail, Outlook, and phone screens.
"""

from html import escape

import markdown as markdown_lib

BRAND = "#4c5fd7"

_SHELL = """\
<!doctype html>
<html>
  <body style="margin:0;padding:0;background:#f6f7fb;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
           style="background:#f6f7fb;padding:24px 12px;">
      <tr><td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
               style="max-width:560px;background:#ffffff;border:1px solid #dfe3ec;
                      border-radius:10px;overflow:hidden;
                      font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                      color:#16192a;">
          <tr><td style="padding:20px 28px;border-bottom:1px solid #dfe3ec;">
            <span style="font-size:18px;font-weight:700;color:{brand};">SocioTurtle</span>
          </td></tr>
          <tr><td style="padding:28px;font-size:15px;line-height:1.6;">{body}</td></tr>
          <tr><td style="padding:18px 28px;border-top:1px solid #dfe3ec;
                         font-size:12px;color:#6b7284;line-height:1.5;">{footer}</td></tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
"""


def _shell(body: str, footer: str) -> str:
    return _SHELL.format(brand=BRAND, body=body, footer=footer)


def _button(url: str, label: str) -> str:
    return (
        f'<p style="margin:26px 0;"><a href="{escape(url, quote=True)}" '
        f'style="background:{BRAND};color:#ffffff;text-decoration:none;padding:12px 22px;'
        f'border-radius:8px;font-weight:600;display:inline-block;">{escape(label)}</a></p>'
    )


def invite_email(name: str, role: str, activate_url: str, expires_hours: int) -> tuple[str, str]:
    """Returns (html, text). Deliberately carries a link, never a password."""
    greeting = escape(name.split(" ")[0] if name else "there")
    role_line = (
        "You will be able to share resources and guide learners."
        if role == "mentor"
        else "You will be able to find and save learning resources."
    )
    days = max(1, expires_hours // 24)

    body = (
        f"<p>Hi {greeting},</p>"
        f"<p>Your SocioTurtle account is ready to set up. {escape(role_line)}</p>"
        f"<p>Click below to choose your username and password — the link works once "
        f"and expires in {days} day{'s' if days != 1 else ''}.</p>"
        f"{_button(activate_url, 'Set up my account')}"
        f'<p style="font-size:13px;color:#6b7284;">If the button does not work, paste this '
        f'into your browser:<br><span style="word-break:break-all;">'
        f"{escape(activate_url)}</span></p>"
        f'<p style="font-size:13px;color:#6b7284;">We will never email you a password. '
        f"If you did not request this, you can ignore this message.</p>"
    )
    text = (
        f"Hi {name or 'there'},\n\n"
        f"Your SocioTurtle account is ready to set up. {role_line}\n\n"
        f"Set your username and password here (works once, expires in {days} day(s)):\n"
        f"{activate_url}\n\n"
        f"We will never email you a password. If you did not request this, ignore this message.\n\n"
        f"— SocioTurtle"
    )
    return _shell(body, "You are receiving this because you registered on socioturtle.com."), text


def newsletter_email(subject: str, body_markdown: str, unsubscribe_url: str) -> tuple[str, str]:
    rendered = markdown_lib.markdown(body_markdown, extensions=["extra", "sane_lists", "nl2br"])
    footer = (
        "You are receiving this because you opted in to the SocioTurtle newsletter."
        f'<br><a href="{escape(unsubscribe_url, quote=True)}" style="color:#6b7284;">'
        "Unsubscribe</a>"
    )
    text = f"{subject}\n\n{body_markdown}\n\n---\nUnsubscribe: {unsubscribe_url}"
    return _shell(rendered, footer), text
