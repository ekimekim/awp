from setuptools import setup

setup(
	name='awp',
	description='Auto-weighted playlist player',
	packages=['awp'],
	install_requires=[
		'escapes',
		'scriptlib',
		'termhelpers',
	],
)
