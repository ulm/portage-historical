# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/prepallstrip.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

prepallstrip() {
	if [ "${FEATURES//*nostrip*/true}" == "true" ] || [ "${RESTRICT//*nostrip*/true}" == "true" ] ; then
		return 0
	fi

	echo "prepallstrip:"
	prepstrip "${D}" || die
}
