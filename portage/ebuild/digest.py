# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/ebuild/digest.py,v 1.1 2005/08/09 08:04:56 ferringb Exp $

from portage.fetch import ChecksumUnavailable
def parse_digest(path):
	d = {}
	try:
		f = open(path)
		for line in f:
			l = line.split()
			if len(l) != 4:
				raise ChecksumUnavailable("failed parsing " + path, l.strip())
			#MD5 c08f3a71a51fff523d2cfa00f14fa939 diffball-0.6.2.tar.bz2 305567
			d[l[2]] = {l[0].lower():l[1], "size":l[3]}
		f.close()
	except (OSError, IOError), e:
			raise ChecksumUnavailable("failed parsing " + path, e)
	return d
