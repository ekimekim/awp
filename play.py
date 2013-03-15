from mplayer.gevent1 import GeventPlayer
from subprocess import PIPE
import gevent
from gevent.fileobject import FileObject
import sys
from readesc import readesc
import escapes


class WeightedPlayer(object):
	POLL_INTERVAL = 0.1

	def __init__(self, playlist):
		self.playlist = playlist
		self.player = GeventPlayer(('-vo=none',), stderr=PIPE)
		self.playing = None # Caches self.player.path to avoid races

	def play_one(self):
		"""Get a file from playlist and play it. Return when finished playing."""
		filename = self.playlist.next()
		try:
			self.player.loadfile(filename)
			if p.path != filename:
				raise Exception("File {} could not be loaded", filename)
			while p.path is not None:
				# There's no good way to wait on this except to poll, so we'll poll
				gevent.sleep(self.POLL_INTERVAL)
		finally:
			if not self.player.paused: self.player.pause()

	def interact(self, stdin=None, stdout=None):
		"""Interact with a command line menu-based interface, showing current song.
		Loops until user exits.
		"""
		# We delay getting sys.{stdin,stdout} until now in order to respect monkey patching.
		stdin = FileObject(stdin or sys.stdin)
		stdout = stdout or sys.stdout

		def user_exit():
			raise KeyboardInterrupt

		def writemenu():
			stdout.write(escapes.CLEAR + '\n')
			for key, (text, fn) in MENU.items():
				stdout.write("{}: {}\n").format(key, text)
			stdout.write(SAVE_CURSOR)

		def writeinfo():
				if not self.playing: return
				stdout.write(LOAD_CURSOR + CLEAR_TO_END)
				stdout.write("\n{}\n".format(self.playlist.format_entry(self.playing)))
				# TODO detailed output here

		# Menu is { key : (description, callback) }
		MENU = {
			'UP' : ("Upvote (2x) current song", lambda: (self.playlist.update(self.playing, lambda x: x*2.),
			                                             writeinfo() )),
			'DOWN' : ("Downvote (.5x) current song", lambda: (self.playlist.update(self.playing, lambda x: x/2.),
			                                                  writeinfo() )),
			'ESC' : ("Quit", user_exit),
		}

		try:
			self.playing = self.player.path
			writemenu()
			writeinfo()
			for c in readesc(stdin):
				if c not in MENU: continue
				text, fn = MENU[c]
				fn()
				old_playing = self.playing
				self.playing = self.player.path or self.playing # Keep reporting previous song until a new one is loaded
				if self.playing != old_playing: writeinfo()
		except KeyboardInterrupt:
			pass
