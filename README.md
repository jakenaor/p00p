# persistent 0-leak 0bject protocol (.p00p)

a password manager thingy designed to avoid scrapers and viruses!! it saves
your passwords in a weird hidden `.p00p` file so hackers definitely wont find
them because hackers dont know how dots work. revolutionary. only **$99.99** :D

im making this for the **Hack Club Crescent Weird Storage** card. its a real
terminal app + custom binary format wrapped in the worlds worst security advice

## what it does

- make hidden `.p00p` or `.poop` password bowls
- add, find, rename, list, and remove fake logins
- hide all the readable strings so basic `grep` and `strings` searches miss them
- save changes atomically with owner-only file permissions
- complain if the file is cut up, changed, malformed, or from the future
- generate random passwords using python's `secrets` stuff
- audit weak/reused passwords without printing the actual password
- admit a vault to an absurd 12-check `doctor` ward with text or JSON charts
- launch byte-identical, owner-only lifeboat snapshots and guarded restores
- compare two bowls and detect safe field changes or likely renames without dumping values
- manufacture loud, obviously fake demo bowls for screenshots without risking real logins
- reroll the random camouflage so unchanged decoded data becomes brand-new binary soup
- count aggregate health, reuse, length buckets, and storage ratios without listing secrets
- run a read-only storage lab over fresh salts, timings, plaintext probes, and corruption
- export one secret-safe text, Markdown, or JSON submission report from all the paperwork
- pour two bowls into a separate third bowl with loud, explicit conflict rules
- stamp and verify owner-only SHA-256 sidecars for exact byte-identity checks
- append secret-safe checkpoints to a hash-chained JSONL bowl ledger
- scatter one bowl into three threshold fragments and recover it from any two
- drop a cosmetic idle privacy curtain that clears only clipboard text p00p owns
- show u the weird file guts with the `anatomy` command
- pass every payload through a wildly unnecessary three-goblin poopline
- calculate a completely fake 100-point security theater score
- use the vault from a blocky qt terminal with an actual crt shader

## important thing before u use it

**this is not a real password manager. dont put real passwords in it.**

the file is compressed + camouflaged, so a super lazy scraper probably wont
see the strings. the decoder is also sitting right here in `main.py` though.
any virus, hacker, or mildly curious person can read it and undo everything

a dot at the front of a filename just makes it hidden in some file browsers.
a stupid extension does not magically make the data safe. use an actual audited
password manager with real authenticated encryption for passwords u care about

## how to run the thingy

u need **Python 3.9 or newer** for the terminal app. the terminal commands only
use pythons standard library

the current good-looking GUI uses **PySide6 + QML**. it does not care what
ancient tkinter apple left under the floorboards. u do not need Homebrew. with
a normal Python.org 3.12 install, do this once inside the project folder:

~~~sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
~~~

these commands are for a macOS/Linux terminal:

the current shader graphical version:

~~~sh
.venv/bin/python qt_gui.py
~~~

`python3 main.py gui` still opens the older tkinter bowl if u are feeling
archaeological. `ctk_gui.py` is also still around as a fossil, but the packaged
app and all the new visual work use `qt_gui.py`

## making the mac app thingy

if u want the actual drag-it-into-applications version instead of summoning it
from a terminal, install the build bits and run the package script:

~~~sh
.venv/bin/python -m pip install -r requirements-build.txt
packaging/build_macos.sh
~~~

that makes `dist/P00P.app` and an apple-silicon dmg at
`dist/P00P-0.2.0-macOS-arm64.dmg`. the app is ad-hoc signed because i do not
have a magic apple developer certificate in the repo. if another mac gets
dramatic about it, right-click the app and choose open. real public releases
would need developer-id signing + apple notarization

## the procedural beep goblin

the qt app throws named sound cues at `HandleSoundCue` in `qt_gui.py`, which now
hands them to `soundboard.py`. the soundboard synthesizes tiny 16-bit mono WAVs
on first use and plays them asynchronously with QtMultimedia. there are no audio
assets to lose, package, license, or accidentally replace with a 40mb explosion

every cue is its own miniature score made from square, triangle, sine, noise,
silence, pitch slides, and click-reducing attack/release envelopes:

~~~text
ui_click, dialog_open, dialog_close, vault_open, vault_new,
vault_close, doctor, backup, entry_save, entry_remove, generate, copy,
reveal, hide, denied (reserved for future nope buttons), error, easter_egg
~~~

one cache and one soundboard handle all playback, repeated cues restart cleanly,
the master volume applies each score's per-cue gain, and unknown cue typos or
audio-device failures get ignored instead of crashing the password bowl

