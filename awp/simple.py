
"""This module uses the existing mplayer interface instead of making a new one.

The advantage is a saving of effort, and exposure of all available information
and controls.

We still have to code commands that edit the playlist ourselves, mainly by intercepting
keystrokes. As such it is less self-documenting (lacking a clear menu system).

Some minor gripes: The latency between a song finishing and the next starting is higher,
due to creating a new process every time.

In less concrete terms, this solution is "hacky" and possibly less reliable.
"""

from gevent.subprocess import Popen, PIPE, STDOUT
import gevent
from gevent.fileobject import FileObject
from gevent.os import make_nonblocking
from signal import SIGCHLD
import os, sys
import errno
from termios import ICANON, ECHO, ECHONL

from readesc import readesc
from escapes import CLEAR
from playlist import Playlist
from withtermios import TermAttrs


class RaiseOnExit(object):
	"""Allows an exception to be raised upon a child exit.
	Usage:
		proc = gevent.subprocess.Popen(...)
		try:
			with RaiseOnExit(proc):
				...
		except RaiseOnExit.ChildExited:
			# proc is dead
		# exception will never occur here
	"""

	class ChildExited(Exception): pass

	def __init__(self, proc, g_target=None, exception=ChildExited):
		"""Pass in a greenlet g_target and a Popen object child.
		When child exits, exception is raised in g_target.
		exception defaults to RaiseOnExit.ChildExited.
		g_target defaults to current greenlet at init time.
		"""
		self.g_target = g_target or gevent.getcurrent()
		self.proc = proc
		self.exception = exception

	def throw_func(self, waiter):
		self.g_target.throw(self.exception)

	def __enter__(self):
		self.waiter = gevent.spawn(lambda: self.proc.wait())
		self.waiter.link(self.throw_func)

	def __exit__(self, *exc_info):
		self.waiter.unlink(self.throw_func)


def play(playlist, stdin=None, stdout=None):
	"""Takes a Playlist and plays forever.
	Controls (in addition to mplayer standard controls):
		q: Skip and demote.
		f: Promote.
		d: Demote without skipping
		Q: Quit.
	All promotions and demotions double/halve the weighting.
	"""

	def convert_fobj(fobj):
		make_nonblocking(fobj.fileno())
		return FileObject(fobj, bufsize=0, close=False)

	if not stdin: stdin = convert_fobj(sys.stdin)
	if not stdout: stdout = convert_fobj(sys.stdout)

	if isinstance(playlist, str): playlist = Playlist(playlist)

	VOL_MAX = int(os.environ.get('VOL_MAX',2)) # Sets what interface reports as "100%"
	VOL_FUDGE = float(os.environ.get('VOL_FUDGE',1)) # Volume fudge factor to modify volume globally.
	                                               # DISABLES PERSISTENT VOLUME CHANGES WHEN NOT DEFAULT

	def out_reader(out, stdout, filename):
		# This is a turd, please ignore it (it sniffs the output stream for "Volume: X %")
		buf = ''
		while 1:
			c = out.read(1)
			if not c: return
			buf += c
			if not 'Volume:'.startswith(buf):
				stdout.write(buf)
				buf = ''
			elif buf == 'Volume:':
				volbuf = ''
				while 1:
					c = out.read(1)
					if not c: return # Volume report was interrupted, ignore it
					buf += c
					if c == '%':
						if VOL_FUDGE == 1:
							playlist.update(filename, volume = float(volbuf) * VOL_MAX / 100.)
						break
					else:
						volbuf += c
				stdout.write(buf)
				buf = ''

	for filename, volume in playlist:
		player_in = None
		player_out = None
		g_out_reader = None
		proc = None
		try:
			stdout.write(CLEAR + '\n{}\n\n'.format(playlist.format_entry(filename)))
			proc = Popen(['mplayer', '-vo', 'none', '-softvol', '-softvol-max', str(VOL_MAX * 100.),
						'-volume', str(VOL_FUDGE * volume * 100. / VOL_MAX), filename],
						 stdin=PIPE, stdout=PIPE, stderr=open('/dev/null','w'))
			player_in = convert_fobj(proc.stdin)
			player_out = convert_fobj(proc.stdout)

			g_out_reader = gevent.spawn(out_reader, player_out, stdout, filename)

			with RaiseOnExit(proc), \
			     TermAttrs.modify(exclude=(0,0,0,ECHO|ECHONL|ICANON)):
				while True:
					c = stdin.read(1)
					if c == 'q':
						playlist.update(filename, weight=lambda x: x/2.)
						player_in.write(" \n")
					elif c == 'f':
						playlist.update(filename, weight=lambda x: x*2.)
					elif c == 'd':
						playlist.update(filename, weight=lambda x: x/2.)
					elif c == 'Q':
						player_in.write("q")
						return
					else:
						player_in.write(c)

		except OSError, e:
			# There's a race that can occur here, causing a broken pipe error
			if e.errno != errno.EPIPE: raise
		except RaiseOnExit.ChildExited:
			# This is the expected path out of the input loop
			pass
		finally:
			if proc:
				try:
					proc.terminate()
				except OSError, e:
					if e.errno != errno.ESRCH: raise
				proc.wait()
			if g_out_reader:
				g_out_reader.join()
		if playlist.dirty: playlist.writefile()


if __name__ == '__main__':
#	import debug
#	import gevent.backdoor
#	gevent.backdoor.BackdoorServer(('localhost', 1666)).start()
#	gevent.spawn(debug.starve_test, open('/tmp/log', 'w'))
#	gevent.sleep(0.2)
	play(*sys.argv[1:])