#!/bin/bash
# ebuild.sh; ebuild phase processing, env handling
# Copyright 2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
$Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/bin/ebuild.sh,v 1.205 2004/11/07 14:06:53 ferringb Exp $

#!/bin/bash
# Gentoo Foundation
# bugs should be thrown at Brian Harring <ferringb@gentoo.org>
# ancestry (obviously) of this file is the original vanilla ebuild.sh; it's been heavily restructured, and nailed down for env 
# purposes.  The final code path executed for phases is functionally the same, although env handling is quite different...
# it's sane for starters.

ORIG_VARS=`declare | egrep '^[^[:space:]{}()]+=' | cut -s -d '=' -f 1`
ORIG_FUNCS=`declare -F | cut -s -d ' ' -f 3`
DONT_EXPORT_FUNCS='portageq speak'
DONT_EXPORT_VARS="ORIG_VARS GROUPS ORIG_FUNCS FUNCNAME DAEMONIZED CCACHE.* DISTCC.* AUTOCLEAN CLEAN_DELAY SYNC
COMPLETED_EBUILD_PHASES (TMP|)DIR FEATURES CONFIG_PROTECT.* (P|)WORKDIR (FETCH|RESUME) COMMAND RSYNC_.* GENTOO_MIRRORS 
(DIST|FILES|RPM|ECLASS)DIR HOME MUST_EXPORT_ENV QA_CONTROLLED_EXTERNALLY COLORTERM COLS ROWS HOSTNAME
ROOTPATH myarg SANDBOX_.* BASH.* EUID PPID SHELLOPTS UID ACCEPT_(KEYWORDS|LICENSE) BUILD(_PREFIX|DIR) T DIRSTACK
DISPLAY (EBUILD|)_PHASE PORTAGE_.* RC_.* SUDO_.* IFS PATH LD_PRELOAD ret line phases D EMERGE_FROM
PORT(_LOGDIR|DIR(|_OVERLAY)) ROOT TERM _ done e ENDCOLS PROFILE_PATHS BRACKET BAD WARN GOOD NORMAL"

#DEBUGGING="yes"

reset_sandbox() {
	export SANDBOX_ON="1"
	export SANDBOX_PREDICT="${SANDBOX_PREDICT:+${SANDBOX_PREDICT}:}/proc/self/maps:/dev/console:/usr/lib/portage/pym:/dev/random"
	export SANDBOX_WRITE="${SANDBOX_WRITE:+${SANDBOX_WRITE}:}/dev/shm:${PORTAGE_TMPDIR}"
	export SANDBOX_READ="${SANDBOX_READ:+${SANDBOX_READ}:}/dev/shm:${PORTAGE_TMPDIR}"
}

# Prevent aliases from causing portage to act inappropriately.
# Make sure it's before everything so we don't mess aliases that follow.
unalias -a

# We need this next line for "die" and "assert". It expands 
# It _must_ preceed all the calls to die and assert.
shopt -s expand_aliases

# Unset some variables that break things.
unset GZIP BZIP BZIP2 CDPATH GREP_OPTIONS GREP_COLOR GLOB_IGNORE

alias die='diefunc "$FUNCNAME" "$LINENO" "$?"'
alias assert='_pipestatus="${PIPESTATUS[*]}"; [[ "${_pipestatus// /}" -eq 0 ]] || diefunc "$FUNCNAME" "$LINENO" "$_pipestatus"'
alias save_IFS='[ "${IFS:-unset}" != "unset" ] && portage_old_IFS="${IFS}"'
alias restore_IFS='if [ "${portage_old_IFS:-unset}" != "unset" ]; then IFS="${portage_old_IFS}"; unset portage_old_IFS; else unset IFS; fi'

diefunc() {
        local funcname="$1" lineno="$2" exitcode="$3"
        shift 3
        echo >&2
        echo "!!! ERROR: $CATEGORY/$PF failed." >&2
        echo "!!! Function $funcname, Line $lineno, Exitcode $exitcode" >&2
        echo "!!! ${*:-(no error message)}" >&2
        echo "!!! If you need support, post the topmost build error, NOT this status message." >&2
        echo >&2
        exit 1
}

