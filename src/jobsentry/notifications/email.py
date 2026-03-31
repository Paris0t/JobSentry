"""Email notifications — send job match digests with resume attached."""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jobsentry.config import get_settings


class EmailNotifier:
    """Send email notifications via SMTP (Gmail by default)."""

    def __init__(self):
        settings = get_settings()
        self.smtp_host = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.recipients = [
            e.strip() for e in (settings.notify_emails or "").split(",") if e.strip()
        ]

    @property
    def enabled(self) -> bool:
        return bool(self.username and self.password and self.recipients)

    def send(
        self,
        subject: str,
        body_html: str,
        attachments: list[Path] | None = None,
    ) -> bool:
        """Send an email with optional attachments."""
        if not self.enabled:
            return False

        msg = MIMEMultipart()
        msg["From"] = self.username
        msg["To"] = ", ".join(self.recipients)
        msg["Subject"] = subject

        msg.attach(MIMEText(body_html, "html"))

        for path in attachments or []:
            if path and Path(path).exists():
                with open(path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=Path(path).name)
                part["Content-Disposition"] = f'attachment; filename="{Path(path).name}"'
                msg.attach(part)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.username, self.recipients, msg.as_string())
            return True
        except Exception as e:
            print(f"Email send failed: {e}")
            return False

    def send_job_digest(
        self,
        jobs: list[dict],
        resume_path: str | None = None,
    ) -> bool:
        """Send a digest of top job matches.

        Each job dict: {title, company, score, url, location, clearance,
                        salary, reasoning}
        """
        if not jobs:
            return False

        rows = []
        for i, j in enumerate(jobs, 1):
            score = f"{j['score']:.0%}"
            salary = j.get("salary", "")
            location = j.get("location", "")
            clearance = j.get("clearance", "")
            reasoning = j.get("reasoning", "")

            rows.append(f"""
            <tr style="border-bottom: 1px solid #e0e0e0;">
                <td style="padding: 12px; text-align: center; font-size: 20px;
                    font-weight: bold; color: {'#2e7d32' if j['score'] >= 0.8 else '#f57f17' if j['score'] >= 0.7 else '#757575'};">
                    {score}
                </td>
                <td style="padding: 12px;">
                    <a href="{j['url']}" style="color: #1565c0; font-weight: bold;
                       font-size: 15px; text-decoration: none;">
                        {j['title']}
                    </a><br>
                    <span style="color: #424242;">{j['company']}</span><br>
                    <span style="color: #757575; font-size: 13px;">
                        {location}{' | ' + clearance if clearance else ''}{' | ' + salary if salary else ''}
                    </span>
                    {f'<br><span style="color: #616161; font-size: 12px; font-style: italic;">{reasoning}</span>' if reasoning else ''}
                </td>
                <td style="padding: 12px; text-align: center;">
                    <a href="{j['url']}" style="background: #1565c0; color: white;
                       padding: 8px 16px; border-radius: 4px; text-decoration: none;
                       font-size: 13px;">Apply</a>
                </td>
            </tr>""")

        body = f"""
        <html>
        <body style="font-family: -apple-system, Arial, sans-serif; max-width: 700px; margin: 0 auto;">
            <div style="background: #1a237e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="margin: 0;">JobSentry — Top Job Matches</h2>
                <p style="margin: 5px 0 0; opacity: 0.8;">{len(jobs)} jobs matched your profile</p>
            </div>
            <table style="width: 100%; border-collapse: collapse; background: white;">
                <tr style="background: #f5f5f5;">
                    <th style="padding: 10px; width: 60px;">Score</th>
                    <th style="padding: 10px; text-align: left;">Job</th>
                    <th style="padding: 10px; width: 80px;"></th>
                </tr>
                {"".join(rows)}
            </table>
            <div style="padding: 15px; background: #f5f5f5; border-radius: 0 0 8px 8px;
                 color: #757575; font-size: 12px;">
                {'Resume attached. ' if resume_path else ''}
                Click any job to apply directly on the job board.
            </div>
        </body>
        </html>
        """

        attachments = [Path(resume_path)] if resume_path else []
        return self.send(
            subject=f"JobSentry: {len(jobs)} New Job Matches",
            body_html=body,
            attachments=attachments,
        )
