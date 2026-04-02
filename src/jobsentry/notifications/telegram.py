"""Telegram bot notifications — send stats and match alerts."""

import httpx

from jobsentry.config import get_settings


class TelegramNotifier:
    """Send notifications via Telegram Bot API."""

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str | None = None, chat_id: str | None = None):
        settings = get_settings()
        self.bot_token = bot_token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_chat_id

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _url(self, method: str) -> str:
        return f"{self.API_BASE.format(token=self.bot_token)}/{method}"

    def send(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a text message. Returns True on success."""
        if not self.enabled:
            return False
        try:
            resp = httpx.post(
                self._url("sendMessage"),
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": parse_mode,
                },
                timeout=10,
            )
            return resp.status_code == 200
        except Exception:
            return False

    def send_photo(self, photo_path: str, caption: str = "") -> bool:
        """Send a screenshot/photo."""
        if not self.enabled:
            return False
        try:
            with open(photo_path, "rb") as f:
                resp = httpx.post(
                    self._url("sendPhoto"),
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"photo": f},
                    timeout=30,
                )
            return resp.status_code == 200
        except Exception:
            return False

    # --- Formatted message helpers ---

    def notify_search_complete(self, board: str, total: int, new: int) -> bool:
        msg = f"🔍 <b>Job Search Complete</b>\nBoard: {board}\nFound: {total} jobs ({new} new)"
        return self.send(msg)

    def notify_matches(self, matches: list[dict]) -> bool:
        """Send top match results. Each dict: {title, company, score, url}."""
        if not matches:
            return False
        lines = ["🎯 <b>New Job Matches</b>\n"]
        for m in matches[:10]:
            score = f"{m['score']:.0%}"
            lines.append(
                f"• <b>{score}</b> — {m['title']}\n"
                f"  {m['company']}\n"
                f'  <a href="{m["url"]}">View →</a>'
            )
        return self.send("\n".join(lines))

    def notify_daily_summary(self, stats: dict) -> bool:
        """Send daily summary. Stats dict keys: total_jobs, new_jobs, matched,
        high_matches."""
        msg = (
            f"📊 <b>Daily Summary</b>\n\n"
            f"Jobs scraped: {stats.get('total_jobs', 0)}\n"
            f"New today: {stats.get('new_jobs', 0)}\n"
            f"AI matched: {stats.get('matched', 0)}\n"
            f"High matches (75%+): {stats.get('high_matches', 0)}"
        )
        return self.send(msg)

    def notify_error(self, error: str) -> bool:
        msg = f"⚠️ <b>JobSentry Error</b>\n\n<code>{error[:500]}</code>"
        return self.send(msg)
