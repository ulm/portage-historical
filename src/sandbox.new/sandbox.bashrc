# Copyright (C) 2001 Geert Bevin, Uwyn, http://www.uwyn.com
# Distributed under the terms of the GNU General Public License, v2 or later 
# Author : Geert Bevin <gbevin@uwyn.com>
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/src/sandbox.new/Attic/sandbox.bashrc,v 1.1 2002/08/18 21:25:23 azarah Exp $
source /etc/profile
export LD_PRELOAD="$SANDBOX_LIB"
alias make="make LD_PRELOAD=$SANDBOX_LIB"
alias su="su -c '/bin/bash -rcfile $SANDBOX_DIR/sandbox.bashrc'"
