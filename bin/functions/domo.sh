# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/domo.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

domo() {
	mynum=${#}
	if [ ${mynum} -lt 1 ] ; then
		echo "domo: at least one argument needed"
		exit 1
	fi
	if [ ! -d "${D}${DESTTREE}/share/locale" ] ; then
		install -d "${D}${DESTTREE}/share/locale/"
	fi

	for x in "$@" ; do
		if [ -e "${x}" ] ; then
			mytiny="${x##*/}"
			mydir="${D}${DESTTREE}/share/locale/${mytiny%.*}/LC_MESSAGES"
			if [ ! -d "${mydir}" ] ; then
				install -d "${mydir}"
			fi
			install -m0644 "${x}" "${mydir}/${MOPREFIX}.mo"
		else
			echo "domo: ${x} does not exist"
		fi
	done
}