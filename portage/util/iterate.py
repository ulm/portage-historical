# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/util/iterate.py,v 1.1 2005/08/16 00:33:27 ferringb Exp $

from itertools import islice

def enumerate(iter, start, end):
	count = start
	for r in islice(iter, start, end):
		yield count, r
		count+=1
