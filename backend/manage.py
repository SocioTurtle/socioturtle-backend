"""Small operational CLI.

    python manage.py make-admin <username-or-email>
    python manage.py list-admins
    python manage.py leads [--role student] [--status new]
    python manage.py send-newsletter <subject> <path-to-markdown-file> [--audience all]
"""

import argparse
import sys

from app.core.email import EmailError, EmailMessage, get_email_sender
from app.core.email_templates import newsletter_email
from app.config import get_settings
from app.core.logging_config import configure_logging
from app.database import Base, SessionLocal, engine
from app.models import Lead, NewsletterIssue, User


def make_admin(identifier: str) -> int:
    db = SessionLocal()
    try:
        ident = identifier.lower()
        user = db.query(User).filter((User.username == ident) | (User.email == ident)).first()
        if user is None:
            print(f"No user found matching {identifier!r}.", file=sys.stderr)
            return 1
        user.is_admin = True
        db.commit()
        print(f"{user.username} ({user.email}) is now an admin.")
        return 0
    finally:
        db.close()


def list_admins() -> int:
    db = SessionLocal()
    try:
        admins = db.query(User).filter(User.is_admin.is_(True)).all()
        if not admins:
            print("No admins yet. Run: python manage.py make-admin <username>")
            return 0
        for user in admins:
            print(f"  {user.username:20} {user.email}")
        return 0
    finally:
        db.close()


def list_leads(role: str | None, status: str | None) -> int:
    db = SessionLocal()
    try:
        query = db.query(Lead)
        if role:
            query = query.filter(Lead.role == role)
        if status:
            query = query.filter(Lead.status == status)
        rows = query.order_by(Lead.created_at.desc()).all()
        print(f"{len(rows)} lead(s)\n")
        for lead in rows:
            flag = "news" if lead.newsletter_opt_in else "----"
            print(f"  [{lead.id:4}] {lead.role:8} {lead.status:10} {flag}  {lead.email:38} {lead.name}")
        return 0
    finally:
        db.close()


def send_newsletter(subject: str, body_path: str, audience: str) -> int:
    settings = get_settings()
    body = open(body_path, encoding="utf-8").read()

    db = SessionLocal()
    try:
        query = db.query(Lead).filter(Lead.newsletter_opt_in.is_(True))
        if audience != "all":
            query = query.filter(Lead.role == audience)
        recipients = query.all()
        if not recipients:
            print("No opted-in subscribers for that audience.", file=sys.stderr)
            return 1

        print(f"Sending {subject!r} to {len(recipients)} subscriber(s) via {settings.email_backend}.")
        if input("Type 'send' to confirm: ").strip() != "send":
            print("Aborted.")
            return 1

        sender = get_email_sender()
        sent = failed = 0
        with sender.connection() as conn:
            for lead in recipients:
                url = (
                    f"{settings.public_api_url.rstrip('/')}"
                    f"/api/newsletter/unsubscribe?token={lead.unsubscribe_token}"
                )
                html, text = newsletter_email(subject, body, url)
                try:
                    conn.send(
                        EmailMessage(
                            to=lead.email,
                            subject=subject,
                            html=html,
                            text=text,
                            list_unsubscribe=url,
                        )
                    )
                    sent += 1
                except EmailError as exc:
                    failed += 1
                    print(f"  failed {lead.email}: {exc}", file=sys.stderr)

        db.add(
            NewsletterIssue(
                subject=subject,
                body_markdown=body,
                audience=audience,
                recipient_count=sent,
                failed_count=failed,
            )
        )
        db.commit()
        print(f"Sent {sent}, failed {failed}.")
        return 0 if failed == 0 else 1
    finally:
        db.close()


def main() -> int:
    configure_logging()
    Base.metadata.create_all(bind=engine)

    parser = argparse.ArgumentParser(description="SocioTurtle operations CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_admin = sub.add_parser("make-admin", help="Grant admin rights to a user")
    p_admin.add_argument("identifier", help="username or email")

    sub.add_parser("list-admins", help="Show current admins")

    p_leads = sub.add_parser("leads", help="List captured leads")
    p_leads.add_argument("--role", choices=["student", "mentor"])
    p_leads.add_argument("--status", choices=["new", "invited", "activated"])

    p_news = sub.add_parser("send-newsletter", help="Send a newsletter issue")
    p_news.add_argument("subject")
    p_news.add_argument("body_path", help="path to a markdown file")
    p_news.add_argument("--audience", default="all", choices=["all", "student", "mentor"])

    args = parser.parse_args()

    if args.command == "make-admin":
        return make_admin(args.identifier)
    if args.command == "list-admins":
        return list_admins()
    if args.command == "leads":
        return list_leads(args.role, args.status)
    if args.command == "send-newsletter":
        return send_newsletter(args.subject, args.body_path, args.audience)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
