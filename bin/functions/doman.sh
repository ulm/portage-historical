# Copyright 1999-2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/functions/Attic/doman.sh,v 1.1 2003/12/10 06:00:57 carpaski Exp $

doman() {
	if [ ${#} -lt 1 ] ; then
		die "doman: at least one argument needed" 1>&2
	fi

	# /usr/share/man
	# /usr/X11R6/man
	# /opt/gnome/man
	# /opt/kde/man

	BASE="/usr/share"
	OLDBASE="$BASE"

	for x in "$@" ; do
		[ "$x" == "--"     ] && BASE="/usr/share"
		[ "$x" == "-kde"   ] && BASE="/opt/kde"
		[ "$x" == "-gnome" ] && BASE="/opt/gnome"
		[ "$x" == "-x11"   ] && BASE="/usr/X11R6"
		if [ "${x:0:1}" == "-" ] ; then
			OLDBASE="$BASE"
			continue
		fi

	  if [ "${x}" == ".keep" ]; then
			continue
		fi

		BASE="$OLDBASE"
		suffix="${x##*.}"
		
		if [ "$suffix" == "gz" ] ; then
			compressed="gz"
			realname="${x%.*}"
			suffix="${realname##*.}"
		else
			realname="$x"
			compressed=""
		fi

		if [ "x" == "${suffix:1:1}" ] ; then
			OLDBASE="$BASE"
			BASE="/usr/X11R6"
		fi

		mandir=man${suffix:0:1}

		if echo ${mandir} | egrep -q '^man[1-8n]$' -; then
			if [ -e "${x}" ] ; then
				if [ ! -d "${D}${BASE}/man/${mandir}" ] ; then
					install -d "${D}${BASE}/man/${mandir}"
				fi

				install -m0644 "${x}" "${D}${BASE}/man/${mandir}"

				if [ -z "${compressed}" ] ; then
					gzip -f -9 "${D}${BASE}/man/${mandir}/${x##*/}"
				fi
			else
				echo "doman: ${x} does not exist." 1>&2
			fi
		else
			echo -e "\adoman: '${x}' is probably not a man page." 1>&2
		fi
	done
}