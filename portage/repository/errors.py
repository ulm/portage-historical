# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/repository/errors.py,v 1.1 2005/07/10 09:21:05 ferringb Exp $

class TreeCorruption(Exception):
	def __init__(self, err):
		self.err = err
	def __str__(self):
		return "unexpected tree corruption: %s" % str(self.err)

class InitializationError(TreeCorruption):
	def __str__(self):
		return "initialization failed: %s" % str(self.err)
