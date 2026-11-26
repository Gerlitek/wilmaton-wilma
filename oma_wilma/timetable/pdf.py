"""Lukujärjestykset PDF:ksi: Wilmasta viikon tunnit, ruudukko (timetable.py), teeman taustakuva (themes.py), HTML ja
siitä PDF Chromella (headless). Yksi tiedosto lasta kohden hakemistoon data/lukujarjestykset (ei Gitissä: nimet)."""
from __future__ import annotations

import os
import subprocess
import tempfile
import unicodedata
from html import escape
from pathlib import Path

from .. import models
from . import themes
from ..config import ROOT, settings
from .grid import (DEFAULT_SUPPORT_WORDS, WEEKDAYS, WORLDVIEW, WORLDVIEW_ALIASES, WORLDVIEW_SUBJECT, Timetable, build, format_time, parse_lunch, parse_snack,
                        parse_week)

OUT_DIR = ROOT / "data" / "lukujarjestykset"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PE_EMOJI, SNACK_EMOJI, LUNCH_EMOJI = "🎽", "🍎", "🍽️"
MORNING_EMOJI, AFTERNOON_EMOJI = "☀️", "🌙"  # koulu alkaa ennen ruokailua / ruokailusta tai myöhemmin
HEADER_H = 13      # päivien otsikkorivi (mm)
BREAK_RATIO = 0.4  # välitunnin rivi suhteessa oppitunnin riviin
MAX_LESSON_H = 22

CSS = """
@page { size: A4 landscape; margin: 0 }
html, body { margin: 0; padding: 0; background: #fff }
.page { position: relative; width: 297mm; height: 210mm; overflow: hidden; color: #000;
        font-family: var(--font) }
.bg { position: absolute; left: 0; top: 0 }
table { position: absolute; border-collapse: collapse; table-layout: fixed; background: #fff }
th, td { border: 0.45mm solid #000; text-align: center; vertical-align: middle; padding: 0 1mm; overflow: hidden }
thead th { font-size: 13pt; font-weight: 800; line-height: 1.05; white-space: nowrap }
thead th.time { font-size: 10pt; font-weight: 600 }
thead th { background: #e6e6e6; -webkit-print-color-adjust: exact; print-color-adjust: exact }
thead .icons { display: block; height: 3.6mm; font-size: 7.5pt; font-weight: 500; line-height: 3.6mm; margin-top: 0.5mm;
               white-space: nowrap }
thead .start { font-size: 14pt; margin-left: 1.2mm }
td.time { font-size: 9.5pt; font-weight: 600; white-space: nowrap }
td.lesson .name { font-size: 13pt; font-weight: 700; line-height: 1.1 }
td.lesson .extra { display: block; font-size: 7.5pt; font-weight: 500; margin-top: 0.4mm }
td.lesson .emoji { font-size: 14pt; margin-right: 1mm }
tr.break td, tr.lunch td { font-size: 8pt; font-style: italic; line-height: 1 }
tr.break td.time, tr.lunch td.time { font-size: 7.5pt; font-weight: 500 }
tr.lunch td.in { font-weight: 700; font-style: normal; font-size: 9pt; color: #777 }
.empty-day { font-size: 9pt; font-style: italic }
"""


def _row_heights(tt: Timetable, box_h: float) -> tuple[float, float]:
    """Oppitunnin ja välitunnin rivin korkeus (mm), niin että taulukko täyttää teeman taulukkoalueen."""
    n_lesson = sum(r.kind == "lesson" for r in tt.rows)
    n_break = len(tt.rows) - n_lesson
    avail = box_h - HEADER_H - 0.5 * (len(tt.rows) + 2)  # reunaviivat vievät tilaa
    unit = min(avail / max(n_lesson + BREAK_RATIO * n_break, 1), MAX_LESSON_H)
    return unit, unit * BREAK_RATIO


def _day_header(tt: Timetable, i: int, start_emoji: bool = False) -> str:
    # Selitteen rivi aina mukana (tyhjänäkin), jotta päivien nimet ovat samalla korkeudella.
    snack = f"{SNACK_EMOJI} välipala" if tt.snack_days[i] else ""
    late = tt.starts_after_lunch[i]
    start = f'<span class="start">{AFTERNOON_EMOJI if late else MORNING_EMOJI}</span>' if start_emoji and late is not None else ""
    return f'<th>{WEEKDAYS[i]}{start}<span class="icons">{snack}</span></th>'


def _lesson_cell(entries, pe_emoji: bool) -> str:
    if not entries:
        return '<td class="lesson free"></td>'
    main, rest = entries[0], entries[1:]
    emoji = f'<span class="emoji">{PE_EMOJI}</span>' if pe_emoji and main.pe else ""
    extra = f'<span class="extra">+ {escape(", ".join(e.name for e in rest))}</span>' if rest else ""
    return f'<td class="lesson">{emoji}<span class="name">{escape(main.name)}</span>{extra}</td>'


