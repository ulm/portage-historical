# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/preplib.so.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

preplib.so() {
	if [ "${FEATURES//*nostrip*/true}" == "true" ] || [ "${RESTRICT//*nostrip*/true}" == "true" ] ; then
		return 0
	fi

	if [ ! -z "${CBUILD}" ] && [ "${CBUILD}" != "${CHOST}" ]; then
		STRIP=${CHOST}-strip
	else
		STRIP=strip
	fi

	for x in "$@" ; do
		if [ -d "${D}${x}" ] ; then
			for y in `find "${D}${x}"/ -type f \( -name "*.so" -or -name "*.so.*" \) 2>/dev/null` ; do
				f="`file "${y}"`"
				if [ "${f/*SB shared object*/1}" == "1" ] ; then
					echo "${y}"
					${STRIP} --strip-debug "${y}" || die
				fi
			done
			ldconfig -n -N "${D}${x}" || die
		fi
	done
}
