from rand import weighted_choice
from collections import OrderedDict
import os

class Playlist(object):
	filepath = None

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
			filepath = ".{}~".format(filepath)
		with open(filepath, 'w') as f:
			for path, (weight, volume) in self.entries.items():
				f.write('{}\t{}\t{}\n'.format(weight, volume, path))
		if atomic:
			os.rename(filepath, true_path)

	def add_item(self, path, weight, volume, warn=True):
		"""If warn=True, prints a warning to stdout on duplicate entry."""
		if warn and path in self.entries:
			print "Warning: Overwriting existing entry %s" % self.format_entry(path)
		self.entries[path] = (weight, volume)

	def update(self, path, weight=None, volume=None):
		"""Update a path's weight or volume or both."""
		old_weight, old_volume = self.entries[path]
		if weight is None: weight = old_weight
		if volume is None: volume = old_volume
		self.add_item(path, weight, volume, warn=False)

	def __iter__(self):
		return self

	def next(self):
		"""Get next thing to play. Returns (path, volume)"""
		weights = { (path, volume) : weight for path, (weight, volume) in self.entries.items() }
		return weighted_choice(weights)

	def format_entry(self, path, weight=None, volume=None):
		"""Return the canonical string form of an entry."""
		actual_weight, actual_volume = self.entries[path]
		if weight is None: weight = actual_weight
		if volume is None: volume = actual_volume
		return "{weight}x {path!r} @{volume}".format(path=path, weight=weight, volume=volume)

	def __str__(self):
		return "<Playlist{} ({} entries)>".format(" {!r}".format(self.filepath) if self.filepath else '', len(self.entries))
	__repr__ = __str__
