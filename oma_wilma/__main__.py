"""python -m oma_wilma <komento>

Komennot: check, students, exams (haku, vain luku) sekä sync-exams, sync-messages, remove-event (kalenteriin kirjoittavat)
ja raw (mikä tahansa wilmai-komento). Kokeet ja viestit ovat omissa moduuleissaan: sync_exams.py ja sync_messages.py.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import bridge, models
from .report import format_exams
from .sync_messages import DEFAULT_DAYS


# ---------------------------------------------------------------- komennot (kukin palauttaa poistumiskoodin)

def want_json(args: argparse.Namespace) -> bool:
    return args.json or (not args.text and not sys.stdout.isatty())


def _print_students(found: list[models.Student], as_json: bool) -> None:
    if as_json:
        print(json.dumps([s.__dict__ for s in found], ensure_ascii=False, indent=2))
    else:
        print("\n".join(f"{s.number}  {s.name}" for s in found) or "(ei oppilaita)")


def cmd_check(args) -> int:
    version = bridge.installed_version()
    warning = bridge.version_warning(version)
    found = models.students()
    if want_json(args):
        print(json.dumps({"wilmai": version, "warning": warning, "students": [s.__dict__ for s in found]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"wilmai {version or '?'}" + (f"\nVAROITUS: {warning}" if warning else ""))
        _print_students(found, as_json=False)
    return 0


def cmd_students(args) -> int:
    _print_students(models.students(), want_json(args))
    return 0


def cmd_exams(args) -> int:
    exams = models.upcoming_exams(args.student, args.limit)
    print(json.dumps([e.to_json() for e in exams], ensure_ascii=False, indent=2) if want_json(args) else format_exams(exams))
    return 0


def cmd_raw(args) -> int:
    if not args.args:
        print("raw tarvitsee wilmai-komennon, esim. `raw schedule week` tai `raw help`", file=sys.stderr)
        return 2
    sys.stdout.write(bridge.run(args.args, json_output=False))
    return 0


def cmd_sync_exams(args) -> int:
    from . import sync_exams
    return sync_exams.run(args.student, args.dry_run)


def cmd_sync_messages(args) -> int:
    from . import sync_messages
    return sync_messages.run(args.student, args.days, args.dry_run, args.again, args.explain)


def cmd_remove_event(args) -> int:
    from .calendar_export import remove_events
    result = remove_events(args.uids)
    print(f"Poistettu {result['removed']}, tuntemattomia tunnisteita {result['unknown']}.")
    return 0


COMMANDS = {"check": cmd_check, "students": cmd_students, "exams": cmd_exams, "raw": cmd_raw,
            "sync-exams": cmd_sync_exams, "sync-messages": cmd_sync_messages, "remove-event": cmd_remove_event}


# ---------------------------------------------------------------- komentorivi

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oma_wilma",
                                     description="Omat Wilma-työkalut (vain luku), wilmai:n CLI:n päällä.")
    sub = parser.add_subparsers(dest="command", required=True)

    def student_option(p):
        p.add_argument("--student", help="vain tämä oppilas (numero tai nimen alku)")

    def output_options(p):
        group = p.add_mutually_exclusive_group()
        group.add_argument("--json", action="store_true", help="JSON (oletus putkessa)")
        group.add_argument("--text", action="store_true", help="teksti (oletus terminaalissa)")

    output_options(sub.add_parser("check", help="näyttää wilmai-version ja kirjautuu (tarkistaa asetukset ja kaksivaiheisen)"))
    output_options(sub.add_parser("students", help="oppilaat"))
    exams = sub.add_parser("exams", help="tulevat kokeet")
    student_option(exams)
    exams.add_argument("--limit", type=int, default=20)
    output_options(exams)

    sync_exams = sub.add_parser("sync-exams", help="vie tulevat kokeet iCloud-kalentereihin 'Wilma <etunimi>'")
    sync_exams.add_argument("--student", help="vain tämä oppilas (numero tai nimen alku); poistoja ei silloin tehdä")
    sync_exams.add_argument("--dry-run", action="store_true", help="näyttää mitä kalenteriin tulisi, ei kirjoita mitään")

    sync_messages = sub.add_parser(
        "sync-messages", help="opettajien viesteistä päivälliset ilmoitukset (liikunta, kuvaus, retki ...) kalentereihin; "
                              "viestit käsittelee vain paikallinen Ollama")
    student_option(sync_messages)
    sync_messages.add_argument("--days", type=int, default=DEFAULT_DAYS,
                               help=f"kuinka monen päivän viestit otetaan mukaan (oletus {DEFAULT_DAYS})")
    sync_messages.add_argument("--again", action="store_true",
                               help="käsittele myös jo käsitellyt viestit uudelleen (esim. kun tulkintaa on korjattu)")
    sync_messages.add_argument("--explain", action="store_true",
                               help="näyttää viestikohtaisesti, mitä malli ehdotti, ja hylkäysten syyt (ei viestin tekstiä)")
    sync_messages.add_argument("--dry-run", action="store_true",
                               help="kertoo montako viestiä käsiteltäisiin; ei avaa viestejä eikä kirjoita mitään")

    remove = sub.add_parser("remove-event", help="poistaa tämän työkalun luoman kalenteritapahtuman tunnisteella (esim. kaksoiskappale)")
    remove.add_argument("uids", nargs="+", help="tunniste, esim. 0123456789abcdef (tapahtuman muistiinpanoissa: [wilma:...])")

    raw = sub.add_parser("raw", help="mikä tahansa wilmai-komento sellaisenaan: oma_wilma raw schedule week")
    raw.add_argument("args", nargs=argparse.REMAINDER)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return COMMANDS[args.command](args)
    except bridge.WilmaError as err:
        print(json.dumps({"status": "error", "code": err.code, "message": err.message}, ensure_ascii=False), file=sys.stderr)
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
