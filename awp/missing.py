
"""A script for listing files in a directory or subdirs that are NOT in given playlist.
Usage:
	python -m awp.missing PLAYLIST DIRECTORY
Also takes optional --options as follows:
	--nomagic: Do not use libmagic to identify audio files
	--extensions: Space-seperated list of file extensions to recognise
	--norecurse: Do not search subdirs
"""

from scriptlib import with_argv
import awp.playlist

@with_argv
def main(filename, searchpath, nomagic=False, extensions=None, norecurse=False):
	if extensions: extensions = extensions.split()
	playlist = awp.playlist.Playlist(filename)
	found_list = awp.playlist.from_directory(searchpath, extensions=extensions, use_magic=(not nomagic), recurse=(not norecurse))
	diff = playlist.diff(found_list)
	for path, (us, them) in diff.items():
		if us is None:
			print path

if __name__=='__main__':
	main()
