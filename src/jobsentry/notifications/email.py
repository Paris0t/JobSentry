"""Email notifications — send job match digests with resume attached."""

import random
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
        """Send a premium branded digest of top job matches.

        Each job dict: {title, company, score, url, location, clearance,
                        salary, reasoning}
        """
        if not jobs:
            return False

        # -- Motivational quotes related to career and persistence -----------
        quotes = [
            ("The only way to do great work is to love what you do.", "Steve Jobs"),
            (
                "Success is not final, failure is not fatal: it is the courage to continue that counts.",
                "Winston Churchill",
            ),
            ("Opportunities don't happen. You create them.", "Chris Grosser"),
            (
                "The future belongs to those who believe in the beauty of their dreams.",
                "Eleanor Roosevelt",
            ),
            ("Don't watch the clock; do what it does. Keep going.", "Sam Levenson"),
            (
                "Your career is a marathon, not a sprint. Pace yourself and stay relentless.",
                "Unknown",
            ),
            (
                "The best time to plant a tree was 20 years ago. The second best time is now.",
                "Chinese Proverb",
            ),
            ("I have not failed. I've just found 10,000 ways that won't work.", "Thomas Edison"),
            (
                "What lies behind us and what lies before us are tiny matters compared to what lies within us.",
                "Ralph Waldo Emerson",
            ),
            ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
            ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
            ("The secret of getting ahead is getting started.", "Mark Twain"),
            ("A year from now you may wish you had started today.", "Karen Lamb"),
            ("Hard work beats talent when talent doesn't work hard.", "Tim Notke"),
            ("Every expert was once a beginner.", "Helen Hayes"),
        ]
        quote_text, quote_author = random.choice(quotes)

        # -- Compute stats ---------------------------------------------------
        from datetime import datetime, timezone

        today_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        scores = [j["score"] for j in jobs]
        score_min = min(scores)
        score_max = max(scores)
        score_range_str = (
            f"{score_min:.0%} &ndash; {score_max:.0%}"
            if score_min != score_max
            else f"{score_max:.0%}"
        )

        # -- Build job cards -------------------------------------------------
        job_rows = ""
        for j in jobs:
            pct = j["score"]
            score_label = f"{pct:.0%}"

            # Score badge colors
            if pct >= 0.80:
                badge_bg = "#1b5e20"
                badge_text = "#ffffff"
                badge_border = "#2e7d32"
            elif pct >= 0.65:
                badge_bg = "#e65100"
                badge_text = "#ffffff"
                badge_border = "#ef6c00"
            else:
                badge_bg = "#616161"
                badge_text = "#ffffff"
                badge_border = "#757575"

            location = j.get("location", "")
            clearance = j.get("clearance", "")
            salary = j.get("salary", "")
            reasoning = j.get("reasoning", "")
            url = j.get("url", "#")
            title = j.get("title", "Untitled Position")
            company = j.get("company", "")

            # Meta line: location | clearance | salary
            meta_parts = [p for p in [location, clearance, salary] if p]
            meta_line = " &nbsp;|&nbsp; ".join(meta_parts) if meta_parts else ""

            reasoning_html = ""
            if reasoning:
                reasoning_html = (
                    '<tr><td colspan="3" style="padding:0 20px 16px 20px;">'
                    '<table cellpadding="0" cellspacing="0" border="0" width="100%"><tr>'
                    '<td style="background:#f0f4ff;border-left:3px solid #42a5f5;'
                    "padding:10px 14px;font-size:13px;color:#37474f;"
                    'font-style:italic;line-height:1.5;border-radius:0 4px 4px 0;">'
                    f"&#x1F916; {reasoning}"
                    "</td></tr></table></td></tr>"
                )

            job_rows += f'''
            <!-- Job Card -->
            <tr><td colspan="3" style="padding:0;">
            <table cellpadding="0" cellspacing="0" border="0" width="100%"
                   style="background:#ffffff;border-bottom:1px solid #e8eaf6;">
            <tr>
                <!-- Score Badge -->
                <td style="padding:20px 12px 16px 20px;vertical-align:top;width:64px;" valign="top">
                    <table cellpadding="0" cellspacing="0" border="0"><tr>
                    <td style="background:{badge_bg};border:2px solid {badge_border};
                               color:{badge_text};font-size:16px;font-weight:bold;
                               text-align:center;width:56px;height:56px;
                               border-radius:8px;line-height:56px;">
                        {score_label}
                    </td>
                    </tr></table>
                </td>
                <!-- Job Details -->
                <td style="padding:20px 8px 16px 4px;vertical-align:top;" valign="top">
                    <a href="{url}" target="_blank"
                       style="color:#0d1b3e;font-size:16px;font-weight:bold;
                              text-decoration:none;line-height:1.3;">
                        {title}
                    </a>
                    <br>
                    <span style="color:#37474f;font-size:14px;line-height:1.6;">
                        {company}
                    </span>
                    <br>
                    <span style="color:#78909c;font-size:12px;line-height:1.6;">
                        {meta_line}
                    </span>
                </td>
                <!-- Apply Button -->
                <td style="padding:20px 20px 16px 8px;vertical-align:middle;
                           text-align:center;width:110px;" valign="middle">
                    <table cellpadding="0" cellspacing="0" border="0"><tr>
                    <td style="background:#0d1b3e;border-radius:6px;text-align:center;">
                        <a href="{url}" target="_blank"
                           style="display:inline-block;padding:10px 20px;color:#ffffff;
                                  font-size:13px;font-weight:bold;text-decoration:none;
                                  letter-spacing:0.3px;">
                            Apply Now
                        </a>
                    </td>
                    </tr></table>
                </td>
            </tr>
            {reasoning_html}
            </table>
            </td></tr>'''

        # -- Resume mention in footer ----------------------------------------
        resume_note = ""
        if resume_path:
            resume_note = (
                '<tr><td style="padding:8px 0 0 0;font-size:12px;color:#90a4ae;'
                'text-align:center;">'
                "&#x1F4CE; Your resume is attached to this email for easy applications."
                "</td></tr>"
            )

        # -- Assemble full email HTML ----------------------------------------
        body = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>JobSentry - Job Intelligence Report</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f6fb;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,
             'Helvetica Neue',Arial,sans-serif;">