killparent() {
	trap INT
	kill ${PORTAGE_MASTER_PID}
}

hasq() {
        local x

        local me=$1
        shift

        # All the TTY checks really only help out depend. Which is nice.
        # Logging kills all this anyway. Everything becomes a pipe. --NJ
        for x in "$@"; do
                if [ "${x}" == "${me}" ]; then
                        return 0
                fi
        done
        return 1
}

hasv() {
	if hasq "$@"; then
		echo "${1}"
		return 0
	fi
	return 1
}

#if no perms are specified, dirs/files will have decent defaults
#(not secretive, but not stupid)
umask 022

# the sandbox is disabled by default except when overridden in the relevant stages
export SANDBOX_ON="0"

gen_filter() {
	if [ "$#" == 0 ]; then 
		#default param to keep things quiet
		echo 
		return
	fi
	echo -n '('
	while [ "$1" ]; do
		echo -n "$1"
		shift
		if [ "$1" ]; then
			echo -n '|'
		fi
	done
	echo -n ')'
}

sleepbeep() {
	if [ ! "$#" -lt 3 ] || [ ! "$#" -gt 0 ]; then
		echo "sleepbeep requires one arg- number of beeps"
		echo "additionally, can supply a 2nd arg- interval between beeps (defaults to 0.25s"
		die "invalid call to sleepbeep"
	fi
	local count=$(($1))
	local interval="${2:-0.25}"
	while [ $count -gt 0 ]; do
		echo -en "\a";
		sleep $interval &> /dev/null
		count=$(($count - 1))
	done
	return 0
}

# basically this runs through the output of export/readonly/declare, properly handling variables w/ values that have newline.
# nothing to it :)
get_vars() {
	local l
	if [ "${portage_old_IFS:-unset}" != "unset" ]; then
		local portage_old_IFS
	fi
	save_IFS
	IFS=''
	while read l; do
		l="${l/=*}"
		echo "${l##* }"
	done
	restore_IFS
}

dump_environ() {
	local f x;
	debug-print "dumping env"
	declare | {
		while read -r f && [ "${f#[^= ]* *\(\)}" == "$f" ]; do
			echo "$f"
		done;
#		echo "stopped on $f" >&2
	} | egrep -v "^$(gen_filter ${DONT_EXPORT_VARS} f x y old_IFS)=";

	save_IFS

	#can't just use which --read-functions, see bug #55522
#	echo "func_filter=$(gen_filter ${DONT_EXPORT_FUNCS} )" >&2
	declare -F | egrep -v " $(gen_filter ${DONT_EXPORT_FUNCS} )\$" | { 
		while read f; do
			IFS=''
#			echo "type '${f##* }'" >&2
			type "${f##* }" | {
				#nuke the first line, which is "blah is a function"
				read -r l
				while read -r l; do
					echo "$l"
				done
			}
			unset IFS
		done;
	}

	restore_IFS
	
	if ! hasq "--no-attributes" "$@"; then
		echo "reinstate_loaded_env_attributes ()"
		echo "{"

#		x=`export | egrep -o '^declare +-[airtx]+ +[^=]+' | cut -s -d ' ' -f 3 | egrep -v "^$(gen_filter ${DONT_EXPORT_VARS} f x y)$"`
#		x=`export | cut -s -d '=' -f 1 | cut -s -d ' ' -f 3 | egrep -v "^$(gen_filter ${DONT_EXPORT_VARS} f x y)$"`
		x=$(export | get_vars | egrep -v "$(gen_filter ${DONT_EXPORT_VARS} f x y)$")
		[ ! -z "$x" ] && echo "    export `echo $x`"
		

#		x=`readonly | egrep -o '^declare +-[airtx]+ +[^=]+'| cut -s -d ' ' -f 3 | egrep -v "^$(gen_filter ${DONT_EXPORT_VARS} f x y)$"`
#		x=`readonly | cut -s -d '=' -f 1 | cut -s -d ' ' -f 3 | egrep -v "^$(gen_filter ${DONT_EXPORT_VARS} f x y)$"`
		x=$(readonly | get_vars | egrep -v "$(gen_filter ${DONT_EXPORT_VARS} f x y)")
		[ ! -z "$x" ] && echo "    readonly `echo $x`"
		

#		x=`declare -i | egrep -o '^declare +-[airtx]+ +[^=]+' | cut -s -d ' ' -f 3 | egrep -v "$(gen_filter ${DONT_EXPORT_VARS} f x y)$"`
#		x=`declare -i | cut -s -d '=' -f 1 | cut -s -d ' ' -f 3 | egrep -v "$(gen_filter ${DONT_EXPORT_VARS} f x y)$"`
		x=$(declare -i | get_vars | egrep -v "$(gen_filter ${DONT_EXPORT_VARS} f x y)")
		[ ! -z "$x" ] && echo "    declare -i `echo $x`"

		declare -F | egrep "^declare -[aFfirtx]+ $(gen_filter ${f} )\$" | egrep -v "^declare -f "
		shopt -p
		echo "    unset reinstate_loaded_env_attributes"
		echo "}"
	fi
	
	debug-print "dumped"
	if [ ! -z ${DEBUGGING} ]; then
		echo "#dumping debug info"
		echo "#var filter..."
		echo "#$(gen_filter ${DONT_EXPORT_VARS} f x | sort)"
		echo "#func filter..."
		echo "#$(gen_filter ${DONT_EXPORT_FUNCS} | sort)"
		echo "#DONT_EXPORT_VARS follow"
		for x in `echo $DONT_EXPORT_VARS | sort`; do
			echo "#    $x";
		done
		echo ""
		echo "#DONT_EXPORT_FUNCS follow"
		for x in `echo $DONT_EXPORT_FUNCS | sort`; do
			echo "#    $x";
		done
	fi
}

