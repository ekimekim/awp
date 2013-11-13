import signal
from gevent import sleep


def starve_test():
	"""Keep a SIGALRM perpetually pending...as long as we get rescheduled in a timely manner."""
	def boom(sig, frame):
		raise Exception("Greenlets being starved")
	signal.signal(signal.SIGALRM, boom)
	while 1:
		signal.alarm(2)
		sleep(0.1)


greenlet = None
def track_switches(callback):
	"""Sets a profile function to watch for changes in current greenlet.
	Calls callback with new greenlet as arg."""
	import gevent, sys
	def prof(frame, event, arg):
		global greenlet
		newgreenlet = gevent.getcurrent()
		if greenlet != newgreenlet:
			greenlet = newgreenlet
			callback(greenlet)
	sys.setprofile(prof)
