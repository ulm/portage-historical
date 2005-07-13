# syncexceptions.py: base sync exception class. not used currently (should be though)
# Copyright 2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
#$Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/sync/syncexceptions.py,v 1.2 2005/07/13 05:51:35 ferringb Exp $

class SyncException(Exception):
	"""base sync exception"""
	def __init__(self,value):
		self.value=value
	def __str__(self):
		return value
