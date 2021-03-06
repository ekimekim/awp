from rand import weighted_choice
from collections import OrderedDict
import os

class Playlist(object):
	"""Playlist files are newline-seperated records of one song per line.
	Each line may have one of two formats:
		WEIGHT \t PATH \n
		WEIGHT \t VOLUME \t PATH \n

	The first version is for compatibility and ease of playlist creation.
	It is replaced by the second form by loading then saving a playlist.

	WEIGHT is any float, and is a weighting used in the random selection of a song.

	VOLUME is a float that should be between 0 and 2, default 0.5.
	It indicates the volume level that the song should be played at.
	Values > 1 use software amplification, which may result in clipping.
	It is for this reason the default volume is half of normal.

	PATH may be any string without newlines, but should be an absolute filepath to an audio file.
	"""

	filepath = None
	dirty = False # flag indicating pending changes not copied to disk. False for new, empty playlist.

	def __init__(self, filepath=None):
		"""Open a playlist file. Omit filepath to create an empty playlist."""
		self.entries = OrderedDict() # { path : (weight, volume) } - ordered so reading a file preserves order
		if filepath:
			self.readfile(filepath)

	def readfile(self, filepath):
		"""Append file to playlist."""
		self.filepath = filepath
		with open(filepath, 'r') as f:
			for line in f:
				line = line[:-1] # Strip newline
				if not line: continue # Blank lines
				if line.lstrip().startswith('#'): continue # Comments
				parts = line.split('\t', 2)
				if len(parts) == 2:
					weight, path = parts
					volume = 1
				elif len(parts) == 3:
					weight, volume, path = parts
				else:
					raise ValueError("Bad line: %s" % line)
				weight = float(weight)
				volume = float(volume)
				self.add_item(path, weight, volume)

	def writefile(self, filepath=None, atomic=True):
		"""Write playlist to file. If atomic, writes to a temp file then does an atomic move operation.
		If no filepath given, defaults to the one most recently read from, or else ValueError.
		"""
		if not filepath: filepath = self.filepath
		if not filepath: raise ValueError("Cannot determine filepath")
		if atomic:
			true_path = filepath
			dirname, basename = os.path.split(filepath)
			filepath = os.path.join(dirname, ".{}~".format(basename))
		with open(filepath, 'w') as f:
			self.write(f)
		if atomic:
			os.rename(filepath, true_path)
		self.dirty = False

	def write(self, f):
		for path, (weight, volume) in self.entries.items():
			f.write('{}\t{}\t{}\n'.format(weight, volume, path))

	def add_item(self, path, weight, volume, warn=True):
		"""If warn=True, prints a warning to stdout on duplicate entry."""
		self.dirty = True
		if warn and path in self.entries:
			print "Warning: Overwriting existing entry %s" % self.format_entry(path)
		self.entries[path] = (weight, volume)

	def update(self, path, weight=None, volume=None):
		"""Update a path's weight or volume or both.
		Either field accepts a new value, None to keep old value, or a callable that maps old -> new value.
		eg. update('example.mp3', lambda x: x*2) would double the weight of 'example.mp3'.
		"""
		old_weight, old_volume = self.entries[path]
		if weight is None: weight = lambda x: x
		if callable(weight): weight = weight(old_weight)
		if volume is None: volume = lambda x: x
		if callable(volume): volume = volume(old_volume)
		self.add_item(path, weight, volume, warn=False)

	def __iter__(self):
		return self

	def next(self):
		"""Get next thing to play. Returns (path, volume)"""
		weights = { (path, volume) : weight for path, (weight, volume) in self.entries.items() }
		return weighted_choice(weights)

	def copy(self):
		result = Playlist()
		result.entries = self.entries.copy()
		return result

	def format_entry(self, path, weight=None, volume=None):
		"""Return the canonical string form of an entry."""
		actual_weight, actual_volume = self.entries[path]
		if weight is None: weight = actual_weight
		if volume is None: volume = actual_volume
		return "{weight}x {path!r} @{volume}".format(path=path, weight=weight, volume=volume)

	def __str__(self):
		return "<Playlist{} ({} entries)>".format(" {!r}".format(self.filepath) if self.filepath else '', len(self.entries))

	def verify(self):
		"""Return a list of all entries whose files cannot be accessed."""
		return [path for path in self.entries if not os.access(path, os.R_OK)]

	def diff(self, other):
		"""Compares this playlist with another and returns a structure describing the differences.
		Return value is an ordered dict mapping paths to tuples of
			((this_weight, this_volume), (other_weight, other_volume))
		with either of the inner tuples being None if the path is not present in that playlist.
		Order is as per this playlist, with paths not in this playlist inserted in order
		at the end.
		"""
		paths = self.entries.copy()
		paths.update(other.entries)
		paths = paths.keys()
		ret = OrderedDict()
		for path in paths:
			ours, theirs = (playlist.entries.get(path, None) for playlist in (self, other))
			if ours != theirs:
				ret[path] = ours, theirs
		return ret

	def merge(self, other, strategy=None):
		"""Update this playlist by merging in another playlist as according to
		the given strategy.

		other may be a filename or a Playlist.

		strategy may be any of the strategies defined in MergeStrategies, or
		a function that takes (path, this_value, other_value) as args, and should
		return the new value to take.
		Either value may be None if the other playlist doesn't have that entry.
		The function may return None to omit the entry.

		Alternately, strategy may be a 2-tuple of such strategies/functions, where
		the first element applies to merging weights and the second to volumes.
		The default value is to use MergeStrategies.average for weight and
		MergeStrategies.extreme(average of current volumes) for volume.

		Note this operation doesn't write immediately, but will set the dirty flag
		if any changes occur.
		"""

		if strategy is None:
			vol_average = sum(vol for weight, vol in self.entries.values()) / len(self.entries)
			strategy = MergeStrategies.average, MergeStrategies.extreme(vol_average)

		if callable(strategy):
			# use the same for both
			strategies = strategy, strategy
		else:
			strategies = strategy

		if not isinstance(other, Playlist):
			other = Playlist(other)

		for path, (ours, theirs) in self.diff(other).items():
			ours, theirs = (x or (None, None) for x in (ours, theirs))
			merged = tuple(strategy(path, wgt, vol) for strategy, wgt, vol in zip(strategies, ours, theirs))
			assert len(merged) == 2, "Something went wrong with the zip"
			if None in merged:
				self.entries.pop(path, None) # remove if present
			else:
				self.add_item(path, *merged, warn=False)

	def _common_divisor_weight(self):
		"""Attempt to guess the greatest common divisor of our weights.
		Will give up and ValueError in some cases. May not give the greatest common divisor,
		but will always give *some* common divisor.
		Note: Ignores entries with 0 weight"""
		BRUTE_LIMIT = 1000

		weights = set(weight for weight, vol in self.entries.values()) - {0}
		def is_divisor(n):
			return all(x % n == 0 for x in weights)
		# we take a VERY naive and VERY inefficient route to guessing a GCD of the set of weights:
		# if the min weight works, use it
		min_weight = min(weights)
		if is_divisor(min_weight):
			return min_weight
		# if all weights are integers and min_weight is reasonably small, just brute force it
		if all(int(x) == x for x in weights) and min_weight < BRUTE_LIMIT:
			for n in xrange(min_weight - 1, 0, -1):
				if is_divisor(n):
					return n
				assert False, "1 was not divisor of all-integer weights"
		# eh, that'll do.
		raise ValueError("Could not determine a common divisor of {} unique weights".format(len(weights)))

	def to_repeated_list(self, scale=None):
		"""Return the playlist in a "repeated list" form - a list of filepaths, using repetition to
		represent the weights, such that random.choice(self.to_repeated_list()) should give correctly
		weighted results. Discards volume info.
		For example, a list like:
			1 foo
			2 bar
			5 baz
		will return ["foo", "bar", "bar", "baz", "baz", "baz", "baz", "baz"].
		By default, will attempt to scale the weights to make the result list as small as possible.
		For example, if the weights were foo=2, bar=4, then the result should be ["foo", "bar", "bar"],
		not ["foo", "foo", "bar", "bar", "bar", "bar"].
		This may not always be successful if weights < 1 are present, and will result in ValueError.
		If scale is given, it explicitly chooses a value to divide by when translating from weights
		to number of instances in the result list. eg. In the above example, you could get the same result
		by passing scale=2. If explicitly given, scale will truncate weights. eg. if you gave scale=2 to the
		first example with foo, bar and baz, the result would be ["bar", "baz", "baz"] (foo was rounded to 0)
		"""
		if not scale:
			scale = self._common_divisor_weight()
		result = []
		for path, (weight, vol) in self.entries.items():
			result += [path] * int(weight / scale)
		return result

	__repr__ = __str__



