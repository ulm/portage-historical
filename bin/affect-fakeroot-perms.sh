#!/bin/bash
# affect-fakeroot-perms.sh; Make claimed fakeroot permissions, a reality.
# Copyright 2004-2005 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/affect-fakeroot-perms.sh,v 1.5 2005/08/05 02:37:14 vapier Exp $


echo "adjusting $2 using $1" >&2
fakeroot -i "$1" -- find "$2" -exec stat -c '%u:%g;%f=%n' {} \; | \
while read l; do
		o="${l/;*}"
		r="${l/${o}}"
		p="${r/=*}"
		p="${p:1}"
		p="$(printf %o 0x${p})"
		p="${p:${#p}-4}"
		f="${r/*=}"
		chown "$o" "$f"
		chmod "$p" "$f"
		echo "tweaking $f"
	done
