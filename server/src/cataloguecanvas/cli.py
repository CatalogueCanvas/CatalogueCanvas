"""``cc`` — maintenance commands for a running CatalogueCanvas instance.

Installed as a console script, so inside the container everything is one
``docker compose exec`` away::

    docker compose exec cataloguecanvas cc reset-password --user admin
    docker compose exec cataloguecanvas cc backup --out /data/backups
    docker compose exec cataloguecanvas cc restore /data/backups/<file>.zip
    docker compose exec cataloguecanvas cc ingest /data/import

Configuration comes from the same ``settings`` object the server reads, so
``CC_DATA_DIR`` and friends behave identically here and in the app.
"""
from __future__ import annotations
import argparse
import getpass
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import audit
from .auth import hash_password
from .backup import (
    RestoreError,
    create_backup,
    current_item_count,
    default_backup_path,
    inspect_archive,
    restore_backup,
)
from .db import (
    ensure_schema,
    get_all_libraries,
    get_connection,
    get_default_library,
    get_library,
    get_user_by_username,
    list_users,
    set_admin_hash,
    update_user,
)
from .settings import settings

RESTORE_CONFIRM = "restore"


def _connect():
    settings.ensure_dirs()
    conn = get_connection(settings.db_path)
    ensure_schema(conn)
    return conn


def _confirm(prompt: str, expected: str) -> bool:
    """Ask for a typed confirmation. Returns False on anything else, including EOF."""
    try:
        answer = input(f"{prompt} Type '{expected}' to continue: ").strip()
    except EOFError:
        return False
    return answer == expected


# --- reset-password ---

def cmd_reset_password(args: argparse.Namespace) -> int:
    conn = _connect()
    try:
        username = args.user or settings.admin_username
        user = get_user_by_username(conn, username)

        # `is None` rather than falsiness: an explicitly-passed empty string is a
        # mistake to reject, not a reason to drop into an interactive prompt --
        # a script with an unset variable would otherwise hang.
        password = args.password
        if password is None:
            password = getpass.getpass(f"New password for '{username}': ")
            if password != getpass.getpass("Repeat password: "):
                print("passwords do not match", file=sys.stderr)
                return 1
        if not password:
            print("password cannot be empty", file=sys.stderr)
            return 1

        new_hash = hash_password(password)
        if user:
            update_user(conn, user["id"], password_hash=new_hash)
            # Keep the legacy single-admin hash in step, since that is what the
            # password-only login path checks when multi-user mode is off.
            if user["role"] == "admin":
                set_admin_hash(conn, new_hash)
        elif username == settings.admin_username:
            # No users row yet (fresh single-admin install): set the admin hash.
            set_admin_hash(conn, new_hash)
        else:
            print(f"no such user: {username}", file=sys.stderr)
            print(f"known users: {', '.join(u['username'] for u in list_users(conn)) or '(none)'}", file=sys.stderr)
            return 1

        # Revoke every existing session: a password reset that leaves old
        # cookies working does not actually lock anyone out.
        revoked = conn.execute("DELETE FROM sessions").rowcount
        conn.commit()

        audit.log_event("user.password_reset", actor="cli", target=username, sessions_revoked=revoked)
        print(f"Password updated for '{username}'. Revoked {revoked} active session(s).")
        return 0
    finally:
        conn.close()


# --- backup ---

def cmd_backup(args: argparse.Namespace) -> int:
    conn = _connect()
    try:
        if args.out:
            out = Path(args.out)
            # A directory (existing, or clearly meant as one) gets a generated
            # filename; anything else is treated as the target file itself.
            if out.is_dir() or args.out.endswith("/"):
                out = out / default_backup_path().name
        else:
            out = default_backup_path()

        create_backup(conn, out)
        size = out.stat().st_size
        audit.log_event("backup.create", actor="cli", target=str(out), size_bytes=size)
        print(f"Backup written to {out} ({size:,} bytes)")
        return 0
    finally:
        conn.close()


# --- restore ---