#selectively saves  the environ- specifically removes things that have been marked to not be exported.
export_environ() {
#	echo "exporting env for ${EBUILD_PHASE}" >&2
	local temp_umask
	if [ "${1:-unset}" == "unset" ]; then
		die "export_environ requires at least one arguement"
	fi
	#the spaces on both sides are important- otherwise, the later ${DONT_EXPORT_VARS/ temp_umask /} won't match.
	#we use spaces on both sides, to ensure we don't remove part of a variable w/ the same name- 
	# ex: temp_umask_for_some_app == _for_some_app.  
	#Do it with spaces on both sides.

	DONT_EXPORT_VARS="${DONT_EXPORT_VARS} temp_umask "
	temp_umask=`umask`
	umask 0002

	debug-print "exporting env for ${EBUILD_PHASE} to $1, using optional post-processor '${2:-none}'"

	if [ "${2:-unset}" == "unset" ]; then
		dump_environ > "$1"
	else
		dump_environ | $2 > "$1"
	fi
	chown portage:portage "$1" &>/dev/null
	chmod 0664 "$1" &>/dev/null

	DONT_EXPORT_VARS="${DONT_EXPORT_VARS/ temp_umask /}"

	umask $temp_umask
	debug-print "exported."
}

load_environ() {
	local src e
	#protect the exterior env to some degree from older saved envs, where *everything* was dumped (no filters applied)
	local SANDBOX_STATE=$SANDBOX_ON
	local EBUILD_PHASE=$EBUILD_PHASE
	SANDBOX_ON=0
	SANDBOX_READ="/bin:${SANDBOX_READ}:/dev/urandom:/dev/random:/usr/lib/portage/bin/"
	SANDBOX_ON=$SANDBOX_STATE

	if [ ! -z $DEBUGGING ]; then
		echo "loading env for $EBUILD_PHASE" >&2
	fi

	if [ -n "$1" ]; then
		src="$1"
#	elif [ "${PORT_ENV_FILE:-unset}" != "unset" ]; then
#		src="$PORT_ENV_FILE"
#	else
#		if [ -f "${T}/environment" ]; then
#			src="${T}/environment"
#		else
#			die "unable to find a valid env. to reload; tried ${T}/environment, but it doesn't exist."
#			return 1
#		fi
		local c=COMPLETED_EBUILD_PHASES
		COMPLETED_EBUILD_PHASES="`cat ${BUILDDIR}/.completed_stages 2> /dev/null`"
		[ -z "$COMPLETED_EBUILD_PHASES" ] && COMPLETED_EBUILD_PHASES="$c"
#		echo "COMPLETED_EBUILD_PHASE loaded=${COMPLETED_EBUILD_PHASES}" >&2
	fi
	[ ! -z $DEBUGGING ] && echo "loading environment from $src" >&2
	if [ -f "$src" ]; then
		eval "$({ [ "${src%.bz2}" != "${src}" ] && bzcat "$src" || cat "${src}"
			} | egrep -v "^$(gen_filter $DONT_EXPORT_VARS)=")"
	else
		echo "ebuild=${EBUILD}, phase $EBUILD_PHASE" >&2
