# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/fperms.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

fperms() {
	if [ ${#} -lt 2 ] ; then
		die "fperms: at least two arguments needed"
	fi

	if [ "${1}" == "-R" ]; then
		FP_RECURSIVE="-R"
		shift
	fi
	PERM="${1}"
	shift

	for FILE in "$@"; do
		chmod ${FP_RECURSIVE} "${PERM}" "${D}${FILE}" || die "Unable to 'chmod ${FP_RECURSIVE} ${PERM} ${D}${FILE}"
	done
}