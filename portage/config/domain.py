# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/config/domain.py,v 1.2 2005/07/13 05:51:35 ferringb Exp $


class domain:
	def __init__(self, config):
		self.__master = config

	def load_all_repositories(self):
		