class MergeStrategies(object):
	def __new__(*args): raise NotImplementedError("This class should not be instantiated")

	@staticmethod
	def average(path, *values):
		"""Takes the average of the two numbers. If one is not present, just uses the other."""
		values = [x for x in values if x is not None]
		return sum(values) / len(values)

	@staticmethod
	def extreme(midpoint):
		"""This is a factory that returns a usable strategy function.
		It takes the 'more extreme' of the two numbers, defined as whichever
		is further from the given midpoint (ties favour the greater value).
		If either value is None, the other is returned.
		A good midpoint to use might be the average of the current value, or the median.
		"""
		def _extreme(path, *values):
			values = [x for x in values if x is not None]
			return sorted(values, key=lambda value: (abs(value-midpoint), value), reverse=True)[0]
		return _extreme

	@staticmethod
	def update(path, old, new):
		"""Always use the new value, unless it doesn't exist (in which case use the old value)"""
		if new is None: return old
		return new

	@staticmethod
	def existsonly(strategy):
		"""Factory function. Wraps another strategy, making it return None unless the path is already present
		in the current playlist. If given a tuple, will wrap both strategies."""
		def _existsonly_factory(single_strat):
			def _existsonly(path, old, new):
				if old is None: return None
				return strategy(path, old, new)
			return _existsonly
		if callable(strategy):
			return _existsonly_factory(strategy)
		else:
			return [_existsonly_factory(strat_func) for strat_func in strategy]


