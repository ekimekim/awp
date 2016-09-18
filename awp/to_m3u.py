
"""Tool to write out a playlist in m3u format using repetition for weight"""

import os

from argh import dispatch_command, arg

from playlist import Playlist


@arg('--scale', type=int, help='scale to pass through to Playlist.to_repeated_list')
def main(playlist, src, dest, scale=None):
	"""Writes the playlist in m3u format to stdout, using repetition for weight.
	src and dest args are for path rewriting - any paths under src will be rewritten
	to be under dest instead."""
	playlist = Playlist(playlist)
	flattened = playlist.to_repeated_list(scale)
	src = '{}/'.format(src.rstrip('/'))
	for path in flattened:
		if path.startswith(src):
			path = os.path.join(dest, os.path.relpath(path, src))
		print 'file://{}'.format(path)


if __name__=='__main__':
	dispatch_command(main)
