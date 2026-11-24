from getpass import getpass
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.db import init_db, connect
from backend.security import hash_password


def main():
    init_db()
    print("TourInsight — create or promote a local administrator")
    email=input("Admin email: ").strip().lower()
    name=input("Full name: ").strip()
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$",email):
        print("Enter a valid email."); return 1
    p1=getpass("Password (minimum 10 characters): ")
    p2=getpass("Confirm password: ")
    if p1!=p2:
        print("Passwords do not match."); return 1
    try: password_hash=hash_password(p1)
    except ValueError as exc:
        print(exc); return 1
    with connect() as conn:
        row=conn.execute("SELECT id FROM users WHERE email=?",(email,)).fetchone()
        if row:
            conn.execute("UPDATE users SET full_name=?,password_hash=?,role='admin' WHERE id=?",(name,password_hash,row["id"]))
            print("Existing account promoted to administrator and password updated.")
        else:
            conn.execute("INSERT INTO users(email,full_name,password_hash,role) VALUES(?,?,?,'admin')",(email,name,password_hash))
            print("Administrator account created.")
        conn.commit()
    print("Sign in through the TourInsight website.")
    return 0

if __name__=="__main__": raise SystemExit(main())
