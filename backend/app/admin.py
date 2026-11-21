"""Gestione locale degli account atleta e professionista."""
from __future__ import annotations

import argparse
import getpass
import uuid

from sqlalchemy import select, update

from .auth import hash_password, validate_email
from .db import AuthSession, Athlete, AthleteAccess, SessionLocal, User, init_db, utcnow


def main() -> None:
    parser = argparse.ArgumentParser(description="Provisiona account BioPulse su invito.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=("athlete", "clinician", "admin"))
    parser.add_argument("--reset-password", action="store_true",
                        help="Reimposta la password di un account esistente e revoca tutte le sessioni.")
    parser.add_argument("--athlete-id", action="append", default=[],
                        help="ID atleta già presente; ripetibile per gli accessi del professionista.")
    parser.add_argument("--name", help="Nome visualizzato, richiesto per creare il profilo atleta.")
    args = parser.parse_args()

    email = validate_email(args.email)
    if args.reset_password:
        if args.role or args.athlete_id or args.name:
            parser.error("--reset-password non si combina con --role, --athlete-id o --name.")
    elif not args.role:
        parser.error("--role è obbligatorio per creare un account.")
    if not args.reset_password and args.role == "athlete" and len(args.athlete_id) != 1:
        parser.error("Un account atleta richiede esattamente un --athlete-id.")
    if not args.reset_password and args.role == "clinician" and not args.athlete_id:
        parser.error("Un professionista richiede almeno un --athlete-id assegnato.")
    if not args.reset_password and args.role == "admin" and args.athlete_id:
        parser.error("Un account admin non può essere associato a profili atleta.")

    password = getpass.getpass("Password iniziale (almeno 12 caratteri): ")
    confirmation = getpass.getpass("Ripeti la password: ")
    if password != confirmation:
        parser.error("Le password non coincidono.")
    password_hash = hash_password(password)

    init_db()
    with SessionLocal.begin() as session:
        if args.reset_password:
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                parser.error("Account non trovato.")
            user.password_hash = password_hash
            session.execute(
                update(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
                .values(revoked_at=utcnow())
            )
        else:
            if session.scalar(select(User.id).where(User.email == email)):
                parser.error("Esiste già un account con questa email.")
            if args.role == "athlete":
                athlete_id = args.athlete_id[0]
                athlete = session.get(Athlete, athlete_id)
                if athlete is None:
                    if not args.name:
                        parser.error("Per creare un nuovo profilo atleta è richiesto --name.")
                    athlete = Athlete(id=athlete_id, name=args.name, consent_data=False, consent_alerts=False)
                    session.add(athlete)
                    session.flush()
            for athlete_id in args.athlete_id:
                if session.get(Athlete, athlete_id) is None:
                    parser.error(f"Profilo atleta inesistente: {athlete_id}")
            user = User(id=str(uuid.uuid4()), email=email, password_hash=password_hash, role=args.role)
            session.add(user)
            session.flush()
            for athlete_id in set(args.athlete_id):
                session.add(AthleteAccess(user_id=user.id, athlete_id=athlete_id))
    if args.reset_password:
        print(f"Password reimpostata per {email}; tutte le sessioni precedenti sono state revocate.")
    else:
        print(f"Account {args.role} creato per {email}. Consegnare la password iniziale tramite canale sicuro.")


if __name__ == "__main__":
    main()
