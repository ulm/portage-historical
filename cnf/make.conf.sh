# Copyright 1999-2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/cnf/make.conf.sh,v 1.4 2005/02/21 12:45:49 genone Exp $
# Contains local system settings for Portage system

# Please review 'man make.conf' for more information.

# Build-time functionality
# ========================
#
# The USE variable is used to enable optional build-time functionality. For
# example, quite a few packages have optional X, gtk or GNOME functionality
# that can only be enabled or disabled at compile-time. Gentoo Linux has a
# very extensive set of USE variables described in our USE variable HOWTO at
# http://www.gentoo.org/doc/en/handbook/handbook-x86.xml?part=2&chap=1
#
# The available list of use flags with descriptions is in your portage tree.
# Use 'less' to view them:  --> less /usr/portage/profiles/use.desc <--
#
# 'ufed' is an ncurses/dialog interface available in portage to make handling
# useflags for you. 'emerge app-portage/ufed'
#
# Example:
#USE="X gtk gnome -alsa"

# Host Setting
# ============
#
# Change this line as appropriate (sh, sh2, sh3, sh4, sh5).
CHOST="sh-unknown-linux-gnu"

# Host and optimization settings 
# ==============================
#
# For optimal performance, enable a CFLAGS setting appropriate for your CPU.
#
# Please note that if you experience strange issues with a package, it may be
# due to gcc's optimizations interacting in a strange way. Please test the
# package (and in some cases the libraries it uses) at default optimizations
# before reporting errors to developers.
#
# Decent examples:
#
#CFLAGS="-Os -pipe"

# If you set a CFLAGS above, then this line will set your default C++ flags to
# the same settings.
#CXXFLAGS="${CFLAGS}"

# Advanced Masking
# ================
#
# Gentoo is using a new masking system to allow for easier stability testing
# on packages. KEYWORDS are used in ebuilds to mask and unmask packages based
# on the platform they are set for. A special form has been added that
# indicates packages and revisions that are expected to work, but have not yet
# been approved for the stable set. '~arch' is a superset of 'arch' which
# includes the unstable, in testing, packages. Users of the 'x86' architecture
# would add '~x86' to ACCEPT_KEYWORDS to enable unstable/testing packages.
# '~ppc', '~sparc' are the unstable KEYWORDS for their respective platforms.
#
# Please note that this is not for development, alpha, beta, nor cvs release
# packages. "Broken" packages will not be added to testing and should not be
# requested to be added. Alternative routes are available to developers
# for experimental packages, and it is at their discretion to use them.
#
# DO NOT PUT ANYTHING BUT YOUR SPECIFIC ~ARCHITECTURE IN THE LIST.
# IF YOU ARE UNSURE OF YOUR ARCH, OR THE IMPLICATIONS, DO NOT MODIFY THIS.
#
#ACCEPT_KEYWORDS="~arch"

# Portage Directories
# ===================
#
# Each of these settings controls an aspect of portage's storage and file
# system usage. If you change any of these, be sure it is available when
# you try to use portage. *** DO NOT INCLUDE A TRAILING "/" ***
#
# PORTAGE_TMPDIR is the location portage will use for compilations and
#     temporary storage of data. This can get VERY large depending upon
#     the application being installed.
#PORTAGE_TMPDIR=/var/tmp
#
# PORTDIR is the location of the portage tree. This is the repository
#     for all profile information as well as all ebuilds. This directory
#     itself can reach 200M. WE DO NOT RECOMMEND that you change this.
#PORTDIR=/usr/portage
#
# DISTDIR is where all of the source code tarballs will be placed for
#     emerges. The source code is maintained here unless you delete
#     it. The entire repository of tarballs for gentoo is 9G. This is
#     considerably more than any user will ever download. 2-3G is
#     a large DISTDIR.
#DISTDIR=${PORTDIR}/distfiles
#
# PKGDIR is the location of binary packages that you can have created
#     with '--buildpkg' or '-b' while emerging a package. This can get
#     upto several hundred megs, or even a few gigs.
#PKGDIR=${PORTDIR}/packages
#
# PORT_LOGDIR is the location where portage will store all the logs it
#     creates from each individual merge. They are stored as NNNN-$PF.log
#     in the directory specified. This is disabled until you enable it by
#     providing a directory. Permissions will be modified as needed IF the
#     directory exists, otherwise logging will be disabled. NNNN is the
#     increment at the time the log is created. Logs are thus sequential.
#PORT_LOGDIR=/var/log/portage
#
# PORTDIR_OVERLAY is a directory where local ebuilds may be stored without
#     concern that they will be deleted by rsync updates. Default is not
#     defined.
#PORTDIR_OVERLAY=/usr/local/portage

