# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/prepstrip.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

prepstrip() {
	if [ "${FEATURES//*nostrip*/tree}" == "true" ] || [ "${RESTRICT//*nostrip*/true}" == "true" ] ; then
		echo "nostrip"
		return 0
	fi

	if [ ! -z "${CBUILD}" ] && [ "${CBUILD}" != "${CHOST}" ]; then
		STRIP=${CHOST}-strip
	else
		STRIP=strip
	fi
	
	echo "strip: "
	for x in "$@"; do # "$@" quotes each element... Plays nice with spaces.
		if [ -d "${x}" ]; then
			# We only want files. So make a pass for each directory and call again.
			find "${x}" -type f \( -perm +0111 -or -regex '\.so$|\.so\.' \) -print0 |
					$XARGS -0 -n500 prepstrip || die
		else
			f=$(file "${x}")
			if [ -z "${f/*SB executable*/}" ]; then
				echo "   ${x:${#D}:${#x}}"
				${STRIP} "${x}" || die
			fi
			if [ -z "${f/*SB shared object*/}" ]; then
				echo "   ${x:${#D}:${#x}}"
				${STRIP} --strip-debug "${x}" || die
	
				# etdyn binaries are shared objects, but not really. Non-relocatable.
				if [ -x /usr/bin/isetdyn ]; then
					if /usr/bin/isetdyn "${x}" >/dev/null; then
						${STRIP} "${x}" || die
					fi
				fi
			fi
		fi
	done
}