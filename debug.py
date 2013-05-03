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