# Fetching files 
# ==============
#
# If you need to set a proxy for wget or lukemftp, add the appropriate "export
# ftp_proxy=<proxy>" and "export http_proxy=<proxy>" lines to /etc/profile if
# all users on your system should use them.
#
# Portage uses wget by default. Here are some settings for some alternate
# downloaders -- note that you need to merge these programs first before they
# will be available.
#
# Default fetch command (5 tries, passive ftp for firewall compatibility)
#FETCHCOMMAND="/usr/bin/wget -t 5 --passive-ftp \${URI} -P \${DISTDIR}"
#RESUMECOMMAND="/usr/bin/wget -c -t 5 --passive-ftp \${URI} -P \${DISTDIR}"
#
# Using wget, ratelimiting downloads
#FETCHCOMMAND="/usr/bin/wget -t 5 --passive-ftp --limit-rate=200k \${URI} -P \${DISTDIR}"
#RESUMECOMMAND="/usr/bin/wget -c -t 5 --passive-ftp --limit-rate=200k \${URI} -P \${DISTDIR}"
#
# Lukemftp (BSD ftp):
#FETCHCOMMAND="/usr/bin/lukemftp -s -a -o \${DISTDIR}/\${FILE} \${URI}"
#RESUMECOMMAND="/usr/bin/lukemftp -s -a -R -o \${DISTDIR}/\${FILE} \${URI}"
#
#
# Portage uses GENTOO_MIRRORS to specify mirrors to use for source retrieval.
# The list is a space separated list which is read left to right. If you use
# another mirror we highly recommend leaving the default mirror at the end of
# the list so that portage will fall back to it if the files cannot be found
# on your specified mirror. We _HIGHLY_ recommend that you change this setting
# to a nearby mirror by merging and using the 'mirrorselect' tool.
#GENTOO_MIRRORS="<your_mirror_here> http://gentoo.osuosl.org http://www.ibiblio.org/pub/Linux/distributions/gentoo"
#
# Portage uses PORTAGE_BINHOST to specify mirrors for prebuilt-binary packages.
# The list is a single entry specifying the full address of the directory
# serving the tbz2's for your system. Running emerge with either '--getbinpkg'
# or '--getbinpkgonly' will cause portage to retrieve the metadata from all
# packages in the directory specified, and use that data to determine what will
# be downloaded and merged. '-g' or '-gK' are the recommend parameters. Please
# consult the man pages and 'emerge --help' for more information. For FTP, the
# default connection is passive -- If you require an active connection, affix
# an asterisk (*) to the end of the host:port string before the path.
#PORTAGE_BINHOST="http://grp.mirror.site/gentoo/grp/1.4/i686/athlon-xp/"
# This ftp connection is passive ftp.
#PORTAGE_BINHOST="ftp://login:pass@grp.mirror.site/pub/grp/i686/athlon-xp/"
# This ftp connection is active ftp.
#PORTAGE_BINHOST="ftp://login:pass@grp.mirror.site:21*/pub/grp/i686/athlon-xp/"

