# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/newdoc.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

newdoc() {
	if [ -z "${T}" ] || [ -z "${2}" ] ; then
		die "newdoc: Nothing defined to do."
	fi

	rm -rf "${T}/${2}" || die
	cp "${1}" "${T}/${2}" || die
	dodoc "${T}/${2}" || die
}