# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/util/strings.py,v 1.2 2005/08/09 07:43:43 ferringb Exp $

def iter_tokens(s, splitter=(" ")):
	"""iterable yielding of splitting of a string"""
	pos = 0
	strlen = len(s)
	while pos < strlen:
		while s[pos] in splitter:
			pos+=1
		next_pos = pos + 1
		try:
			while s[next_pos] not in splitter:
				next_pos+=1
		except IndexError:
			next_pos = strlen
		yield s[pos:next_pos]
		pos = next_pos + 1