#		echo "dir=`ls ${EBUILD%/*}`" >&2
#		die "wth, load_environ called yet $src doesn't exist.  phase=${EBUILD_PHASE}"
		return 1
	fi
	if [ -f "${BUILDDIR}/.completed_stages" ]; then
		COMPLETED_EBUILD_PHASES=`cat ${BUILDDIR}/.completed_stages`
	else
		COMPLETED_EBUILD_PHASES=''
	fi
	return 0
}

source_profiles() {
	#this may belong being stored w/ the ebuild.  Not sure.
	local dir
	save_IFS
	IFS=$'\n'
	for dir in ${PROFILE_PATHS}; do
		if [ -f "${dir}/profile.bashrc" ]; then
			source "${dir}/profile.bashrc"
		fi
	done
	restore_IFS
	if [ -f "$PORTAGE_BASHRC" ]; then
		source "$PORTAGE_BASHRC"
	fi
}

init_environ() {
#	echo "initializating environment" >&2
	OCC="$CC"
	OCXX="$CXX"


	export PATH="/sbin:/usr/sbin:/usr/lib/portage/bin:/bin:/usr/bin${ROOTPATH:+:${ROOTPATH}}"
	if [ "${EBUILD_PHASE}" == "setup" ]; then
		#we specifically save the env so it's not stomped on by sourcing.
		#bug 51552
		dump_environ --no-attributes > "${T}/.temp_env"

		if [ "$USERLAND" == "GNU" ]; then
			local PORTAGE_SHIFTED_PATH="$PATH"
			source /etc/profile.env &>/dev/null
			PATH="${PORTAGE_SHIFTED_PATH:+${PORTAGE_SHIFTED_PATH}}${PATH:+:${PATH}}"
		fi
		#shift path.  I don't care about 51552, I'm not using the env's supplied path, alright? :)

		#restore the saved env vars.
		if ! load_environ "${T}/.temp_env"; then
			#this shouldn't happen.
			die "failed to load ${T}/.tmp_env- fs is readonly?"
		fi

		rm "${T}/.temp_env"
		source_profiles
	fi

	if [ "${EBUILD_PHASE}" != "depend" ]; then
		[ ! -z "$OCC" ] && export CC="$OCC"
		[ ! -z "$OCXX" ] && export CXX="$OCXX"

	fi

	[ ! -z "$PREROOTPATH" ] && export PATH="${PREROOTPATH%%:}:$PATH"


	export DESTTREE=/usr
	export INSDESTTREE=""
	export EXEDESTTREE=""
	export DOCDESTTREE=""
	export INSOPTIONS="-m0644"
	export EXEOPTIONS="-m0755"	
	export LIBOPTIONS="-m0644"
	export DIROPTIONS="-m0755"
	export MOPREFIX=${PN}

#	echo "srcing funcs"
	if [ "$DAEMONIZED" != "yes" ]; then
		source "/usr/lib/portage/bin/ebuild-functions.sh" || die "failed sourcing ebuild-functions.sh"
	fi
	SANDBOX_ON="1"
	export S=${WORKDIR}/${P}

	# Expand KEYWORDS
	# We need to turn off pathname expansion for -* in KEYWORDS and 
	# we need to escape ~ to avoid tilde expansion (damn bash) :)
	set -f
	KEYWORDS="$(echo ${KEYWORDS//~/\\~})"
	set +f

	unset   IUSE   DEPEND   RDEPEND   CDEPEND   PDEPEND
	unset E_IUSE E_DEPEND E_RDEPEND E_CDEPEND E_PDEPEND

	if [ ! -f "${EBUILD}" ]; then
		echo "bailing, ebuild not found"
		die "EBUILD=${EBUILD}; problem is, it doesn't exist.  bye." >&2
	fi
#	eval "$(cat "${EBUILD}"; echo ; echo 'true')" || die "error sourcing ebuild"
	source "${EBUILD}"
	if [ "${EBUILD_PHASE}" != "depend" ]; then
		RESTRICT="${PORTAGE_RESTRICT}"
		unset PORTAGE_RESTRICT
	fi

	[ -z "${ERRORMSG}" ] || die "${ERRORMSG}"

	hasq nostrip ${RESTRICT} && export DEBUGBUILD=1

	#a reasonable default for $S
	if [ "$S" = "" ]; then
		export S=${WORKDIR}/${P}
	fi

	#some users have $TMP/$TMPDIR to a custom dir in their home ...
	#this will cause sandbox errors with some ./configure
	#scripts, so set it to $T.
	export TMP="${T}"
	export TMPDIR="${T}"

	# Note: this next line is not the same as export RDEPEND=${RDEPEND:-${DEPEND}}
	# That will test for unset *or* NULL ("").  We want just to set for unset...

	#turn off glob expansion from here on in to prevent *'s and ? in the DEPEND
	#syntax from getting expanded :)  Fixes bug #1473
#	set -f
	if [ "${RDEPEND-unset}" == "unset" ]; then
		export RDEPEND="${DEPEND}"
		debug-print "RDEPEND: not set... Setting to: ${DEPEND}"
	fi

	#add in dependency info from eclasses
	IUSE="$IUSE $E_IUSE"
	DEPEND="${DEPEND} ${E_DEPEND}"
	RDEPEND="$RDEPEND $E_RDEPEND"
	CDEPEND="$CDEPEND $E_CDEPEND"
	PDEPEND="$PDEPEND $E_PDEPEND"

	unset E_IUSE E_DEPEND E_RDEPEND E_CDEPEND E_PDEPEND
#	set +f

#	declare -r DEPEND RDEPEND SLOT SRC_URI RESTRICT HOMEPAGE LICENSE DESCRIPTION
#	declare -r KEYWORDS INHERITED IUSE CDEPEND PDEPEND PROVIDE
	COMPLETED_EBUILD_PHASES=''
#	echo "DONT_EXPORT_FUNCS=$DONT_EXPORT_FUNCS" >&2
}

