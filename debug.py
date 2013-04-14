import signal
from gevent import sleep, greenlet
from greenlet_tb import print_greenlets, extract_frames
import traceback

def starve_test(report=None):
	"""Keep a SIGALRM perpetually pending...as long as we get rescheduled in a timely manner."""
	def boom(sig, frame):
		if report:
			print_greenlets(report)
			report.write('CURRENT:\n')
			report.write(''.join(traceback.format_list(extract_frames(frame))) + '\n')
		raise Exception("Greenlets being starved")
	signal.signal(signal.SIGALRM, boom)
	while 1:
		signal.alarm(2)
		sleep(0.1)

