# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/prepall.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

prepall() {
	prepallman   || die
	prepallinfo  || die
	prepallstrip || die

	#this should help to ensure that all (most?) shared libraries are executable
	for i in "${D}"opt/*/lib "${D}"lib "${D}"usr/lib "${D}"usr/X11R6/lib ; do
		[ ! -d "${i}" ] && continue
	
		for j in "${i}"/*.so.* "${i}"/*.so ; do
			[ ! -e "${j}" ] && continue
			[ -L "${j}" ] && continue
			echo "making executable: /${j/${D}/}"
			chmod +x "${j}" || die
		done
	done
	
	# Move aclocals
	for i in `find "${D}"/ -name "aclocal" -type d 2>/dev/null` ; do
		[ -z "${i}" ] && continue
	
		# Strip double '/'
		dir1="`echo "${i}" | sed  -e 's://:/:g'`"
		dir2="`echo "${D}/usr/share/aclocal" | sed  -e 's://:/:g'`"
		
		[ "${dir1}" == "${dir2}" ] && continue
	
		echo "moving aclocal: /${i/${D}/}"
		install -d "${D}"usr/share/aclocal || die
		mv "${i}"/* "${D}"usr/share/aclocal || die
		rm -fr "${i}" || die
	done
}