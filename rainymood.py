import os

from gevent.subprocess import Popen, PIPE
import gevent

def spawn_rainymood():
	"""Returns a greenlet. Kill the greenlet to stop the rainymood instance."""
	@gevent.spawn
	def rainymood():
		proc = None
		with open(os.devnull, 'r+') as null:
			try:
				proc = Popen(['rainymood'], stdin=PIPE, stdout=null)
				proc.wait() # intentional deadlock (proc won't terminate unless it errors)
				            # we wait for outside code to kill the greenlet
			except BaseException:
				if proc: proc.terminate()
	return rainymood