the GUI opens the password bowl window. from there u can make/open vaults, search,
sort by name/user/health/date, add/edit/remove entries, copy usernames, reveal
or temporarily copy a password. the
list shows basic password-health counts without showing the password itself.
revealed passwords hide again after the configured timer (20 seconds by
default), and copied stuff clears after its own timer if something else hasnt
replaced it already. copying again restarts the clock instead of letting an old
timer sneak up and eat the new copy.
the add/edit window has a configurable generator and live basic health feedback

the settings tab remembers one master sfx on/off switch, one master volume for
every sound, the clipboard/reveal timers, and the crt shader toggle between
launches. it also has buttons to test the procedural beep goblin, clear the clipboard,
reset app settings, and delete every entry in the open vault. delete-all asks
first and then saves the empty vault atomically because even the giant red joke
button should not corrupt the bowl

the idle privacy curtain can wait from 30 seconds to 60 minutes. real mouse,
keyboard, wheel, and touch events restart its deadline. when it drops, it covers
the whole in-scene editor, hides a revealed password, and clears clipboard text
only when p00p still owns that exact text. lifting it never asks for a password:
it is a shoulder-surfing cover, not authentication, and the screen says so loudly

the settings page also has a vault-utilities clinic. it shows the current
12-check doctor summary, can refresh it without printing credentials, and can
launch a hidden timestamped lifeboat snapshot beside the open bowl with one
button. the last snapshot path stays visible for the rest of the app session.
it can also make and immediately open a separate 24-entry fake demo bowl; an
existing destination gets a real confirmation instead of a surprise overwrite.
the same panel exports secret-safe Markdown, JSON, or text submission reports
and asks before replacing a report that is already there. it can pour another
bowl into a separate third bowl after making u choose a conflict policy. the
byte-seal buttons stamp or verify a `<vault>.seal.json` sidecar; any later GUI
save marks that seal as possibly stale instead of pretending it still matches.
the 10-round storage-lab button benchmarks fresh in-memory envelopes, checks
plaintext probes and corruption rejection, then keeps only a secret-safe summary.
the bowl-ledger buttons append or verify a `<vault>.ledger.jsonl` breadcrumb
without writing entry names, usernames, notes, or passwords into the paperwork.
the ledger is a change detector, not a magic hacker-proof audit trail

the qt app keeps up to 50 old in-memory bowl snapshots for session undo/redo.
every undo and redo still goes through the normal atomic disk save, and the
timeline does not move if that save fails. opening or making another vault clears
the history so an undo can never throw data from one bowl into a different bowl

the interface uses blocky terminal panels, a moving crt shader, a tic-80-ish
mouse, and exactly one visible poop mascot. the shader switch lives in settings

keyboard things for people who hate clicking:

- `cmd/ctrl + f` jumps into vault search
- `cmd/ctrl + shift + n` opens a new entry
- `cmd/ctrl + e` edits the selected entry
- `cmd/ctrl + s` saves the open entry editor
- `cmd/ctrl + z` undoes the last add/edit/remove/delete-all from this app session
- `cmd/ctrl + shift + z` redoes the thing u just undid
- `cmd/ctrl + l` drops the cosmetic privacy curtain immediately
- the sort box understands arrows, home/end, enter/space, and escape
- tab into the vault list, then use up/down/home/end; enter edits the row
- `escape` closes the editor or releases the fake mouse

if u want to open a specific bowl:

~~~sh
.venv/bin/python qt_gui.py --vault .secrets.poop
~~~

the terminal version still works too:

~~~sh
# make the default hidden vault
python3 main.py init

# add a very fake login
python3 main.py add example.com -u totally-real-user -p fake-password-123

# leave out -p if u want a hidden password prompt
python3 main.py add definitely-not-a-bank.biz -u jake

# or make + store a random one
python3 main.py add moon-base.gov -u astronaut --generate 24
~~~

the default file is `.passwords.p00p` in whatever folder your terminal is in.
if u want a different bowl, add `--vault` to the command:

~~~sh
python3 main.py init --vault .secrets.poop
python3 main.py add nefarious-bank.biz --vault .secrets.poop
~~~

u can also set `P00P_FILE` if typing `--vault` every time is too much work lol

## looking at your fake passwords

~~~sh
# names + usernames only
python3 main.py list

# password stays covered unless u add --show
python3 main.py get example.com
python3 main.py get example.com --show

# search names, usernames, and notes (not the passwords)
python3 main.py search moon

# rename/remove stuff
python3 main.py rename example.com definitely-not-a-bank.biz
python3 main.py remove definitely-not-a-bank.biz