source "/usr/lib/portage/bin/ebuild-default-functions.sh" || die "failed sourcing ebuild-default-functions.sh"
source "/usr/lib/portage/bin/isolated-functions.sh" || die "failed sourcing stripped down functions.sh"

execute_phases() {
	local ret
	for myarg in $*; do
		EBUILD_PHASE="$myarg"
		MUST_EXPORT_ENV="no"
		case $EBUILD_PHASE in
		nofetch)
			init_environ
			pkg_nofetch
			;;
		prerm|postrm|preinst|postinst|config)
			export SANDBOX_ON="0"

			if ! load_environ $PORT_ENV_FILE; then
				#hokay.  this sucks.
				ewarn 
				ewarn "failed to load env"
				ewarn "this installed pkg may not behave correctly"
				ewarn
				sleepbeep 10
			fi	

			if type reinstate_loaded_env_attributes &> /dev/null; then
				reinstate_loaded_env_attributes
			fi
			[ "$PORTAGE_DEBUG" == "1" ] && set -x
			type -p pre_pkg_${EBUILD_PHASE} &> /dev/null && pre_pkg_${EBUILD_PHASE}
			if type -p dyn_${EBUILD_PHASE}; then
				dyn_${EBUILD_PHASE}
			else
				pkg_${EBUILD_PHASE}
			fi
			ret=0
			type -p post_pkg_${EBUILD_PHASE} &> /dev/null && post_pkg_${EBUILD_PHASE}
			[ "$PORTAGE_DEBUG" == "1" ] && set +x
			;;
		clean)
			einfo "clean phase is now handled in the python side of portage."
			einfo "ebuild-daemon calls it correctly, upgrading from vanilla portage to ebd" 
			einfo "always triggers this though.  Please ignore it."
			;;