def render_html(tt: Timetable, theme: themes.Theme, *, pe_emoji: bool = False, start_emoji: bool = False) -> str:
    x, y, w, h = theme.table_box
    lesson_h, break_h = _row_heights(tt, h)
    rows = []
    for row in tt.rows:
        time = f"{format_time(row.start)}–{format_time(row.end)}"
        if row.kind == "lesson":
            cells = "".join(_lesson_cell(e, pe_emoji) for e in row.lessons)
            rows.append(f'<tr class="lesson" style="height:{lesson_h:.2f}mm"><td class="time">{time}</td>{cells}</tr>')
        else:
            label = f"{LUNCH_EMOJI} ruokailu" if row.kind == "lunch" else "välitunti"
            cells = "".join(f'<td class="in">{label}</td>' if here else '<td class="off"></td>' for here in row.at_school)
            rows.append(f'<tr class="{row.kind}" style="height:{break_h:.2f}mm"><td class="time">{time}</td>{cells}</tr>')
    if not tt.rows:
        rows.append(f'<tr style="height:40mm"><td></td><td colspan="5" class="empty-day">Ei tunteja tällä viikolla</td></tr>')
    head = "".join(_day_header(tt, i, start_emoji) for i in range(5))
    title = escape(f"Lukujärjestys – {tt.first_name}")
    return f"""<!doctype html>
<html lang="fi"><head><meta charset="utf-8"><title>{title}</title><style>{CSS}</style></head>
<body><div class="page" style='--font: {theme.font}'>
{theme.background(tt.first_name)}
<table style="left:{x}mm; top:{y}mm; width:{w}mm">
<colgroup><col style="width:23mm"><col span="5"></colgroup>
<thead><tr style="height:{HEADER_H}mm"><th class="time">klo</th>{head}</tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>
</div></body></html>
"""


def chrome_path() -> Path:
    path = Path(os.environ.get("CHROME", CHROME))
    if not path.exists():
        raise SystemExit(f"Chromea ei löydy: {path}. Aseta CHROME=/polku/chromeen tai käytä --html (tulosta selaimesta).")
    return path


def html_to_pdf(html_file: Path, pdf_file: Path) -> None:
    with tempfile.TemporaryDirectory() as profile:  # oma profiili: ei häiritse käynnissä olevaa Chromea
        subprocess.run([str(chrome_path()), "--headless", "--disable-gpu", f"--user-data-dir={profile}",
                        "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={pdf_file}",
                        html_file.as_uri()], check=True, capture_output=True, timeout=120)


def _slug(text: str) -> str:
    """Tiedostonimeen ääkkösettä: "Äijä" -> "aija" (sopii skripteihin)."""
    plain = unicodedata.normalize("NFKD", text.casefold()).encode("ascii", "ignore").decode()
    return "".join(c for c in plain if c.isalnum() or c == "-") or "oppilas"


def run(student: str | None, week: str, drop_support: bool, theme_name: str, breaks: str, pe_emoji: bool,
        snack: list[str], lunch: str | None, out_dir: Path | None, html_only: bool, worldview: str | None = None,
        start_emoji: bool = False) -> int:
    cfg = settings()
    tcfg = cfg.get("timetable", {})
    try:
        theme = themes.get(theme_name)
        monday = parse_week(week)
        snack_rules = parse_snack(snack)
        lunch_time = parse_lunch(lunch if lunch is not None else tcfg.get("lunch"))
    except ValueError as e:
        raise SystemExit(str(e))
    if start_emoji and not lunch_time:
        raise SystemExit("--start-emoji tarvitsee ruokatauon ajan: --lunch 11:00-11:30 tai config.toml [timetable] lunch")
    if breaks == "lunch" and not lunch_time:
        raise SystemExit("--meals tarvitsee ruokatauon ajan: --lunch 11:00-11:30 tai config.toml [timetable] lunch")
    pe_words = cfg.get("messages", {}).get("pe_subject_words", ["liikunta"])
    support_words = tcfg.get("support_words", DEFAULT_SUPPORT_WORDS)
    names = dict(tcfg.get("names", {}))
    if worldview:
        names[WORLDVIEW_SUBJECT] = WORLDVIEW[WORLDVIEW_ALIASES.get(worldview, worldview)]

    kids = [s for s in models.students() if student is None or models.is_student(s, student)]
    if not kids:
        raise SystemExit(f"Oppilasta {student!r} ei löydy." if student else "Wilmasta ei löytynyt oppilaita.")
    lessons = models.week_schedule(student, monday)
    out_dir = out_dir or OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    if not html_only:
        chrome_path()

    for kid in kids:
        snack_days = set().union(*(days for ref, days in snack_rules if ref is None or models.is_student(kid, ref)))
        tt = build([l for l in lessons if l.student.number == kid.number], kid, monday, drop_support=drop_support,
                   support_words=support_words, pe_words=pe_words, names=names, breaks=breaks, lunch=lunch_time,
                   snack_days=snack_days)
        html = render_html(tt, theme, pe_emoji=pe_emoji, start_emoji=start_emoji)
        base = out_dir / f"lukujarjestys-{_slug(tt.first_name)}-{theme.name}-{monday.isoformat()}"
        if html_only:
            base.with_suffix(".html").write_text(html, encoding="utf-8")
            print(f"{tt.first_name}: {base.with_suffix('.html')}")
        else:
            with tempfile.TemporaryDirectory() as d:
                page = Path(d, "lukujarjestys.html")
                page.write_text(html, encoding="utf-8")
                html_to_pdf(page, base.with_suffix(".pdf"))
            print(f"{tt.first_name}: {base.with_suffix('.pdf')}")
        empty = [WEEKDAYS[i].lower() for i in range(5) if tt.empty_days[i]]
        if empty and len(empty) < 5:
            print(f"  huom: ei tunteja ({', '.join(empty)}); onko loma? Valitse tarvittaessa toinen viikko: --week YYYY-MM-DD")
        elif len(empty) == 5:
            print("  huom: koko viikko tyhjä; valitse toinen viikko: --week YYYY-MM-DD")
    return 0
