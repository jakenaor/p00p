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

## adding ur sound effects later

the qt app already throws named sound cues at `HandleSoundCue` in `qt_gui.py`.
right now that function does absolutely nothing on purpose. put ur non-blocking
wav player there and map these names however u want:

~~~text
ui_click, dialog_open, dialog_close, vault_open, vault_new,
entry_save, entry_remove, generate, copy, reveal, hide, error, easter_egg
~~~

dont make every button load a file by itself or the ui will become thirteen
tiny audio systems fighting in a trench coat. the backend signal keeps all the
actual playback in one spot, and unknown cue typos get ignored

the GUI opens the password bowl window. from there u can make/open vaults, search,
sort by name/user/health/date, add/edit/remove entries, copy usernames, reveal
or temporarily copy a password. the
list shows basic password-health counts without showing the password itself.
revealed passwords hide again after 20 seconds, and copied stuff clears from
the clipboard after 20 seconds if something else hasnt replaced it already.
the add/edit window has a configurable generator and live basic health feedback

the interface uses blocky terminal panels, a moving crt shader, a tic-80-ish
mouse, and exactly one visible poop mascot. press `F8` if the shader needs to
get out of the way while u debug it

keyboard things for people who hate clicking:

- `cmd/ctrl + f` jumps into vault search
- `cmd/ctrl + shift + n` opens a new entry
- `cmd/ctrl + e` edits the selected entry
- `cmd/ctrl + s` saves the open entry editor
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
supports that stuff

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
the whole CLI workflow

## credits + important legal poop

made by **Jnaor** for Hack Club Crescent :D

again: this is a Weird Storage demo, not somewhere to put the password to your
bank account. if u ignore this and get hacked thats between u and the hacker