#			if [ "${SANDBOX_DISABLED="0"}" == "0" ]; then
#				export SANDBOX_ON="1"
#			else
#				export SANDBOX_ON="0"
#			fi
#
#			trap "killparent" INT
#
#			init_environ
#	
#			trap - INT
#			unset killparent
#
#			if [ "$PORTAGE_DEBUG" != "1" ]; then
#				dyn_${EBUILD_PHASE}
#				#Allow non-zero return codes since they can be caused by &&
#			else
#				set -x
#				dyn_${EBUILD_PHASE}
#				#Allow non-zero return codes since they can be caused by &&
#				set +x
#			fi
#			export SANDBOX_ON="0"
#			MUST_EXPORT_ENV="no"
#			unset COMPLETED_EBUILD_PHASES
#			;;
		unpack|compile|test|install)
			if [ "${SANDBOX_DISABLED="0"}" == "0" ]; then
				export SANDBOX_ON="1"
			else
				export SANDBOX_ON="0"
			fi

			if ! load_environ ${T}/environment; then
				ewarn 
				ewarn "failed to load env.  This is bad, bailing."
				die "unable to load saved env for phase $EBUILD_PHASE, unwilling to continue"
			fi
			if type reinstate_loaded_env_attributes &> /dev/null; then
#				echo "reinstating attribs" >&2
				reinstate_loaded_env_attributes
			fi
			[ "$PORTAGE_DEBUG" == "1" ] && set -x
			type -p pre_src_${EBUILD_PHASE} &> /dev/null && pre_src_${EBUILD_PHASE}
			dyn_${EBUILD_PHASE}
			ret=0
			type -p post_src_${EBUILD_PHASE} &> /dev/null && post_src_${EBUILD_PHASE}
			[ "$PORTAGE_DEBUG" == "1" ] && set +x
			COMPLETED_EBUILD_PHASES="${COMPLETED_EBUILD_PHASES} ${EBUILD_PHASE}"
			export SANDBOX_ON="0"
			;;
		setup)
			#pkg_setup needs to be out of the sandbox for tmp file creation;
			#for example, awking and piping a file in /tmp requires a temp file to be created
			#in /etc.  If pkg_setup is in the sandbox, both our lilo and apache ebuilds break.

			export SANDBOX_ON="0"

			temp_ebuild_phase=`cat "${BUILDDIR}/.completed_stages" 2> /dev/null`
