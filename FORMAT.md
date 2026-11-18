# how the `.p00p` file thingy works

this is the exact layout for `.p00p` version 1. its here so the format isnt just
magic numbers hiding in `main.py` and so future me can remember what i did lol

all multi-byte numbers are big-endian

## the outside wrapper
##
| offset | size | thing | what it means |
| ---: | ---: | --- | --- |
| `0` | 5 | magic | ASCII `P00P` + a null byte |
| `5` | 1 | version | file version. its `1` right now |
| `6` | 16 | salt | random bytes so every save looks different |
| `22` | 4 | length | unsigned payload length |
| `26` | changes | payload | compressed + camouflaged JSON stuffs |
| changes | 16 | digest | first 16 bytes of SHA-256 for everything before it |

the whole file is `42 + payload length` bytes

## what happens to the payload

the actual data is compact UTF-8 JSON with its object keys sorted. it gets
compressed with zlib level 9, then every compressed byte gets XORed with the
matching byte from this stream:

~~~text
SHAKE-256("persistent-zero-leak-object-protocol-but-not-really" || salt)
~~~

SHAKE-256 spits out exactly as many bytes as the payload needs. decoding makes
the same stream, XORs it again, and decompresses the result because XOR is weird
like that

## the extremely necessary poopline ritual

the file format still only does the three operations above. the code now makes
them wear name tags and stand in a very official line though:

~~~text
PoopParcel
  -> JsonGoblin       (dict becomes sorted compact UTF-8)
  -> TrashCompactor   (UTF-8 becomes zlib bytes)
  -> ToiletCurtain    (zlib bytes get the reversible XOR disguise)
~~~

`RitualBook.Perform()` looks up a direction, dynamically chooses the matching
method on every goblin, passes around a context object, and saves a receipt for
each handoff. decoding reverses the stage order and asks every goblin to do its
opposite move. yes, this is ridiculous. that is the point

the receipts only contain stage names, Python type names, and byte counts. they
never contain payload bytes or password text. `anatomy` prints a one-line ritual
summary so u can admire all the ceremony

most importantly, old version-1 files and newly written files are byte-compatible.
the test suite independently runs the original boring three-line algorithm and
checks that the enormous poopline produces the exact same bytes

the JSON inside looks like this:

~~~json
{
  "protocol": "p00p",
  "created_at": "2030-01-01T00:00:00+00:00",
  "updated_at": "2030-01-01T00:00:00+00:00",
  "entries": {
    "example.com": {
      "username": "fake-user",
      "password": "fake-password",
      "notes": "demo data",
      "updated_at": "2030-01-01T00:00:00+00:00"
    }
  }
}
~~~

## when the decoder says nope

it rejects the file if:

- the `P00P` magic is wrong
- the version is unsupported
- the payload length doesnt match the actual file
- the SHA-256 digest doesnt match
- the payload wont turn into valid UTF-8 JSON
- the JSON doesnt have a valid P00P entry table

the digest is good for noticing corruption + uncomplicated tampering. it is not
a proper message authentication code because there is no secret key involved

## security stuff so nobody gets the wrong idea

anyone with this source code can reverse the encoding. SHAKE-256 sounds fancy,
but im using it as a repeatable camouflage stream, **not encryption**. the key
is a public constant sitting in the decoder. the random salt changes how each
save looks; it does not make the contents secret

adding classes, dynamic method lookup, parcels, receipts, a context object, and
three named goblins also does not make it secret. complexity is not cryptography,
even when the complexity has excellent poop jokes

the point is to mess with custom storage, parsing, checksums, atomic saves, and
why hiding stuff is not the same as securing it. do not put real credentials in
one of these files unless u enjoy learning lessons the painful way :D
