# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/prepallman.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

prepallman() {
	echo "man:"
	for x in "${D}"opt/*/man "${D}"usr/share/man "${D}"usr/local/man "${D}"usr/X11R6/man ; do
		if [ -d "${x}" ]; then
			prepman "`echo "${x}" | sed -e "s:${D}::" -e "s:/man[/]*$::"`" || die
		fi
	done
}