# Copyright (C) 2001 The Leaf, http://www.theleaf.be
# Distributed under the terms of the GNU General Public License, v2 or later 
# Author : Geert Bevin <gbevin@theleaf.be>
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/sandbox/files/sandbox/Attic/sandbox.bashrc,v 1.2 2001/12/06 22:26:33 gbevin Exp $
source /etc/profile
export LD_PRELOAD="$SANDBOX_LIB"
alias make="make LD_PRELOAD=$SANDBOX_LIB"
alias su="su -c '/bin/bash -rcfile $SANDBOX_DIR/sandbox.bashrc'"
