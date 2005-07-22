# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/config/__init__.py,v 1.3 2005/07/20 14:33:12 ferringb Exp $

from ConfigParser import ConfigParser
import central, os
from portage.const import DEFAULT_CONF_FILE

def load_config(file=DEFAULT_CONF_FILE):
	c = CaseSensitiveConfigParser()
	if os.path.isfile(file):
		c.read(file)
		c = central.config(c)
	else:
		# make.conf...
		raise Exception("sorry, default '%s' doesn't exist, and I don't like make.conf currently (I'm working out my issues however)" %
			file)
	return c

class CaseSensitiveConfigParser(ConfigParser):
	def optionxform(self, val):
		return val