# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/config/profiles.py,v 1.2 2005/08/09 07:47:34 ferringb Exp $

class base(object):
	pass

class ProfileException(Exception):
	def __init__(self, err):	self.err = err
	def __str__(self): return str(self.err)
