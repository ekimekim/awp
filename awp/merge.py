
"""Command line tool to merge playlists with extreme strategy centred on 16 and 0.5
Prints new list to stdout.
"""

import sys
from playlist import Playlist, MergeStrategies

def merge(*playlists):
	playlists = map(Playlist, playlists)
	if not playlists: return
	result = playlists.pop(0).copy()
	strategy = MergeStrategies.extreme(16), MergeStrategies.extreme(0.5)
	for playlist in playlists:
		result.merge(playlist, strategy)
	result.write(sys.stdout)

if __name__ == '__main__':
	merge(*sys.argv[1:])