#			echo "temp_ebuild_phase=$temp_ebuild_phase"
			if hasq setup ${temp_ebuild_phase}; then
				unset temp_ebuild_phase
				MUST_EXPORT_ENV="no"
			else
				unset temp_ebuild_phase
				init_environ
				MUST_EXPORT_ENV="yes"

				[ "$PORTAGE_DEBUG" == "1" ] && set -x
				type -p pre_pkg_${EBUILD_PHASE} &> /dev/null && pre_pkg_${EBUILD_PHASE}
				dyn_${EBUILD_PHASE}
				ret=0;
				type -p post_pkg_${EBUILD_PHASE} &> /dev/null && post_pkg_${EBUILD_PHASE}
				[ "$PORTAGE_DEBUG" == "1" ] && set +x

				if hasq distcc ${FEATURES} &>/dev/null; then
					if [ -d /usr/lib/distcc/bin ]; then
						#We can enable distributed compile support
						if [ -z "${PATH/*distcc*/}" ]; then
							# Remove the other reference.
							remove_path_entry "distcc"
						fi
						export PATH="/usr/lib/distcc/bin:${PATH}"
						[ ! -z "${DISTCC_LOG}" ] && addwrite "$(dirname ${DISTCC_LOG})"
					elif type -p distcc &>/dev/null; then
						export CC="distcc $CC"
						export CXX="distcc $CXX"
					fi
				fi

				if hasq ccache ${FEATURES} &>/dev/null; then
					#We can enable compiler cache support
					if [ -z "${PATH/*ccache*/}" ]; then
						# Remove the other reference.
						remove_path_entry "ccache"
					fi

					if [ -d /usr/lib/ccache/bin ]; then
						export PATH="/usr/lib/ccache/bin:${PATH}"
					elif [ -d /usr/bin/ccache ]; then
						export PATH="/usr/bin/ccache:${PATH}"
					fi

					[ -z "${CCACHE_DIR}" ] && export CCACHE_DIR="/root/.ccache"

					addread "${CCACHE_DIR}"
					addwrite "${CCACHE_DIR}"

					[ -z "${CCACHE_SIZE}" ] && export CCACHE_SIZE="2G"
					ccache -M ${CCACHE_SIZE} &> /dev/null
				fi
			fi
			COMPLETED_EBUILD_PHASES="${COMPLETED_EBUILD_PHASES} ${EBUILD_PHASE}"
			;;

	
		help)
			#pkg_setup needs to be out of the sandbox for tmp file creation;
			#for example, awking and piping a file in /tmp requires a temp file to be created
			#in /etc.  If pkg_setup is in the sandbox, both our lilo and apache ebuilds break.

			init_environ
			export SANDBOX_ON="1"

			[ "$PORTAGE_DEBUG" == "1" ] && set -x
			type -p pre_pkg_${EBUILD_PHASE} &> /dev/null && pre_pkg_${EBUILD_PHASE}
			dyn_${EBUILD_PHASE}
			ret=0
			type -p post_pkg_${EBUILD_PHASE} &> /dev/null && post_pkg_${EBUILD_PHASE}
			[ "$PORTAGE_DEBUG" == "1" ] && set +x

			COMPLETED_EBUILD_PHASES="${COMPLETED_EBUILD_PHASES} ${EBUILD_PHASE}"
			;;
		package|rpm)
			export SANDBOX_ON="0"

			if ! load_environ ${T}/environment; then
				ewarn 
				ewarn "unable to load saved env for phase $EBUILD_PHASE"
				ewarn "attempting to continue, although this could result in a broken/invalid"
				ewarn "rpm/binpkg"
				sleepbeep 10
			fi

			if type reinstate_loaded_env_attributes &> /dev/null; then
				reinstate_loaded_env_attributes
			fi

			[ "$PORTAGE_DEBUG" == "1" ] && set -x
			type -p pre_pkg_${EBUILD_PHASE} &> /dev/null && pre_pkg_${EBUILD_PHASE}
			dyn_${EBUILD_PHASE}
			ret=0
			type -p post_pkg_${EBUILD_PHASE} &> /dev/null && post_pkg_${EBUILD_PHASE}
			[ "$PORTAGE_DEBUG" == "1" ] && set +x

			COMPLETED_EBUILD_PHASES="${COMPLETED_EBUILD_PHASES} ${EBUILD_PHASE}"
			;;
		depend)
			SANDBOX_ON="0"
			MUST_EXPORT_ENV="no"
#			echo "hidey ho biznitch"

			trap 'killparent' INT
			if [ -z "$QA_CONTROLLED_EXTERNALLY" ]; then
				enable_qa_interceptors
			fi

			init_environ

			if [ -z "$QA_CONTROLLED_EXTERNALLY" ]; then
				disable_qa_interceptors
			fi
			trap - INT

			set -f
			speak 'sending_keys'
			[ "${DEPEND:-unset}" != "unset" ] && 		speak "DEPEND=$(echo $DEPEND)"
			[ "${RDEPEND:-unset}" != "unset" ] && 		speak "RDEPEND=$(echo $RDEPEND)"
			[ "$SLOT:-unset}" != "unset" ] && 		speak "SLOT=$(echo $SLOT)"
			[ "$SRC_URI:-unset}" != "unset" ] && 		speak "SRC_URI=$(echo $SRC_URI)"
			[ "$RESTRICT:-unset}" != "unset" ] && 		speak "RESTRICT=$(echo $RESTRICT)"
			[ "$HOMEPAGE:-unset}" != "unset" ] && 		speak "HOMEPAGE=$(echo $HOMEPAGE)"
			[ "$LICENSE:-unset}" != "unset" ] && 		speak "LICENSE=$(echo $LICENSE)"
			[ "$DESCRIPTION:-unset}" != "unset" ] && 	speak "DESCRIPTION=$(echo $DESCRIPTION)"
			[ "$KEYWORDS:-unset}" != "unset" ] && 		speak "KEYWORDS=$(echo $KEYWORDS)"
			[ "$INHERITED:-unset}" != "unset" ] && 		speak "INHERITED=$(echo $INHERITED)"
			[ "$IUSE:-unset}" != "unset" ] && 		speak "IUSE=$(echo $IUSE)"
			[ "$CDEPEND:-unset}" != "unset" ] && 		speak "CDEPEND=$(echo $CDEPEND)"
			[ "$PDEPEND:-unset}" != "unset" ] && 		speak "PDEPEND=$(echo $PDEPEND)"
			[ "$PROVIDE:-unset}" != "unset" ] && 		speak "PROVIDE=$(echo $PROVIDE)"
			speak 'end_keys'
			set +f
			;;
		*)
			export SANDBOX_ON="1"
			echo "Please specify a valid command: $EBUILD_PHASE isn't valid."
			echo
			dyn_help
			exit 1
			;;
		esac

		cd ${BUILDDIR} &> /dev/null
		if [ "${MUST_EXPORT_ENV}" == "yes" ]; then
