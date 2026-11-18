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

## important thing before u use it

**this is not a real password manager. dont put real passwords in it.**

the file is compressed + camouflaged, so a super lazy scraper probably wont
see the strings. the decoder is also sitting right here in `main.py` though.
any virus, hacker, or mildly curious person can read it and undo everything

a dot at the front of a filename just makes it hidden in some file browsers.
a stupid extension does not magically make the data safe. use an actual audited
password manager with real authenticated encryption for passwords u care about

## how to run the thingy

u need **Python 3.9 or newer**. there are no packages to install because i didnt
feel like making u download half of the internet for one poop file

these commands are for a macOS/Linux terminal:

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
| `anatomy` | shows the binary file bits + checks the file |

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

[FORMAT.md](FORMAT.md) has the exact byte layout if u wanna see all the nerdy
file format details

## testing it

~~~sh
python3 -m unittest -v
~~~

the project only uses python's standard library. the tests cover encoding,
corruption checks, password generation, file permissions, and the whole CLI
workflow

## credits + important legal poop

made by **Jnaor** for Hack Club Crescent :D

again: this is a Weird Storage demo, not somewhere to put the password to your
bank account. if u ignore this and get hacked thats between u and the hacker
