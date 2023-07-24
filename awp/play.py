
"""This module uses the existing mplayer interface instead of making a new one.

The advantage is a saving of effort, and exposure of all available information
and controls.

We still have to code commands that edit the playlist ourselves, mainly by intercepting
keystrokes. As such it is less self-documenting (lacking a clear menu system).

Some minor gripes: The latency between a song finishing and the next starting is higher,
due to creating a new process every time.

In less concrete terms, this solution is "hacky" and possibly less reliable.
"""

from gevent.subprocess import Popen, PIPE
import gevent.queue
from gevent.select import select
from gevent import socket
import os, sys
import errno
import logging
import json
from importlib import import_module
from termios import ICANON, ECHO, ECHONL

from escapes import CLEAR
from termhelpers import TermAttrs

from playlist import Playlist
from lastfm import LastFM, getmetadata
from rainymood import spawn_rainymood

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


def set_lastfm(lastfm, filename):
	try:
		metadata = getmetadata(filename)
		title = (metadata['title'][0] if 'title' in metadata
				 else os.path.splitext(os.path.basename(filename))[0])
		artist = metadata['artist'][0] if 'artist' in metadata else 'unknown'
		lastfm.nowplaying(title, artist)
	except Exception:
		logging.warning("Failed to set lastfm now playing", exc_info=True)


def clamp(lower, value, upper):
	return min(upper, max(lower, value))


def play(playlist, ptype=Playlist, stdin=None, stdout=None, lastfm=None, file_regex=None, control_sock=None, force_ext=None):
	"""Takes a Playlist and plays forever.
	Controls (in addition to mplayer standard controls):
		q: Skip and demote.
		f: Promote.
		d: Demote without skipping
		Q: Quit.
		r: Toggle rainymood
	All promotions and demotions double/halve the weighting.
	ptype is the Playlist subtype to use if paylist is string.
	ptype may be string, in which case it should be "module:name" to import
	Will only play files matching file_regex.
	force_ext will make it act as though all files had that extension
	"""

	if not stdin:
		stdin = sys.stdin
	if not stdout:
		stdout = sys.stdout

	input_queue = gevent.queue.Queue()

	# We can't guarentee stdin is gevent-safe, and using a FileObject
	# wrapper leaves it in non-blocking mode after exit.
	def read_stdin():
		while True:
			r, w, x = select([stdin], [], [])
			if stdin in r:
				c = stdin.read(1)
				input_queue.put(c)

	def control_sock_accept():
		while True:
			client, addr = control_sock.accept()
			gevent.spawn(read_control_sock, client)

	def read_control_sock(client):
		c = client.recv(1)
		while c:
			input_queue.put(c)
			c = client.recv(1)
		client.close()

	def get_input(timeout=None):
		return input_queue.get(timeout=timeout)

	gevent.spawn(read_stdin)
	if control_sock:
		gevent.spawn(control_sock_accept)

	if isinstance(playlist, str):
		playlist = ptype(playlist)
	else:
		ptype = type(playlist)

	VOL_MAX = int(os.environ.get('VOL_MAX',2)) # Sets what interface reports as "100%"
	VOL_FUDGE = float(os.environ.get('VOL_FUDGE',1)) # Volume fudge factor to modify volume globally.
	                                               # DISABLES PERSISTENT VOLUME CHANGES WHEN NOT DEFAULT

	new_volume = [None] # one-element list to force non-local variable
	rainymood = None

	while True:

		filename, volume = playlist.next(file_regex=file_regex)
		original_weight, _ = playlist.entries[filename]

		if lastfm:
			gevent.spawn(set_lastfm, lastfm, filename)

		proc = None
		new_volume = volume
		weight_change = 1
		try:
			real_filename = filename if force_ext is None else filename.rsplit('.', 1)[0] + '.' + force_ext
			stdout.write(CLEAR + '\n{weight}x @{volume}\n{name}\n\n'.format(name=filename, volume=volume, weight=original_weight))
			proc = Popen(['mplayer', '-vo', 'none', '-softvol', '-softvol-max', str(VOL_MAX * 100.),
						'-volume', str(VOL_FUDGE * volume * 100. / VOL_MAX), real_filename],
						 stdin=PIPE, stderr=open('/dev/null','w'))

			with RaiseOnExit(proc), \
			     TermAttrs.modify(exclude=(0,0,0,ECHO|ECHONL|ICANON)):
				while True:
					c = get_input()
					if c == 'q':
						weight_change *= 0.5
						proc.stdin.write("q")
					elif c == 'f':
						weight_change *= 2
					elif c == 'd':
						weight_change *= 0.5
					elif c == 'Q':
						proc.stdin.write("q")
						proc.stdin.flush()
						return
					elif c in '*/':
						change = 0.03 * VOL_MAX
						if c == '/':
							change = -change
						new_volume = clamp(0, volume + change, 1)
						# also write volume change so it takes effect immediately.
						# note player can exceed 1 volume but we do not.
						proc.stdin.write(c)
					elif c == 'r':
						if rainymood:
							rainymood.kill(block=False)
							rainymood = None
						else:
							rainymood = spawn_rainymood()
					elif c == '\x1b':
						# we need to deliver entire escapes at once, or else
						# mplayer does unexpected things (like quitting)
						# so we read the entire available input before acting
						while True:
							try:
								c += get_input(timeout=0.1)
							except gevent.queue.Empty:
								break
						proc.stdin.write(c)
					else:
						proc.stdin.write(c)
					proc.stdin.flush()

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

		# Don't update volume on VOL_FUDGE
		if VOL_FUDGE != 1:
			new_volume = volume

		# update playlist: read, update, write to minimize window where races may occur
		playlist = ptype(playlist.filepath)
		if weight_change != 1 or new_volume != volume:
			playlist.update(filename, weight=lambda x: x * weight_change, volume=new_volume)
			playlist.writefile()


def log_config(level, filepath, filelevel='DEBUG'):
	format = logging.Formatter('%(asctime)s:%(process)d:%(levelname)s:%(name)s:%(message)s')
	logger = logging.getLogger()
	logger.setLevel('DEBUG')
	stderr = logging.StreamHandler()
	stderr.setLevel(level)
	stderr.setFormatter(format)
	file = logging.FileHandler(filepath)
	file.setLevel(filelevel)
	file.setFormatter(format)
	logger.addHandler(stderr)
	logger.addHandler(file)


def main(playlist, ptype='', lastfm_creds=None, loglevel='WARNING', logfile='/tmp/awp', logfilelevel='DEBUG', file_regex=None, control_path=None, force_ext=None):
	log_config(loglevel, logfile, logfilelevel)
	kwargs = {}
	if ptype:
		module, name = ptype.split(':')
		module = import_module(module)
		kwargs['ptype'] = getattr(module, name)
	if lastfm_creds:
		creds = json.loads(open(lastfm_creds).read())
		lastfm = LastFM(**creds)
		kwargs['lastfm'] = lastfm
	if control_path:
		# Delete existing if it exists
		try:
			os.remove(control_path)
		except EnvironmentError as e:
			if e.errno != errno.ENOENT:
				raise
		control_sock = socket.socket(socket.AF_UNIX)
		control_sock.bind(control_path)
		control_sock.listen(128)
		kwargs['control_sock'] = control_sock
	play(playlist, file_regex=file_regex, force_ext=force_ext, **kwargs)


if __name__ == '__main__':
	import argh
	argh.dispatch_command(main)