def cmd_restore(args: argparse.Namespace) -> int:
    archive = Path(args.archive)
    try:
        info = inspect_archive(archive)
    except RestoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    existing_items = current_item_count()
    print(f"Archive:   {archive}")
    print(f"Contains:  {info['entries']} entries, {info['storage_files']} storage files, {info['total_bytes']:,} bytes")
    print(f"Target:    {settings.data_dir}")
    print(f"Current DB: {existing_items} item(s)")

    if existing_items > 0 and not args.force:
        print(
            f"\nrefusing to restore over a database that already holds {existing_items} item(s).\n"
            "Re-run with --force if that is what you intend.",
            file=sys.stderr,
        )
        return 1

    if not args.force and not _confirm("\nThis will replace the current database.", RESTORE_CONFIRM):
        print("aborted")
        return 1

    try:
        result = restore_backup(archive)
    except RestoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    audit.log_event("backup.restore", actor="cli", target=str(archive), extracted=result["extracted"])
    print(f"Restored {result['extracted']} file(s) into {settings.data_dir}")
    if result["previous_db"]:
        print(f"Previous database kept at {result['previous_db']}")
    print("Restart the app so it picks up the restored database.")
    return 0


# --- ingest ---

def cmd_ingest(args: argparse.Namespace) -> int:
    # Imported here rather than at module load: ingest pulls in Pillow and
    # cairosvg, which are slow to import and irrelevant to the other commands.
    from .ingest import ingest_zip_bytes

    source = Path(args.directory)
    if not source.is_dir():
        print(f"error: not a directory: {source}", file=sys.stderr)
        return 1

    conn = _connect()
    try:
        if args.library:
            lib = get_library(conn, args.library)
            if not lib:
                known = ", ".join(f"{x['id']} ({x['name']})" for x in get_all_libraries(conn))
                print(f"error: unknown library {args.library}. Known: {known or '(none)'}", file=sys.stderr)
                return 1
        else:
            lib = get_default_library(conn)
            if not lib:
                print("error: no default library configured", file=sys.stderr)
                return 1

        zips = sorted(p for p in source.rglob("*.zip") if p.is_file())
        if not zips:
            print(f"No .zip files found under {source}")
            return 0

        print(f"Ingesting {len(zips)} zip(s) from {source} into library '{lib['name']}' ({lib['id']})")
        created = skipped = failed = 0
        for path in zips:
            try:
                result = ingest_zip_bytes(
                    path.read_bytes(),
                    path.name,
                    conn,
                    lib["id"],
                    Path(lib["path"]),
                    force=args.force,
                )
            except (ValueError, OSError) as exc:
                failed += 1
                print(f"  FAIL  {path.name}: {exc}")
                continue

            if result.created:
                created += 1
                print(f"  ok    {path.name} -> {result.item['id']}{f' ({result.note})' if result.note else ''}")
            else:
                skipped += 1
                print(f"  skip  {path.name}: {result.note or 'already ingested'}")

        audit.log_event(
            "item.cli_ingest", actor="cli", target=str(source),
            created=created, skipped=skipped, failed=failed, library_id=lib["id"],
        )
        print(f"\nDone: {created} created, {skipped} skipped, {failed} failed")
        return 1 if failed else 0
    finally:
        conn.close()


# --- diagnostics ---

def cmd_diagnostics(args: argparse.Namespace) -> int:
    from .diagnostics import build_report

    report = build_report()
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report)
        print(f"Diagnostic report written to {out}")
    else:
        print(report)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cc",
        description="CatalogueCanvas maintenance commands.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_reset = sub.add_parser("reset-password", help="set a user's password and revoke active sessions")
    p_reset.add_argument("--user", help=f"username (default: {settings.admin_username})")
    p_reset.add_argument("--password", help="new password; prompted for when omitted")
    p_reset.set_defaults(func=cmd_reset_password)

    p_backup = sub.add_parser("backup", help="write a database + storage backup zip")
    p_backup.add_argument("--out", help="output file or directory (default: <data dir>/backups)")
    p_backup.set_defaults(func=cmd_backup)

    p_restore = sub.add_parser("restore", help="restore a backup zip over the current data dir")
    p_restore.add_argument("archive", help="path to a backup zip")
    p_restore.add_argument("--force", action="store_true", help="skip confirmation and allow overwriting a populated database")
    p_restore.set_defaults(func=cmd_restore)

    p_ingest = sub.add_parser("ingest", help="ingest every .zip under a directory")
    p_ingest.add_argument("directory", help="directory to scan (recursively) for .zip files")
    p_ingest.add_argument("--library", help="library id to ingest into (default: the default library)")
    p_ingest.add_argument("--force", action="store_true", help="re-ingest files already present by content hash")
    p_ingest.set_defaults(func=cmd_ingest)

    p_diag = sub.add_parser("diagnostics", help="print a redacted diagnostic report")
    p_diag.add_argument("--out", help="write to this file instead of stdout")
    p_diag.set_defaults(func=cmd_diagnostics)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
