# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/config/cparser.py,v 1.1 2005/08/09 07:47:34 ferringb Exp $

from ConfigParser import ConfigParser

class CaseSensitiveConfigParser(ConfigParser):
	def optionxform(self, val):
		return val
