
"""Tool to print a list of files, generated randomly from a playlist."""

import errno

from scriptlib import with_argv
from playlist import Playlist

@with_argv
def main(playlist):
	"""TODO: Add unique option, add limit option"""
	playlist = Playlist(playlist)
	for path, volume in playlist:
		try:
			print path
		except (OSError, IOError) as e:
			if e.errno == errno.EPIPE:
				return
			raise


if __name__=='__main__':
	main()
