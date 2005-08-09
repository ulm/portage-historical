# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/util/inheritance.py,v 1.2 2005/08/09 07:43:43 ferringb Exp $

def check_for_base(obj, allowed):
	"""Look through __class__ to see if any of the allowed classes are found, returning the first allowed found"""
	for x in allowed:
		if issubclass(obj.__class__, x):
			return x
	return None