#			echo "exporting environ ${EBUILD_PHASE} to ${T}/environment" >&2
			export_environ "${T}/environment"
			list=''
			for x in ${COMPLETED_EBUILD_PHASES}; do
				if ! hasq $x $list; then
					list="${list} ${x}"
				fi
			done
			COMPLETED_EBUILD_PHASES="${list}"
			unset list
			echo "$COMPLETED_EBUILD_PHASES" > "${BUILDDIR}/.completed_stages"
			chown portage:portage "${BUILDDIR}/.completed_stages" &> /dev/null
			chmod g+w "${BUILDDIR}/.completed_stages" &> /dev/null
			MUST_EXPORT_ENV="no"
		fi
	done
	return ${ret:-0}
}

#echo, everything has been sourced.  now level the read-only's.
for x in ${DONT_EXPORT_FUNCS}; do
	declare -fr "$x"
done

f="$(declare | { 
	read l; 
	while [ "${l% \(\)}" == "$l" ]; do
		echo "${l/=*}";
		read l;
	done;
#	echo "bailing at '$l'" >&2
	unset l
   })"

if [ -z "${ORIG_VARS}" ]; then
	DONT_EXPORT_VARS="${DONT_EXPORT_VARS} ${f}"
else
#	echo "f=$f"
#	echo "prior dont_export_vars='`echo $DONT_EXPORT_VARS`'"
	DONT_EXPORT_VARS="${DONT_EXPORT_VARS} $(echo "${f}" | egrep -v "^`gen_filter ${ORIG_VARS}`\$")"
#	echo "after dont_export_vars='`echo $DONT_EXPORT_VARS`'"
fi
unset f
                 
if [ -z "${ORIG_FUNCS}" ]; then
	DONT_EXPORT_FUNCS="${DONT_EXPORT_FUNCS} $(declare -F | cut -s -d ' ' -f 3)"
else  
#	DONT_EXPORT_FUNCS="${DONT_EXPORT_FUNCS} $(declare -F | cut -s -d ' ' -f 3 | egrep -v \"^`gen_filter ${ORIG_FUNCS}`\$\")"
	DONT_EXPORT_FUNCS="${DONT_EXPORT_FUNCS} $(declare -F | cut -s -d ' ' -f 3 )"
fi
set +f

export XARGS
if [ `id -nu` == "portage" ] ; then
	export USER=portage
fi
set +H -h
if [ "$*" != "daemonize" ]; then
#	echo "yo.  whats up?"
#	echo "ebuild=$EBUILD; non-daemonize"

	if [ "${*/depend}" != "$*" ]; then
		speak() {
			echo "$*" >&4
		}
		declare -rf speak
	fi
	if [ -z "${NOCOLOR}" ]; then
		set_colors
	else
		unset_colors
	fi
	execute_phases $*
	exit 0
else
	DAEMONIZED="yes"
	export DAEMONIZED
	readonly DAEMONIZED
fi
true
