# Copyright: 2004-2005 Gentoo Foundation
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/chksum/sha1hash.py,v 1.1 2005/07/10 09:21:05 ferringb Exp $

import sha

def sha1hash(filename, chksum):
	f = open(filename, 'rb')
	blocksize=32768
	data = f.read(blocksize)
	size = 0L
	sum = sha.new()
	while data:
		sum.update(data)
		size = size + len(data)
		data = f.read(blocksize)
	f.close()

	return sum.hexdigest() == chksum

chksum_types = (("sha1", sha1hash),)
