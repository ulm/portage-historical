# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/portage_exception.py,v 1.1 2004/05/17 04:21:21 carpaski Exp $

class CorruptionError(Exception):
	"""Corruption indication"""
	def __init__(self,value):
		self.value = value[:]
	def __str__(self):
		return repr(self.value)