AUDIO_EXTENSIONS = ['flac', 'aac', 'm4a', 'wav', 'ogg', 'mp3', 'wma']
def from_directory(root, weight=16, volume=0.5, extensions=AUDIO_EXTENSIONS, use_magic=True,
                   recurse=True, relative=False, detect_duplicates=True, followlinks=False,
                   onerror=None):
	"""Constructs a playlist by scanning a directory and all sub-directories.
	All found files will be added to the playlist with the given weight and volume.
	Other options:
		extensions: If not None, assume any files with an extension in the given iterable is
		            an audio file.
		use_magic: If available, try to use the python-magic library to detect audio files
		recurse: Set False to not scan sub-directories.
		relative: If True and path is relative, create a playlist of relative paths.
		          Otherwise, absolute paths are used.
		detect_duplicates: Consider files of the form 'x', 'x.ext1' and 'x.ext2' to be the same item.
		                   The extension given earliest in extensions (if any) takes precedence.
		                   Otherwise the first one found is used.
		followlinks: As per os.walk
		onerror: As per os.walk
	"""

	magic = None
	if use_magic:
		try:
			import magic
			magic = magic.Magic(mime=True)
		except ImportError:
			use_magic = False

	if not relative:
		root = os.path.abspath(root)

	playlist = Playlist()
	duplicate_check = {}

	for path, subdirs, files in os.walk(root, followlinks=followlinks, onerror=onerror):
		if not recurse:
			# empty list in-place
			while subdirs: subdirs.pop()

		for file in files:
			filepath = os.path.join(path, file)
			name, ext = os.path.splitext(filepath)
			ext = ext.lower().lstrip('.')

			if (not extensions or ext not in extensions):
				if not use_magic:
					continue
				mime = magic.from_file(filepath)
				if not mime or not mime.startswith('audio/'):
					continue

			if detect_duplicates:
				if name in duplicate_check:
					other = duplicate_check[name]
					if extensions and ext in extensions:
						junk, other_ext = os.path.splitext(other)
						other_ext = other_ext.lower().lstrip('.')
						if other_ext in extensions and extensions.index(other_ext) <= extensions.index(ext):
							continue
						playlist.entries.pop(other)
					else:
						continue

				duplicate_check[name] = filepath

			playlist.add_item(filepath, weight=weight, volume=volume)

	return playlist
