# portage: Lock management code
# Copyright 2004-2004 Gentoo Foundation
# Distributed under the GNU Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/portage_locks.py,v 1.1 2004/08/15 05:33:57 carpaski Exp $

def lockdir(mydir):
	return lockfile(mydir,wantnewlockfile=1)
def unlockdir(mylock):
	return unlockfile(mylock)

def lockfile(mypath,wantnewlockfile=0,unlinkfile=0):
	"""Creates all dirs upto, the given dir. Creates a lockfile
	for the given directory as the file: directoryname+'.portage_lockfile'."""
	import fcntl

	if not mypath:
		raise portage_exception.InvalidData, "Empty path given"

	if type(mypath) == types.StringType and mypath[-1] == '/':
		mypath = mypath[:-1]

	if type(mypath) == types.FileType:
		mypath = mypath.fileno()
	if type(mypath) == types.IntType:
		lockfilename    = mypath
		wantnewlockfile = 0
		unlinkfile      = 0
	elif wantnewlockfile:
		lockfilename = mypath+".portage_lockfile"
		unlinkfile   = 1
	else:
		lockfilename = mypath
	
	if type(mypath) == types.StringType:
		if not os.path.exists(os.path.dirname(mypath)):
			raise portage_exception.DirectoryNotFound, os.path.dirname(mypath)
		if not os.path.exists(lockfilename):
			old_mask=os.umask(000)
			myfd = os.open(lockfilename, os.O_CREAT|os.O_RDWR,0660)
			if os.stat(lockfilename).st_gid != portage_gid:
				os.chown(lockfilename,os.getuid(),portage_gid)
			os.umask(old_mask)
		else:
			myfd = os.open(lockfilename, os.O_CREAT|os.O_WRONLY,0660)

	elif type(mypath) == types.IntType:
		myfd = mypath

	else:
		raise ValueError, "Unknown type passed in '%s': '%s'" % (type(mypath),mypath)

	#try for a non-blocking lock, if it's held, throw a message we're waiting on lockfile and use a blocking attempt.
	try:
		fcntl.flock(myfd,fcntl.LOCK_EX|fcntl.LOCK_NB)

	except IOError, ie:

		# 11 == resource temp unavailable; eg, someone beat us to the lock.
		if ie.errno == 11:
			if type(mypath) == types.IntType:
				print "waiting for lock on fd %i" % myfd
			else:
				print "waiting for lock on %s" % lockfilename
			# try for the exclusive lock now.
			fcntl.flock(myfd,fcntl.LOCK_EX)
		else:
			raise ie
				
	if type(lockfilename) == types.StringType and not os.path.exists(lockfilename):
		# The file was deleted on us... Keep trying to make one...
		os.close(myfd)
		writemsg("lockfile recurse\n",1)
		lockfilename,myfd,unlinkfile = lockfile(mypath,wantnewlockfile,unlinkfile)

	writemsg(str((lockfilename,myfd,unlinkfile))+"\n",1)
	return (lockfilename,myfd,unlinkfile)

def unlockfile(mytuple):
	import fcntl

	lockfilename,myfd,unlinkfile = mytuple
	
	if type(lockfilename) == types.StringType and not os.path.exists(lockfilename):
		writemsg("lockfile does not exist '%s'\n" % lockfile,1)
		return None

	try:
		if myfd == None:
			myfd = os.open(lockfilename, os.O_WRONLY,0660)
			unlinkfile = 1
		fcntl.flock(myfd,fcntl.LOCK_UN)
	except Exception, e:
		raise IOError, "Failed to unlock file '%s'\n" % lockfilename

	try:
		fcntl.flock(myfd,fcntl.LOCK_EX|fcntl.LOCK_NB)
		# We won the lock, so there isn't competition for it.
		# We can safely delete the file.
		writemsg("Got the lockfile...\n",1)
		if unlinkfile:
			#writemsg("Unlinking...\n")
			os.unlink(lockfilename)
			writemsg("Unlinked lockfile...\n",1)
		fcntl.flock(myfd,fcntl.LOCK_UN)
	except Exception, e:
		# We really don't care... Someone else has the lock.
		# So it is their problem now.
		writemsg("Failed to get lock... someone took it.\n",1)
		writemsg(str(e)+"\n",1)
		pass
	# why test lockfilename?  because we may have been handed an fd originally, and the caller might not like having their
	# open fd closed automatically on them.
	if type(lockfilename) == types.StringType:
		os.close(myfd)
			
	return 1
