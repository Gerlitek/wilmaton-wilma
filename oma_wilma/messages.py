"""Wilma-viestit omaan muotoon. Viestien sisältöä ei kirjata lokiin eikä tulosteta: vain paikallinen Ollama lukee sen."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from . import bridge
from .models import Student, parse_student


@dataclass(frozen=True)
class MessageInfo:
    """Viestilistan rivi (ei sisältöä)."""
    student: Student
    id: int
    subject: str
    sent: date
    sender: str | None
    unread: bool
    reply_count: int
    sent_at: str = ""   # täsmällinen lähetysaika (vertailuun: sama viesti eri tunnisteilla)


@dataclass(frozen=True)
class Message:
    info: MessageInfo
    text: str = field(repr=False)   # viesti ja vastaukset; repr piilottaa sisällön vahingossa tulostetulta oliolta


def _day(value: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().date()
    except ValueError:
        return None


def parse_message_list(data: dict[str, Any]) -> list[MessageInfo]:
    """`wilma messages --json`: { students: [{ student, messages: [{ wilmaId, subject, sentAt, senderName, unread, replyCount }] }] }"""
    out: list[MessageInfo] = []
    for entry in data.get("students", []):
        student = parse_student(entry.get("student", {}))
        for m in entry.get("messages", []):
            sent = _day(m.get("sentAt"))
            if m.get("wilmaId") is None or sent is None:
                continue
            out.append(MessageInfo(student, int(m["wilmaId"]), str(m.get("subject") or ""), sent,
                                   m.get("senderName") or None, bool(m.get("unread")), int(m.get("replyCount") or 0), str(m.get("sentAt") or "")))
    return sorted(out, key=lambda x: (x.sent, x.id), reverse=True)


def parse_message(info: MessageInfo, data: dict[str, Any]) -> Message:
    """`wilma messages <id> --json`: { student, message: { content, replies: [{ content }] } }"""
    m = data.get("message") or {}
    parts = [str(m.get("content") or "")] + [str(r.get("content") or "") for r in (m.get("replies") or [])]
    return Message(info, "\n\n".join(p.strip() for p in parts if p.strip()))


def recent_messages(student: str | None = None, limit: int = 50) -> list[MessageInfo]:
    args = ["messages", "--limit", str(limit)]
    if student:
        args += ["--student", student]
    return parse_message_list(bridge.run(args))


def read_message(info: MessageInfo) -> Message:
    """Avaa yhden viestin. HUOM: Wilma voi merkitä viestin luetuksi, kun se avataan."""
    data = bridge.run(["messages", str(info.id), "--student", info.student.number])
    owner = str((data.get("student") or {}).get("studentNumber") or "")
    if owner and owner != info.student.number:      # viestiä ei koskaan käsitellä väärän lapsen nimissä
        raise bridge.WilmaError("student_mismatch", "viesti avautui toisen oppilaan tunnuksella, ohitetaan")
    return parse_message(info, data)
