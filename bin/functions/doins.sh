# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/doins.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

doins() {
	if [ $# -lt 1 ] ; then
		die "doins: at least one argument needed"
	fi
	if [ ! -d "${D}${INSDESTTREE}" ] ; then
		install -d "${D}${INSDESTTREE}" || die
	fi

	for x in "$@" ; do
		if [ -L "$x" ] ; then
			cp "$x" "${T}" || die
			mysrc="${T}"/`/usr/bin/basename "${x}"`
		elif [ -d "$x" ] ; then
			echo "doins: warning, skipping directory ${x}"
			continue
		else
			mysrc="${x}"
		fi
		install ${INSOPTIONS} "${mysrc}" "${D}${INSDESTTREE}" || die
	done
}
