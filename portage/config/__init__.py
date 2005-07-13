# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/config/__init__.py,v 1.2 2005/07/13 05:51:35 ferringb Exp $

import ConfigParser
import central, os
from portage.const import DEFAULT_CONF_FILE

def load_config(file=DEFAULT_CONF_FILE):
	c = ConfigParser.ConfigParser()
	if os.path.isfile(file):
		c.read(file)
		c = central.config(c)
	else:
		# make.conf...
		raise Exception("sorry, default '%s' doesn't exist, and I don't like make.conf currently (I'm working out my issues however)" %
			file)
	return c