# Synchronizing Portage
# =====================
#
# Each of these settings affects how Gentoo synchronizes your Portage tree.
# Synchronization is handled by rsync and these settings allow some control
# over how it is done.
#
#
# SYNC is the server used by rsync to retrieve a localized rsync mirror
#     rotation. This allows you to select servers that are geographically
#     close to you, yet still distribute the load over a number of servers.
#     Please do not single out specific rsync mirrors. Doing so places undue
#     stress on particular mirrors.  Instead you may use one of the following
#     continent specific rotations:
#
#   Default:       "rsync://rsync.gentoo.org/gentoo-portage"
#   North America: "rsync://rsync.namerica.gentoo.org/gentoo-portage"
#   South America: "rsync://rsync.samerica.gentoo.org/gentoo-portage"
#   Europe:        "rsync://rsync.europe.gentoo.org/gentoo-portage"
#   Asia:          "rsync://rsync.asia.gentoo.org/gentoo-portage"
#   Australia:     "rsync://rsync.au.gentoo.org/gentoo-portage"
#SYNC="rsync://rsync.gentoo.org/gentoo-portage"
#
# RSYNC_RETRIES sets the number of times portage will attempt to retrieve
#     a current portage tree before it exits with an error. This allows
#     for a more successful retrieval without user intervention most times.
#RSYNC_RETRIES="3"
#
# RSYNC_TIMEOUT sets the length of time rsync will wait before it times out
#     on a connection. Most users will benefit from this setting as it will
#     reduce the amount of 'dead air' they experience when they run across
#     the occasional, unreachable mirror. Dialup users might want to set this
#     value up around the 300 second mark.
#RSYNC_TIMEOUT=180

# Advanced Features
# =================
#
# MAKEOPTS provides extra options that may be passed to 'make' when a
#     program is compiled. Presently the only use is for specifying
#     the number of parallel makes (-j) to perform. The suggested number
#     for parallel makes is CPUs+1.
#MAKEOPTS="-j2"
#
# PORTAGE_NICENESS provides a default increment to emerge's niceness level.
#     Note: This is an increment. Running emerge in a niced environment will
#     reduce it further. Default is unset.
#PORTAGE_NICENESS=3
#
# FEATURES are settings that affect the functionality of portage. Most of
#     these settings are for developer use, but some are available to non-
#     developers as well. 
#
#  'autoaddcvs'  causes portage to automatically try to add files to cvs
#                that will have to be added later. Done at generation times
#                and only has an effect when 'cvs' is also set.
#  'buildpkg'    causes binary packages to be created of all packages that 
#                are being merged.
#  'ccache'      enables ccache support via CC.
#  'collision-protect'
#                prevents packages from overwriting files that are owned by
#                another package or by no package at all.
#  'cvs'         causes portage to enable all cvs features (commits, adds),
#                and to apply all USE flags in SRC_URI for digests -- for
#                developers only.
#  'digest'      causes digests to be generated for all packages being merged.
#  'distcc'      enables distcc support via CC.
#  'distlocks'   enables distfiles locking using fcntl or hardlinks. This
#                is enabled by default. Tools exist to help clean the locks
#                after crashes: /usr/lib/portage/bin/clean_locks.
#  'fixpackages' allows portage to fix binary packages that are stored in
#                PKGDIR. This can consume a lot of time. 'fixpackages' is
#                also a script that can be run at any given time to force
#                the same actions.
#  'gpg'         enables basic verification of Manifest files using gpg.
#                This features is UNDER DEVELOPMENT and reacts to features
#                of strict and severe. Heavy use of gpg sigs is coming.
#  'keeptemp'    prevents the clean phase from deleting the temp files ($T) 
#                from a merge.
#  'keepwork'    prevents the clean phase from deleting the WORKDIR.
#  'maketest'    causes ebuilds to perform testing phases if they are capable
#                of it. Some packages support this automaticaly via makefiles.
#  'noauto'      causes ebuild to perform only the action requested and 
#                not any other required actions like clean or unpack -- for
#                debugging purposes only.
#  'noclean'     prevents portage from removing the source and temporary files 
#                after a merge -- for debugging purposes only. 
#  'nostrip'     prevents the stripping of binaries.
#  'notitles'    disables xterm titlebar updates (which contain status info). 
#  'sandbox'     enables sandboxing when running emerge and ebuild.
#  'strict'      causes portage to react strongly to conditions that are
#                potentially dangerous, like missing/incorrect Manifest files.
#  'userpriv'    allows portage to drop root privileges while it is compiling,
#                as a security measure.  As a side effect this can remove 
#                sandbox access violations for users. 
#  'usersandbox' enables sandboxing while portage is running under userpriv.
#FEATURES="sandbox buildpkg ccache distcc userpriv usersandbox notitles noclean noauto cvs keeptemp keepwork autoaddcvs"
#FEATURES="sandbox ccache distcc distlocks autoaddcvs"
#
# CCACHE_SIZE sets the space use limitations for ccache. The default size is
#     2G, and will be set if not defined otherwise and ccache is in features. 
#     Portage will set the default ccache dir if it is not present in the
#     user's environment, for userpriv it sets: ${PORTAGE_TMPDIR}/ccache
#     (/var/tmp/ccache), and for regular use the default is /root/.ccache.
#     Sizes are specified with 'G' 'M' or 'K'.
#     '2G' for 2 gigabytes, '2048M' for 2048 megabytes (same as 2G).
#CCACHE_SIZE="512M"
#
# DISTCC_DIR sets the temporary space used by distcc.
#DISTCC_DIR="${PORTAGE_TMPDIR}/.distcc"
#
# RSYNC_EXCLUDEFROM is a file that portage will pass to rsync when it updates
#     the portage tree. Specific chunks of the tree may be excluded from
#     consideration. This may cause dependency failures if you are not careful.
#     The file format is one pattern per line, blanks and ';' or '#' lines are
#     comments. See 'man rsync' for more details on the exclude-from format.
#RSYNC_EXCLUDEFROM=/etc/portage/rsync_excludes