# award applause points for dots, wrong extensions, and other serious nonsense
python3 main.py theater
~~~

## more suspicious tools

~~~sh
# make a password without storing it
python3 main.py generate --length 32

# letters + numbers only if symbols annoy u
python3 main.py gen --length 20 --no-symbols

# check for basic bad-password stuff without revealing the passwords
python3 main.py audit

# run the full binary/file/timestamp/credential clinic
python3 main.py doctor

# machine-readable results for a robot doctor
python3 main.py doctor --json

# explicitly repair loose file permissions, then re-check everything
python3 main.py doctor --fix-permissions

# launch a hidden timestamped byte-for-byte snapshot beside the vault
python3 main.py backup

# or choose the destination and ask for a JSON dock receipt
python3 main.py lifeboat .demo-backup.p00p --json

# restore refuses to replace an existing bowl unless u explicitly add --force
python3 main.py restore .demo-backup.p00p --vault .restored.p00p

# compare decoded contents even though each file has different random camouflage
python3 main.py diff .other-bowl.p00p

# hide entry names too and hand the result to another program
python3 main.py compare .other-bowl.p00p --anonymous --json

# make 20 fictional logins that all scream DEMO and use reserved .invalid emails
python3 main.py decoy --count 20 --vault .showcase.p00p

# use a seed when u want the exact same screenshot bowl again later
python3 main.py demo --count 20 --seed "moon sewer screenshot" --vault .showcase.p00p

# keep every decoded value/timestamp but swap in fresh salt and totally new bytes
python3 main.py reroll --vault .showcase.p00p

# same thing, more bureaucratic receipt
python3 main.py repack --json --vault .showcase.p00p

# print a secret-safe histogram and storage report
python3 main.py stats --vault .showcase.p00p

# the count alias can feed the same aggregate numbers to another program
python3 main.py count --json --vault .showcase.p00p

# run 25 read-only encode/decode experiments without printing credential values
python3 main.py lab --vault .showcase.p00p

# choose another round count and feed machine-readable results to something else
python3 main.py bench --rounds 50 --json --vault .showcase.p00p

# combine anatomy + doctor + stats + theater + the lab into Markdown on stdout
python3 main.py report --vault .showcase.p00p

# atomically write an owner-only JSON report instead
python3 main.py report --format json --output submission.json --vault .showcase.p00p

# pour two bowls into a brand-new third bowl; real conflicts stop the pour
python3 main.py merge .right.p00p --output .combined.p00p --vault .left.p00p

# keep both sides of a conflict by renaming the right-side copy
python3 main.py combine .right.p00p --output .combined.p00p \
  --conflict rename-right --json --vault .left.p00p

# stamp an owner-only JSON sidecar for this exact sequence of vault bytes
python3 main.py seal --vault .showcase.p00p

# returns 0 for an exact match, 2 for a mismatch, and 1 for a broken command/file
python3 main.py verify-seal --json --vault .showcase.p00p

# append a checkpoint for the current bytes to an owner-only hash-chained JSONL log
python3 main.py ledger --record checkpoint --vault .showcase.p00p

# verify the current bowl against the last checkpoint (logbook is the silly alias)
python3 main.py logbook --json --vault .showcase.p00p

# make three owner-only fragments; keep any two if u want the bowl back
python3 main.py scatter --vault .showcase.p00p

# recover from any two; output is explicit and existing files are refused by default
python3 main.py gather .showcase.p00p.fragment.1-of-3.p00pshard \
  .showcase.p00p.fragment.3-of-3.p00pshard --output .recovered.p00p

# look at the binary envelope + make sure it still decodes
python3 main.py anatomy

# boring metadata
python3 main.py info
~~~

## every command

run `python3 main.py --help` or `python3 main.py <command> --help` if u forget
something

