"""Durable transactional email outbox. Run as a separate Compose service."""

import json
import logging
import os
import smtplib
import ssl
import time
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import and_, or_, select

from app.core.security import PRODUCTION, aware, decrypt, utcnow
from app.db.database import SessionLocal
from app.models.accounts import MailJob
from app.services.account_service import cleanup

log = logging.getLogger("casa.mail")


def send_mail(payload):
    message = EmailMessage()
    message["From"] = os.environ["SMTP_FROM"]
    message["To"] = payload["to"]
    message["Subject"] = payload["subject"]
    message.set_content(payload["body"])
    host, port = os.environ["SMTP_HOST"], int(os.getenv("SMTP_PORT", "587"))
    mode = os.getenv("SMTP_SECURITY", "starttls")
    if PRODUCTION and mode not in ("ssl", "starttls"):
        raise RuntimeError("SMTP em produção exige TLS.")
    context = ssl.create_default_context()
    smtp = (
        smtplib.SMTP_SSL(host, port, timeout=20, context=context)
        if mode == "ssl"
        else smtplib.SMTP(host, port, timeout=20)
    )
    with smtp:
        if mode == "starttls":
            smtp.starttls(context=context)
        username = os.getenv("SMTP_USERNAME")
        if username:
            smtp.login(username, os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)


def process_one():
    with SessionLocal() as db:
        job = db.scalar(
            select(MailJob)
            .where(
                or_(
                    and_(MailJob.status == "pending", MailJob.available_at <= utcnow()),
                    and_(
                        MailJob.status == "processing", MailJob.lease_until < utcnow()
                    ),
                )
            )
            .order_by(MailJob.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            return False
        if aware(job.expires_at) <= utcnow():
            job.status, job.payload = "expired", None
            db.commit()
            return True
        job.status = "processing"
        job.attempts += 1
        job.lease_until = utcnow() + timedelta(minutes=5)
        db.commit()
        job_id, encrypted = job.id, job.payload
    try:
        send_mail(json.loads(decrypt(encrypted)))
        success = True
    except Exception:
        # Provider errors can contain recipients, URLs or credentials. Do not log exception bodies.
        log.warning("Falha ao enviar job %s; nova tentativa será agendada.", job_id)
        success = False
    with SessionLocal() as db:
        job = db.get(MailJob, job_id)
        if success:
            job.status, job.payload = "sent", None
        elif job.attempts >= 10:
            job.status, job.payload = "failed", None
        else:
            job.status = "pending"
            job.available_at = utcnow() + timedelta(
                seconds=min(3600, 30 * 2**job.attempts)
            )
        job.lease_until = None
        db.commit()
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    last_cleanup = 0
    while True:
        try:
            if time.monotonic() - last_cleanup >= 3600:
                with SessionLocal() as db:
                    cleanup(db)
                last_cleanup = time.monotonic()
            if not process_one():
                time.sleep(5)
        except Exception:
            log.warning("Fila de e-mail indisponível; nova tentativa em 10 segundos.")
            time.sleep(10)