<!-- Wrapper -->
<table cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background-color:#f4f6fb;">
<tr><td align="center" style="padding:24px 16px;">

<!-- Main Container (max 640px) -->
<table cellpadding="0" cellspacing="0" border="0" width="640"
       style="max-width:640px;width:100%;background-color:#ffffff;
              border-radius:12px;overflow:hidden;
              box-shadow:0 2px 12px rgba(13,27,62,0.08);">

<!-- ============================================================ -->
<!-- HEADER with inline SVG logo                                   -->
<!-- ============================================================ -->
<tr><td style="background:linear-gradient(135deg,#0d1b3e 0%,#1a237e 100%);
               padding:0;" bgcolor="#0d1b3e">
    <!--[if gte mso 9]>
    <v:rect xmlns:v="urn:schemas-microsoft-com:vml" fill="true" stroke="false"
            style="width:640px;height:160px;">
    <v:fill type="gradient" color="#0d1b3e" color2="#1a237e" angle="135"/>
    <v:textbox inset="0,0,0,0">
    <![endif]-->
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
        <td style="padding:32px 32px 28px 32px;text-align:center;" align="center">
            <!-- Inline SVG Shield + Radar Logo -->
            <table cellpadding="0" cellspacing="0" border="0" align="center"><tr><td style="text-align:center;" align="center">
            <!--[if !mso]><!-->
            <svg xmlns="http://www.w3.org/2000/svg" width="60" height="68" viewBox="0 0 60 68" style="display:block;margin:0 auto 12px auto;">
                <!-- Shield body -->
                <path d="M30 2 L56 14 L56 34 C56 50 44 62 30 66 C16 62 4 50 4 34 L4 14 Z"
                      fill="none" stroke="#4fc3f7" stroke-width="2.5" opacity="0.9"/>
                <path d="M30 6 L52 16 L52 34 C52 48 42 58 30 62 C18 58 8 48 8 34 L8 16 Z"
                      fill="#0d1b3e" fill-opacity="0.5" stroke="#42a5f5"
                      stroke-width="1" opacity="0.6"/>
                <!-- Radar circles -->
                <circle cx="30" cy="34" r="16" fill="none" stroke="#42a5f5"
                        stroke-width="0.8" opacity="0.35"/>
                <circle cx="30" cy="34" r="10" fill="none" stroke="#42a5f5"
                        stroke-width="0.8" opacity="0.5"/>
                <circle cx="30" cy="34" r="4" fill="none" stroke="#4fc3f7"
                        stroke-width="0.8" opacity="0.7"/>
                <!-- Radar sweep line -->
                <line x1="30" y1="34" x2="44" y2="24" stroke="#4fc3f7"
                      stroke-width="1.5" opacity="0.8"/>
                <!-- Radar blip -->
                <circle cx="40" cy="28" r="2.5" fill="#4fc3f7" opacity="0.95"/>
                <circle cx="40" cy="28" r="5" fill="#4fc3f7" opacity="0.25"/>
                <!-- Crosshairs -->
                <line x1="30" y1="20" x2="30" y2="48" stroke="#42a5f5"
                      stroke-width="0.5" opacity="0.3"/>
                <line x1="16" y1="34" x2="44" y2="34" stroke="#42a5f5"
                      stroke-width="0.5" opacity="0.3"/>
            </svg>
            <!--<![endif]-->
            </td></tr></table>
            <table cellpadding="0" cellspacing="0" border="0" align="center"><tr><td style="text-align:center;" align="center">
                <span style="font-size:28px;font-weight:bold;color:#ffffff;
                             letter-spacing:1px;line-height:1.2;">
                    JobSentry
                </span>
                <br>
                <span style="font-size:13px;color:#4fc3f7;letter-spacing:2px;
                             text-transform:uppercase;line-height:2;">
                    Your AI Job Intelligence Report
                </span>
            </td></tr></table>
        </td>
    </tr>
    </table>
    <!--[if gte mso 9]>
    </v:textbox></v:rect>
    <![endif]-->
