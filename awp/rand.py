import random

def weighted_choice(d):
	"""Choose a random key from d, with each choice weighted by the value of d, which may be int or float."""

	total = sum(d.values())
	x = random.random() * total
	for k in d:
		x -= d[k]
		if x <= 0:
			return k
