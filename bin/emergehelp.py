#!/usr/bin/env python2.2
# Copyright 1999-2002 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/Attic/emergehelp.py,v 1.1 2002/12/30 11:37:25 carpaski Exp $

import os,sys
from output import *

def help(myaction):
	import portage
	if (not sys.stdout.isatty()) or (portage.settings["NOCOLOR"] in ["yes","true"]):
		nocolor()
	if not myaction:
		print
		print bold("Usage: ")+turquoise("emerge")+" [ "+green("options")+" ] [ "+green("action")+" ] [ "+turquoise("ebuildfile")+" | "+turquoise("tbz2file")+" | "+turquoise("dependency")+" ] ..."
		print "       "+turquoise("emerge")+" [ "+green("options")+" ] [ "+green("action")+" ] "+turquoise("system")
		print "       "+turquoise("emerge")+" "+turquoise("sync")+" | "+turquoise("rsync")
		print "       "+turquoise("emerge")+" "+green("--help")+" "" "+green("-h")+" [ "+turquoise("system")+" | "+turquoise("config")+" ] "
		print
		print turquoise("Help (this screen):")
		print "       "+green("--help")+" ("+green("-h")+" short option)"
		print "              Displays this help; an additional argument (see above) will tell"
		print "              emerge to display detailed help."
		print
		print turquoise("Actions:")
		print "       "+green("clean")+" ("+green("-c")+" short option)"
		print "              Cleans the system by removing outdated packages which will not"
		print "              remove functionalities or prevent your system from working."
		print "              The arguments can be in several different formats :"
		print "              * world "
		print "              * system "
		print "              * /var/db/pkg/category/package-version, or"
		print "              * 'dependency specification' (in single quotes is best.)"
		print "              Here are a few examples of the dependency specification format:"
		print "              "+bold("binutils")+" matches"
		print "                  binutils-2.11.90.0.7 and binutils-2.11.92.0.12.3-r1"
		print "              "+bold(">binutils-2.11.90.0.7")+" matches"
		print "                  binutils-2.11.92.0.12.3-r1"
		print "              "+bold("sys-devel/binutils")+" matches"
		print "                  binutils-2.11.90.0.7 and binutils-2.11.92.0.12.3-r1"
		print "              "+bold("sys-devel/binutils-2.11.90.0.7")+" matches"
		print "                  binutils-2.11.90.0.7"
		print "              "+bold(">sys-devel/binutils-2.11.90.0.7")+" matches"
		print "                  binutils-2.11.92.0.12.3-r1"
		print "              "+bold(">=sys-devel/binutils-2.11.90.0.7")+" matches"
		print "                  binutils-2.11.90.0.7 and binutils-2.11.92.0.12.3-r1"
		print "              "+bold("<sys-devel/binutils-2.11.92.0.12.3-r1")+" matches"
		print "                  binutils-2.11.90.0.7"
		print "              "+bold("<=sys-devel/binutils-2.11.92.0.12.3-r1")+" matches"
		print "                  binutils-2.11.90.0.7 and binutils-2.11.92.0.12.3-r1"
		print
		print "       "+green("unmerge")+" ("+green("-C")+" short option)"
		print "              "+turquoise("WARNING: This action can remove important packages!")
		print "              Removes all matching packages without checking for outdated."
		print "              versions. This thus effectively removes a package "+bold("completely")+" from"
		print "              your system. Specify arguments using the dependency specification"
		print "              format described in the "+bold("clean")+" action above."
		print
		print "       "+green("prune")+" ("+green("-P")+" short option)"
		print "              "+turquoise("WARNING: This action can remove important packages!")
		print "              Removes all older versions of a package from your system."
		print "              This action doesn't always verify the possible binary"
		print "              incompatibility between versions and can thus remove essential"
		print "              dependencies from your system."
		print "              The argument format is the same as for the "+bold("clean")+" action."
		print
		print "       "+green("depclean")
		print "              Cleans the system by removing packages that are not associated"
		print "              with explicitly merged packages. Depclean works by creating the"
		print "              full dependancy tree from the system list and the world file,"
		print "              then comparing it to installed packages. Packages installed, but"
		print "              not associated with an explicit merge are listed as candidates"
		print "              for unmerging."+turquoise(" WARNING: This can seriously affect your system by")
		print "              "+turquoise("removing packages that may have been linked against, but due to")
		print "              "+turquoise("changes in USE flags may no longer be part of the dep tree. Use")
		print "              "+turquoise("caution when employing this feature.")
		print
		print "       "+green("search")+" ("+green("-s")+" short option)"
		print "              searches for matches of the supplied string in the current local"
		print "              portage tree. The search string is a regular expression."
		print "              A few examples: "
		print "              "+bold("emerge search '^kde'")
		print "                  list all packages starting with kde"
		print "              "+bold("emerge search 'gcc$'")
		print "                  list all packages ending with gcc"
		print "              "+bold("emerge search ''")+" or"
		print "              "+bold("emerge search '.*'")
		print "                  list all available packages "
		print
		print "       "+green("inject")+" ("+green("-i")+" short option)"
		print "              Add a stub entry for a package so that Portage thinks that it's"
		print "              installed when it really isn't.  Handy if you roll your own"
		print "              packages.  Example: "
		#NOTE: this next line *needs* the "sys-kernel/"; *please* don't remove it!
		print "              "+bold("emerge inject sys-kernel/gentoo-sources-2.4.19")
		print
		print turquoise("Options:")
		print "       "+green("--autoclean")+" ("+green("-a")+" short option)"
		print "              emerge normally cleans out the package-specific temporary"
		print "              build directory before it starts the building a package.  With"
		print "              --autoclean, it will also clean the directory *after* the"
		print "              build completes.  This option is automatically enabled for"
		print "              normal users, but maintainers can use this option to enable"
		print "              autocleaning."
		print
		print "       "+green("--buildpkg")+" ("+green("-b")+" short option)"
		print "              tell emerge to build binary packages for all ebuilds processed"
		print "              (in addition to actually merging the packages.  Useful for"
		print "              maintainers or if you administrate multiple Gentoo Linux"
		print "              systems (build once, emerge tbz2s everywhere)."
		print
		print "       "+green("--debug")+" ("+green("-d")+" short option)"
		print "              Tell emerge to run the ebuild command in --debug mode. In this"
		print "              mode, the bash build environment will run with the -x option,"
		print "              causing it to output verbose debug information print to stdout."
		print "              --debug is great for finding bash syntax errors."
		print
		print "       "+green("--emptytree")+" ("+green("-e")+" short option)"
		print "              Virtually tweaks the tree of installed packages to only contain"
		print "              glibc, this is great to use together with --pretend. This makes"
		print "              it possible for developers to get a complete overview of the"
		print "              complete dependency tree of a certain package."
		print
		print "       "+green("--fetchonly")+" ("+green("-f")+" short option)"
		print "              Instead of doing any package building, just perform fetches for"
		print "              all packages (main package as well as all dependencies.) When"
		print "              used in combination with --pretend all the SRC_URIs will be"
		print "              displayed multiple mirrors per line, one line per file."
		print
		print "       "+green("--nodeps")
		print "              Merge specified packages, but don't merge any dependencies."
		print "              Note that the build may fail if deps aren't satisfied."
		print 
		print "       "+green("--noreplace")+" ("+green("-n")+" short option)"
		print "              Skip the packages specified on the command-line that have"
		print "              already been installed.  Without this option, any packages,"
		print "              ebuilds, or deps you specify on on the command-line *will* cause"
		print "              Portage to remerge the package, even if it is already installed."
		print "              Note that Portage won't remerge dependencies by default."
		print
		print "       "+green("--oneshot")
		print "              Emerge as normal, but don't add packages to the world profile for"
		print "              later updating."
		print
		print "       "+green("--onlydeps")+" ("+green("-o")+" short option)"
		print "              Only merge (or pretend to merge) the dependencies of the"
		print "              specified packages, not the packages themselves."
		print
		print "       "+green("--pretend")+" ("+green("-p")+" short option)"
		print "              instead of actually performing the merge, simply display what"
		print "              ebuilds and tbz2s *would* have been installed if --pretend"
		print "              weren't used.  Using --pretend is strongly recommended before"
		print "              installing an unfamiliar package.  In the printout, N = new,"
		print "              U = upgrading, R = replacing, B = blocked by an already installed"
		print "              package."
		print
		print "       "+green("--changelog")
		print "              When pretending, also display the ChangeLog entries for packages"
		print "              that will be upgraded."
		print
		print "       "+green("--searchdesc")+" ("+green("-S")+" short option)"
		print "              Matches the search string against the description field as well"
		print "              the package's name. Take caution as the descriptions are also"
		print "              matched as regular expressions."
		print "                emerge -S html"
		print "                emerge -S applet"
		print "                emerge -S 'perl.*module'"
		print
		print "       "+green("--update")+" ("+green("-u")+" short option)"
		print "              Updates packages to the most recent version available."
		print 
		print "       "+green("--usepkg")+" ("+green("-k")+" short option)"
		print "              tell emerge to use binary packages (from $PKGDIR) if they are"
		print "              available, thus possibly avoiding some time-consuming compiles."
		print "              This option is useful for CD installs; you can export"
		print "              PKGDIR=/mnt/cdrom/packages and then use this option to have"
		print "              emerge \"pull\" binary packages from the CD in order to satisfy" 
		print "              dependencies."
		print
		print "       "+green("--verbose")+" ("+green("-v")+" short option)"
		print "              Tell emerge to run in verbose mode.  Currently, this causes"
		print "              emerge to print out GNU info errors, if any."
	elif myaction in ["rsync","sync"]:
		print
		print bold("Usage: ")+turquoise("emerge")+" "+turquoise("sync")
		print
		print "       \"emerge sync\" tells emerge to update the Portage tree as specified in"
		print "       The SYNC variable found in /etc/make.conf.  By default, SYNC instructs"
		print "       emerge to perform an rsync-style update with cvs.gentoo.org.  Available"
		print "       sync methods are rsync and anoncvs.  To use anoncvs rather than rsync,"
		print "       put 'SYNC=\"cvs://:pserver:cvs.gentoo.org:/home/cvsroot\" in your"
		print "       /etc/make.conf.  If you haven't used anoncvs before, you'll be prompted"
		print "       for a password, which for cvs.gentoo.org is empty (just hit enter.)"
		print
		print "       "+turquoise("WARNING:")
		print "       If using our rsync server, emerge will clean out all files that do not"
		print "       exist on it, including ones that you may have created."
		print
	elif myaction=="system":
		print
		print bold("Usage: ")+turquoise("emerge")+" [ "+green("options")+" ] "+turquoise("system")
		print
		print "       \"emerge system\" is the Portage system update command.  When run, it"
		print "       will scan the etc/make.profile/packages file and determine what"
		print "       packages need to be installed so that your system meets the minimum"
		print "       requirements of your current system profile.  Note that this doesn't"
		print "       necessarily bring your system up-to-date at all; instead, it just"
		print "       ensures that you have no missing parts.  For example, if your system"
		print "       profile specifies that you should have sys-apps/iptables installed"
		print "       and you don't, then \"emerge system\" will install it (the most"
		print "       recent version that matches the profile spec) for you.  It's always a"
		print "       good idea to do an \"emerge --pretend system\" before an \"emerge"
		print "       system\", just so you know what emerge is planning to do."
		print
	elif myaction=="config":
		outstuff=green("Config file management support (preliminary)")+"""

Portage has a special feature called "config file protection".  The purpose of
this feature is to prevent new package installs from clobbering existing
configuration files.  By default, config file protection is turned on for /etc
and the KDE configuration dirs; more may be added in the future.

When Portage installs a file into a protected directory tree like /etc, any
existing files will not be overwritten.  If a file of the same name already
exists, Portage will change the name of the to-be- installed file from 'foo' to
'._cfg0000_foo'.  If '._cfg0000_foo' already exists, this name becomes
'._cfg0001_foo', etc.  In this way, existing files are not overwritten,
allowing the administrator to manually merge the new config files and avoid any
unexpected changes.

In addition to protecting overwritten files, Portage will not delete any files
from a protected directory when a package is unmerged.  While this may be a
little bit untidy, it does prevent potentially valuable config files from being
deleted, which is of paramount importance.

Protected directories are set using the CONFIG_PROTECT variable, normally
defined in /etc/make.globals.  Directory exceptions to the CONFIG_PROTECTed
directories can be specified using the CONFIG_PROTECT_MASK variable.  To find
files that need to be updated in /etc, type:

# find /etc -iname '._cfg????_*'

You can disable this feature by setting CONFIG_PROTECT="-*" in /etc/make.conf.
Then, Portage will mercilessly auto-update your config files.  Alternatively,
you can leave Config File Protection on but tell Portage that it can overwrite
files in certain specific /etc subdirectories.  For example, if you wanted
Portage to automatically update your rc scripts and your wget configuration,
but didn't want any other changes made without your explicit approval, you'd
add this to /etc/make.conf:

CONFIG_PROTECT_MASK="/etc/wget /etc/rc.d"

"""
		print outstuff