# logging related variables:
# PORTAGE_LOG_CLASSES: selects messages to be logged, possible values are:
#                          info, warn, error, log
PORTAGE_LOG_CLASSES="warn error log"

# PORTAGE_LOG_SYSTEM: selects the module(s) to process the log messages. Modules
#                     included in portage are (empty means logging is disabled):
#                          save (saves one log per package in $PORTAGE_TMPDIR/elogs)
#                          custom (passes all messages to $PORTAGE_LOG_COMMAND)
#                          syslog (sends all messages to syslog)
#                          mail (send all messages to the mailserver defined 
#                                in $PORTAGE_LOG_MAILURI)
#PORTAGE_LOG_SYSTEM="save mail"

# PORTAGE_LOG_COMMAND: only used with the "custom" logging module. Specifies a command
#                      to process log messages. Two variables are expanded:
#                          ${PACKAGE} - expands to the cpv entry of the processed 
#                                       package (see $PVR in ebuild(5))
#                          ${LOGFILE} - absolute path to the logfile
#PORTAGE_LOG_COMMAND="/path/to/logprocessor -p ${PACKAGE} -f ${LOGFILE}"

# PORTAGE_LOG_MAILURI: this variable holds all important settings for the mail
#                      module. In most cases listing the recipient adress and
#                      the receiving mailserver should be sufficient, but you can
#                      also use advanced settings like authentication or TLS. The
#                      full syntax is:
#                          adress [[user:passwd@]mailserver[:port]]
#                      where
#                          adress:     recipient adress
#                          user:       username for smtp auth (defaults to none)
#                          passwd:     password for smtp auth (defaults to none)
#                          mailserver: smtp server that should be used to deliver the mail (defaults to localhost)
#                          port:       port to use on the given smtp server (defaults to 25, values > 100000 indicate that starttls should be used on (port-100000))
#                      Examples:
#PORTAGE_LOG_MAILURI="root@localhost localhost" (this is also the default setting)
#PORTAGE_LOG_MAILURI="user@some.domain mail.some.domain" (sends mails to user@some.domain using the mailserver mail.some.domain)
#PORTAGE_LOG_MAILURI="user@some.domain user:secret@mail.some.domain:100465" (this is left uncommented as a reader excercise ;)
