"""Populate the database with demo resources so search has something to return."""

from app.core.security import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Resource, User

DEMO_RESOURCES = [
    ("FastAPI Documentation", "https://fastapi.tiangolo.com", "Modern Python web framework for building APIs.", "python,api,backend"),
    ("React Documentation", "https://react.dev", "The library for web and native user interfaces.", "javascript,react,frontend"),
    ("SQLAlchemy ORM", "https://docs.sqlalchemy.org", "Python SQL toolkit and object-relational mapper.", "python,database,orm"),
    ("MDN Web Docs", "https://developer.mozilla.org", "Reference for HTML, CSS, JavaScript and web APIs.", "javascript,web,reference"),
    ("Real Python", "https://realpython.com", "Tutorials and articles for Python developers.", "python,tutorial"),
    ("React Native Docs", "https://reactnative.dev", "Build native mobile apps using React.", "react,mobile,javascript"),
    ("PostgreSQL Manual", "https://www.postgresql.org/docs/", "Official PostgreSQL documentation.", "database,sql,postgres"),
    ("OWASP Top Ten", "https://owasp.org/www-project-top-ten/", "The ten most critical web application security risks.", "security,web"),
]


DEMO_USERS = [
    ("demo", "demo@example.com", "demo-password-1", "student"),
    ("mentor", "mentor@example.com", "mentor-password-1", "mentor"),
]


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for username, email, password, role in DEMO_USERS:
            if db.query(User).filter(User.username == username).first() is None:
                db.add(
                    User(
                        email=email,
                        username=username,
                        password_hash=hash_password(password),
                        role=role,
                    )
                )
        db.commit()
        demo = db.query(User).filter(User.username == "mentor").first()

        created = 0
        for title, url, description, tags in DEMO_RESOURCES:
            if db.query(Resource).filter(Resource.url == url).first():
                continue
            db.add(
                Resource(
                    title=title, url=url, description=description, tags=tags, owner_id=demo.id
                )
            )
            created += 1
        db.commit()
        print(f"Seeded {created} resources.")
        for username, _, password, role in DEMO_USERS:
            print(f"  {role:8} login: {username} / {password}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
