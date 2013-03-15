
"""A simple iterator for reading characters of input, but substituting
strings 'UP', 'DOWN', 'LEFT', 'RIGHT', etc. when the relevant escape is read in.
Failed escapes are output as individual characters as normal."""

def readesc(f):
	ESCAPES = {
		'\x1b[A': 'UP',
		'\x1b[B': 'DOWN',
		'\x1b[C': 'RIGHT',
		'\x1b[D': 'LEFT',
	}

	buf = ''
	while 1:
		c = f.read(1)
		if not c: return
		buf += c
		if buf in ESCAPES:
			yield ESCAPES[buf]
			buf = ''
			continue
		if any(escape.startswith(buf) for escape in ESCAPES):
			continue
		for c in buf:
			yield c
		buf = ''
