# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/preplib.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

preplib() {
	if [ -z "$1" ] ; then
		z="${D}usr/lib"
	else
		z="${D}$1/lib"
	fi

	if [ -d "${z}" ] ; then
		ldconfig -n -N "${z}" || die
	fi
}
