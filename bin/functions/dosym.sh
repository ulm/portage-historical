# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/dosym.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

dosym() {
	if [ ${#} -ne 2 ] ; then
		die "dosym: two arguments needed"
	fi

	target="${1}"
	linkname="${2}"
	ln -snf "${target}" "${D}${linkname}" || die
}