| command | what it does |
| --- | --- |
| `init` | makes an empty password bowl |
| `add` | adds or replaces an entry |
| `list` | lists names + usernames |
| `get` | reads one entry, with the password covered by default |
| `search` | searches names, usernames, and notes |
| `rename` | changes an entry name |
| `remove` / `rm` | removes an entry after asking first |
| `info` | shows basic file metadata + permissions |
| `generate` / `gen` | makes a random password without storing it |
| `audit` | finds basic password/file hygiene problems |
| `doctor` | runs 12 secret-safe diagnostics; optionally emits JSON or repairs permissions |
| `backup` / `lifeboat` | makes an atomic byte-identical snapshot with `600` permissions |
| `restore` | validates a lifeboat and atomically docks it without surprise overwrites |
| `diff` / `compare` | finds added/removed/changed/renamed entries without printing values |
| `decoy` / `demo` | manufactures a guarded bowl of unmistakably fake demo credentials |
| `reroll` / `repack` | atomically re-camouflages unchanged decoded data with fresh salt |
| `stats` / `count` | reports secret-safe aggregate health, reuse, lengths, and storage ratios |
| `lab` / `bench` | repeatedly probes format timing, randomization, plaintext, and corruption behavior |
| `report` | combines anatomy, doctor, stats, theater, and a 10-round lab into safe text/Markdown/JSON |
| `merge` / `combine` | pours two vaults into a guarded third vault with explicit conflict rules |
| `seal` / `stamp` | writes a secret-safe SHA-256 byte-identity sidecar with `600` permissions |
| `verify-seal` / `check-seal` | checks filename, size, digest, and decoded entry count against a seal |
| `ledger` / `logbook` | appends fixed-action checkpoints or verifies the current bowl against the last one |
| `scatter` / `shard` | writes three owner-only GF(256) fragments where any two reconstruct the bowl |
| `gather` / `unshard` | validates two matching fragments and atomically writes their exact recovered bowl |
| `theater` | awards a fake security-theater score out of 100 |
| `anatomy` | shows the binary file bits + checks the file |
| `gui` | opens the legacy tkinter password bowl |

## how the weird storage works

~~~text
P00P magic | version | random salt | payload length | camouflaged payload | checksum
~~~

the vault data starts as JSON. it gets squished with zlib, then XORed with a
repeatable SHAKE-256 byte stream. the checksum notices accidental corruption.
new saves get random salt, atomic writes, and `600` permissions when the OS
supports that stuff. loads also cap the file and decompressed payload sizes so
a cursed `.p00p` zip-bomb costume gets rejected before it eats the whole machine

this stops casual plaintext searches. it is still **not encryption** because
the "secret" camouflage key is literally included in the program dum dum

internally, `poopline.py` makes those three tiny transformations look extremely
official. a parcel gets handed to a JSON goblin, a trash compactor, and a toilet
curtain. every goblin issues a size-only receipt, and the decoder performs the
ritual backwards. this makes the code funnier and the `anatomy` report longer.
it does **not** make the passwords harder for an attacker to recover

`theater.py` takes the joke further with seven cue classes and an applause
meter. it awards points for a hidden filename, poop extension, owner-only file
permissions, absent plaintext strings, salt, checksum, and completed goblin
paperwork. a perfect 100 means maximum security theater. it does not mean the
file is secure, even a little bit

[FORMAT.md](FORMAT.md) has the exact byte layout if u wanna see all the nerdy
file format details

## testing it

~~~sh
.venv/bin/python -m unittest discover -v
~~~

the terminal/storage guts use pythons standard library and the GUI dependency
is pinned in `requirements.txt`. the tests cover encoding, corruption checks,
password generation, file permissions, GUI search/sort/audit helpers,
password-safe list summaries, dialog health/generator validation, easter-egg
behavior, byte-for-byte poopline compatibility, security-theater scoring, and
the whole CLI workflow. the doctor tests also verify that one diagnostic can
fall over without cancelling the rest of the ward and that reports never print
stored credentials. merge tests make sure neither input gets touched, collision
policies stay deterministic, and receipts only contain counts. the sound tests
decode every generated WAV, validate sample
ranges and envelopes, and exercise caching/playback with a fake audio device
the privacy-curtain tests verify event-driven deadline resets, explicit lifting,
password covering, clipboard ownership, and the real QML overlay state
the storage-lab tests use both real and deliberately broken encoders to verify
randomized envelopes, strict round limits, safe rendering, and attention results

the toilet-wax seal is deliberately not a signature or a MAC. it catches a
changed, truncated, renamed, or accidentally replaced bowl, but an attacker can
edit the bowl and stamp a brand-new seal. that would require a private signing
key or authenticated encryption, neither of which this joke format has

the bowl ledger adds sequence numbers, timestamps, a digest of each exact vault,
and a SHA-256 link back to the previous ledger record. fixed action names keep
passwords out of somebody's creative comment. it is useful for spotting an
accidental edit or a missing middle record, but it is still not authenticated:
somebody who can replace both files can recalculate the entire chain. ledger
tests cover malformed chains, stale vaults, owner-only output, and credential
text staying out of every rendered result

## credits + important legal poop

made by **Jnaor** for Hack Club Crescent :D

again: this is a Weird Storage demo, not somewhere to put the password to your
bank account. if u ignore this and get hacked thats between u and the hacker
