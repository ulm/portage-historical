# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/Attic/regenworld.sh,v 1.2 2003/02/16 03:03:41 carpaski Exp $

egrep '^[0-9]+:  \*\*\* emerge' /var/log/emerge.log |
egrep -v 'oneshot|nodeps|emerge .* search ' |
sed 's:^.*\* emerge ::;s:--[^ ]\+ ::;s: :\n:g' |
egrep '^[a-zA-Z=><]' |
egrep -v '^[0-9]|\.ebuild$|\.tbz2$' |
sort -u
