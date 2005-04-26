# Copyright 1999-2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/cnf/make.globals.sh,v 1.3 2005/04/26 09:40:59 genone Exp $
# System-wide defaults for the Portage system

#            *****************************
#            **  DO NOT EDIT THIS FILE  **
# ***************************************************
# **** CHANGES TO make.conf *OVERRIDE* THIS FILE ****
# ***************************************************
# ** Incremental Variables Accumulate Across Files **
# **  USE, CONFIG_*, and FEATURES are incremental  **
# ***************************************************

GENTOO_MIRRORS="http://gentoo.osuosl.org http://distro.ibiblio.org/pub/Linux/distributions/gentoo"
SYNC="rsync://rsync.gentoo.org/gentoo-portage"
# Host-type
CHOST=sh-unknown-linux-gnu
PORTAGE_TMPDIR=/var/tmp

PORTDIR=/usr/portage
DISTDIR=${PORTDIR}/distfiles
PKGDIR=${PORTDIR}/packages
RPMDIR=${PORTDIR}/rpm
CONFIG_PROTECT="/etc /var/qmail/control /usr/share/config /usr/kde/2/share/config /usr/kde/3/share/config"
CONFIG_PROTECT_MASK="/etc/gconf"

# Options passed to make during the build process
MAKEOPTS="-j2"

# Fetching command (5 tries, passive ftp for firewall compatibility)
FETCHCOMMAND="/usr/bin/wget -t 5 --passive-ftp -P \${DISTDIR} \${URI}"
RESUMECOMMAND="/usr/bin/wget -c -t 5 --passive-ftp -P \${DISTDIR} \${URI}"

CFLAGS="-Os -pipe"
CXXFLAGS=${CFLAGS}

# Debug build -- if defined, binaries won't be stripped
#DEBUGBUILD=true

# Default maintainer options
#FEATURES="digest sandbox noclean noauto buildpkg usersandbox"
# Default user options
FEATURES="sandbox distlocks ccache autoaddcvs strict"

# By default output colored text where possible, set to "true" to output only
#black&white text
NOCOLOR="false"

PORTAGE_BINHOST_CHUNKSIZE="3000"
USE_EXPAND="VIDEO_CARDS INPUT_DEVICES LINGUAS"

# By default wait 5 secs before cleaning a package
CLEAN_DELAY="5"

# Set to yes automatically run "emerge --clean" after each merge
# Important, as without this you may experience missing symlinks when
# downgrading libraries during a batch (world/system) update.
# DEPRECATED, THIS IS ALWAYS ENABLED IN >=PORTAGE-2.1
AUTOCLEAN="yes"

# Number of times 'emerge --sync' will run before giving up.
RSYNC_RETRIES="3"
# Number of seconds rsync will wait before timing out.
RSYNC_TIMEOUT="180"

#            *****************************
#            **  DO NOT EDIT THIS FILE  **
# ***************************************************
# **** CHANGES TO make.conf *OVERRIDE* THIS FILE ****
# ***************************************************
# ** Incremental Variables Accumulate Across Files **
# **  USE, CONFIG_*, and FEATURES are incremental  **
# ***************************************************
