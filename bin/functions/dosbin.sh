# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/dosbin.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

dosbin() {
	if [ ${#} -lt 1 ] ; then
		die "dosbin: at least one argument needed"
	fi
	if [ ! -d "${D}${DESTTREE}/sbin" ] ; then
		install -d "${D}${DESTTREE}/sbin" || die
	fi

	if [ ! -z "${CBUILD}" ] && [ "${CBUILD}" != "${CHOST}" ]; then
		STRIP=${CHOST}-strip
	else
		STRIP=strip
	fi

	for x in "$@" ; do
		if [ -x "${x}" ] ; then
			if [ "${FEATURES//*nostrip*/true}" != "true" ] && [ "${RESTRICT//*nostrip*/true}" != "true" ] ; then
				MYVAL=`file "${x}" | grep "ELF"`
				if [ "$MYVAL" ] ; then
					${STRIP} "${x}" || die
				fi
			fi
			#if executable, use existing perms
			install -m0755 "${x}" "${D}${DESTTREE}/sbin" || die
		else
			#otherwise, use reasonable defaults
			echo ">>> dosbin: making ${x} executable..."
			install -m0755 --owner=root --group=root "${x}" "${D}${DESTTREE}/sbin" || die
		fi
	done
}
