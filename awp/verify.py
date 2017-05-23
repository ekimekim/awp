
import sys

import argh

from awp.playlist import Playlist


def main(playlist):
	playlist = Playlist(playlist)
	bad = playlist.verify()
	if bad:
		print '\n'.join(bad)
		sys.exit(1)


if __name__ == '__main__':
	argh.dispatch_command(main)
