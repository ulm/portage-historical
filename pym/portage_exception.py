# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/portage_exception.py,v 1.2 2004/08/03 21:34:00 carpaski Exp $

class CorruptionError(Exception):
	"""Corruption indication"""
	def __init__(self,value):
		self.value = value[:]
	def __str__(self):
		return repr(self.value)

class InvalidDependString(Exception):
	"""An invalid depend string has been encountered"""
	def __init__(self,value):
		self.value = value[:]
	def __str__(self):
		return repr(self.value)

