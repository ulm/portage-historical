# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/dolib.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

dolib() {
	if [ ${#} -lt 1 ] ; then
		die "dolib: at least one argument needed"
	fi
	if [ ! -d "${D}${DESTTREE}/lib" ] ; then
		install -d "${D}${DESTTREE}/lib" || die
	fi

	for x in "$@" ; do
		if [ -e "${x}" ] ; then
			install ${LIBOPTIONS} "${x}" "${D}${DESTTREE}/lib" || die
		else
			die "dolib: ${x} does not exist"
		fi
	done
}
