
"""A script for listing files in a directory or subdirs that are NOT in given playlist.
Usage:
	python -m awp.missing PLAYLIST DIRECTORY
Also takes optional --options as follows:
	--nomagic: Do not use libmagic to identify audio files
	--extensions: Space-seperated list of file extensions to recognise
	--norecurse: Do not search subdirs
	--verbose
"""

from scriptlib import with_argv
import awp.playlist

@with_argv
def main(filename, searchpath, nomagic=False, extensions=None, norecurse=False, verbose=False):
	if extensions: extensions = extensions.split()
	playlist = awp.playlist.Playlist(filename)
	kwargs = {'extensions': extensions} if extensions is not None else {}
	found_list = awp.playlist.from_directory(searchpath, use_magic=(not nomagic), recurse=(not norecurse), **kwargs)
	diff = playlist.diff(found_list)
	if verbose:
		print "{} contains {} entries".format(filename, len(playlist.entries))
		print "{}/ contains {} entries".format(searchpath.rstrip('/'), len(found_list.entries))
	for path, (us, them) in diff.items():
		if us is None:
			print path
		if verbose and them is None:
			print "WARNING: {} not in found list".format(path)

if __name__=='__main__':
	main()
