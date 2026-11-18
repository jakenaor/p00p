# P00P, the password manager that is actually safe.
# No more getting your passwords stolen after every time you download fartnite!
# Scrapers won't look for .p00p files and will leave your very important passwords alone!

"""Persistent 0-leak 0bject Protocol (.p00p).

A tiny, intentionally silly password-vault demo for Hack Club Crescent's
Weird Storage card.  The custom format camouflages strings so that a basic
grep will not find them, but it is NOT encryption and must not be treated as
real password-manager security.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import secrets
import struct
import sys
import tempfile
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


MAGIC = b"P00P\x00"
VERSION = 1
SALT_SIZE = 16
DIGEST_SIZE = 16
DEFAULT_VAULT = ".passwords.p00p"
CAMOUFLAGE_KEY = b"persistent-zero-leak-object-protocol-but-not-really"


class P00PError(Exception):
    """An error that can be shown to the user without a traceback."""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_vault() -> Dict[str, Any]:
    timestamp = now()
    return {
        "protocol": "p00p",
        "created_at": timestamp,
        "updated_at": timestamp,
        "entries": {},
    }


def camouflage(data: bytes, salt: bytes) -> bytes:
    """XOR data with a reproducible SHAKE stream.

    This prevents casual plaintext searches. It deliberately does not claim
    to provide cryptographic secrecy: the key ships with the program.
    """
    stream = hashlib.shake_256(CAMOUFLAGE_KEY + salt).digest(len(data))
    return bytes(left ^ right for left, right in zip(data, stream))


def encode_vault(vault: Dict[str, Any], salt: Optional[bytes] = None) -> bytes:
    salt = salt or secrets.token_bytes(SALT_SIZE)
    raw = json.dumps(vault, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload = camouflage(zlib.compress(raw, level=9), salt)
    header = MAGIC + bytes([VERSION]) + salt + struct.pack(">I", len(payload))
    digest = hashlib.sha256(header + payload).digest()[:DIGEST_SIZE]
    return header + payload + digest


def decode_vault(blob: bytes) -> Dict[str, Any]:
    minimum_size = len(MAGIC) + 1 + SALT_SIZE + 4 + DIGEST_SIZE
    if len(blob) < minimum_size or not blob.startswith(MAGIC):
        raise P00PError("that is not a valid .p00p file")

    cursor = len(MAGIC)
    version = blob[cursor]
    cursor += 1
    if version != VERSION:
        raise P00PError(f"unsupported .p00p version: {version}")

    salt = blob[cursor : cursor + SALT_SIZE]
    cursor += SALT_SIZE
    payload_size = struct.unpack(">I", blob[cursor : cursor + 4])[0]
    cursor += 4
    expected_size = cursor + payload_size + DIGEST_SIZE
    if len(blob) != expected_size:
        raise P00PError("the vault is truncated or has trailing data")

    payload = blob[cursor : cursor + payload_size]
    digest = blob[-DIGEST_SIZE:]
    expected_digest = hashlib.sha256(blob[:-DIGEST_SIZE]).digest()[:DIGEST_SIZE]
    if not secrets.compare_digest(digest, expected_digest):
        raise P00PError("the vault is corrupted (integrity check failed)")

    try:
        raw = zlib.decompress(camouflage(payload, salt))
        vault = json.loads(raw.decode("utf-8"))
    except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise P00PError("the vault payload could not be decoded") from error

    if not isinstance(vault, dict) or not isinstance(vault.get("entries"), dict):
        raise P00PError("the vault has an invalid structure")
    return vault


def load_vault(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise P00PError(f"vault not found: {path} (run 'init' first)")
    if not path.is_file():
        raise P00PError(f"vault is not a regular file: {path}")
    try:
        return decode_vault(path.read_bytes())
    except OSError as error:
        raise P00PError(f"could not read {path}: {error}") from error


def save_vault(path: Path, vault: Dict[str, Any]) -> None:
    """Atomically save a vault with owner-only permissions where supported."""
    path.parent.mkdir(parents=True, exist_ok=True)
    vault["updated_at"] = now()
    encoded = encode_vault(vault)
    temporary_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", dir=path.parent, delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(encoded)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    except OSError as error:
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise P00PError(f"could not save {path}: {error}") from error


def normalize_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise P00PError("entry names cannot be empty")
    return cleaned


def find_entry(entries: Dict[str, Any], requested_name: str) -> str:
    requested = requested_name.casefold()
    matches = [name for name in entries if name.casefold() == requested]
    if not matches:
        raise P00PError(f"entry not found: {requested_name}")
    return matches[0]


def command_init(args: argparse.Namespace) -> None:
    if args.vault.exists() and not args.force:
        raise P00PError(f"vault already exists: {args.vault} (use --force to replace it)")
    save_vault(args.vault, new_vault())
    print(f"made a suspiciously secure vault at {args.vault}")
    print("warning: .p00p camouflage is not encryption; use fake passwords for demos")


def command_add(args: argparse.Namespace) -> None:
    vault = load_vault(args.vault)
    entries = vault["entries"]
    name = normalize_name(args.name)
    existing = next((item for item in entries if item.casefold() == name.casefold()), None)
    if existing and not args.replace:
        raise P00PError(f"entry already exists: {existing} (use --replace to update it)")

    password = args.password
    if password is None:
        password = getpass.getpass("password (hidden while typing): ")
    if not password:
        raise P00PError("password cannot be empty")

    if existing and existing != name:
        del entries[existing]
    entries[name] = {
        "username": args.username or "",
        "password": password,
        "notes": args.notes or "",
        "updated_at": now(),
    }
    save_vault(args.vault, vault)
    verb = "updated" if existing else "added"
    print(f"{verb} {name!r} in {args.vault}")


def command_list(args: argparse.Namespace) -> None:
    entries = load_vault(args.vault)["entries"]
    if not entries:
        print("the vault is empty (a pristine bowl)")
        return
    for name in sorted(entries, key=str.casefold):
        username = entries[name].get("username") or "-"
        print(f"{name}\t{username}")


def command_get(args: argparse.Namespace) -> None:
    entries = load_vault(args.vault)["entries"]
    name = find_entry(entries, args.name)
    entry = entries[name]
    password = entry.get("password", "")
    visible_password = password if args.show else ("*" * max(8, min(len(password), 24)))
    print(f"name:     {name}")
    print(f"username: {entry.get('username') or '-'}")
    print(f"password: {visible_password}")
    if entry.get("notes"):
        print(f"notes:    {entry['notes']}")
    if not args.show:
        print("(pass --show to reveal the password)")


def command_remove(args: argparse.Namespace) -> None:
    vault = load_vault(args.vault)
    entries = vault["entries"]
    name = find_entry(entries, args.name)
    if not args.yes:
        answer = input(f"remove {name!r}? [y/N] ").strip().casefold()
        if answer not in {"y", "yes"}:
            print("cancelled")
            return
    del entries[name]
    save_vault(args.vault, vault)
    print(f"removed {name!r}")


def command_info(args: argparse.Namespace) -> None:
    vault = load_vault(args.vault)
    print(f"file:       {args.vault}")
    print(f"format:     .p00p v{VERSION} (camouflaged, NOT encrypted)")
    print(f"entries:    {len(vault['entries'])}")
    print(f"created:    {vault.get('created_at', 'unknown')}")
    print(f"updated:    {vault.get('updated_at', 'unknown')}")
    try:
        mode = args.vault.stat().st_mode & 0o777
        print(f"permissions: {mode:03o}")
    except OSError:
        pass


def add_vault_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--vault",
        type=Path,
        default=Path(os.environ.get("P00P_FILE", DEFAULT_VAULT)),
        help=f"vault path (default: {DEFAULT_VAULT}, or $P00P_FILE)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="p00p",
        description="hide fake passwords in a very serious custom file format",
        epilog="This is a Hack Club demo, not a secure password manager.",
    )
    parser.add_argument("--version", action="version", version="p00p 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="create an empty vault")
    add_vault_argument(init_parser)
    init_parser.add_argument("--force", action="store_true", help="replace an existing vault")
    init_parser.set_defaults(handler=command_init)

    add_parser = subparsers.add_parser("add", help="add an entry")
    add_vault_argument(add_parser)
    add_parser.add_argument("name", help="entry name, such as example.com")
    add_parser.add_argument("-u", "--username", help="username or email")
    add_parser.add_argument("-p", "--password", help="password (prompted securely if omitted)")
    add_parser.add_argument("-n", "--notes", help="optional notes")
    add_parser.add_argument("--replace", action="store_true", help="replace a matching entry")
    add_parser.set_defaults(handler=command_add)

    list_parser = subparsers.add_parser("list", help="list entry names")
    add_vault_argument(list_parser)
    list_parser.set_defaults(handler=command_list)

    get_parser = subparsers.add_parser("get", help="show one entry")
    add_vault_argument(get_parser)
    get_parser.add_argument("name", help="entry name (case-insensitive)")
    get_parser.add_argument("--show", action="store_true", help="reveal the stored password")
    get_parser.set_defaults(handler=command_get)

    remove_parser = subparsers.add_parser("remove", aliases=["rm"], help="remove an entry")
    add_vault_argument(remove_parser)
    remove_parser.add_argument("name", help="entry name (case-insensitive)")
    remove_parser.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    remove_parser.set_defaults(handler=command_remove)

    info_parser = subparsers.add_parser("info", help="inspect vault metadata")
    add_vault_argument(info_parser)
    info_parser.set_defaults(handler=command_info)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except (P00PError, KeyboardInterrupt, EOFError) as error:
        message = str(error) or "cancelled"
        print(f"p00p: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