</td></tr>

<!-- ============================================================ -->
<!-- STATS BAR                                                     -->
<!-- ============================================================ -->
<tr><td style="padding:0;">
    <table cellpadding="0" cellspacing="0" border="0" width="100%"
           style="background:#f0f4ff;border-bottom:2px solid #e8eaf6;">
    <tr>
        <td style="padding:16px 0;text-align:center;" align="center" width="33%">
            <span style="font-size:24px;font-weight:bold;color:#0d1b3e;
                         display:block;line-height:1.2;">
                {len(jobs)}
            </span>
            <span style="font-size:11px;color:#78909c;text-transform:uppercase;
                         letter-spacing:1px;">
                Matches
            </span>
        </td>
        <td style="padding:16px 0;text-align:center;
                   border-left:1px solid #dce3f0;border-right:1px solid #dce3f0;"
            align="center" width="34%">
            <span style="font-size:24px;font-weight:bold;color:#0d1b3e;
                         display:block;line-height:1.2;">
                {score_range_str}
            </span>
            <span style="font-size:11px;color:#78909c;text-transform:uppercase;
                         letter-spacing:1px;">
                Score Range
            </span>
        </td>
        <td style="padding:16px 0;text-align:center;" align="center" width="33%">
            <span style="font-size:14px;font-weight:bold;color:#0d1b3e;
                         display:block;line-height:1.7;">
                {today_str}
            </span>
            <span style="font-size:11px;color:#78909c;text-transform:uppercase;
                         letter-spacing:1px;">
                Report Date
            </span>
        </td>
    </tr>
    </table>
</td></tr>

<!-- ============================================================ -->
<!-- JOB CARDS                                                     -->
<!-- ============================================================ -->
<tr><td style="padding:0;">
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    {job_rows}
    </table>
</td></tr>

<!-- ============================================================ -->
<!-- MOTIVATIONAL QUOTE                                            -->
<!-- ============================================================ -->
<tr><td style="padding:24px 24px 0 24px;">
    <table cellpadding="0" cellspacing="0" border="0" width="100%">
    <tr>
        <td style="border-left:4px solid #42a5f5;padding:16px 20px;
                   background:#f8f9fe;border-radius:0 8px 8px 0;">
            <span style="font-size:14px;color:#37474f;font-style:italic;
                         line-height:1.6;display:block;">
                &ldquo;{quote_text}&rdquo;
            </span>
            <span style="font-size:12px;color:#78909c;display:block;
                         margin-top:6px;">
                &mdash; {quote_author}
            </span>
        </td>
    </tr>
    </table>
</td></tr>

<!-- ============================================================ -->
<!-- FOOTER                                                        -->
<!-- ============================================================ -->
<tr><td style="padding:24px 24px 28px 24px;">
    <table cellpadding="0" cellspacing="0" border="0" width="100%"
           style="border-top:1px solid #e8eaf6;">
    <tr>
        <td style="padding:20px 0 0 0;text-align:center;" align="center">
            <span style="font-size:13px;color:#78909c;line-height:1.6;">
                Powered by
                <a href="https://github.com/Paris0t/JobSentry" target="_blank"
                   style="color:#1a237e;font-weight:bold;text-decoration:none;">
                    JobSentry
                </a>
                &mdash; Your clearance is your edge.
            </span>
        </td>
    </tr>
    {resume_note}
    <tr>
        <td style="padding:12px 0 0 0;text-align:center;" align="center">
            <a href="https://github.com/Paris0t/JobSentry" target="_blank"
               style="font-size:11px;color:#90a4ae;text-decoration:none;">
                github.com/Paris0t/JobSentry
            </a>
        </td>
    </tr>
    </table>
</td></tr>

</table>
<!-- End Main Container -->

</td></tr>
</table>
<!-- End Wrapper -->

</body>
</html>"""

        attachments = [Path(resume_path)] if resume_path else []
        return self.send(
            subject=f"JobSentry: {len(jobs)} New Job Matches",
            body_html=body,
            attachments=attachments,
        )
