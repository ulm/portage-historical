# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/config/domain.py,v 1.3 2005/07/20 14:33:12 ferringb Exp $

# ow ow ow ow ow ow....
# this manages a *lot* of crap.  so... this is fun.
# ~harring
class domain:
	def __init__(self, use, distdir, features):
		self.__master = config

	def load_all_repositories(self):
		
