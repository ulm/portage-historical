# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/dohard.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

dohard() {
	if [ ${#} -ne 2 ] ; then
		die "dohard: two arguments needed"
	fi

	mysrc="${1}"
	mydest="${2}"
	ln -f "${D}${mysrc}" "${D}${mydest}" || die
}
