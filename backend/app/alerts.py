"""Alert verso il professionista. Twilio se configurato, altrimenti simulazione tracciata a DB."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .config import get_settings
from .db import AlertLog

log = logging.getLogger("biopulse.alerts")


def send_alert(session: Session, athlete_id: str, body: str, channel: str = "sms") -> dict:
    s = get_settings()
    simulated = True
    if s.twilio_account_sid and s.twilio_auth_token and s.twilio_from and s.clinician_phone:
        try:
            from twilio.rest import Client
            Client(s.twilio_account_sid, s.twilio_auth_token).messages.create(
                to=s.clinician_phone, from_=s.twilio_from, body=body[:300])
            simulated = False
        except Exception as exc:  # noqa: BLE001
            log.error("Invio Twilio fallito (%s): alert registrato come simulato.", exc)
    session.add(AlertLog(athlete_id=athlete_id, channel=channel, body=body, simulated=simulated))
    session.commit()
    log.info("ALERT %s [%s]: %s", "SIMULATO" if simulated else "INVIATO", channel, body)
    return {"sent": not simulated, "simulated": simulated, "channel": channel}
