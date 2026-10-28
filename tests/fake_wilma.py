#!/usr/bin/env python3
"""Tekaistu `wilma`-CLI testeihin: tulostaa wilmai:n dokumentoidun JSON-muodon."""
import json
import os
import sys

args = sys.argv[1:]
if os.environ.get("FAKE_FAIL") == "not_logged_in":
    print(json.dumps({"status": "error", "code": "not_logged_in", "message": "Log in first"}), file=sys.stderr)
    sys.exit(3)
kid = {"studentNumber": "1", "name": "Kiia Virtanen"}
if args[:1] == ["students"]:
    print(json.dumps({"students": [kid]}))
elif args[:1] == ["exams"]:
    print(json.dumps({"students": [{"student": kid, "exams": [
        {"date": "2026-10-30", "time": None, "subject": "Matematiikka", "name": "Koe 2", "topic": "Yhtälöt", "teacher": "Aho"},
        {"date": "2026-10-29", "time": "08:30", "subject": "Englanti", "name": "Unit test", "topic": "Units 7-9", "teacher": "Ek"},
    ]}], "argv": args, "password": os.environ.get("WILMA_PASSWORD")}))
elif args[:1] == ["schedule"]:
    print("raakateksti " + " ".join(args))
else:
    print(json.dumps({"status": "error", "code": "unknown_command", "message": "?"}), file=sys.stderr)
    sys.exit(2)
