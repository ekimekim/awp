
"""Print stats about a playlist file"""

import errno
from collections import Counter

from scriptlib import with_argv
from playlist import Playlist

@with_argv
def main(playlist):
	playlist = Playlist(playlist)
	print "Total songs: {}".format(len(playlist.entries))
	print "Count by weight:"
	by_weight = Counter(weight for weight, volume in playlist.entries.values())
	total = sum(weight for weight, volume in playlist.entries.values())
	for weight, count in sorted(by_weight.items()):
		print "{}x : {} songs\t({:5.2f}% total chance)".format(weight, count, 100 * weight * count / total)


if __name__=='__main__':
	main()
