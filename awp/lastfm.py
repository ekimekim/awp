
import functools
import md5
import time
import logging

import requests


def ratelimited(cooldown):
	"""Decorator preventing wrapped fn from being called less than cooldown seconds
	after the previous call. Returns None if the function isn't run."""
	def _ratelimited(fn):
		last_called = [None] # inside a list to allow assignment (py2 has no nonlocal keyword)
		@functools.wraps(fn)
		def _wrapper(*a, **k):
			if last_called[0] is None or time.time() - last_called[0] > cooldown:
				last_called[0] = time.time()
				return fn(*a, **k)
		return _wrapper
	return _ratelimited


class LastFM(object):
	URL = 'http://ws.audioscrobbler.com/2.0/'
	COOLDOWN = 30

	def __init__(self, user, session_key, api_key, api_secret):
		self.user = user
		self.session_key = session_key
		self.api_key = api_key
		self.api_secret = api_secret

	@ratelimited(COOLDOWN)
	def call(self, method, post=False, **args):
		args['method'] = method
		args['sk'] = self.session_key
		args['api_key'] = self.api_key
		sig = self.sign(args)
		args['format'] = 'json'
		args['api_sig'] = sig
		if post:
			resp = requests.post(self.URL, data=args)
		else:
			resp = requests.get(self.URL, params=args)
		try:
			resp.raise_for_status()
		except requests.HTTPError:
			logging.warning("Failed api call {} with {}: {}".format(args, resp.status_code, resp.content))
			raise
		return resp.json()

	def sign(self, args):
		s = ''.join('{}{}'.format(k, v) for k, v in sorted(args.items()))
		s += self.api_secret
		logging.debug("String to hash: {!r}".format(s))
		return md5.new(s).hexdigest()

	def nowplaying(self, track, artist):
		self.call('track.updateNowPlaying', post=True, artist=artist, track=track)
		logging.info("Successfully set {} - {} as playing".format(track, artist))


def getmetadata(filepath):
	import mutagen
	return mutagen.File(filepath)
