# Persistent 0-leak 0bject Protocol (`.p00p`)

> The password manager designed to avoid scrapers and viruses!

P00P saves your passwords as a custom hidden file. When—not if—you get hacked,
the hackers will never find them because the filename has a dot in front and
the extension is spelled wrong. Revolutionary. Only **$99.99**!

This is a project for the **Hack Club Crescent Weird Storage** card. It is a
working terminal app and custom binary file format wrapped in intentionally
terrible security advice.

## Important reality check

**P00P is not a real password manager. Do not put real passwords in it.**

The format compresses and camouflages its contents, so `grep` and `strings`
will not casually reveal them. However, the program contains everything needed
to reverse that camouflage. A virus, scraper, or mildly curious hacker can read
the code and decode the file. Hidden filenames and unusual extensions are not
security controls.

For real passwords, use a reputable, audited password manager with real
authenticated encryption.

## Try it

P00P only needs Python 3.9 or newer—there are no packages to install.

```sh
# Create a hidden vault in the current directory
python3 main.py init

# Add an obviously fake password (omit -p to enter it in a hidden prompt)
python3 main.py add example.com -u totally-real-user -p fake-password-123

# Look around without exposing stored passwords
python3 main.py list
python3 main.py get example.com
python3 main.py info

# Reveal one password
python3 main.py get example.com --show

# Remove it
python3 main.py remove example.com
```

The default vault is `.passwords.p00p`. Use another file with `--vault`:

```sh
python3 main.py init --vault .secrets.poop
python3 main.py add nefarious-bank.biz --vault .secrets.poop
```

You can also set `P00P_FILE` to choose a default vault path.

## What is in a `.p00p` file?

```text
P00P magic | version | random salt | payload length | camouflaged payload | checksum
```

The payload is JSON compressed with zlib and XORed with a reproducible SHAKE-256
byte stream. The checksum catches accidental corruption. This is weird storage
and casual string hiding—not encryption.

Vault writes are atomic, and newly written vaults use owner-only (`600`) file
permissions on systems that support them. Those are useful safety details, but
they do not turn the camouflage into cryptographic protection.

## Commands

Run `python3 main.py --help` or `python3 main.py <command> --help` for all
options.

| Command | Purpose |
| --- | --- |
| `init` | Create an empty vault |
| `add` | Add or replace an entry |
| `list` | List names and usernames |
| `get` | Read an entry, masked by default |
| `remove` / `rm` | Delete an entry after confirmation |
| `info` | Show format metadata and permissions |
