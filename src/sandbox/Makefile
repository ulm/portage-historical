# Copyright (C) 2001 Geert Bevin, Uwyn, http://www.uwyn.com
# Distributed under the terms of the GNU General Public License, v2 or later 
# Author : Geert Bevin <gbevin@uwyn.com>
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/src/sandbox/Attic/Makefile,v 1.2 2002/03/06 09:51:02 gbevin Exp $
default: sandbox libsandbox.so

sandbox: sandbox.c
	gcc -Wall -O2 -o sandbox sandbox.c

libsandbox.so: libsandbox.c
	gcc -Wall -O2 -ldl --shared -o libsandbox.so libsandbox.c

clean:
	rm sandbox
	rm libsandbox.so
