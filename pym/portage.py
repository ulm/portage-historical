# portage.py -- core Portage functionality
# Copyright 1998-2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/portage.py,v 1.542 2004/11/07 13:37:57 ferringb Exp $

# ===========================================================================
# START OF CONSTANTS -- START OF CONSTANTS -- START OF CONSTANTS -- START OF
# ===========================================================================

VERSION="20040626"

INCREMENTALS=["USE","FEATURES","ACCEPT_KEYWORDS","ACCEPT_LICENSE","CONFIG_PROTECT_MASK","CONFIG_PROTECT","PRELINK_PATH","PRELINK_PATH_MASK"]
incrementals=INCREMENTALS
STICKIES=["KEYWORDS_ACCEPT","USE","CFLAGS","CXXFLAGS","MAKEOPTS","EXTRA_ECONF","EXTRA_EINSTALL","EXTRA_EMAKE"]
stickies=STICKIES


# ===========================================================================
# START OF IMPORTS -- START OF IMPORTS -- START OF IMPORTS -- START OF IMPORT
# ===========================================================================


try:
	import sys
except SystemExit, e:
	raise
except:
	print "Failed to import sys! Something is _VERY_ wrong with python."
	raise SystemExit, 127

try:
	import os,string,types,atexit,signal,fcntl
	import time,cPickle,traceback,copy
	import re,pwd,grp
	import shlex,shutil
	from orig_dict_cache import cacheddir
	import stat
	from time import sleep
	from random import shuffle
except SystemExit, e:
	raise
except Exception, e:
	sys.stderr.write("\n\n")
	sys.stderr.write("!!! Failed to complete python imports. There are internal modules for\n")
	sys.stderr.write("!!! python and failure here indicates that you have a problem with python\n")
	sys.stderr.write("!!! itself and thus portage is no able to continue processing.\n\n")

	sys.stderr.write("!!! You might consider starting python with verbose flags to see what has\n")
	sys.stderr.write("!!! gone wrong. Here is the information we got for this exception:\n")
	
	sys.stderr.write("    "+str(e)+"\n\n");
	sys.exit(127)
except:
	sys.stderr.write("\n\n")
	sys.stderr.write("!!! Failed to complete python imports. There are internal modules for\n")
	sys.stderr.write("!!! python and failure here indicates that you have a problem with python\n")
	sys.stderr.write("!!! itself and thus portage is no able to continue processing.\n\n")

	sys.stderr.write("!!! You might consider starting python with verbose flags to see what has\n")
	sys.stderr.write("!!! gone wrong. The exception was non-standard and we were unable to catch it.\n\n")
	sys.exit(127)


try:
	from portage_const import *
	import ebuild
	import cvstree
	import xpak
	import getbinpkg
	import portage_dep

	#assign these to portage's namespace to keep the esearch monkeys happy.
	catpkgsplit = portage_dep.catpkgsplit
	pkgsplit = portage_dep.pkgsplit

	# XXX: This needs to get cleaned up.
	# XXX: Output's color handling is mildly broken is a few cases.
	from output import *

	from portage_data import ostype, lchown, userland, secpass, uid, wheelgid, \
	                         portage_uid, portage_gid
	
	import portage_util
	from portage_util import grab_multiple, grabdict, grabdict_package, grabfile, grabfile_package, \
		grabints, map_dictlist_vals, pickle_read, pickle_write, stack_dictlist, stack_dicts, stack_lists, \
		unique_array, varexpand, writedict, writeints, writemsg, getconfig, movefile, flatten
	from portage_file import normpath
	import portage_exception
	import portage_gpg
	import portage_locks
	import portage_exec
	from portage_locks import unlockfile,unlockdir,lockfile,lockdir
	import portage_checksum
	from portage_checksum import perform_md5,perform_checksum,prelink_capable

	import transports.bundled_lib
	import transports.fetchcommand
except SystemExit, e:
	raise
except Exception, e:
	sys.stderr.write("\n\n")
	sys.stderr.write("!!! Failed to complete portage imports. There are internal modules for\n")
	sys.stderr.write("!!! portage and failure here indicates that you have a problem with your\n")
	sys.stderr.write("!!! installation of portage. Please try a rescue portage located in the\n")
	sys.stderr.write("!!! portage tree under '/usr/portage/sys-apps/portage/files/' (default).\n")
	sys.stderr.write("!!! There is a README.rescue file that details the steps required to perform\n")
	sys.stderr.write("!!! a recovery of portage.\n")
	
	sys.stderr.write("    "+str(e)+"\n\n")
	sys.exit(127)


# ===========================================================================
# END OF IMPORTS -- END OF IMPORTS -- END OF IMPORTS -- END OF IMPORTS -- END
# ===========================================================================


def exithandler(signum,frame):
	"""Handles ^C interrupts in a sane manner"""
	signal.signal(signal.SIGINT, signal.SIG_IGN)
	signal.signal(signal.SIGTERM, signal.SIG_IGN)

	# 0=send to *everybody* in process group
	print "caught %i in %i" % (signum, os.getpid())
	portageexit()
	print "Exiting due to signal"
	os.kill(0,signum)
	sys.exit(1)

signal.signal(signal.SIGCHLD, signal.SIG_DFL)
signal.signal(signal.SIGINT, exithandler)
signal.signal(signal.SIGTERM, exithandler)

def load_mod(name):
	modname = string.join(string.split(name,".")[:-1],".")
	mod = __import__(modname)
	components = name.split('.')
	for comp in components[1:]:
		mod = getattr(mod, comp)
	return mod

def best_from_dict(key, top_dict, key_order, EmptyOnError=1, FullCopy=1, AllowEmpty=1):
	for x in key_order:
		if top_dict.has_key(x) and top_dict[x].has_key(key):
			if FullCopy:
				return copy.deepcopy(top_dict[x][key])
			else:
				return top_dict[x][key]
	if EmptyOnError:
		return ""
	else:
		raise KeyError, "Key not found in list; '%s'" % key

def getcwd():
	"this fixes situations where the current directory doesn't exist"
	try:
		return os.getcwd()
	except SystemExit, e:
		raise
	except:
		os.chdir("/")
		return "/"
getcwd()

def abssymlink(symlink):
	"This reads symlinks, resolving the relative symlinks, and returning the absolute."
	mylink=os.readlink(symlink)
	if mylink[0] != '/':
		mydir=os.path.dirname(symlink)
		mylink=mydir+"/"+mylink
	return os.path.normpath(mylink)

def suffix_array(array,suffix,doblanks=1):
	"""Appends a given suffix to each element in an Array/List/Tuple.
	Returns a List."""
	if type(array) not in [types.ListType, types.TupleType]:
		raise TypeError, "List or Tuple expected. Got %s" % type(array)
	newarray=[]
	for x in array:
		if x or doblanks:
			newarray.append(x + suffix)
		else:
			newarray.append(x)
	return newarray

def prefix_array(array,prefix,doblanks=1):
	"""Prepends a given prefix to each element in an Array/List/Tuple.
	Returns a List."""
	if type(array) not in [types.ListType, types.TupleType]:
		raise TypeError, "List or Tuple expected. Got %s" % type(array)
	newarray=[]
	for x in array:
		if x or doblanks:
			newarray.append(prefix + x)
		else:
			newarray.append(x)
	return newarray

def listdir(mypath,
			recursive=False,
			filesonly=False,
			ignorecvs=False,
			ignorelist=[],
			EmptyOnError=False, 
			followSymlinks=True):

	list, ftype = cacheddir(mypath, ignorecvs, ignorelist, EmptyOnError,followSymlinks=followSymlinks)

	if list is None:
		list=[]
	if ftype is None:
		ftype=[]

	if not filesonly and not recursive:
		return list

	if recursive:
		x=0
		while x<len(ftype):
			if ftype[x]==1 and \
			   not (ignorecvs and (len(list[x])>=3) and (("/"+list[x][-3:])=="/CVS")) and \
				 not (ignorecvs and (len(list[x])>=4) and (("/"+list[x][-4:])=="/.svn")):

				l,f = cacheddir(mypath+"/"+list[x],
								  ignorecvs,
								  ignorelist,
								  EmptyOnError,
								  followSymlinks=followSymlinks)
								  
				l=l[:]
				for y in range(0,len(l)):
					l[y]=list[x]+"/"+l[y]
				list=list+l
				ftype=ftype+f
			x+=1
	if filesonly:
		rlist=[]
		for x in range(0,len(ftype)):
			if ftype[x]==0:
				rlist=rlist+[list[x]]
	else:
		rlist=list
			
	return rlist

starttime=long(time.time())
features=[]

def tokenize(mystring):
	"""breaks a string like 'foo? (bar) oni? (blah (blah))'
	into embedded lists; returns None on paren mismatch"""

	# This function is obsoleted.
	# Use dep_parenreduce

	newtokens=[]
	curlist=newtokens
	prevlists=[]
	level=0
	accum=""
	for x in mystring:
		if x=="(":
			if accum:
				curlist.append(accum)
				accum=""
			prevlists.append(curlist)
			curlist=[]
			level=level+1
		elif x==")":
			if accum:
				curlist.append(accum)
				accum=""
			if level==0:
				writemsg("!!! tokenizer: Unmatched left parenthesis in:\n'"+str(mystring)+"'\n")
				return None
			newlist=curlist
			curlist=prevlists.pop()
			curlist.append(newlist)
			level=level-1
		elif x in string.whitespace:
			if accum:
				curlist.append(accum)
				accum=""
		else:
			accum=accum+x
	if accum:
		curlist.append(accum)
	if (level!=0):
		writemsg("!!! tokenizer: Exiting with unterminated parenthesis in:\n'"+str(mystring)+"'\n")
		return None
	return newtokens

#beautiful directed graph object

class digraph:
	def __init__(self):
		self.dict={}
		#okeys = keys, in order they were added (to optimize firstzero() ordering)
		self.okeys=[]
	
	def addnode(self,mykey,myparent):
		if not self.dict.has_key(mykey):
			self.okeys.append(mykey)
			if myparent==None:
				self.dict[mykey]=[0,[]]
			else:
				self.dict[mykey]=[0,[myparent]]
				self.dict[myparent][0]=self.dict[myparent][0]+1
			return
		if myparent and (not myparent in self.dict[mykey][1]):
			self.dict[mykey][1].append(myparent)
			self.dict[myparent][0]=self.dict[myparent][0]+1
	
	def delnode(self,mykey):
		if not self.dict.has_key(mykey):
			return
		for x in self.dict[mykey][1]:
			self.dict[x][0]=self.dict[x][0]-1
		del self.dict[mykey]
		while 1:
			try:
				self.okeys.remove(mykey)	
			except ValueError:
				break
	
	def allnodes(self):
		"returns all nodes in the dictionary"
		return self.dict.keys()
	
	def firstzero(self):
		"returns first node with zero references, or NULL if no such node exists"
		for x in self.okeys:
			if self.dict[x][0]==0:
				return x
		return None

	def depth(self, mykey):
		depth=0
		while (self.dict[mykey][1]):
			depth=depth+1
			mykey=self.dict[mykey][1][0]
		return depth

	def allzeros(self):
		"returns all nodes with zero references, or NULL if no such node exists"
		zerolist = []
		for x in self.dict.keys():
			mys = string.split(x)
			if mys[0] != "blocks" and self.dict[x][0]==0:
				zerolist.append(x)
		return zerolist

	def hasallzeros(self):
		"returns 0/1, Are all nodes zeros? 1 : 0"
		zerolist = []
		for x in self.dict.keys():
			if self.dict[x][0]!=0:
				return 0
		return 1

	def empty(self):
		if len(self.dict)==0:
			return 1
		return 0

	def hasnode(self,mynode):
		return self.dict.has_key(mynode)

	def copy(self):
		mygraph=digraph()
		for x in self.dict.keys():
			mygraph.dict[x]=self.dict[x][:]
			mygraph.okeys=self.okeys[:]
		return mygraph

# valid end of version components; integers specify offset from release version
# pre=prerelease, p=patchlevel (should always be followed by an int), rc=release candidate
# all but _p (where it is required) can be followed by an optional trailing integer

endversion={"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}
# as there's no reliable way to set {}.keys() order
# netversion_keys will be used instead of endversion.keys
# to have fixed search order, so that "pre" is checked
# before "p"
endversion_keys = ["pre", "p", "alpha", "beta", "rc"]

#parse /etc/env.d and generate /etc/profile.env

#move this to config.
def env_update(root,makelinks=1):
	if not os.path.exists(root+"etc/env.d"):
		prevmask=os.umask(0)
		os.makedirs(root+"etc/env.d",0755)
		os.umask(prevmask)
	fns=listdir(root+"etc/env.d",EmptyOnError=1)
	fns.sort()
	pos=0
	while (pos<len(fns)):
		if len(fns[pos])<=2:
			del fns[pos]
			continue
		if (fns[pos][0] not in string.digits) or (fns[pos][1] not in string.digits):
			del fns[pos]
			continue
		pos=pos+1

	specials={
	  "KDEDIRS":[],"PATH":[],"CLASSPATH":[],"LDPATH":[],"MANPATH":[],
		"INFODIR":[],"INFOPATH":[],"ROOTPATH":[],"CONFIG_PROTECT":[],
		"CONFIG_PROTECT_MASK":[],"PRELINK_PATH":[],"PRELINK_PATH_MASK":[],
		"PYTHONPATH":[], "ADA_INCLUDE_PATH":[], "ADA_OBJECTS_PATH":[]
	}
	colon_separated = [
		"ADA_INCLUDE_PATH",  "ADA_OBJECTS_PATH",
		"LDPATH",            "MANPATH",
		"PATH",              "PRELINK_PATH",
		"PRELINK_PATH_MASK", "PYTHON_PATH"
	]
	
	env={}

	for x in fns:
		# don't process backup files
		if x[-1]=='~' or x[-4:]==".bak":
			continue
		myconfig=getconfig(root+"etc/env.d/"+x)
		if myconfig==None:
			writemsg("!!! Parsing error in "+str(root)+"etc/env.d/"+str(x)+"\n")
			#parse error
			continue
		# process PATH, CLASSPATH, LDPATH
		for myspec in specials.keys():
			if myconfig.has_key(myspec):
				if myspec in colon_separated:
					specials[myspec].extend(string.split(varexpand(myconfig[myspec]),":"))
				else:
					specials[myspec].append(varexpand(myconfig[myspec]))
				del myconfig[myspec]
		# process all other variables
		for myenv in myconfig.keys():
			env[myenv]=varexpand(myconfig[myenv])
			
	if os.path.exists(root+"etc/ld.so.conf"):
		myld=open(root+"etc/ld.so.conf")
		myldlines=myld.readlines()
		myld.close()
		oldld=[]
		for x in myldlines:
			#each line has at least one char (a newline)
			if x[0]=="#":
				continue
			oldld.append(x[:-1])
	#	os.rename(root+"etc/ld.so.conf",root+"etc/ld.so.conf.bak")
	# Where is the new ld.so.conf generated? (achim)
	else:
		oldld=None

	ld_cache_update=False
	if os.environ.has_key("PORTAGE_CALLER") and \
	   os.environ["PORTAGE_CALLER"] == "env-update":
		ld_cache_update = True
							 
	newld=specials["LDPATH"]
	if (oldld!=newld):
		#ld.so.conf needs updating and ldconfig needs to be run
		myfd=open(root+"etc/ld.so.conf","w")
		myfd.write("# ld.so.conf autogenerated by env-update; make all changes to\n")
		myfd.write("# contents of /etc/env.d directory\n")
		for x in specials["LDPATH"]:
			myfd.write(x+"\n")
		myfd.close()
		ld_cache_update=True

	# Update prelink.conf if we are prelink-enabled
	if prelink_capable:
		newprelink=open(root+"etc/prelink.conf","w")
		newprelink.write("# prelink.conf autogenerated by env-update; make all changes to\n")
		newprelink.write("# contents of /etc/env.d directory\n")
	
		for x in ["/bin","/sbin","/usr/bin","/usr/sbin","/lib","/usr/lib"]:
			newprelink.write("-l "+x+"\n");
		for x in specials["LDPATH"]+specials["PATH"]+specials["PRELINK_PATH"]:
			if not x:
				continue
			plmasked=0
			for y in specials["PRELINK_PATH_MASK"]:
				if y[-1]!='/':
					y=y+"/"
				if y==x[0:len(y)]:
					plmasked=1
					break
			if not plmasked:
				newprelink.write("-h "+x+"\n")
		for x in specials["PRELINK_PATH_MASK"]:
			newprelink.write("-b "+x+"\n")
		newprelink.close()

	if not mtimedb.has_key("ldpath"):
		mtimedb["ldpath"]={}

	for x in specials["LDPATH"]+['/usr/lib','/lib']:
		try:
			newldpathtime=os.stat(x)[stat.ST_MTIME]
		except SystemExit, e:
			raise
		except:
			newldpathtime=0
		if mtimedb["ldpath"].has_key(x):
			if mtimedb["ldpath"][x]==newldpathtime:
				pass
			else:
				mtimedb["ldpath"][x]=newldpathtime
				ld_cache_update=True
		else:
			mtimedb["ldpath"][x]=newldpathtime
			ld_cache_update=True

	if (ld_cache_update or makelinks):
		# We can't update links if we haven't cleaned other versions first, as
		# an older package installed ON TOP of a newer version will cause ldconfig
		# to overwrite the symlinks we just made. -X means no links. After 'clean'
		# we can safely create links.
		writemsg(">>> Regenerating "+str(root)+"etc/ld.so.cache...\n")
		cwd="/"
		try:	cwd=os.getcwd()
		except (OSError, IOError): pass
		if makelinks:
			portage_exec.spawn("/sbin/ldconfig -r "+root)
		else:
			portage_exec.spawn("/sbin/ldconfig -X -r "+root)
		try:	os.chdir(cwd)
		except OSError: pass
			
	del specials["LDPATH"]

	penvnotice  = "# THIS FILE IS AUTOMATICALLY GENERATED BY env-update.\n"
	penvnotice += "# DO NOT EDIT THIS FILE. CHANGES TO STARTUP PROFILES\n"
	cenvnotice  = penvnotice[:]
	penvnotice += "# GO INTO /etc/profile NOT /etc/profile.env\n\n"
	cenvnotice += "# GO INTO /etc/csh.cshrc NOT /etc/csh.env\n\n"

	#create /etc/profile.env for bash support
	outfile=open(root+"/etc/profile.env","w")
	outfile.write(penvnotice)

	for path in specials.keys():
		if len(specials[path])==0:
			continue
		outstring="export "+path+"='"
		if path in ["CONFIG_PROTECT","CONFIG_PROTECT_MASK"]:
			for x in specials[path][:-1]:
				outstring += x+" "
		else:
			for x in specials[path][:-1]:
				outstring=outstring+x+":"
		outstring=outstring+specials[path][-1]+"'"
		outfile.write(outstring+"\n")
	
	#create /etc/profile.env
	for x in env.keys():
		if type(env[x])!=types.StringType:
			continue
		outfile.write("export "+x+"='"+env[x]+"'\n")
	outfile.close()
	
	#create /etc/csh.env for (t)csh support
	outfile=open(root+"/etc/csh.env","w")
	outfile.write(cenvnotice)
	
	for path in specials.keys():
		if len(specials[path])==0:
			continue
		outstring="setenv "+path+" '"
		if path in ["CONFIG_PROTECT","CONFIG_PROTECT_MASK"]:
			for x in specials[path][:-1]:
				outstring += x+" "
		else:
			for x in specials[path][:-1]:
				outstring=outstring+x+":"
		outstring=outstring+specials[path][-1]+"'"
		outfile.write(outstring+"\n")
		#get it out of the way
		del specials[path]
	
	#create /etc/csh.env
	for x in env.keys():
		if type(env[x])!=types.StringType:
			continue
		outfile.write("setenv "+x+" '"+env[x]+"'\n")
	outfile.close()
	if os.path.exists(DEPSCAN_SH_BINARY):	
		spawn(DEPSCAN_SH_BINARY,settings,free=1)

def new_protect_filename(mydest, newmd5=None):
	"""Resolves a config-protect filename for merging, optionally
	using the last filename if the md5 matches.
	(dest,md5) ==> 'string'            --- path_to_target_filename
	(dest)     ==> ('next', 'highest') --- next_target and most-recent_target
	"""

	# config protection filename format:
	# ._cfg0000_foo
	# 0123456789012
	prot_num=-1
	last_pfile=""
		
	if (len(mydest) == 0):
		raise ValueError, "Empty path provided where a filename is required"
	if (mydest[-1]=="/"): # XXX add better directory checking
		raise ValueError, "Directory provided but this function requires a filename"
	if not os.path.exists(mydest):
		return mydest
		
	real_filename = os.path.basename(mydest)
	real_dirname  = os.path.dirname(mydest)
	for pfile in listdir(real_dirname):
		if pfile[0:5] != "._cfg":
			continue
		if pfile[10:] != real_filename:
			continue
		try:
			new_prot_num = int(pfile[5:9])
			if new_prot_num > prot_num:
				prot_num = new_prot_num
				last_pfile = pfile
		except SystemExit, e:
			raise
		except:
			continue
	prot_num = prot_num + 1

	new_pfile = os.path.normpath(real_dirname+"/._cfg"+string.zfill(prot_num,4)+"_"+real_filename)
	old_pfile = os.path.normpath(real_dirname+"/"+last_pfile)
	if last_pfile and newmd5:
		if portage_checksum.perform_md5(real_dirname+"/"+last_pfile) == newmd5:
			return old_pfile
		else:
			return new_pfile
	elif newmd5:
		return new_pfile
	else:
		return (new_pfile, old_pfile)

#XXX: These two are now implemented in portage_util.py but are needed here
#XXX: until the isvalidatom() dependency is sorted out.

def grabdict_package(myfilename,juststrings=0):
	pkgs=grabdict(myfilename, juststrings=juststrings, empty=1)
	for x in pkgs.keys():
		if not portage_dep.isvalidatom(x):
			del(pkgs[x])
			writemsg("--- Invalid atom in %s: %s\n" % (myfilename, x))
	return pkgs

def grabfile_package(myfilename,compatlevel=0):
	pkgs=grabfile(myfilename,compatlevel)
	for x in range(len(pkgs)-1,-1,-1):
		pkg = pkgs[x]
		if pkg[0] == "*":
			pkg = pkg[1:]
		if not portage_dep.isvalidatom(pkg):
			writemsg("--- Invalid atom in %s: %s\n" % (myfilename, pkgs[x]))
			del(pkgs[x])
	return pkgs

# returns a tuple.  (version[string], error[string])
# They are pretty much mutually exclusive.
# Either version is a string and error is none, or
# version is None and error is a string
#
def ExtractKernelVersion(base_dir):
	lines = []
	pathname = os.path.join(base_dir, 'Makefile')
	try:
		f = open(pathname, 'r')
	except OSError, details:
		return (None, str(details))
	except IOError, details:
		return (None, str(details))

	try:
		for i in range(4):
			lines.append(f.readline())
	except OSError, details:
		return (None, str(details))
	except IOError, details:
		return (None, str(details))
		
	lines = map(string.strip, lines)

	version = ''

	#XXX: The following code relies on the ordering of vars within the Makefile
	for line in lines:
		# split on the '=' then remove annoying whitespace
		items = string.split(line, '=')
		items = map(string.strip, items)
		if items[0] == 'VERSION' or \
			items[0] == 'PATCHLEVEL':
			version += items[1]
			version += "."
		elif items[0] == 'SUBLEVEL':
			version += items[1]
		elif items[0] == 'EXTRAVERSION' and \
			items[-1] != items[0]:
			version += items[1]

	# Grab a list of files named localversion* and sort them
	localversions = os.listdir(base_dir)
	for x in range(len(localversions)-1,-1,-1):
		if localversions[x][:12] != "localversion":
			del localversions[x]
	localversions.sort()

	# Append the contents of each to the version string, stripping ALL whitespace
	for lv in localversions:
		version += string.join(string.split(string.join(grabfile(base_dir+"/"+lv))), "")

	# Check the .config for a CONFIG_LOCALVERSION and append that too, also stripping whitespace
	kernelconfig = getconfig(base_dir+"/.config")
	if kernelconfig and kernelconfig.has_key("CONFIG_LOCALVERSION"):
		version += string.join(string.split(kernelconfig["CONFIG_LOCALVERSION"]), "")

	return (version,None)

aumtime=0

def check_config_instance(test):
	if not test or (str(test.__class__) != 'portage.config'):
		raise TypeError, "Invalid type for config object: %s" % test.__class__

class config:
	def __init__(self, clone=None, mycpv=None, config_profile_path=PROFILE_PATH, config_incrementals=None):

		self.already_in_regenerate = 0

		self.locked   = 0
		self.mycpv    = None
		self.puse     = []
		self.modifiedkeys = []
	
		self.virtuals = {}
		self.v_count  = 0

		if clone:
			self.incrementals = copy.deepcopy(clone.incrementals)
			self.profile_path = copy.deepcopy(clone.profile_path)

			self.module_priority = copy.deepcopy(clone.module_priority)
			self.modules         = copy.deepcopy(clone.modules)
			
			self.depcachedir = copy.deepcopy(clone.depcachedir)

			self.packages = copy.deepcopy(clone.packages)
			self.virtuals = copy.deepcopy(clone.virtuals)

			self.use_defs = copy.deepcopy(clone.use_defs)
			self.usemask  = copy.deepcopy(clone.usemask)

			self.configlist = copy.deepcopy(clone.configlist)
			self.configlist[-1] = os.environ.copy()
			self.configdict = { "globals":   self.configlist[0],
			                    "defaults":  self.configlist[1],
			                    "conf":      self.configlist[2],
			                    "pkg":       self.configlist[3],
			                    "auto":      self.configlist[4],
			                    "backupenv": self.configlist[5],
			                    "env":       self.configlist[6] }
			self.backupenv  = copy.deepcopy(clone.backupenv)
			self.pusedict   = copy.deepcopy(clone.pusedict)
			self.categories = copy.deepcopy(clone.categories)
			self.pkeywordsdict = copy.deepcopy(clone.pkeywordsdict)
			self.pmaskdict = copy.deepcopy(clone.pmaskdict)
			self.punmaskdict = copy.deepcopy(clone.punmaskdict)
			self.prevmaskdict = copy.deepcopy(clone.prevmaskdict)
			self.pprovideddict = copy.deepcopy(clone.pprovideddict)
			self.lookuplist = copy.deepcopy(clone.lookuplist)
			self.uvlist     = copy.deepcopy(clone.uvlist)
			self.dirVirtuals = copy.deepcopy(clone.dirVirtuals)
			self.treeVirtuals = copy.deepcopy(clone.treeVirtuals)
			self.userVirtuals = copy.deepcopy(clone.userVirtuals)
		else:
			self.depcachedir = DEPCACHE_PATH
			
			if not os.path.exists(config_profile_path):
				writemsg("config_profile_path not specified to class config\n")
				sys.exit(1)
			self.profile_path = config_profile_path[:]

			if not config_incrementals:
				import traceback
				traceback.print_stack()
				writemsg("incrementals not specified to class config\n")
				writemsg("sayonara, sucker.\n")
				sys.exit(1)
			self.incrementals = copy.deepcopy(config_incrementals)
			
			self.module_priority    = ["user","default"]
			self.modules            = {}
			self.modules["user"]    = getconfig(MODULES_FILE_PATH)
			if self.modules["user"] == None:
				self.modules["user"] = {}
			self.modules["default"] = {
				"portdbapi.metadbmodule": "portage_db_flat.database",
				"portdbapi.auxdbmodule":  "portage_db_flat.database",
				"eclass_cache.dbmodule":  "portage_db_cpickle.database",
			}
			
			self.usemask=[]
			self.configlist=[]
			self.backupenv={}
			# back up our incremental variables:
			self.configdict={}
			# configlist will contain: [ globals, defaults, conf, pkg, auto, backupenv (incrementals), origenv ]

			# The symlink might not exist or might not be a symlink.
			try:
				self.profiles=[abssymlink(self.profile_path)]
			except SystemExit, e:
				raise
			except:
				self.profiles=[self.profile_path]

			mypath = self.profiles[0]
			while os.path.exists(mypath+"/parent"):
				mypath = os.path.normpath(mypath+"///"+grabfile(mypath+"/parent")[0])
				if os.path.exists(mypath):
					self.profiles.insert(0,mypath)

			if os.environ.get("PORTAGE_CALLER",'') == "repoman":
				pass
			else:
				# XXX: This should depend on ROOT?
				if os.path.exists("/"+CUSTOM_PROFILE_PATH):
					self.profiles.append("/"+CUSTOM_PROFILE_PATH)

			self.packages_list = grab_multiple("packages", self.profiles, grabfile_package)
			self.packages      = stack_lists(self.packages_list, incremental=1)
			del self.packages_list
			#self.packages = grab_stacked("packages", self.profiles, grabfile, incremental_lines=1)

			# revmaskdict
			self.prevmaskdict={}
			for x in self.packages:
				mycatpkg=dep_getkey(x)
				if not self.prevmaskdict.has_key(mycatpkg):
					self.prevmaskdict[mycatpkg]=[x]
				else:
					self.prevmaskdict[mycatpkg].append(x)

			# get profile-masked use flags -- INCREMENTAL Child over parent
			usemask_lists = grab_multiple("use.mask", self.profiles, grabfile)
			self.usemask  = stack_lists(usemask_lists, incremental=True)
			del usemask_lists
			use_defs_lists = grab_multiple("use.defaults", self.profiles, grabdict)
			self.use_defs  = stack_dictlist(use_defs_lists, incremental=True)
			del use_defs_lists

			try:
				mygcfg_dlists = grab_multiple("make.globals", self.profiles+["/etc"], getconfig)
				self.mygcfg   = stack_dicts(mygcfg_dlists, incrementals=INCREMENTALS, ignore_none=1)

				if self.mygcfg == None:
					self.mygcfg = {}
			except SystemExit, e:
				raise
			except Exception, e:
				writemsg("!!! %s\n" % (e))
				writemsg("!!! Incorrect multiline literals can cause this. Do not use them.\n")
				writemsg("!!! Errors in this file should be reported on bugs.gentoo.org.\n")
				sys.exit(1)
			self.configlist.append(self.mygcfg)
			self.configdict["globals"]=self.configlist[-1]

			self.mygcfg = {}
			if self.profiles:
				try:
					mygcfg_dlists = grab_multiple("make.defaults", self.profiles, getconfig)
					self.mygcfg   = stack_dicts(mygcfg_dlists, incrementals=self.incrementals[:], ignore_none=1)
					#self.mygcfg = grab_stacked("make.defaults", self.profiles, getconfig)
					if self.mygcfg == None:
						self.mygcfg = {}
				except SystemExit, e:
					raise
				except Exception, e:
					writemsg("!!! %s\n" % (e))
					writemsg("!!! 'rm -Rf /usr/portage/profiles; emerge sync' may fix this. If it does\n")
					writemsg("!!! not then please report this to bugs.gentoo.org and, if possible, a dev\n")
					writemsg("!!! on #gentoo (irc.freenode.org)\n")
					sys.exit(1)
			self.configlist.append(self.mygcfg)
			self.configdict["defaults"]=self.configlist[-1]

			try:
				# XXX: Should depend on root?
				self.mygcfg=getconfig("/"+MAKE_CONF_FILE)
				if self.mygcfg == None:
					self.mygcfg = {}
			except SystemExit, e:
				raise
			except Exception, e:
				writemsg("!!! %s\n" % (e))
				writemsg("!!! Incorrect multiline literals can cause this. Do not use them.\n")
				sys.exit(1)
			

			self.configlist.append(self.mygcfg)
			self.configdict["conf"]=self.configlist[-1]

			self.configlist.append({})
			self.configdict["pkg"]=self.configlist[-1]

			#auto-use:
			self.configlist.append({})
			self.configdict["auto"]=self.configlist[-1]

			#backup-env (for recording our calculated incremental variables:)
			self.backupenv = os.environ.copy()
			self.configlist.append(self.backupenv) # XXX Why though?
			self.configdict["backupenv"]=self.configlist[-1]

			self.configlist.append(os.environ.copy())
			self.configdict["env"]=self.configlist[-1]


			# make lookuplist for loading package.*
			self.lookuplist=self.configlist[:]
			self.lookuplist.reverse()

			archlist = grabfile(self["PORTDIR"]+"/profiles/arch.list")
			self.configdict["conf"]["PORTAGE_ARCHLIST"] = string.join(archlist)

			if os.environ.get("PORTAGE_CALLER",'') == "repoman":
				# repoman shouldn't use local settings.
				locations = [self["PORTDIR"] + "/profiles"]
				self.pusedict = {}
				self.pkeywordsdict = {}
				self.punmaskdict = {}
			else:
				locations = [self["PORTDIR"] + "/profiles", USER_CONFIG_PATH]

				# Never set anything in this. It's for non-originals.
				self.pusedict=grabdict_package(USER_CONFIG_PATH+"/package.use")

				#package.keywords
				pkgdict=grabdict_package(USER_CONFIG_PATH+"/package.keywords")
				self.pkeywordsdict = {}
				for key in pkgdict.keys():
					# default to ~arch if no specific keyword is given
					if not pkgdict[key]:
						mykeywordlist = []
						if self.configdict["defaults"] and self.configdict["defaults"].has_key("ACCEPT_KEYWORDS"):
							groups = self.configdict["defaults"]["ACCEPT_KEYWORDS"].split()
						else:
							groups = []
						for keyword in groups:
							if not keyword[0] in "~-":
								mykeywordlist.append("~"+keyword)
						pkgdict[key] = mykeywordlist
					cp = dep_getkey(key)
					if not self.pkeywordsdict.has_key(cp):
						self.pkeywordsdict[cp] = {}
					self.pkeywordsdict[cp][key] = pkgdict[key]

				#package.unmask
				pkgunmasklines = grabfile_package(USER_CONFIG_PATH+"/package.unmask")
				self.punmaskdict = {}
				for x in pkgunmasklines:
					mycatpkg=dep_getkey(x)
					if self.punmaskdict.has_key(mycatpkg):
						self.punmaskdict[mycatpkg].append(x)
					else:
						self.punmaskdict[mycatpkg]=[x]

			#getting categories from an external file now
			categories = grab_multiple("categories", locations, grabfile)
			self.categories = stack_lists(categories, incremental=1)
			del categories

			# get virtuals -- needs categories
			self.loadVirtuals('/')
					
			#package.mask
			# Don't enable per profile package.mask unless the profile
			# specifically depends on the >=portage-2.0.51 using
			# <portage-2.0.51 syntax.
			# don't hardcode portage versions into portage.  It's not nice.
			if self.profiles and (">=sys-apps/portage-2.0.51" in self.packages \
                                      or "*>=sys-apps/portage-2.0.51" in self.packages):
				pkgmasklines = grab_multiple("package.mask", self.profiles + locations, grabfile_package)
			else:
				pkgmasklines = grab_multiple("package.mask", locations, grabfile_package)
			pkgmasklines = stack_lists(pkgmasklines, incremental=1)

			self.pmaskdict = {}
			for x in pkgmasklines:
				mycatpkg=dep_getkey(x)
				if self.pmaskdict.has_key(mycatpkg):
					self.pmaskdict[mycatpkg].append(x)
				else:
					self.pmaskdict[mycatpkg]=[x]

			pkgprovidedlines = grab_multiple("package.provided", self.profiles, grabfile)
			pkgprovidedlines = stack_lists(pkgprovidedlines, incremental=1)

			self.pprovideddict = {}
			for x in pkgprovidedlines:
				cpv=portage_dep.catpkgsplit(x)
				if not x:
					continue
				mycatpkg=dep_getkey(x)
				if self.pprovideddict.has_key(mycatpkg):
					self.pprovideddict[mycatpkg].append(x)
				else:
					self.pprovideddict[mycatpkg]=[x]

		self.lookuplist=self.configlist[:]
		self.lookuplist.reverse()
	
		useorder=self["USE_ORDER"]
		if not useorder:
			# reasonable defaults; this is important as without USE_ORDER,
			# USE will always be "" (nothing set)!
			useorder="env:pkg:conf:auto:defaults"
		useordersplit=useorder.split(":")

		self.uvlist=[]
		for x in useordersplit:
			if self.configdict.has_key(x):
				if "PKGUSE" in self.configdict[x].keys():
					del self.configdict[x]["PKGUSE"] # Delete PkgUse, Not legal to set.
				#prepend db to list to get correct order
				self.uvlist[0:0]=[self.configdict[x]]		

		self.configdict["env"]["PORTAGE_GID"]=str(portage_gid)
		self.backupenv["PORTAGE_GID"]=str(portage_gid)

		if self.has_key("PORT_LOGDIR") and not self["PORT_LOGDIR"]:
			# port_logdir is defined, but empty.  this causes a traceback in doebuild.
			writemsg(yellow("!!!")+" PORT_LOGDIR was defined, but set to nothing.\n")
			writemsg(yellow("!!!")+" Disabling it.  Please set it to a non null value.\n")
			del self["PORT_LOGDIR"]

		if self["PORTAGE_CACHEDIR"]:
			# XXX: Deprecated -- April 15 -- NJ
			writemsg(yellow(">>> PORTAGE_CACHEDIR has been deprecated!")+"\n")
			writemsg(">>> Please use PORTAGE_DEPCACHEDIR instead.\n")
			self.depcachedir = self["PORTAGE_CACHEDIR"]
			del self["PORTAGE_CACHEDIR"]

		if self["PORTAGE_DEPCACHEDIR"]:
			#the auxcache is the only /var/cache/edb/ entry that stays at / even when "root" changes.
			# XXX: Could move with a CHROOT functionality addition.
			self.depcachedir = self["PORTAGE_DEPCACHEDIR"]
			del self["PORTAGE_DEPCACHEDIR"]

		overlays = string.split(self["PORTDIR_OVERLAY"])
		if overlays:
			new_ov=[]
			for ov in overlays:
				ov=os.path.normpath(ov)
				if os.path.isdir(ov):
					new_ov.append(ov)
				else:
					writemsg(red("!!! Invalid PORTDIR_OVERLAY (not a dir): "+ov+"\n"))
			self["PORTDIR_OVERLAY"] = string.join(new_ov)
			self.backup_changes("PORTDIR_OVERLAY")

		self.regenerate()
		
		
		self.features = portage_util.unique_array(self["FEATURES"].split())
		self.features.sort()

		#XXX: Should this be temporary? Is it possible at all to have a default?
		if "gpg" in self.features:
			if not os.path.exists(self["PORTAGE_GPG_DIR"]) or not os.path.isdir(self["PORTAGE_GPG_DIR"]):
				writemsg("PORTAGE_GPG_DIR is invalid. Removing gpg from FEATURES.\n")
				self.features.remove("gpg")
				self["FEATURES"] = string.join(self.features, " ")
				self.backup_changes("FEATURES")
		
		if mycpv:
			self.setcpv(mycpv)

	def autouse(self, myvartree,use_cache=1):
		"returns set of USE variables auto-enabled due to packages being installed"
		if profiledir==None:
			return ""
		myusevars=""
		for myuse in self.use_defs:
			dep_met = True
			for mydep in self.use_defs[myuse]:
				if not myvartree.dep_match(mydep,use_cache=True):
					dep_met = False
					break
			if dep_met:
				myusevars += " "+myuse
		return myusevars



	def loadVirtuals(self,root):
		self.virtuals = self.getvirtuals(root)

	def load_best_module(self,property_string):
		best_mod = best_from_dict(property_string,self.modules,self.module_priority)
		return load_mod(best_mod)
			
	def lock(self):
		self.locked = 1

	def unlock(self):
		self.locked = 0
	
	def modifying(self):
		if self.locked:
			raise Exception, "Configuration is locked."
	
	def backup_changes(self,key=None):
		if key and self.configdict["env"].has_key(key):
			self.backupenv[key] = copy.deepcopy(self.configdict["env"][key])
		else:
			raise KeyError, "No such key defined in environment: %s" % key
	
	def reset(self,keeping_pkg=0,use_cache=1):
		"reset environment to original settings"
		for x in self.configlist[-1].keys():
			if x not in self.backupenv.keys():
				del self.configlist[-1][x]

		self.configdict["env"].update(self.backupenv)

		self.modifiedkeys = []
		if not keeping_pkg:
			self.puse = ""
			self.configdict["pkg"].clear()
		self.regenerate(use_cache=use_cache)

	def load_infodir(self,infodir):
		if self.configdict.has_key("pkg"):
			for x in self.configdict["pkg"].keys():
				del self.configdict["pkg"][x]
		else:
			writemsg("No pkg setup for settings instance?\n")
			sys.exit(17)
		
		if os.path.exists(infodir):
			if os.path.exists(infodir+"/environment"):
				self.configdict["pkg"]["PORT_ENV_FILE"] = infodir+"/environment"
			elif os.path.exists(infodir+"/environment.bz2"):
				self.configdict["pkg"]["PORT_ENV_FILE"] = infodir+"/environment.bz2"
#			else:
#				print "wth, no env found in the infodir, '%s'" % infodir
#				import traceback
#				traceback.print_stack()
#				sys.exit(15)
			myre = re.compile('^[A-Z]+$')
			for filename in listdir(infodir,filesonly=1,EmptyOnError=1):
				if myre.match(filename):
					try:
						mydata = string.strip(open(infodir+"/"+filename).read())
						if len(mydata)<2048:
							if filename == "USE":
								self.configdict["pkg"][filename] = "-* "+mydata
							else:
								self.configdict["pkg"][filename] = mydata
					except SystemExit, e:
						raise
					except:
						writemsg("!!! Unable to read file: %s\n" % infodir+"/"+filename)
						pass
			return 1
		return 0

	def setcpv(self,mycpv,use_cache=1):
		self.modifying()
		self.mycpv = mycpv
		self.pusekey = best_match_to_list(self.mycpv, self.pusedict.keys())
		if self.pusekey:
			newpuse = string.join(self.pusedict[self.pusekey])
		else:
			newpuse = ""
		if newpuse == self.puse:
			return
		self.puse = newpuse
		self.configdict["pkg"]["PKGUSE"] = self.puse[:] # For saving to PUSE file
		self.configdict["pkg"]["USE"]    = self.puse[:] # this gets appended to USE
		self.reset(keeping_pkg=1,use_cache=use_cache)

	def setinst(self,mycpv,mydbapi):
		# Grab the virtuals this package provides and add them into the tree virtuals.
		provides = mydbapi.aux_get(mycpv, ["PROVIDE"])[0]
		if isinstance(mydbapi, portdbapi):
			myuse = self["USE"]
		else:
			myuse = mydbapi.aux_get(mycpv, ["USE"])[0]
		virts = flatten(portage_dep.use_reduce(portage_dep.paren_reduce(provides), uselist=myuse.split()))

		cp = dep_getkey(mycpv)
		for virt in virts:
			virt = dep_getkey(virt)
			if not self.treeVirtuals.has_key(virt):
				self.treeVirtuals[virt] = []
			self.treeVirtuals[virt] = portage_util.unique_array(self.treeVirtuals[virt]+[cp])
		# Reconstruct the combined virtuals.
		val = stack_dictlist([self.userVirtuals]+[self.treeVirtuals]+self.dirVirtuals,incremental=1)
		for x in val.keys():
			val[x].reverse()
		self.virtuals = val
	
	def regenerate(self,useonly=0,use_cache=1):
		global usesplit
		
		if self.already_in_regenerate:
			# XXX: THIS REALLY NEEDS TO GET FIXED. autouse() loops.
			writemsg("!!! Looping in regenerate.\n",1)
			return
		else:
			self.already_in_regenerate = 1

		if useonly:
			myincrementals=["USE"]
		else:
			myincrementals=self.incrementals[:]
		for mykey in myincrementals:
			if mykey=="USE":
				mydbs=self.uvlist
				# XXX Global usage of db... Needs to go away somehow.
				if db.has_key(root) and db[root].has_key("vartree"):
					self.configdict["auto"]["USE"]=self.autouse(db[root]["vartree"],use_cache=use_cache)
				else:
					self.configdict["auto"]["USE"]=""
			else:
				mydbs=self.configlist[:-1]

			myflags=[]
			for curdb in mydbs:
				if not curdb.has_key(mykey):
					continue
				#variables are already expanded
				mysplit=curdb[mykey].split()
				
				for x in mysplit:
					if x=="-*":
						# "-*" is a special "minus" var that means "unset all settings".
						# so USE="-* gnome" will have *just* gnome enabled.
						myflags=[]
						continue

					if x[0]=="+":
						# Not legal. People assume too much. Complain.
						writemsg(red("USE flags should not start with a '+': %s\n" % x))
						x=x[1:]

					if (x[0]=="-"):
						if (x[1:] in myflags):
							# Unset/Remove it.
							del myflags[myflags.index(x[1:])]
						continue

					# We got here, so add it now.
					if x not in myflags:
						myflags.append(x)

			myflags.sort()
			#store setting in last element of configlist, the original environment:
			self.configlist[-1][mykey]=string.join(myflags," ")
			del myflags

		#cache split-up USE var in a global
		usesplit=[]

		for x in string.split(self.configlist[-1]["USE"]):
			if x not in self.usemask:
				usesplit.append(x)

		if self.has_key("USE_EXPAND"):
			for var in string.split(self["USE_EXPAND"]):
				if self.has_key(var):
					for x in string.split(self[var]):
						mystr = string.lower(var)+"_"+x
						if mystr not in usesplit:
							usesplit.append(mystr)

		# Pre-Pend ARCH variable to USE settings so '-*' in env doesn't kill arch.
		if profiledir:
			if self.configdict["defaults"].has_key("ARCH"):
				if self.configdict["defaults"]["ARCH"]:
					if self.configdict["defaults"]["ARCH"] not in usesplit:
						usesplit.insert(0,self.configdict["defaults"]["ARCH"])

		self.configlist[-1]["USE"]=string.join(usesplit," ")

		self.already_in_regenerate = 0

	def getvirtuals(self, myroot):
		myvirts     = {}

		# This breaks catalyst/portage when setting to a fresh/empty root.
		# Virtuals cannot be calculated because there is nothing to work
		# from. So the only ROOT prefixed dir should be local configs.
		#myvirtdirs  = prefix_array(self.profiles,myroot+"/")
		myvirtdirs = copy.deepcopy(self.profiles)
		
		self.treeVirtuals = {}

		# Repoman should ignore these.
		user_profile_dir = None
		if os.environ.get("PORTAGE_CALLER","") != "repoman":
		   	user_profile_dir = myroot+USER_CONFIG_PATH
		
		if os.path.exists("/etc/portage/virtuals"):
			writemsg("\n\n*** /etc/portage/virtuals should be moved to /etc/portage/profile/virtuals\n")
			writemsg("*** Please correct this by merging or moving the file. (Deprecation notice)\n\n")
			time.sleep(1)
		
		
		self.dirVirtuals = grab_multiple("virtuals", myvirtdirs, grabdict)
		self.dirVirtuals.reverse()
		self.userVirtuals = {}
		if user_profile_dir and os.path.exists(user_profile_dir+"/virtuals"):
			self.userVirtuals = grabdict(user_profile_dir+"/virtuals")

		# User settings and profile settings take precedence over tree.
		profile_virtuals = stack_dictlist([self.userVirtuals]+self.dirVirtuals,incremental=1)
		
		# repoman doesn't need local virtuals
		if os.environ.has_key("PORTAGE_CALLER") and os.environ["PORTAGE_CALLER"] == "repoman":
			pass
		else:
			temp_vartree = vartree(myroot,profile_virtuals,categories=self.categories)
			myTreeVirtuals = map_dictlist_vals(getCPFromCPV,temp_vartree.get_all_provides())
			for x in myTreeVirtuals.keys():
				self.treeVirtuals[x] = portage_util.unique_array(myTreeVirtuals[x])
			del myTreeVirtuals
			
		# User settings and profile settings take precendence over tree
		val = stack_dictlist([self.userVirtuals]+[self.treeVirtuals]+self.dirVirtuals,incremental=1)
		
		for x in val.keys():
			val[x].reverse()
		return val 
	
	def __delitem__(self,mykey):
		for x in self.lookuplist:
			if x != None:
				if mykey in x:
					del x[mykey]
	
	def __getitem__(self,mykey):
		match = ''
		for x in self.lookuplist:
			if x == None:
				writemsg("!!! lookuplist is null.\n")
			elif x.has_key(mykey):
				match = x[mykey]
				break

		if 0 and match and mykey in ["PORTAGE_BINHOST"]:
			# These require HTTP Encoding
			try:
				import urllib
				if urllib.unquote(match) != match:
					writemsg("Note: %s already contains escape codes." % (mykey))
				else:
					match = urllib.quote(match)
			except SystemExit, e:
				raise
			except:
				writemsg("Failed to fix %s using urllib, attempting to continue.\n"  % (mykey))
				pass
			
		elif mykey == "CONFIG_PROTECT_MASK":
			match += " /etc/env.d"

		return match

	def has_key(self,mykey):
		for x in self.lookuplist:
			if x.has_key(mykey):
				return 1 
		return 0
	
	def keys(self):
		mykeys=[]
		for x in self.lookuplist:
			for y in x.keys():
				if y not in mykeys:
					mykeys.append(y)
		return mykeys

	def __setitem__(self,mykey,myvalue):
		"set a value; will be thrown away at reset() time"
		if type(myvalue) != types.StringType:
			raise ValueError("Invalid type being used as a value: '%s': '%s'" % (str(mykey),str(myvalue)))
		self.modifying()
		self.modifiedkeys += [mykey]
		self.configdict["env"][mykey]=myvalue
	
	def environ(self):
		"return our locally-maintained environment"
		mydict={}
		for x in self.keys(): 
			mydict[x]=self[x]
		if not mydict.has_key("HOME") and mydict.has_key("BUILD_PREFIX"):
			writemsg("*** HOME not set. Setting to "+mydict["BUILD_PREFIX"]+"\n")
			mydict["HOME"]=mydict["BUILD_PREFIX"][:]

		return mydict

	def bash_environ(self):
		"return our locally-maintained environment in a suitable bash assignment form"
		mydict=self.environ()
		final={}
		for k in mydict.keys():
			# quotes and escaped chars suck.
			s=mydict[k].replace("\\","\\\\\\\\")
			s=s.replace("'","\\'")
			s=s.replace("\n","\\\n")
			final[k]="$'%s'" % s
		return final


# XXX This would be to replace getstatusoutput completely.
# XXX Issue: cannot block execution. Deadlock condition.
def spawn(mystring,mysettings,debug=0,free=0,droppriv=0,fd_pipes=None,**keywords):
	"""spawn a subprocess with optional sandbox protection, 
	depending on whether sandbox is enabled.  The "free" argument,
	when set to 1, will disable sandboxing.  This allows us to 
	spawn processes that are supposed to modify files outside of the
	sandbox.  We can't use os.system anymore because it messes up
	signal handling.  Using spawn allows our Portage signal handler
	to work."""

	if type(mysettings) == types.DictType:
		env=mysettings
		keywords["opt_name"]="[ %s ]" % "portage"
	else:
		check_config_instance(mysettings)
		env=mysettings.environ()
		keywords["opt_name"]="[%s]" % mysettings["PF"]


	droppriv=(droppriv and ("userpriv" in features) and \
		("nouserpriv" not in string.split(mysettings["RESTRICT"])))

	if ("sandbox" in features) and (not free):
		keywords["opt_name"] += " sandbox"
		if droppriv and portage_gid and portage_uid:
			keywords.update({"uid":portage_uid,"gid":portage_gid,"groups":[portage_gid],"umask":002})
		return portage_exec.spawn_sandbox(mystring,env=env,**keywords)
	else:
		keywords["opt_name"] += " bash"
		return portage_exec.spawn_bash(mystring,env=env,**keywords)

def fetch(myuris, mysettings, listonly=0, fetchonly=0, locks_in_subdir=".locks",use_locks=1, try_mirrors=1,verbosity=0):
	"fetch files.  Will use digest file if available."
	if ("mirror" in features) and ("nomirror" in mysettings["RESTRICT"].split()):
		if verbosity:
			print ">>> \"mirror\" mode and \"nomirror\" restriction enabled; skipping fetch."
		return 1
	global thirdpartymirrors
	
	check_config_instance(mysettings)

	custommirrors=grabdict(CUSTOM_MIRRORS_FILE)

	mymirrors=[]
	
	if listonly or ("distlocks" not in features):
		use_locks = 0

	# local mirrors are always added
	if custommirrors.has_key("local"):
		mymirrors += custommirrors["local"]

	if ("nomirror" in mysettings["RESTRICT"].split()) or \
	   ("mirror"   in mysettings["RESTRICT"].split()):
		# We don't add any mirrors.
		pass
	else:
		if try_mirrors:
			for x in mysettings["GENTOO_MIRRORS"].split():
				if x:
					if x[-1] == '/':
						mymirrors += [x[:-1]]
					else:
						mymirrors += [x]
	
	mydigests={}
	digestfn = mysettings["FILESDIR"]+"/digest-"+mysettings["PF"]
	if os.path.exists(digestfn):
		mydigests = digestParseFile(digestfn)

	fsmirrors = []
	for x in range(len(mymirrors)-1,-1,-1):
		if mymirrors[x] and mymirrors[x][0]=='/':
			fsmirrors += [mymirrors[x]]
			del mymirrors[x]

	for myuri in myuris:
		myfile=os.path.basename(myuri)
		try:
			destdir = mysettings["DISTDIR"]+"/"
			if not os.path.exists(destdir+myfile):
				for mydir in fsmirrors:
					if os.path.exists(mydir+"/"+myfile):
						writemsg(_("Local mirror has file: %(file)s\n" % {"file":myfile}))
						shutil.copyfile(mydir+"/"+myfile,destdir+"/"+myfile)
						break
		except (OSError,IOError),e:
			# file does not exist
			writemsg(_("!!! %(file)s not found in %(dir)s." % {"file":myfile,"dir":mysettings["DISTDIR"]}),verbosity)
			gotit=0

	if "fetch" in mysettings["RESTRICT"].split():
		# fetch is restricted.	Ensure all files have already been downloaded; otherwise,
		# print message and exit.
		gotit=1
		for myuri in myuris:
			myfile=os.path.basename(myuri)
			try:
				mystat=os.stat(mysettings["DISTDIR"]+"/"+myfile)
			except (OSError,IOError),e:
				# file does not exist
				writemsg(_("!!! %(file) not found in %(dir)s." % {"file":myfile, "dir":mysettings["DISTDIR"]}),verbosity)
				gotit=0
		if not gotit:
			writemsg("\n!!!",mysettings["CATEGORY"]+"/"+mysettings["PF"],"has fetch restriction turned on.\n"+
				"!!! This probably means that this ebuild's files must be downloaded\n"+
				"!!! manually.  See the comments in the ebuild for more information.\n\n",
				verbosity)
			spawn(EBUILD_SH_BINARY+" nofetch",mysettings)
			return 0
		return 1
	locations=mymirrors[:]
	filedict={}
	for myuri in myuris:
		myfile=os.path.basename(myuri)
		if not filedict.has_key(myfile):
			filedict[myfile]=[]
			for y in range(0,len(locations)):
				filedict[myfile].append(locations[y]+"/distfiles/"+myfile)
		if myuri[:9]=="mirror://":
			eidx = myuri.find("/", 9)
			if eidx != -1:
				mirrorname = myuri[9:eidx]

				# Try user-defined mirrors first
				if custommirrors.has_key(mirrorname):
					for cmirr in custommirrors[mirrorname]:
						filedict[myfile].append(cmirr+"/"+myuri[eidx+1:])
						# remove the mirrors we tried from the list of official mirrors
						if cmirr.strip() in thirdpartymirrors[mirrorname]:
							thirdpartymirrors[mirrorname].remove(cmirr)
				# now try the official mirrors
				if thirdpartymirrors.has_key(mirrorname):
					try:
						shuffle(thirdpartymirrors[mirrorname])
					except SystemExit, e:
						raise
					except:
						writemsg(red("!!! YOU HAVE A BROKEN PYTHON/GLIBC.\n"),verbosity)
						writemsg(    "!!! You are most likely on a pentium4 box and have specified -march=pentium4\n",verbosity)
						writemsg(    "!!! or -fpmath=sse2. GCC was generating invalid sse2 instructions in versions\n",verbosity)
						writemsg(    "!!! prior to 3.2.3. Please merge the latest gcc or rebuid python with either\n",verbosity)
						writemsg(    "!!! -march=pentium3 or set -mno-sse2 in your cflags.\n\n\n",verbosity)
						time.sleep(10)
						
					for locmirr in thirdpartymirrors[mirrorname]:
						filedict[myfile].append(locmirr+"/"+myuri[eidx+1:])
      
        
				if not filedict[myfile]:
					writemsg("No known mirror by the name: %s\n" % (mirrorname),verbosity)
			else:
				writemsg("Invalid mirror definition in SRC_URI:\n",verbosity)
				writemsg("  %s\n" % (myuri),verbosity)
		else:
				filedict[myfile].append(myuri)

	missingSourceHost = False
	for myfile in filedict.keys(): # Gives a list, not just the first one
		if not filedict[myfile]:
			writemsg("Warning: No mirrors available for file '%s'\n" % (myfile),verbosity)
			missingSourceHost = True
	if missingSourceHost:
		return 0
	del missingSourceHost

	can_fetch=True
	if not os.access(mysettings["DISTDIR"]+"/",os.W_OK):
		writemsg("!!! No write access to %s" % mysettings["DISTDIR"]+"/\n",verbosity)
		can_fetch=False
	else:
		mystat=os.stat(mysettings["DISTDIR"]+"/")
		if mystat.st_gid != portage_gid:
			try:
				os.chown(mysettings["DISTDIR"],-1,portage_gid)
			except OSError, oe:
				if oe.errno == 1:
					writemsg(red("!!!")+" Unable to chgrp of %s to portage, continuing\n" % 
						mysettings["DISTDIR"],verbosity)
				else:
					raise oe
	
		# writable by portage_gid?  This is specific to root, adjust perms if needed automatically.
		if not stat.S_IMODE(mystat.st_mode) & 020:
			try:
				os.chmod(mysettings["DISTDIR"],stat.S_IMODE(mystat.st_mode) | 020)
			except OSError, oe:
				if oe.errno == 1:
					writemsg(red("!!!")+" Unable to chmod %s to perms 0755.  Non-root users will experience issues.\n" % mysettings["DISTDIR"],verbosity)
				else:
					raise oe
 		
		if use_locks and locks_in_subdir:
			if os.path.exists(mysettings["DISTDIR"]+"/"+locks_in_subdir):
				if not os.access(mysettings["DISTDIR"]+"/"+locks_in_subdir,os.W_OK):
					writemsg("!!! No write access to write to %s.  Aborting.\n" % mysettings["DISTDIR"]+"/"+locks_in_subdir,verbosity)
					return 0
			else:
				old_umask=os.umask(0002)
				os.mkdir(mysettings["DISTDIR"]+"/"+locks_in_subdir,0775)
				if os.stat(mysettings["DISTDIR"]+"/"+locks_in_subdir).st_gid != portage_gid:
					try:
						os.chown(mysettings["DISTDIR"]+"/"+locks_in_subdir,-1,portage_gid)
					except SystemExit, e:
						raise
					except:
						pass
				os.umask(old_umask)

	
	fetcher = get_preferred_fetcher()
	for myfile in filedict.keys():
		fetched=0
		file_lock = None
		if listonly:
			writemsg("\n",verbosity)
		else:
			if use_locks and can_fetch:
				if locks_in_subdir:
					file_lock = portage_locks.lockfile(mysettings["DISTDIR"]+"/"+locks_in_subdir+"/"+myfile,wantnewlockfile=1,verbosity=verbosity)
				else:
					file_lock = portage_locks.lockfile(mysettings["DISTDIR"]+"/"+myfile,wantnewlockfile=1,verbosity=verbosity)
		try:
			for loc in filedict[myfile]:
				if listonly:
					writemsg(loc+" ",verbosity)
					continue
	
				try:
					mystat=os.stat(mysettings["DISTDIR"]+"/"+myfile)
					if mydigests.has_key(myfile):
						#if we have the digest file, we know the final size and can resume the download.
						if mystat[stat.ST_SIZE]<mydigests[myfile]["size"]:
							fetched=1
						else:
							#we already have it downloaded, skip.
							#if our file is bigger than the recorded size, digestcheck should catch it.
							if not fetchonly:
								fetched=2
							else:
								# Check md5sum's at each fetch for fetchonly.
								verified_ok,reason = portage_checksum.verify_all(mysettings["DISTDIR"]+"/"+myfile, mydigests[myfile])
								if not verified_ok:
									writemsg("!!! Previously fetched file: "+str(myfile)+"\n!!! Reason: "+reason+"\nRefetching...\n\n",verbosity)
									os.unlink(mysettings["DISTDIR"]+"/"+myfile)
									fetched=0
								else:
									for x_key in mydigests[myfile].keys():
										writemsg(">>> Previously fetched file: "+str(myfile)+" "+x_key+" ;-)\n",verbosity)
									fetched=2
									break #No need to keep looking for this file, we have it!
					else:
						#we don't have the digest file, but the file exists.  Assume it is fully downloaded.
						fetched=2
				except (OSError,IOError),e:
					writemsg("An exception was caught(1)...\nFailing the download: %s.\n" % (str(e)),verbosity+1)
					fetched=0
	
				if not can_fetch:
					if fetched != 2:
						if fetched == 0:
							writemsg("!!! File %s isn't fetched but unable to get it.\n" % myfile,verbosity)
						else:
							writemsg("!!! File %s isn't fully fetched, but unable to complete it\n" % myfile,verbosity)
						return 0
					else:
						continue
		
				# check if we can actually write to the directory/existing file.
				if fetched!=2 and os.path.exists(mysettings["DISTDIR"]+"/"+myfile) != \
					os.access(mysettings["DISTDIR"]+"/"+myfile, os.W_OK):
					writemsg(red("***")+" Lack write access to %s, failing fetch\n" % str(mysettings["DISTDIR"]+"/"+myfile),verbosity)
					fetched=0
					break
				elif fetched!=2:
					#we either need to resume or start the download
					#you can't use "continue" when you're inside a "try" block
					if fetched==1:
						#resume mode:
						writemsg(">>> Resuming download...\n",verbosity)
						locfetch=fetcher.resume
					else:
						#normal mode:
						locfetch=fetcher.fetch
					writemsg(">>> Downloading "+str(loc)+"\n",verbosity)
					try:
						myret=locfetch(loc,file_name=mysettings["DISTDIR"]+"/"+myfile, \
							verbose=(verbosity==0))
						if myret==127 and \
							isinstance(fetcher,transports.fetchcommand.CustomConnection):
							# this is an indication of a missing libs for the binary.
							# fex: USE="ssl" wget, missing libssl.
							#
							# lets try to be helpful. ;-)
							f=transports.bundled_lib.BundledConnection()
							if fetched==1:
								myret=f.resume(loc, \
								file_name=mysettings["DISTDIR"]+"/"+myfile,
								verbose=(verbosity==0))
							else:
								myret=f.fetch(loc, \
								file_name=mysettings["DISTDIR"]+"/"+myfile,
								verbose=(verbosity==0))
							if not myret:
								writemsg(red("!!!")+"\n")
								writemsg(red("!!!")+" FETCHCOMMAND/RESUMECOMMAND with exit code 127\n")
								writemsg(red("!!!")+" This is indicative of missing libs for the fetch/resume binaries\n")
								writemsg(red("!!!")+" Added, the independ BundledConnection succeeded\n")
								writemsg(red("!!!")+" Please check your installation.\n")
								writemsg(red("!!!")+" Defaulting to BundledConnection for the remainder of this fetch request\n")
								writemsg(red("!!!")+"\n")
								fetcher = f
					finally:
						#if root, -always- set the perms.
						if os.path.exists(mysettings["DISTDIR"]+"/"+myfile) and (fetched != 1 or os.getuid() == 0):
							if os.stat(mysettings["DISTDIR"]+"/"+myfile).st_gid != portage_gid:
								try:
									os.chown(mysettings["DISTDIR"]+"/"+myfile,-1,portage_gid)
								except SystemExit, e:
									raise
								except:
									writemsg("chown failed on distfile: " + str(myfile),verbosity)
							os.chmod(mysettings["DISTDIR"]+"/"+myfile,0664)
	
					if mydigests!=None and mydigests.has_key(myfile):
						try:
							mystat=os.stat(mysettings["DISTDIR"]+"/"+myfile)
							# no exception?  file exists. let digestcheck() report
							# an appropriately for size or md5 errors
							if (mystat[stat.ST_SIZE]<mydigests[myfile]["size"]):
								# Fetch failed... Try the next one... Kill 404 files though.
								if (mystat[stat.ST_SIZE]<100000) and (len(myfile)>4) and not ((myfile[-5:]==".html") or (myfile[-4:]==".htm")):
									html404=re.compile("<title>.*(not found|404).*</title>",re.I|re.M)
									try:
										if html404.search(open(mysettings["DISTDIR"]+"/"+myfile).read()):
											try:
												os.unlink(mysettings["DISTDIR"]+"/"+myfile)
												writemsg(">>> Deleting invalid distfile. (Improper 404 redirect from server.)\n",verbosity)
											except SystemExit, e:
												raise
											except:
												pass
									except SystemExit, e:
										raise
									except:
										pass
								continue
							if not fetchonly:
								fetched=2
								break
							else:
								# File is the correct size--check the MD5 sum for the fetched
								# file NOW, for those users who don't have a stable/continuous
								# net connection. This way we have a chance to try to download
								# from another mirror...
								verified_ok,reason = portage_checksum.verify_all(mysettings["DISTDIR"]+"/"+myfile, mydigests[myfile])
								if not verified_ok:
									writemsg("!!! Fetched file: "+str(myfile)+" VERIFY FAILED!\n!!! Reason: "+reason+"\nRemoving corrupt distfile...\n",verbosity)
									os.unlink(mysettings["DISTDIR"]+"/"+myfile)
									fetched=0
								else:
									for x_key in mydigests[myfile].keys():
										writemsg(">>> "+str(myfile)+" "+x_key+" ;-)\n",verbosity)
									fetched=2
									break
						except (OSError,IOError),e:
							writemsg("An exception was caught(2)...\nFailing the download: %s.\n" % (str(e)),verbosity+1)
							fetched=0
					else:
						if not myret:
							fetched=2
							break
						elif mydigests!=None:
							writemsg("No digest file available and download failed.\n\n")
		finally:
			if use_locks and file_lock:
				portage_locks.unlockfile(file_lock)
		
		if listonly:
			writemsg("\n")
		if (fetched!=2) and not listonly:
			writemsg("!!! Couldn't download "+str(myfile)+". Aborting.\n",verbosity)
			return 0
	return 1


def digestCreate(myfiles,basedir,oldDigest={}):
	"""Takes a list of files and the directory they are in and returns the
	dict of dict[filename][CHECKSUM_KEY] = hash
	returns None on error."""
	mydigests={}
	for x in myfiles:
		print "<<<",x
		myfile=os.path.normpath(basedir+"///"+x)
		if os.path.exists(myfile):
			if not os.access(myfile, os.R_OK):
				print "!!! Given file does not appear to be readable. Does it exist?"
				print "!!! File:",myfile
				return None
			mysize = os.stat(myfile)[stat.ST_SIZE]
			mysums = portage_checksum.perform_all(myfile)
		else:
			if oldDigest.has_key(x):
				#DeepCopy because we might not have a unique reference
				mydigests[x] = copy.deepcopy(olddigest[x])
				mysize = copy.deepcopy(olddigest[x]["size"])
			else:
				print "!!! We have a source URI, but no file..."
				print "!!! File:",myfile
				return None
			
		mydigests[x] = mysums
		if mydigests[x].has_key("size") and (mydigests[x]["size"] != mysize):
			raise portage_exception.DigestException, "Size mismatch during checksums"
		mydigests[x]["size"] = copy.deepcopy(mysize)


	return mydigests

def digestCreateLines(filelist, mydict):
	mylines = []
	mydigests = copy.deepcopy(mydict)
	for myarchive in filelist:
		mysize = mydigests[myarchive]["size"]
		if len(mydigests[myarchive]) == 0:
			raise portage_exception.DigestException, "No generate digest for '%(file)s'" % {"file":myarchive}
		for sumName in mydigests[myarchive].keys():
			if sumName not in portage_checksum.get_valid_checksum_keys():
				continue
			mysum = mydigests[myarchive][sumName]
			
			myline = sumName[:]
			myline += " "+mysum
			myline += " "+myarchive
			myline += " "+str(mysize)
			if sumName != "MD5":
				# XXXXXXXXXXXXXXXX This cannot be used!
				# Older portage make very dumb assumptions about the formats.
				# We need a lead-in period before we break everything.
				continue
			mylines.append(myline)
	return mylines

def digestgen(myarchives,mysettings,overwrite=1,manifestonly=0,verbosity=0):
	"""generates digest file if missing.  Assumes all files are available.	If
	overwrite=0, the digest will only be created if it doesn't already exist."""

	# archive files
	basedir=mysettings["DISTDIR"]+"/"
	digestfn=mysettings["FILESDIR"]+"/digest-"+mysettings["PF"]

	# portage files -- p(ortagefiles)basedir
	pbasedir=mysettings["O"]+"/"
	manifestfn=pbasedir+"Manifest"

	if not manifestonly:
		if not os.path.isdir(mysettings["FILESDIR"]):
			os.makedirs(mysettings["FILESDIR"])
		mycvstree=cvstree.getentries(pbasedir, recursive=1)

		if ("cvs" in features) and os.path.exists(pbasedir+"/CVS"):
			if not cvstree.isadded(mycvstree,"files"):
				if "autoaddcvs" in features:
					writemsg(">>> Auto-adding files/ dir to CVS...\n",verbosity - 1)
					spawn("cd "+pbasedir+"; cvs add files",mysettings,free=1)
				else:
					writemsg("--- Warning: files/ is not added to cvs.\n",verbosity)

		if (not overwrite) and os.path.exists(digestfn):
			return 1

		print green(">>> Generating digest file...")

		# Track the old digest so that we can assume checksums without requiring
		# all files be downloaded. 'Assuming'
		# XXX: <harring>- why does this seem like a way to pollute the hell out of the 
		# digests?  This strikes me as lining the path between your bed and coffee machine
		# with land mines...
		myolddigest = {}
		if os.path.exists(digestfn):
			myolddigest = digestParseFile(digestfn)
		
		mydigests=digestCreate(myarchives, basedir,oldDigest=myolddigest)
		if mydigests==None: # There was a problem, exit with an errorcode.
			return 0

		try:
			outfile=open(digestfn, "w+")
		except SystemExit, e:
			raise
		except Exception, e:
			print "!!! Filesystem error skipping generation. (Read-Only?)"
			print "!!!",e
			return 0
		for x in digestCreateLines(myarchives, mydigests):
			outfile.write(x+"\n")
		outfile.close()
		try:
			os.chown(digestfn,os.getuid(),portage_gid)
			os.chmod(digestfn,0664)
		except SystemExit, e:
			raise
		except Exception,e:
			print e

	print green(">>> Generating manifest file...")
	mypfiles=listdir(pbasedir,recursive=1,filesonly=1,ignorecvs=1,EmptyOnError=1)
	mypfiles=cvstree.apply_cvsignore_filter(mypfiles)
	if "Manifest" in mypfiles:
		del mypfiles[mypfiles.index("Manifest")]

	mydigests=digestCreate(mypfiles, pbasedir)
	if mydigests==None: # There was a problem, exit with an errorcode.
		return 0

	try:
		outfile=open(manifestfn, "w+")
	except SystemExit, e:
		raise
	except Exception, e:
		print "!!! Filesystem error skipping generation. (Read-Only?)"
		print "!!!",e
		return 0
	for x in digestCreateLines(mypfiles, mydigests):
		outfile.write(x+"\n")
	outfile.close()
	try:
		os.chown(manifestfn,os.getuid(),portage_gid)
		os.chmod(manifestfn,0664)
	except SystemExit, e:
		raise
	except Exception,e:
		print e

	if "cvs" in features and os.path.exists(pbasedir+"/CVS"):
		mycvstree=cvstree.getentries(pbasedir, recursive=1)
		myunaddedfiles=""
		if not manifestonly and not cvstree.isadded(mycvstree,digestfn):
			if digestfn[:len(pbasedir)]==pbasedir:
				myunaddedfiles=digestfn[len(pbasedir):]+" "
			else:
				myunaddedfiles=digestfn+" "
		if not cvstree.isadded(mycvstree,manifestfn[len(pbasedir):]):
			if manifestfn[:len(pbasedir)]==pbasedir:
				myunaddedfiles+=manifestfn[len(pbasedir):]+" "
			else:
				myunaddedfiles+=manifestfn
		if myunaddedfiles:
			if "autoaddcvs" in features:
				print blue(">>> Auto-adding digest file(s) to CVS...")
				spawn("cd "+pbasedir+"; cvs add "+myunaddedfiles,mysettings,free=1)
			else:
				print "--- Warning: digests are not yet added into CVS."
	print darkgreen(">>> Computed message digests.")
	print
	return 1


def digestParseFile(myfilename):
	"""(filename) -- Parses a given file for entries matching:
	MD5 MD5_STRING_OF_HEX_CHARS FILE_NAME FILE_SIZE
	Ignores lines that do not begin with 'MD5' and returns a
	dict with the filenames as keys and [md5,size] as the values."""

	if not os.path.exists(myfilename):
		return None
	mylines = portage_util.grabfile(myfilename, compat_level=1)

	mydigests={}
	for x in mylines:
		myline=string.split(x)
		if len(myline) < 4:
			#invalid line
			continue
		if myline[0] not in portage_checksum.get_valid_checksum_keys():
			continue
		mykey  = myline.pop(0)
		myhash = myline.pop(0)
		mysize = long(myline.pop())
		myfn   = string.join(myline, " ")
		if myfn not in mydigests:
			mydigests[myfn] = {}
		mydigests[myfn][mykey] = myhash
		if "size" in mydigests[myfn]:
			if mydigests[myfn]["size"] != mysize:
				raise portage_exception.DigestException, "Conflicting sizes in digest: %(filename)s" % {"filename":myfilename}
		else:
			mydigests[myfn]["size"] = mysize
	return mydigests

# XXXX strict was added here to fix a missing name error.
# XXXX It's used below, but we're not paying attention to how we get it?
def digestCheckFiles(myfiles, mydigests, basedir, note="", strict=0,verbosity=0):
	"""(fileslist, digestdict, basedir) -- Takes a list of files and a dict
	of their digests and checks the digests against the indicated files in
	the basedir given. Returns 1 only if all files exist and match the md5s.
	"""
	for x in myfiles:
		if not mydigests.has_key(x):
			writemsg("\n",verbosity)
			writemsg(red("!!! No message digest entry found for file \""+x+".\"")+"\n"+
			"!!! Most likely a temporary problem. Try 'emerge sync' again later.\n"+
			"!!! If you are certain of the authenticity of the file then you may type\n"+
			"!!! the following to generate a new digest:\n"+
			"!!!   ebuild /usr/portage/category/package/package-version.ebuild digest\n",
			verbosity)
			return 0
		myfile=os.path.normpath(basedir+"/"+x)
		if not os.path.exists(myfile):
			if strict:
				writemsg("!!! File does not exist:"+str(myfile)+"\n",verbosity)
				return 0
			continue
		
		ok,reason = portage_checksum.verify_all(myfile,mydigests[x])
		if not ok:
			writemsg("\n"+red("!!! Digest verification Failed:")+"\n"+
			red("!!!")+"    "+str(myfile)+"\n"+
			red("!!! Reason: ")+reason+"\n",
			verbosity)
			return 0
		else:
			writemsg(">>> md5 "+note+" ;-) %s\n" % str(x),verbosity)
	return 1


def digestcheck(myfiles, mysettings, strict=0,verbosity=0):
	"""Checks md5sums.  Assumes all files have been downloaded."""
	# archive files
	basedir=mysettings["DISTDIR"]+"/"
	digestfn=mysettings["FILESDIR"]+"/digest-"+mysettings["PF"]

	# portage files -- p(ortagefiles)basedir
	pbasedir=mysettings["O"]+"/"
	manifestfn=pbasedir+"Manifest"

	if not (os.path.exists(digestfn) and os.path.exists(manifestfn)):
		if "digest" in features:
			writemsg(">>> No package digest/Manifest file found.\n",verbosity)
			writemsg(">>> \"digest\" mode enabled; auto-generating new digest...\n",verbosity)
			return digestgen(myfiles,mysettings,verbosity=verbosity)
		else:
			if not os.path.exists(manifestfn):
				if strict:
					writemsg(red("!!! No package manifest found:")+" %s\n" % manifestfn,verbosity)
					return 0
				else:
					writemsg("--- No package manifest found: %s\n" % manifestfn,verbosity)
			if not os.path.exists(digestfn):
				writemsg("!!! No package digest file found: %s\n" % digestfn,verbosity)
				writemsg("!!! Type \"ebuild foo.ebuild digest\" to generate it.\n", verbosity)
				return 0

	mydigests=digestParseFile(digestfn)
	if mydigests==None:
		writemsg("!!! Failed to parse digest file: %s\n" % digestfn, verbosity)
		return 0
	mymdigests=digestParseFile(manifestfn)
	if "strict" not in features:
		# XXX: Remove this when manifests become mainstream.
		pass
	elif mymdigests==None:
			writemsg("!!! Failed to parse manifest file: %s\n" % manifestfn,verbosity)
			if strict:
				return 0
	else:
		# Check the portage-related files here.
		mymfiles=listdir(pbasedir,recursive=1,filesonly=1,ignorecvs=1,EmptyOnError=1)
		manifest_files = mymdigests.keys()
		for x in range(len(mymfiles)-1,-1,-1):
			if mymfiles[x]=='Manifest': # We don't want the manifest in out list.
				del mymfiles[x]
				continue
			if mymfiles[x] in manifest_files:
				manifest_files.remove(mymfiles[x])
			elif len(cvstree.apply_cvsignore_filter([mymfiles[x]]))==0:
				# we filter here, rather then above; manifest might have files flagged by the filter.
				# if something is returned, then it's flagged as a bad file
				# manifest doesn't know about it, so we kill it here.
				del mymfiles[x]
			else:
				writemsg(red("!!! Security Violation: A file exists that is not in the manifest.")+"\n",verbosity)
				writemsg("!!! File: %s\n" % mymfiles[x],verbosity)
				if strict:
					return 0
		if manifest_files and strict:
			writemsg(red("!!! Files listed in the manifest do not exist!")+"\n",verbosity)
			for x in manifest_files:
				writemsg(x+"\n",verbosity)
			return 0

		if not digestCheckFiles(mymfiles, mymdigests, pbasedir, note="files  ", strict=strict, verbosity=verbosity):
			if strict:
				writemsg(">>> Please ensure you have sync'd properly. Please try '"+bold("emerge sync")+"' and\n"+
				">>> optionally examine the file(s) for corruption. "+bold("A sync will fix most cases.")+"\n\n",
				verbosity)
				return 0
			else:
				writemsg("--- Manifest check failed. 'strict' not enabled; ignoring.\n\n",verbosity)
	
	# Just return the status, as it's the last check.
	return digestCheckFiles(myfiles, mydigests, basedir, note="src_uri", strict=strict,verbosity=verbosity)

# note, use_info_env is a hack to allow treewalk to specify the correct env.  it sucks, but so does this doebuild 
# setup
def doebuild(myebuild,mydo,myroot,mysettings,debug=0,listonly=0,fetchonly=0,cleanup=0,dbkey=None,use_cache=1,\
	fetchall=0,tree="porttree",allstages=True,use_info_env=True,verbosity=0):

	retval = ebuild.ebuild_handler().process_phase(mydo,mysettings,myebuild,myroot, debug=debug, listonly=listonly, \
	fetchonly=fetchonly, cleanup=cleanup, use_cache=use_cache, fetchall=fetchall, tree=tree, allstages=allstages, \
	use_info_env=use_info_env,verbosity=verbosity)

	#def doebuild(myebuild,mydo,myroot,mysettings,debug=0,listonly=0,fetchonly=0,cleanup=0,dbkey=None,use_cache=1,fetchall=0,tree="porttree",allstages=True,use_info_env=True):
#	retval=ebuild.ebuild_handler().process_phase(mydo, mysettings,myebuild,myroot,debug=debug,listonly=listonly,fetchonly=fetchonly,cleanup=cleanup,dbkey=None,use_cache=1,fetchall=0,tree="porttree",allstages=allstages,use_info_env=use_info_env)
	return retval


	
expandcache={}

def merge(mycat,mypkg,pkgloc,infloc,myroot,mysettings,myebuild=None):
	mylink=dblink(mycat,mypkg,myroot,mysettings)
	return mylink.merge(pkgloc,infloc,myroot,myebuild)
	
def unmerge(cat,pkg,myroot,mysettings,mytrimworld=1):
	mylink=dblink(cat,pkg,myroot,mysettings)
	if mylink.exists():
		mylink.unmerge(trimworld=mytrimworld,cleanup=1)
	mylink.delete()

def relparse(myver):
	"converts last version part into three components"
	number=0
	suffix=0
	endtype=0
	endnumber=0
	
	mynewver=string.split(myver,"_")
	myver=mynewver[0]

	#normal number or number with letter at end
	divider=len(myver)-1
	if myver[divider:] not in "1234567890":
		#letter at end
		suffix=ord(myver[divider:])
		number=string.atof(myver[0:divider])
	else:
		number=string.atof(myver)  

	if len(mynewver)==2:
		#an endversion
		for x in endversion_keys:
			elen=len(x)
			if mynewver[1][:elen] == x:
				match=1
				endtype=endversion[x]
				try:
					endnumber=string.atof(mynewver[1][elen:])
				except SystemExit, e:
					raise
				except:
					endnumber=0
				break
	return [number,suffix,endtype,endnumber]

iscache={}
def isspecific(mypkg):
	"now supports packages with no category"
	try:
		return iscache[mypkg]
	except SystemExit, e:
		raise
	except:
		pass
	mysplit=string.split(mypkg,"/")
	if not portage_dep.isjustname(mysplit[-1]):
			iscache[mypkg]=1
			return 1
	iscache[mypkg]=0
	return 0

def getCPFromCPV(mycpv):
	"""Calls portage_dep.pkgsplit on a cpv and returns only the cp."""
	return portage_dep.pkgsplit(mycpv)[0]

# vercmp:
# This takes two version strings and returns an integer to tell you whether
# the versions are the same, val1>val2 or val2>val1.
vcmpcache={}
def vercmp(val1,val2):
	if val1==val2:
		#quick short-circuit
		return 0
	valkey=val1+" "+val2
	try:
		return vcmpcache[valkey]
		try:
			return -vcmpcache[val2+" "+val1]
		except KeyError:
			pass
	except KeyError:
		pass
	
	# consider 1_p2 vc 1.1
	# after expansion will become (1_p2,0) vc (1,1)
	# then 1_p2 is compared with 1 before 0 is compared with 1
	# to solve the bug we need to convert it to (1,0_p2)
	# by splitting _prepart part and adding it back _after_expansion
	val1_prepart = val2_prepart = ''
	if val1.count('_'):
		val1, val1_prepart = val1.split('_', 1)
	if val2.count('_'):
		val2, val2_prepart = val2.split('_', 1)

	# replace '-' by '.'
	# FIXME: Is it needed? can val1/2 contain '-'?
	val1=string.split(val1,'-')
	if len(val1)==2:
		val1[0]=val1[0]+"."+val1[1]
	val2=string.split(val2,'-')
	if len(val2)==2:
		val2[0]=val2[0]+"."+val2[1]

	val1=string.split(val1[0],'.')
	val2=string.split(val2[0],'.')

	#add back decimal point so that .03 does not become "3" !
	for x in range(1,len(val1)):
		if val1[x][0] == '0' :
			val1[x]='.' + val1[x]
	for x in range(1,len(val2)):
		if val2[x][0] == '0' :
			val2[x]='.' + val2[x]

	# extend version numbers
	if len(val2)<len(val1):
		val2.extend(["0"]*(len(val1)-len(val2)))
	elif len(val1)<len(val2):
		val1.extend(["0"]*(len(val2)-len(val1)))

	# add back _prepart tails
	if val1_prepart:
		val1[-1] += '_' + val1_prepart
	if val2_prepart:
		val2[-1] += '_' + val2_prepart
	#The above code will extend version numbers out so they
	#have the same number of digits.
	for x in range(0,len(val1)):
		cmp1=relparse(val1[x])
		cmp2=relparse(val2[x])
		for y in range(0,4):
			myret=cmp1[y]-cmp2[y]
			if myret != 0:
				vcmpcache[valkey]=myret
				return myret
	vcmpcache[valkey]=0
	return 0


def pkgcmp(pkg1,pkg2):
	"""if returnval is less than zero, then pkg2 is newer than pkg1, zero if equal and positive if older."""
	if pkg1[0] != pkg2[0]:
		return None
	mycmp=vercmp(pkg1[1],pkg2[1])
	if mycmp>0:
		return 1
	if mycmp<0:
		return -1
	r1=int(pkg1[2][1:])
	r2=int(pkg2[2][1:])
	if r1>r2:
		return 1
	if r2>r1:
		return -1
	return 0

def dep_parenreduce(mysplit,mypos=0):
	"Accepts a list of strings, and converts '(' and ')' surrounded items to sub-lists"
	while (mypos<len(mysplit)): 
		if (mysplit[mypos]=="("):
			firstpos=mypos
			mypos=mypos+1
			while (mypos<len(mysplit)):
				if mysplit[mypos]==")":
					mysplit[firstpos:mypos+1]=[mysplit[firstpos+1:mypos]]
					mypos=firstpos
					break
				elif mysplit[mypos]=="(":
					#recurse
					mysplit=dep_parenreduce(mysplit,mypos=mypos)
				mypos=mypos+1
		mypos=mypos+1
	return mysplit

def dep_opconvert(mysplit,myuse,mysettings):
	"Does dependency operator conversion"
	
	#check_config_instance(mysettings)
	
	mypos=0
	newsplit=[]
	while mypos<len(mysplit):
		if type(mysplit[mypos])==types.ListType:
			newsplit.append(dep_opconvert(mysplit[mypos],myuse,mysettings))
			mypos += 1
		elif mysplit[mypos]==")":
			#mismatched paren, error
			return None
		elif mysplit[mypos]=="||":
			if ((mypos+1)>=len(mysplit)) or (type(mysplit[mypos+1])!=types.ListType):
				# || must be followed by paren'd list
				return None
			try:
				mynew=dep_opconvert(mysplit[mypos+1],myuse,mysettings)
			except SystemExit, e:
				raise
			except Exception, e:
				print "!!! Unable to satisfy OR dependency:",string.join(mysplit," || ")
				raise
			mynew[0:0]=["||"]
			newsplit.append(mynew)
			mypos += 2
		elif mysplit[mypos][-1]=="?":
			#uses clause, i.e "gnome? ( foo bar )"
			#this is a quick and dirty hack so that repoman can enable all USE vars:
			if (len(myuse)==1) and (myuse[0]=="*") and mysettings:
				# enable it even if it's ! (for repoman) but kill it if it's
				# an arch variable that isn't for this arch. XXX Sparc64?
				k=mysplit[mypos][:-1]
				if k[0]=="!":
					k=k[1:]
				if k not in archlist and k not in mysettings.usemask:
					enabled=1
				elif k in archlist:
					if k==mysettings["ARCH"]:
						if mysplit[mypos][0]=="!":
							enabled=0
						else:
							enabled=1
					elif mysplit[mypos][0]=="!":
						enabled=1
					else:
						enabled=0
				else:
					enabled=0
			else:
				if mysplit[mypos][0]=="!":
					myusevar=mysplit[mypos][1:-1]
					if myusevar in myuse:
						enabled=0
					else:
						enabled=1
				else:
					myusevar=mysplit[mypos][:-1]
					if myusevar in myuse:
						enabled=1
					else:
						enabled=0
			if (mypos+2<len(mysplit)) and (mysplit[mypos+2]==":"):
				#colon mode
				if enabled:
					#choose the first option
					if type(mysplit[mypos+1])==types.ListType:
						newsplit.append(dep_opconvert(mysplit[mypos+1],myuse,mysettings))
					else:
						newsplit.append(mysplit[mypos+1])
				else:
					#choose the alternate option
					if type(mysplit[mypos+1])==types.ListType:
						newsplit.append(dep_opconvert(mysplit[mypos+3],myuse,mysettings))
					else:
						newsplit.append(mysplit[mypos+3])
				mypos += 4
			else:
				#normal use mode
				if enabled:
					if type(mysplit[mypos+1])==types.ListType:
						newsplit.append(dep_opconvert(mysplit[mypos+1],myuse,mysettings))
					else:
						newsplit.append(mysplit[mypos+1])
				#otherwise, continue.
				mypos += 2
		else:
			#normal item
			newsplit.append(mysplit[mypos])
			mypos += 1
	return newsplit

def dep_virtual(mysplit, mysettings):
	"Does virtual dependency conversion"



	newsplit=[]
	for x in mysplit:
		if type(x)==types.ListType:
			newsplit.append(dep_virtual(x, mysettings))
		else:
			mykey=dep_getkey(x)
			if mysettings.virtuals.has_key(mykey):
				if len(mysettings.virtuals[mykey])==1:
					a=string.replace(x, mykey, mysettings.virtuals[mykey][0])
				else:
					if x[0]=="!":
						# blocker needs "and" not "or(||)".
						a=[]
					else:
						a=['||']
					for y in mysettings.virtuals[mykey]:
						a.append(string.replace(x, mykey, y))
				newsplit.append(a)
			else:
				newsplit.append(x)
	return newsplit

def dep_eval(deplist):
	if len(deplist)==0:
		return 1
	if deplist[0]=="||":
		#or list; we just need one "1"
		for x in deplist[1:]:
			if type(x)==types.ListType:
				if dep_eval(x)==1:
					return 1
			elif x==1:
					return 1
		return 0
	else:
		for x in deplist:
			if type(x)==types.ListType:
				if dep_eval(x)==0:
					return 0
			elif x==0 or x==2:
				return 0
		return 1

def dep_zapdeps(unreduced,reduced,vardbapi=None,use_binaries=0):
	"""Takes an unreduced and reduced deplist and removes satisfied dependencies.
	Returned deplist contains steps that must be taken to satisfy dependencies."""
	writemsg("ZapDeps -- %s\n" % (use_binaries), 2)
	if unreduced==[] or unreduced==['||'] :
		return []
	if unreduced[0]=="||":
		if dep_eval(reduced):
			#deps satisfied, return empty list.
			return []
		else:
			#try to find an installed dep.
			### We use fakedb when --update now, so we can't use local vardbapi here.
			### This should be fixed in the feature.
			### see bug 45468.
			##if vardbapi:
			##	mydbapi=vardbapi
			##else:
			##	mydbapi=db[root]["vartree"].dbapi
			mydbapi=db[root]["vartree"].dbapi

			if db["/"].has_key("porttree"):
				myportapi=db["/"]["porttree"].dbapi
			else:
				myportapi=None

			if use_binaries and db["/"].has_key("bintree"):
				mybinapi=db["/"]["bintree"].dbapi
				writemsg("Using bintree...\n",2)
			else:
				mybinapi=None

			x=1
			candidate=[]
			while x<len(reduced):
				writemsg("x: %s, reduced[x]: %s\n" % (x,reduced[x]), 2)
				if (type(reduced[x])==types.ListType):
					newcand = dep_zapdeps(unreduced[x], reduced[x], vardbapi=vardbapi, use_binaries=use_binaries)
					candidate.append(newcand)
				else:
					if (reduced[x]==False):
						candidate.append([unreduced[x]])
					else:
						candidate.append([])
				x+=1

			#use installed and no-masked package(s) in portage.
			for x in candidate:
				match=1
				for pkg in x:
					if not mydbapi.match(pkg):
						match=0
						break
					if myportapi:
						if not myportapi.match(pkg):
							match=0
							break
				if match:
					writemsg("Installed match: %s\n" % (x), 2)
					return x

			# Use binary packages if available.
			if mybinapi:
				for x in candidate:
					match=1
					for pkg in x:
						if not mybinapi.match(pkg):
							match=0
							break
						else:
							writemsg("Binary match: %s\n" % (pkg), 2)
					if match:
						writemsg("Binary match final: %s\n" % (x), 2)
						return x

			#use no-masked package(s) in portage tree
			if myportapi:
				for x in candidate:
					match=1
					for pkg in x:
						if not myportapi.match(pkg):
							match=0
							break
					if match:
						writemsg("Porttree match: %s\n" % (x), 2)
						return x

			#none of the no-masked pkg, use the first one
			writemsg("Last resort candidate: %s\n" % (candidate[0]), 2)
			return candidate[0]
	else:
		if dep_eval(reduced):
			#deps satisfied, return empty list.
			return []
		else:
			returnme=[]
			x=0
			while x<len(reduced):
				if type(reduced[x])==types.ListType:
					returnme+=dep_zapdeps(unreduced[x],reduced[x], vardbapi=vardbapi, use_binaries=use_binaries)
				else:
					if reduced[x]==False:
						returnme.append(unreduced[x])
				x += 1
			return returnme

def dep_getkey(mydep):
	if not len(mydep):
		return mydep
	if mydep[0]=="*":
		mydep=mydep[1:]
	if mydep[-1]=="*":
		mydep=mydep[:-1]
	if mydep[0]=="!":
		mydep=mydep[1:]
	if mydep[:2] in [ ">=", "<=" ]:
		mydep=mydep[2:]
	elif mydep[:1] in "=<>~":
		mydep=mydep[1:]
	if isspecific(mydep):
		mysplit=portage_dep.catpkgsplit(mydep)
		if not mysplit:
			return mydep
		return mysplit[0]+"/"+mysplit[1]
	else:
		return mydep

def cpv_getkey(mycpv):
	myslash=mycpv.split("/")
	mysplit=portage_dep.pkgsplit(myslash[-1])
	mylen=len(myslash)
	if mylen==2:
		return myslash[0]+"/"+mysplit[0]
	elif mylen==1:
		return mysplit[0]
	else:
		return mysplit

def key_expand(mykey,mydb=None,use_cache=1):
	mysplit=mykey.split("/")
	if len(mysplit)==1:
		if mydb and type(mydb)==types.InstanceType:
			for x in settings.categories:
				if mydb.cp_list(x+"/"+mykey,use_cache=use_cache):
					return x+"/"+mykey
			if virts_p.has_key(mykey):
				print "VIRTS_P (Report to #gentoo-portage or bugs.g.o):",mykey
				return(virts_p[mykey][0])
		return "null/"+mykey
	elif mydb:
		if type(mydb)==types.InstanceType:
			if (not mydb.cp_list(mykey,use_cache=use_cache)) and virts and virts.has_key(mykey):
				return virts[mykey][0]
		return mykey

def cpv_expand(mycpv,mydb=None,use_cache=1):
	"""Given a string (packagename or virtual) expand it into a valid
	cat/package string. Virtuals use the mydb to determine which provided
	virtual is a valid choice and defaults to the first element when there
	are no installed/available candidates."""
	myslash=mycpv.split("/")
	mysplit=portage_dep.pkgsplit(myslash[-1])
	if len(myslash)>2:
		# this is illegal case.
		mysplit=[]
		mykey=mycpv
	elif len(myslash)==2:
		if mysplit:
			mykey=myslash[0]+"/"+mysplit[0]
		else:
			mykey=mycpv
		if mydb:
			writemsg("mydb.__class__: %s\n" % (mydb.__class__), 1)
			if type(mydb)==types.InstanceType:
				if (not mydb.cp_list(mykey,use_cache=use_cache)) and virts and virts.has_key(mykey):
					writemsg("virts[%s]: %s\n" % (str(mykey),virts[mykey]), 1)
					mykey_orig = mykey[:]
					for vkey in virts[mykey]:
						if mydb.cp_list(vkey,use_cache=use_cache):
							mykey = vkey
							writemsg("virts chosen: %s\n" % (mykey), 1)
							break
					if mykey == mykey_orig:
						mykey=virts[mykey][0]
						writemsg("virts defaulted: %s\n" % (mykey), 1)
			#we only perform virtual expansion if we are passed a dbapi
	else:
		#specific cpv, no category, ie. "foo-1.0"
		if mysplit:
			myp=mysplit[0]
		else:
			# "foo" ?
			myp=mycpv
		mykey=None
		matches=[]
		if mydb:
			for x in settings.categories:
				if mydb.cp_list(x+"/"+myp,use_cache=use_cache):
					matches.append(x+"/"+myp)
		if (len(matches)>1):
			raise ValueError, matches
		elif matches:
			mykey=matches[0]

		if not mykey and type(mydb)!=types.ListType:
			if virts_p.has_key(myp):
				print "VIRTS_P,ce (Report to #gentoo-portage or bugs.g.o):",myp
				mykey=virts_p[myp][0]
			#again, we only perform virtual expansion if we have a dbapi (not a list)
		if not mykey:
			mykey="null/"+myp
	if mysplit:
		if mysplit[2]=="r0":
			return mykey+"-"+mysplit[1]
		else:
			return mykey+"-"+mysplit[1]+"-"+mysplit[2]
	else:
		return mykey

def dep_transform(mydep,oldkey,newkey):
	origdep=mydep
	if not len(mydep):
		return mydep
	if mydep[0]=="*":
		mydep=mydep[1:]
	prefix=""
	postfix=""
	if mydep[-1]=="*":
		mydep=mydep[:-1]
		postfix="*"
	if mydep[:2] in [ ">=", "<=" ]:
		prefix=mydep[:2]
		mydep=mydep[2:]
	elif mydep[:1] in "=<>~!":
		prefix=mydep[:1]
		mydep=mydep[1:]
	if mydep==oldkey:
		return prefix+newkey+postfix
	else:
		return origdep

def dep_expand(mydep,mydb=None,use_cache=1):
	if not len(mydep):
		return mydep
	if mydep[0]=="*":
		mydep=mydep[1:]
	prefix=""
	postfix=""
	if mydep[-1]=="*":
		mydep=mydep[:-1]
		postfix="*"
	if mydep[:2] in [ ">=", "<=" ]:
		prefix=mydep[:2]
		mydep=mydep[2:]
	elif mydep[:1] in "=<>~!":
		prefix=mydep[:1]
		mydep=mydep[1:]
	return prefix+cpv_expand(mydep,mydb=mydb,use_cache=use_cache)+postfix

def get_parsed_deps(depstring,mydbapi,mysettings,use="yes",mode=None,myuse=None):
	#check_config_instance(mysettings)

	if use=="all":
		#enable everything (for repoman)
		myusesplit=["*"]
	elif use=="yes":
		if myuse==None:
			#default behavior
			myusesplit = string.split(mysettings["USE"])
		else:
			myusesplit = myuse
			# We've been given useflags to use.
			#print "USE FLAGS PASSED IN."
			#print myuse
			#if "bindist" in myusesplit:
			#	print "BINDIST is set!"
			#else:
			#	print "BINDIST NOT set."
	else:
		#we are being run by autouse(), don't consult USE vars yet.
		# WE ALSO CANNOT USE SETTINGS
		myusesplit=[]
		
	#convert parenthesis to sublists
	mysplit = portage_dep.paren_reduce(depstring)

	if mysettings:
		# XXX: use="all" is only used by repoman. Why would repoman checks want
		# profile-masked USE flags to be enabled?
		#if use=="all":
		#	mymasks=archlist[:]
		#else:
		mymasks=mysettings.usemask+archlist[:]

		while mysettings["ARCH"] in mymasks:
			del mymasks[mymasks.index(mysettings["ARCH"])]
		mysplit = portage_dep.use_reduce(mysplit,uselist=myusesplit,masklist=mymasks,matchall=(use=="all"),excludeall=[mysettings["ARCH"]])
	else:
		mysplit = portage_dep.use_reduce(mysplit,uselist=myusesplit,matchall=(use=="all"))
	return mysplit
	
def dep_check(depstring,mydbapi,mysettings,use="yes",mode=None,myuse=None,use_cache=1,use_binaries=0):
	"""Takes a depend string and parses the condition."""

	mysplit=get_parsed_deps(depstring,mydbapi,mysettings,use=use,myuse=myuse)
	# Do the || conversions
	mysplit=portage_dep.dep_opconvert(mysplit)
	
	#convert virtual dependencies to normal packages.
	mysplit=dep_virtual(mysplit, mysettings)
	#if mysplit==None, then we have a parse error (paren mismatch or misplaced ||)
	#up until here, we haven't needed to look at the database tree

	if mysplit==None:
		return [0,"Parse Error (parentheses mismatch?)"]
	elif mysplit==[]:
		#dependencies were reduced to nothing
		return [1,[]]
	mysplit2=mysplit[:]
	mysplit2=dep_wordreduce(mysplit2,mysettings,mydbapi,mode,use_cache=use_cache)
	if mysplit2==None:
		return [0,"Invalid token"]
	
	writemsg("\n\n\n", 1)
	writemsg("mysplit:  %s\n" % (mysplit), 1)
	writemsg("mysplit2: %s\n" % (mysplit2), 1)
	myeval=dep_eval(mysplit2)
	writemsg("myeval:   %s\n" % (myeval), 1)
	
	if myeval:
		return [1,[]]
	else:
		myzaps = dep_zapdeps(mysplit,mysplit2,vardbapi=mydbapi,use_binaries=use_binaries)
		mylist = flatten(myzaps)
		writemsg("myzaps:   %s\n" % (myzaps), 1)
		writemsg("mylist:   %s\n" % (mylist), 1)
		#remove duplicates
		mydict={}
		for x in mylist:
			mydict[x]=1
		writemsg("mydict:   %s\n" % (mydict), 1)
		return [1,mydict.keys()]

def dep_wordreduce(mydeplist,mysettings,mydbapi,mode,use_cache=1):
	"Reduces the deplist to ones and zeros"
	mypos=0
	deplist=mydeplist[:]
	while mypos<len(deplist):
		if type(deplist[mypos])==types.ListType:
			#recurse
			deplist[mypos]=dep_wordreduce(deplist[mypos],mysettings,mydbapi,mode,use_cache=use_cache)
		elif deplist[mypos]=="||":
			pass
		else:
			mykey = dep_getkey(deplist[mypos])
			if mysettings and mysettings.pprovideddict.has_key(mykey) and \
			        match_from_list(deplist[mypos], mysettings.pprovideddict[mykey]):
				deplist[mypos]=True
			else:
				if mode:
					mydep=mydbapi.xmatch(mode,deplist[mypos])
				else:
					mydep=mydbapi.match(deplist[mypos],use_cache=use_cache)
				if mydep!=None:
					tmp=(len(mydep)>=1)
					if deplist[mypos][0]=="!":
						#tmp=not tmp
						# This is ad-hoc code. We should rewrite this later.. (See #52377)
						# The reason is that portage uses fakedb when --update option now.
						# So portage considers that a block package doesn't exist even if it exists.
						# Then, #52377 happens.
						# ==== start
						# emerge checks if it's block or not, so we can always set tmp=False.
						# but it's not clean..
						tmp=False
						# ==== end
					deplist[mypos]=tmp
				else:
					#encountered invalid string
					return None
		mypos=mypos+1
	return deplist

def fixdbentries(old_value, new_value, dbdir):
	"""python replacement for the fixdbentries script, replaces old_value 
	with new_value for package names in files in dbdir."""
	for myfile in [f for f in os.listdir(dbdir) if not f == "CONTENTS"]:
		f = open(dbdir+"/"+myfile, "r")
		mycontent = f.read()
		f.close()
		if not mycontent.count(old_value):
			continue
		old_value = re.escape(old_value);
		mycontent = re.sub(old_value+"$", new_value, mycontent)
		mycontent = re.sub(old_value+"(\\s)", new_value+"\\1", mycontent)
		mycontent = re.sub(old_value+"(-[^a-zA-Z])", new_value+"\\1", mycontent)
		mycontent = re.sub(old_value+"([^a-zA-Z0-9-])", new_value+"\\1", mycontent)
		f = open(dbdir+"/"+myfile, "w")
		f.write(mycontent)
		f.close()

class packagetree:
	def __init__(self,virtual,clone=None):
		if clone:
			self.tree=clone.tree.copy()
			self.populated=clone.populated
			self.virtual=clone.virtual
			self.dbapi=None
		else:
			self.tree={}
			self.populated=0
			self.virtual=virtual
			self.dbapi=None
		
	def resolve_key(self,mykey):
		return key_expand(mykey,mydb=self.dbapi)
	
	def dep_nomatch(self,mypkgdep):
		mykey=dep_getkey(mypkgdep)
		nolist=self.dbapi.cp_list(mykey)
		mymatch=self.dbapi.match(mypkgdep)
		if not mymatch:
			return nolist
		for x in mymatch:
			if x in nolist:
				nolist.remove(x)
		return nolist

	def depcheck(self,mycheck,use="yes",myusesplit=None):
		return dep_check(mycheck,self.dbapi,use=use,myuse=myusesplit)

	def populate(self):
		"populates the tree with values"
		populated=1
		pass

def best(mymatches):
	"accepts None arguments; assumes matches are valid."
	global bestcount
	if mymatches==None:
		return "" 
	if not len(mymatches):
		return "" 
	bestmatch=mymatches[0]
	p2=portage_dep.catpkgsplit(bestmatch)[1:]
	for x in mymatches[1:]:
		p1=portage_dep.catpkgsplit(x)[1:]
		if pkgcmp(p1,p2)>0:
			bestmatch=x
			p2=portage_dep.catpkgsplit(bestmatch)[1:]
	return bestmatch		

def match_to_list(mypkg,mylist):
	"""(pkgname,list)
	Searches list for entries that matches the package.
	"""
	matches=[]
	for x in mylist:
		if match_from_list(x,[mypkg]):
			if x not in matches:
				matches.append(x)
	return matches

def best_match_to_list(mypkg,mylist):
	"""(pkgname,list)
	Returns the most specific entry (assumed to be the longest one)
	that matches the package given.
	"""
	# XXX Assumption is wrong sometimes.
	maxlen = 0
	bestm  = None
	for x in match_to_list(mypkg,mylist):
		if len(x) > maxlen:
			maxlen = len(x)
			bestm  = x
	return bestm

def catsplit(mydep):
	return mydep.split("/", 1)
	
def match_from_list(mydep,candidate_list):
	if mydep[0] == "!":
		mydep = mydep[1:]

	mycpv     = portage_dep.dep_getcpv(mydep)
	mycpv_cps = portage_dep.catpkgsplit(mycpv) # Can be None if not specific

	if not mycpv_cps:
		cat,pkg = catsplit(mycpv)
		ver     = None
		rev     = None
	else:
		cat,pkg,ver,rev = mycpv_cps
		if mydep == mycpv:
			raise KeyError, "Specific key requires an operator (%s) (try adding an '=')" % (mydep)

	if ver and rev:
		operator = portage_dep.get_operator(mydep)
		if not operator:
			writemsg("!!! Invanlid atom: %s\n" % mydep)
			return []
	else:
		operator = None

	mylist = []

	if operator == None:
		for x in candidate_list:
			xs = portage_dep.pkgsplit(x)
			if xs == None:
				if x != mycpv:
					continue
			elif xs[0] != mycpv:
				continue
			mylist.append(x)

	elif operator == "=": # Exact match
		if mycpv in candidate_list:
			mylist = [mycpv]
	
	elif operator == "=*": # glob match
		# The old verion ignored _tag suffixes... This one doesn't.
		for x in candidate_list:
			if x[0:len(mycpv)] == mycpv:
				mylist.append(x)

	elif operator == "~": # version, any revision, match
		for x in candidate_list:
			xs = portage_dep.catpkgsplit(x)
			if xs[0:2] != mycpv_cps[0:2]:
				continue
			if xs[2] != ver:
				continue
			mylist.append(x)

	elif operator in [">", ">=", "<", "<="]:
		for x in candidate_list:
			try:
				result = pkgcmp(portage_dep.pkgsplit(x), [cat+"/"+pkg,ver,rev])
			except SystemExit, e:
				raise
			except:
				writemsg("\nInvalid package name: %s\n" % x)
				sys.exit(73)
			if result == None:
				continue
			elif operator == ">":
				if result > 0:
					mylist.append(x)
			elif operator == ">=":
				if result >= 0:
					mylist.append(x)
			elif operator == "<":
				if result < 0:
					mylist.append(x)
			elif operator == "<=":
				if result <= 0:
					mylist.append(x)
			else:
				raise KeyError, "Unknown operator: %s" % mydep
	else:
		raise KeyError, "Unknown operator: %s" % mydep
	

	return mylist
				

def match_from_list_original(mydep,mylist):
	"""(dep,list)
	Reduces the list down to those that fit the dep
	"""
	mycpv=portage_dep.dep_getcpv(mydep)
	if isspecific(mycpv):
		cp_key=portage_dep.catpkgsplit(mycpv)
		if cp_key==None:
			return []
	else:
		cp_key=None
	#Otherwise, this is a special call; we can only select out of the ebuilds specified in the specified mylist
	if (mydep[0]=="="):
		if cp_key==None:
			return []
		if mydep[-1]=="*":
			#example: "=sys-apps/foo-1.0*"
			try:
				#now, we grab the version of our dependency...
				mynewsplit=string.split(cp_key[2],'.')
				#split it...
				mynewsplit[-1]=`int(mynewsplit[-1])+1`
				#and increment the last digit of the version by one.
				#We don't need to worry about _pre and friends because they're not supported with '*' deps.
				new_v=string.join(mynewsplit,".")+"_alpha0"
				#new_v will be used later in the code when we do our comparisons using pkgcmp()
			except SystemExit, e:
				raise
			except:
				#erp, error.
				return [] 
			mynodes=[]
			cmp1=cp_key[1:]
			cmp1[1]=cmp1[1]+"_alpha0"
			cmp2=[cp_key[1],new_v,"r0"]
			for x in mylist:
				cp_x=portage_dep.catpkgsplit(x)
				if cp_x==None:
					#hrm, invalid entry.  Continue.
					continue
				#skip entries in our list that do not have matching categories
				if cp_key[0]!=cp_x[0]:
					continue
				# ok, categories match. Continue to next step.	
				if ((pkgcmp(cp_x[1:],cmp1)>=0) and (pkgcmp(cp_x[1:],cmp2)<0)):
					# entry is >= the version in specified in our dependency, and <= the version in our dep + 1; add it:
					mynodes.append(x)
			return mynodes
		else:
			# Does our stripped key appear literally in our list?  If so, we have a match; if not, we don't.
			if mycpv in mylist:
				return [mycpv]
			else:
				return []
	elif (mydep[0]==">") or (mydep[0]=="<"):
		if cp_key==None:
			return []
		if (len(mydep)>1) and (mydep[1]=="="):
			cmpstr=mydep[0:2]
		else:
			cmpstr=mydep[0]
		mynodes=[]
		for x in mylist:
			cp_x=portage_dep.catpkgsplit(x)
			if cp_x==None:
				#invalid entry; continue.
				continue
			if cp_key[0]!=cp_x[0]:
				continue
			if eval("pkgcmp(cp_x[1:],cp_key[1:])"+cmpstr+"0"):
				mynodes.append(x)
		return mynodes
	elif mydep[0]=="~":
		if cp_key==None:
			return []
		myrev=-1
		for x in mylist:
			cp_x=portage_dep.catpkgsplit(x)
			if cp_x==None:
				#invalid entry; continue
				continue
			if cp_key[0]!=cp_x[0]:
				continue
			if cp_key[2]!=cp_x[2]:
				#if version doesn't match, skip it
				continue
			myint = int(cp_x[3][1:])
			if myint > myrev:
				myrev   = myint
				mymatch = x
		if myrev == -1:
			return []
		else:
			return [mymatch]
	elif cp_key==None:
		if mydep[0]=="!":
			return []
			#we check ! deps in emerge itself, so always returning [] is correct.
		mynodes=[]
		cp_key=mycpv.split("/")
		for x in mylist:
			cp_x=portage_dep.catpkgsplit(x)
			if cp_x==None:
				#invalid entry; continue
				continue
			if cp_key[0]!=cp_x[0]:
				continue
			if cp_key[1]!=cp_x[1]:
				continue
			mynodes.append(x)
		return mynodes
	else:
		return []


class portagetree:
	def __init__(self,root="/",virtual=None,clone=None):
		global portdb
		if clone:
			self.root=clone.root
			self.portroot=clone.portroot
			self.pkglines=clone.pkglines
		else:
			self.root=root
			self.portroot=settings["PORTDIR"]
			self.virtual=virtual
			self.dbapi=portdb

	def dep_bestmatch(self,mydep):
		"compatibility method"
		mymatch=self.dbapi.xmatch("bestmatch-visible",mydep)
		if mymatch==None:
			return ""
		return mymatch

	def dep_match(self,mydep):
		"compatibility method"
		mymatch=self.dbapi.xmatch("match-visible",mydep)
		if mymatch==None:
			return []
		return mymatch

	def exists_specific(self,cpv):
		return self.dbapi.cpv_exists(cpv)

	def getallnodes(self):
		"""new behavior: these are all *unmasked* nodes.  There may or may not be available
		masked package for nodes in this nodes list."""
		return self.dbapi.cp_all()

	def getname(self,pkgname):
		"returns file location for this particular package (DEPRECATED)"
		if not pkgname:
			return ""
		mysplit=string.split(pkgname,"/")
		psplit=portage_dep.pkgsplit(mysplit[1])
		return self.portroot+"/"+mysplit[0]+"/"+psplit[0]+"/"+mysplit[1]+".ebuild"

	def resolve_specific(self,myspec):
		cps=portage_dep.catpkgsplit(myspec)
		if not cps:
			return None
		mykey=key_expand(cps[0]+"/"+cps[1],mydb=self.dbapi)
		mykey=mykey+"-"+cps[2]
		if cps[3]!="r0":
			mykey=mykey+"-"+cps[3]
		return mykey

	def depcheck(self,mycheck,use="yes",myusesplit=None):
		return dep_check(mycheck,self.dbapi,use=use,myuse=myusesplit)

	def getslot(self,mycatpkg):
		"Get a slot for a catpkg; assume it exists."
		myslot = ""
		try:
			myslot=self.dbapi.aux_get(mycatpkg,["SLOT"])[0]
		except SystemExit, e:
			raise
		except Exception, e:
			pass
		return myslot


class dbapi:
	def __init__(self):
		pass
	
	def close_caches(self):
		pass

	def cp_list(self,cp,use_cache=1):
		return

	def aux_get(self,mycpv,mylist):
		"stub code for returning auxiliary db information, such as SLOT, DEPEND, etc."
		'input: "sys-apps/foo-1.0",["SLOT","DEPEND","HOMEPAGE"]'
		'return: ["0",">=sys-libs/bar-1.0","http://www.foo.com"] or [] if mycpv not found'
		raise NotImplementedError

	def match(self,origdep,use_cache=1):
		mydep=dep_expand(origdep,mydb=self)
		mykey=dep_getkey(mydep)
		mycat=mykey.split("/")[0]
		return match_from_list(mydep,self.cp_list(mykey,use_cache=use_cache))

	def match2(self,mydep,mykey,mylist):
		writemsg("DEPRECATED: dbapi.match2\n")
		match_from_list(mydep,mylist)

	def counter_tick(self,myroot,mycpv=None):
		return self.counter_tick_core(myroot,incrementing=1,mycpv=mycpv)

	def get_counter_tick_core(self,myroot,mycpv=None):
		return self.counter_tick_core(myroot,incrementing=0,mycpv=mycpv)+1

	def counter_tick_core(self,myroot,incrementing=1,mycpv=None):
		"This method will grab the next COUNTER value and record it back to the global file.  Returns new counter value."
		cpath=myroot+"var/cache/edb/counter"
		changed=0
		min_counter = 0
		if mycpv:
			mysplit = portage_dep.pkgsplit(mycpv)
			for x in self.match(mysplit[0],use_cache=0):
				# fixed bug #41062
				if x==mycpv:
					continue
				try:
					old_counter = long(self.aux_get(x,["COUNTER"])[0])
					writemsg("COUNTER '%d' '%s'\n" % (old_counter, x),1)
				except SystemExit, e:
					raise
				except:
					old_counter = 0
					writemsg("!!! BAD COUNTER in '%s'\n" % (x))
				if old_counter > min_counter:
					min_counter = old_counter

		# We write our new counter value to a new file that gets moved into
		# place to avoid filesystem corruption.
		if os.path.exists(cpath):
			cfile=open(cpath, "r")
			try:
				counter=long(cfile.readline())
			except (ValueError,OverflowError):
				try:
					counter=long(portage_exec.spawn_get_output("for FILE in $(find /"+VDB_PATH+" -type f -name COUNTER); do echo $(<${FILE}); done | sort -n | tail -n1 | tr -d '\n'",spawn_type=portage_exec.spawn_bash)[1])
					writemsg("!!! COUNTER was corrupted; resetting to value of %d\n" % counter)
					changed=1
				except (ValueError,OverflowError):
					writemsg("!!! COUNTER data is corrupt in pkg db. The values need to be\n")
					writemsg("!!! corrected/normalized so that portage can operate properly.\n")
					writemsg("!!! A simple solution is not yet available so try #gentoo on IRC.\n")
					sys.exit(2)
			cfile.close()
		else:
			try:
				counter=long(portage_exec.spawn_get_output("for FILE in $(find /"+VDB_PATH+" -type f -name COUNTER); do echo $(<${FILE}); done | sort -n | tail -n1 | tr -d '\n'",spawn_type=portage_exec.spawn_bash)[1])
				writemsg("!!! Global counter missing. Regenerated from counter files to: %s\n" % counter)
			except SystemExit, e:
				raise
			except:
				writemsg("!!! Initializing global counter.\n")
				counter=long(0)
			changed=1

		if counter < min_counter:
			counter = min_counter+1000
			changed = 1

		if incrementing or changed:
			
			#increment counter
			counter += 1
			# update new global counter file
			newcpath=cpath+".new"
			newcfile=open(newcpath,"w")
			newcfile.write(str(counter))
			newcfile.close()
			# now move global counter file into place
			os.rename(newcpath,cpath)
		return counter

	def invalidentry(self, mypath):
		if re.search("portage_lockfile$",mypath):
			if not os.environ.has_key("PORTAGE_MASTER_PID"):
				writemsg("Lockfile removed: %s\n" % mypath, 1)
				portage_locks.unlockfile((mypath,None,None))
			else:
				# Nothing we can do about it. We're probably sandboxed.
				pass
		elif re.search(".*/-MERGING-(.*)",mypath):
			if os.path.exists(mypath):
				writemsg(red("INCOMPLETE MERGE:")+" "+mypath+"\n")
		else:
			writemsg("!!! Invalid db entry: %s\n" % mypath)



class fakedbapi(dbapi):
	"This is a dbapi to use for the emptytree function.  It's empty, but things can be added to it."
	def __init__(self):
		self.cpvdict={}
		self.cpdict={}

	def cpv_exists(self,mycpv):
		return self.cpvdict.has_key(mycpv)
	
	def cp_list(self,mycp,use_cache=1):
		if not self.cpdict.has_key(mycp):
			return []
		else:
			return self.cpdict[mycp]

	def cp_all(self):
		returnme=[]
		for x in self.cpdict.keys():
			returnme.extend(self.cpdict[x])
		return returnme

	def cpv_inject(self,mycpv):
		"""Adds a cpv from the list of available packages."""
		mycp=cpv_getkey(mycpv)
		self.cpvdict[mycpv]=1
		if not self.cpdict.has_key(mycp):
			self.cpdict[mycp]=[]
		if not mycpv in self.cpdict[mycp]:
			self.cpdict[mycp].append(mycpv)

	#def cpv_virtual(self,oldcpv,newcpv):
	#	"""Maps a cpv to the list of available packages."""
	#	mycp=cpv_getkey(newcpv)
	#	self.cpvdict[newcpv]=1
	#	if not self.virtdict.has_key(mycp):
	#		self.virtdict[mycp]=[]
	#	if not mycpv in self.virtdict[mycp]:
	#		self.virtdict[mycp].append(oldcpv)
	#	cpv_remove(oldcpv)

	def cpv_remove(self,mycpv):
		"""Removes a cpv from the list of available packages."""
		mycp=cpv_getkey(mycpv)
		if self.cpvdict.has_key(mycpv):
			del	self.cpvdict[mycpv]
		if not self.cpdict.has_key(mycp):
			return
		while mycpv in self.cpdict[mycp]:
			del self.cpdict[mycp][self.cpdict[mycp].index(mycpv)]
		if not len(self.cpdict[mycp]):
			del self.cpdict[mycp]

class bindbapi(fakedbapi):
	def __init__(self,mybintree=None):
		self.bintree = mybintree
		self.cpvdict={}
		self.cpdict={}

	def aux_get(self,mycpv,wants):
		mysplit = string.split(mycpv,"/")
		mylist  = []
		tbz2name = mysplit[1]+".tbz2"
		if self.bintree and not self.bintree.isremote(mycpv):
			tbz2 = xpak.tbz2(self.bintree.getname(mycpv))
		for x in wants:
			if self.bintree and self.bintree.isremote(mycpv):
				# We use the cache for remote packages
				if self.bintree.remotepkgs[tbz2name].has_key(x):
					mylist.append(self.bintree.remotepkgs[tbz2name][x][:]) # [:] Copy String
				else:
					mylist.append("")
			else:
				myval = tbz2.getfile(x)
				if myval == None:
					myval = ""
				else:
					myval = string.join(myval.split(),' ')
				mylist.append(myval)

		return mylist


cptot=0
class vardbapi(dbapi):
	def __init__(self,root,categories=None):
		self.root       = root[:]
		#cache for category directory mtimes
		self.mtdircache = {}
		#cache for dependency checks
		self.matchcache = {}
		#cache for cp_list results
		self.cpcache    = {}	
		self.blockers   = None
		self.categories = copy.deepcopy(categories)

	def cpv_exists(self,mykey):
		"Tells us whether an actual ebuild exists on disk (no masking)"
		return os.path.exists(self.root+VDB_PATH+"/"+mykey)

	def cpv_counter(self,mycpv):
		"This method will grab the COUNTER. Returns a counter value."
		cdir=self.root+VDB_PATH+"/"+mycpv
		cpath=self.root+VDB_PATH+"/"+mycpv+"/COUNTER"

		# We write our new counter value to a new file that gets moved into
		# place to avoid filesystem corruption on XFS (unexpected reboot.)
		corrupted=0
		if os.path.exists(cpath):
			cfile=open(cpath, "r")
			try:
				counter=long(cfile.readline())
			except ValueError:
				print "portage: COUNTER for",mycpv,"was corrupted; resetting to value of 0"
				counter=long(0)
				corrupted=1
			cfile.close()
		elif os.path.exists(cdir):
			mys = portage_dep.pkgsplit(mycpv)
			myl = self.match(mys[0],use_cache=0)
			print mys,myl
			if len(myl) == 1:
				try:
					# Only one package... Counter doesn't matter.
					myf = open(cpath, "w")
					myf.write("1")
					myf.flush()
					myf.close()
					counter = 1
				except SystemExit, e:
					raise
				except Exception, e:
					writemsg("!!! COUNTER file is missing for "+str(mycpv)+" in /var/db.\n")
					writemsg("!!! Please run /usr/lib/portage/bin/fix-db.pl or\n")
					writemsg("!!! Please run /usr/lib/portage/bin/fix-db.py or\n")
					writemsg("!!! unmerge this exact version.\n")
					writemsg("!!! %s\n" % e)
					sys.exit(1)
			else:
				writemsg("!!! COUNTER file is missing for "+str(mycpv)+" in /var/db.\n")
				writemsg("!!! Please run /usr/lib/portage/bin/fix-db.pl or\n")
				writemsg("!!! Please run /usr/lib/portage/bin/fix-db.py or\n")
				writemsg("!!! remerge the package.\n")
				sys.exit(1)
		else:
			counter=long(0)
		if corrupted:
			newcpath=cpath+".new"
			# update new global counter file
			newcfile=open(newcpath,"w")
			newcfile.write(str(counter))
			newcfile.close()
			# now move global counter file into place
			os.rename(newcpath,cpath)
		return counter
	
	def cpv_inject(self,mycpv):
		"injects a real package into our on-disk database; assumes mycpv is valid and doesn't already exist"
		os.makedirs(self.root+VDB_PATH+"/"+mycpv)	
		counter=db[self.root]["vartree"].dbapi.counter_tick(self.root,mycpv=mycpv)
		# write local package counter so that emerge clean does the right thing
		lcfile=open(self.root+VDB_PATH+"/"+mycpv+"/COUNTER","w")
		lcfile.write(str(counter))
		lcfile.close()

	def isInjected(self,mycpv):
		if self.cpv_exists(mycpv):
			if os.path.exists(self.root+VDB_PATH+"/"+mycpv+"/INJECTED"):
				return True
			if not os.path.exists(self.root+VDB_PATH+"/"+mycpv+"/CONTENTS"):
				return True
		return False

	def move_ent(self,mylist):
		origcp=mylist[1]
		newcp=mylist[2]
		origmatches=self.match(origcp,use_cache=0)
		if not origmatches:
			return
		for mycpv in origmatches:
			mycpsplit=portage_dep.catpkgsplit(mycpv)
			mynewcpv=newcp+"-"+mycpsplit[2]
			mynewcat=newcp.split("/")[0]
			if mycpsplit[3]!="r0":
				mynewcpv += "-"+mycpsplit[3]
			mycpsplit_new = portage_dep.catpkgsplit(mynewcpv)
			origpath=self.root+VDB_PATH+"/"+mycpv
			if not os.path.exists(origpath):
				continue
			writemsg("@")
			if not os.path.exists(self.root+VDB_PATH+"/"+mynewcat):
				#create the directory
				os.makedirs(self.root+VDB_PATH+"/"+mynewcat)	
			newpath=self.root+VDB_PATH+"/"+mynewcpv
			if os.path.exists(newpath):
				#dest already exists; keep this puppy where it is.
				continue
			spawn(MOVE_BINARY+" "+origpath+" "+newpath,settings, free=1)

			# We need to rename the ebuild now.
			old_eb_path = newpath+"/"+mycpsplit[1]    +"-"+mycpsplit[2]
			new_eb_path = newpath+"/"+mycpsplit_new[1]+"-"+mycpsplit[2]
			if mycpsplit[3] != "r0":
				old_eb_path += "-"+mycpsplit[3]
				new_eb_path += "-"+mycpsplit[3]
			if os.path.exists(old_eb_path+".ebuild"):
				os.rename(old_eb_path+".ebuild", new_eb_path+".ebuild")
			
			catfile=open(newpath+"/CATEGORY", "w")
			catfile.write(mynewcat+"\n")
			catfile.close()

		dbdir = self.root+VDB_PATH
		for catdir in listdir(dbdir):
			catdir = dbdir+"/"+catdir
			if os.path.isdir(catdir):
				for pkgdir in listdir(catdir):
					pkgdir = catdir+"/"+pkgdir
					if os.path.isdir(pkgdir):
						fixdbentries(origcp, newcp, pkgdir)
	
	def move_slot_ent(self,mylist):
		pkg=mylist[1]
		origslot=mylist[2]
		newslot=mylist[3]

		origmatches=self.match(pkg,use_cache=0)
		if not origmatches:
			return
		for mycpv in origmatches:
			origpath=self.root+VDB_PATH+"/"+mycpv
			if not os.path.exists(origpath):
				continue

			slot=grabfile(origpath+"/SLOT");
			if (not slot):
				continue

			if (slot[0]!=origslot):
				continue

			writemsg("s")
			slotfile=open(origpath+"/SLOT", "w")
			slotfile.write(newslot+"\n")
			slotfile.close()

	def cp_list(self,mycp,use_cache=1):
		mysplit=mycp.split("/")
		if mysplit[0] == '*':
			mysplit[0] = mysplit[0][1:]
		try:
			mystat=os.stat(self.root+VDB_PATH+"/"+mysplit[0])[stat.ST_MTIME]
		except OSError:
			mystat=0
		if use_cache and self.cpcache.has_key(mycp):
			cpc=self.cpcache[mycp]
			if cpc[0]==mystat:
				return cpc[1]
		list=listdir(self.root+VDB_PATH+"/"+mysplit[0],EmptyOnError=1)

		if (list==None):
			return []
		returnme=[]
		for x in list:
			if x[0] == '-':
				#writemsg(red("INCOMPLETE MERGE:")+str(x[len("-MERGING-"):])+"\n")
				continue
			ps=portage_dep.pkgsplit(x)
			if not ps:
				self.invalidentry(self.root+VDB_PATH+"/"+mysplit[0]+"/"+x)
				continue
			if len(mysplit) > 1:
				if ps[0]==mysplit[1]:
					returnme.append(mysplit[0]+"/"+x)
		if use_cache:
			self.cpcache[mycp]=[mystat,returnme]
		elif self.cpcache.has_key(mycp):
			del self.cpcache[mycp]
		return returnme

	def cpv_all(self,use_cache=1):
		returnme=[]
		basepath = self.root+VDB_PATH+"/"
		
		mycats = self.categories
		if mycats == None:
			# XXX: CIRCULAR DEP! This helps backwards compat. --NJ (10 Sept 2004)
			mycats = settings.categories
		
		for x in mycats:
			for y in listdir(basepath+x,EmptyOnError=1):
				subpath = x+"/"+y
				# -MERGING- should never be a cpv, nor should files.
				if os.path.isdir(basepath+subpath) and (portage_dep.pkgsplit(y) is not None):
					returnme += [subpath]
		return returnme

	def cp_all(self,use_cache=1):
		returnme=[]
		mylist = self.cpv_all(use_cache=use_cache)
		for y in mylist:
			if y[0] == '*':
				y = y[1:]
			mysplit=portage_dep.catpkgsplit(y)
			if not mysplit:
				self.invalidentry(self.root+VDB_PATH+"/"+y)
				continue
			mykey=mysplit[0]+"/"+mysplit[1]
			if not mykey in returnme:
				returnme.append(mykey)
		return returnme

	def checkblockers(self,origdep):
		pass

	def match(self,origdep,use_cache=1):
		"caching match function"
		mydep=dep_expand(origdep,mydb=self,use_cache=use_cache)
		mykey=dep_getkey(mydep)
		mycat=mykey.split("/")[0]
		if not use_cache:
			if self.matchcache.has_key(mycat):
				del self.mtdircache[mycat]
				del self.matchcache[mycat]
			return match_from_list(mydep,self.cp_list(mykey,use_cache=use_cache))
		try:
			curmtime=os.stat(self.root+VDB_PATH+"/"+mycat)[stat.ST_MTIME]
		except SystemExit, e:
			raise
		except:
			curmtime=0

		if not self.matchcache.has_key(mycat) or not self.mtdircache[mycat]==curmtime:
			# clear cache entry
			self.mtdircache[mycat]=curmtime
			self.matchcache[mycat]={}
		if not self.matchcache[mycat].has_key(mydep):
			mymatch=match_from_list(mydep,self.cp_list(mykey,use_cache=use_cache))
			self.matchcache[mycat][mydep]=mymatch
		return self.matchcache[mycat][mydep][:]
	
	def aux_get(self, mycpv, wants):
		global auxdbkeys
		results = []
		if not self.cpv_exists(mycpv):
			return []
		for x in wants:
			myfn = self.root+VDB_PATH+"/"+str(mycpv)+"/"+str(x)
			if os.access(myfn,os.R_OK):
				myf = open(myfn, "r")
				myd = myf.read()
				myf.close()
				myd = re.sub("[\n\r\t]+"," ",myd)
				myd = re.sub(" +"," ",myd)
				myd = string.strip(myd)
			else:
				myd = ""
			results.append(myd)
		return results
		

class vartree(packagetree):
	"this tree will scan a var/db/pkg database located at root (passed to init)"
	def __init__(self,root="/",virtual=None,clone=None,categories=None):
		if clone:
			self.root       = clone.root[:]
			self.dbapi      = copy.deepcopy(clone.dbapi)
			self.populated  = 1
		else:
			self.root       = root[:]
			self.dbapi      = vardbapi(self.root,categories=categories)
			self.populated  = 1

	def zap(self,mycpv):
		return

	def inject(self,mycpv):
		return
		
	def get_provide(self,mycpv):
		myprovides=[]
		try:
			mylines = grabfile(self.root+VDB_PATH+"/"+mycpv+"/PROVIDE")
			if mylines:
				myuse = grabfile(self.root+VDB_PATH+"/"+mycpv+"/USE")
				myuse = string.split(string.join(myuse))
				mylines = string.join(mylines)
				mylines = flatten(portage_dep.use_reduce(portage_dep.paren_reduce(mylines), uselist=myuse))
				for myprovide in mylines:
					mys = portage_dep.catpkgsplit(myprovide)
					if not mys:
						mys = string.split(myprovide, "/")
					myprovides += [mys[0] + "/" + mys[1]]
			return myprovides
		except SystemExit, e:
			raise
		except Exception, e:
			print
			print "Check " + self.root+VDB_PATH+"/"+mycpv+"/PROVIDE and USE."
			print "Possibly Invalid: " + str(mylines)
			print "Exception: "+str(e)
			print
			return []

	def get_all_provides(self):
		myprovides = {}
		for node in self.getallcpv():
			for mykey in self.get_provide(node):
				if myprovides.has_key(mykey):
					myprovides[mykey] += [node]
				else:
					myprovides[mykey]  = [node]
		return myprovides
	
	def dep_bestmatch(self,mydep,use_cache=1):
		"compatibility method -- all matches, not just visible ones"
		#mymatch=best(match(dep_expand(mydep,self.dbapi),self.dbapi))
		mymatch=best(self.dbapi.match(dep_expand(mydep,mydb=self.dbapi),use_cache=use_cache))
		if mymatch==None:
			return ""
		else:
			return mymatch
			
	def dep_match(self,mydep,use_cache=1):
		"compatibility method -- we want to see all matches, not just visible ones"
		#mymatch=match(mydep,self.dbapi)
		mymatch=self.dbapi.match(mydep,use_cache=use_cache)
		if mymatch==None:
			return []
		else:
			return mymatch

	def exists_specific(self,cpv):
		return self.dbapi.cpv_exists(cpv)

	def getallcpv(self):
		"""temporary function, probably to be renamed --- Gets a list of all
		category/package-versions installed on the system."""
		return self.dbapi.cpv_all()
	
	def getallnodes(self):
		"""new behavior: these are all *unmasked* nodes.  There may or may not be available
		masked package for nodes in this nodes list."""
		return self.dbapi.cp_all()

	def exists_specific_cat(self,cpv,use_cache=1):
		cpv=key_expand(cpv,mydb=self.dbapi,use_cache=use_cache)
		a=portage_dep.catpkgsplit(cpv)
		if not a:
			return 0
		mylist=listdir(self.root+VDB_PATH+"/"+a[0],EmptyOnError=1)
		for x in mylist:
			b=portage_dep.pkgsplit(x)
			if not b:
				self.dbapi.invalidentry(self.root+VDB_PATH+"/"+a[0]+"/"+x)
				continue
			if a[1]==b[0]:
				return 1
		return 0
			
	def getebuildpath(self,fullpackage):
		cat,package=fullpackage.split("/")
		return self.root+VDB_PATH+"/"+fullpackage+"/"+package+".ebuild"

	def getnode(self,mykey,use_cache=1):
		mykey=key_expand(mykey,mydb=self.dbapi,use_cache=use_cache)
		if not mykey:
			return []
		mysplit=mykey.split("/")
		mydirlist=listdir(self.root+VDB_PATH+"/"+mysplit[0],EmptyOnError=1)
		returnme=[]
		for x in mydirlist:
			mypsplit=portage_dep.pkgsplit(x)
			if not mypsplit:
				self.dbapi.invalidentry(self.root+VDB_PATH+"/"+mysplit[0]+"/"+x)
				continue
			if mypsplit[0]==mysplit[1]:
				appendme=[mysplit[0]+"/"+x,[mysplit[0],mypsplit[0],mypsplit[1],mypsplit[2]]]
				returnme.append(appendme)
		return returnme

	
	def getslot(self,mycatpkg):
		"Get a slot for a catpkg; assume it exists."
		myslot = ""
		try:
			myslot=string.join(grabfile(self.root+VDB_PATH+"/"+mycatpkg+"/SLOT"))
		except SystemExit, e:
			raise
		except Exception, e:
			pass
		return myslot
	
	def hasnode(self,mykey,use_cache):
		"""Does the particular node (cat/pkg key) exist?"""
		mykey=key_expand(mykey,mydb=self.dbapi,use_cache=use_cache)
		mysplit=mykey.split("/")
		mydirlist=listdir(self.root+VDB_PATH+"/"+mysplit[0],EmptyOnError=1)
		for x in mydirlist:
			mypsplit=portage_dep.pkgsplit(x)
			if not mypsplit:
				self.dbapi.invalidentry(self.root+VDB_PATH+"/"+mysplit[0]+"/"+x)
				continue
			if mypsplit[0]==mysplit[1]:
				return 1
		return 0
	
	def populate(self):
		self.populated=1

# ----------------------------------------------------------------------------
class eclass_cache:
	"""Maintains the cache information about eclasses used in ebuild."""
	def __init__(self,porttree_root,settings):
		self.porttree_root = porttree_root
		self.settings = settings
		self.depcachedir = self.settings.depcachedir[:]

		self.dbmodule = self.settings.load_best_module("eclass_cache.dbmodule")

		self.packages = {} # {"PV": {"eclass1": ["location", "_mtime_"]}}
		self.eclasses = {} # {"Name": ["location","_mtime_"]}
		
		self.porttrees=self.settings["PORTDIR_OVERLAY"].split()+[self.porttree_root]
		self.update_eclasses()

	def close_caches(self):
		for x in self.packages.keys():
			for y in self.packages[x].keys():
				try:
					self.packages[x][y].sync()
					self.packages[x][y].close()
				except SystemExit, e:
					raise
				except Exception,e:
					writemsg("Exception when closing DB: %s: %s\n" % (Exception,e))
				del self.packages[x][y]
			del self.packages[x]

	def flush_cache(self):
		self.packages = {}
		self.eclasses = {}
		self.update_eclasses()

	def update_eclasses(self):
		self.eclasses = {}
		for x in suffix_array(self.porttrees, "/eclass"):
			if x and os.path.exists(x):
				dirlist = listdir(x)
				for y in dirlist:
					if y[-len(".eclass"):]==".eclass":
						try:
							ys=y[:-len(".eclass")]
							ymtime=os.stat(x+"/"+y)[stat.ST_MTIME]
						except SystemExit, e:
							raise
						except:
							continue
						self.eclasses[ys] = [x, ymtime]
	
	def setup_package(self, location, cat, pkg):
		if not self.packages.has_key(location):
			self.packages[location] = {}

		if not self.packages[location].has_key(cat):
			try:
				self.packages[location][cat] = self.dbmodule(self.depcachedir+"/"+location, cat+"-eclass", [], uid, portage_gid)
			except SystemExit, e:
				raise
			except Exception, e:
				writemsg("\n!!! Failed to open the dbmodule for eclass caching.\n")
				writemsg("!!! Generally these are permission problems. Caught exception follows:\n")
				writemsg("!!! "+str(e)+"\n")
				writemsg("!!! Dirname:  "+str(self.depcachedir+"/"+location)+"\n")
				writemsg("!!! Basename: "+str(cat+"-eclass")+"\n\n")
				sys.exit(123)
	
	def sync(self, location, cat, pkg):
		if self.packages[location].has_key(cat):
			self.packages[location][cat].sync()
	
	def update_package(self, location, cat, pkg, eclass_list):
		self.setup_package(location, cat, pkg)
		if not eclass_list:
			return 1

		data = {}
		for x in eclass_list:
			if x not in self.eclasses:
				writemsg("Eclass '%s' does not exist for '%s'\n" % (x, cat+"/"+pkg))
				return 0
			data[x] = [self.eclasses[x][0],self.eclasses[x][1]]
		
		self.packages[location][cat][pkg] = data
		self.sync(location,cat,pkg)
		return 1

	def is_current(self, location, cat, pkg, eclass_list):
		self.setup_package(location, cat, pkg)

		if not eclass_list:
			return 1

		if not (self.packages[location][cat].has_key(pkg) and self.packages[location][cat][pkg] and eclass_list):
			return 0

		eclass_list.sort()
		eclass_list = portage_util.unique_array(eclass_list)
		
		ec_data = self.packages[location][cat][pkg].keys()
		ec_data.sort()
		if eclass_list != ec_data:
			return 0

		for x in eclass_list:
			if x not in self.eclasses:
				return 0
			data = self.packages[location][cat][pkg][x]
			if data[1] != self.eclasses[x][1]:
				return 0
			if data[0] != self.eclasses[x][0]:
				return 0

		return 1			
				
# ----------------------------------------------------------------------------

auxdbkeys=[
  'DEPEND',    'RDEPEND',   'SLOT',      'SRC_URI',
	'RESTRICT',  'HOMEPAGE',  'LICENSE',   'DESCRIPTION',
	'KEYWORDS',  'INHERITED', 'IUSE',      'CDEPEND',
	'PDEPEND',   'PROVIDE',
	'UNUSED_01', 'UNUSED_02', 'UNUSED_03', 'UNUSED_04',
	'UNUSED_05', 'UNUSED_06', 'UNUSED_07', 'UNUSED_08',
	]
auxdbkeylen=len(auxdbkeys)

def close_portdbapi_caches():
	for i in portdbapi.portdbapi_instances:
		i.close_caches()
class portdbapi(dbapi):
	"""this tree will scan a portage directory located at root (passed to init)"""
	portdbapi_instances = []

	def __init__(self,porttree_root,mysettings=None):
		portdbapi.portdbapi_instances.append(self)
		self.lock_held = 0;

		if mysettings:
			self.mysettings = mysettings
		else:
			self.mysettings = config(clone=settings)

		self.manifestVerifyLevel  = None
		self.manifestVerifier     = None
		self.manifestCache        = {}    # {location: [stat, md5]}
		self.manifestMissingCache = []

		if "gpg" in self.mysettings.features:
			self.manifestVerifyLevel   = portage_gpg.EXISTS
			if "strict" in self.mysettings.features:
				self.manifestVerifyLevel = portage_gpg.MARGINAL
				self.manifestVerifier = portage_gpg.FileChecker(self.mysettings["PORTAGE_GPG_DIR"], "gentoo.gpg", minimumTrust=self.manifestVerifyLevel)
			elif "severe" in self.mysettings.features:
				self.manifestVerifyLevel = portage_gpg.TRUSTED
				self.manifestVerifier = portage_gpg.FileChecker(self.mysettings["PORTAGE_GPG_DIR"], "gentoo.gpg", requireSignedRing=True, minimumTrust=self.manifestVerifyLevel)
			else:
				self.manifestVerifier = portage_gpg.FileChecker(self.mysettings["PORTAGE_GPG_DIR"], "gentoo.gpg", minimumTrust=self.manifestVerifyLevel)

		#self.root=settings["PORTDIR"]
		self.porttree_root = porttree_root
		
		self.depcachedir = self.mysettings.depcachedir[:]

		self.tmpfs = self.mysettings["PORTAGE_TMPFS"]
		if not os.path.exists(self.tmpfs):
			self.tmpfs = None
		
		self.eclassdb = eclass_cache(self.porttree_root, self.mysettings)

		self.metadb       = {}
		self.metadbmodule = self.mysettings.load_best_module("portdbapi.metadbmodule")
		
		self.auxdb        = {}
		self.auxdbmodule  = self.mysettings.load_best_module("portdbapi.auxdbmodule")

		#if the portdbapi is "frozen", then we assume that we can cache everything (that no updates to it are happening)
		self.xcache={}
		self.frozen=0

		self.porttrees=[self.porttree_root]+self.mysettings["PORTDIR_OVERLAY"].split()

	def getmaskingreason(self,mycpv):
		mysplit = portage_dep.catpkgsplit(mycpv)
		if not mysplit:
			raise ValueError("invalid CPV: %s" % mycpv)
		if not self.cpv_exists(mycpv):
			raise KeyError("CPV %s does not exist" % mycpv)
		mycp=mysplit[0]+"/"+mysplit[1]

		if settings.pmaskdict.has_key(mycp):
			for x in settings.pmaskdict[mycp]:
				if mycpv in self.xmatch("match-all", x):
					pmaskfile = open(settings["PORTDIR"]+"/profiles/package.mask")
					comment = ""
					l = "\n"
					while len(l) > 0:
						l = pmaskfile.readline()
						if len(l) == 0:
							pmaskfile.close()
							return None
						if l[0] == "#":
							comment += l
						elif l == "\n":
							comment = ""
						elif l.strip() == x:
							pmaskfile.close()
							return comment
					pmaskfile.close()
		return None

	def getmaskingstatus(self,mycpv):
		mysplit = portage_dep.catpkgsplit(mycpv)
		if not mysplit:
			raise ValueError("invalid CPV: %s" % mycpv)
		if not self.cpv_exists(mycpv):
			raise KeyError("CPV %s does not exist" % mycpv)
		mycp=mysplit[0]+"/"+mysplit[1]
	
		rValue = []

		# profile checking
		revmaskdict=settings.prevmaskdict
		if revmaskdict.has_key(mycp):
			for x in revmaskdict[mycp]:
				if x[0]=="*":
					myatom = x[1:]
				else:
					myatom = x
				if not match_to_list(mycpv, [myatom]):
					rValue.append("profile")
					break

		# package.mask checking
		maskdict=settings.pmaskdict
		unmaskdict=settings.punmaskdict
		if maskdict.has_key(mycp):
			for x in maskdict[mycp]:
				if mycpv in self.xmatch("match-all", x):
					unmask=0
					if unmaskdict.has_key(mycp):
						for z in unmaskdict[mycp]:
							if mycpv in self.xmatch("match-all",z):
								unmask=1
								break
					if unmask==0:
						rValue.append("package.mask")

		# keywords checking
		mygroups = self.aux_get(mycpv, ["KEYWORDS"])[0].split()
		pgroups=groups[:]
		myarch = settings["ARCH"]
		pkgdict = settings.pkeywordsdict

		cp = dep_getkey(mycpv)
		if pkgdict.has_key(cp):
			matches = match_to_list(mycpv, pkgdict[cp].keys())
			for match in matches:
				pgroups.extend(pkgdict[cp][match])

		kmask = "missing"

		for keyword in pgroups:
			if keyword in mygroups:
				kmask=None

		if kmask:
			for gp in mygroups:
				if gp=="*":
					kmask=None
					break
				elif gp=="-*":
					kmask="-*"
					break
				elif gp=="-"+myarch:
					kmask="-"+myarch
					break
				elif gp=="~"+myarch:
					kmask="~"+myarch
					break

		if kmask:
			rValue.append(kmask+" keyword")
		return rValue


	def regen_keys(self,cleanse_stale=True,verbose=True,src_cache=None,debug=False):
		"""walk all entries of this instance to update the cache.
		If the cache is pregenned, pass it in via src_cache, and the cache will be updated
		from that instance.
		cleanse_stale controls whether or not the cache's old/stale entries are removed.
		This is useful both for emerge metadata, and emerge regen (moreso for regen)"""
		l=self.cp_all()
		l.sort()
		if not len(l):
			return
		oldcat = catsplit(l[0])[0]
		savelist = []

		for p in l:
			cat=catsplit(p)[0]
			if cleanse_stale and oldcat != cat:
				for x in range(0,len(savelist)):
					savelist[x] = catsplit(savelist[x])[1]
				for tree in self.porttrees:
					if not self.auxdb.get(tree,{}).has_key(oldcat):
						continue
					elif len(savelist) == 0:
						self.auxdb[tree][oldcat].clear()
					else:
						for cpv in self.auxdb[tree][oldcat].keys():
							if cpv not in savelist:
								self.auxdb[tree][oldcat].del_key(cpv)
				savelist = []
				oldcat = cat

			mymatches=self.xmatch("match-all",p)
			if cleanse_stale:
				savelist.extend(mymatches)
			if verbose:
				print "processing %s" % p
			for cpv in mymatches:
				try:
					foo=self.aux_get(cpv,[],debug=debug,metacachedir=src_cache)
				except SystemExit, e:
					raise
				except Exception, e:
					print "\n  error processing %s, continuing... (%s)" % (cpv, str(e))

		if cleanse_stale:
			for x in range(0,len(savelist)):
				savelist[x] = catsplit(savelist[x])[1]
			for tree in self.porttrees:
				if not self.auxdb.get(tree,{}).has_key(oldcat):
					continue
				elif len(savelist) == 0:
					self.auxdb[tree][oldcat].clear()
				else:
					for cpv in self.auxdb[tree][oldcat].keys():
						if cpv not in savelist:
							self.auxdb[tree][oldcat].del_key(cpv)

	def close_caches(self):
		for x in self.auxdb.keys():
			for y in self.auxdb[x].keys():
				self.auxdb[x][y].sync()
				self.auxdb[x][y].close()
				del self.auxdb[x][y]
			del self.auxdb[x]
		self.eclassdb.close_caches()

	def flush_cache(self):
		self.metadb = {}
		self.auxdb  = {}
		self.eclassdb.flush_cache()
		
	def finddigest(self,mycpv):
		try:
			mydig   = self.findname2(mycpv)[0]
			mydigs  = string.split(mydig, "/")[:-1]
			mydig   = string.join(mydigs, "/")

			mysplit = mycpv.split("/")
		except SystemExit, e:
			raise
		except:
			return ""
		return mydig+"/files/digest-"+mysplit[-1]

	def findname(self,mycpv):
		return self.findname2(mycpv)[0]

	def findname2(self,mycpv):
		"returns file location for this particular package and in_overlay flag"
		if not mycpv:
			return "",0
		mysplit=mycpv.split("/")
		if mysplit[0]=="virtual":
			print "!!! Cannot resolve a virtual package name to an ebuild."
			print "!!! This is a bug, please report it. ("+mycpv+")"
			sys.exit(1)
		
		psplit=portage_dep.pkgsplit(mysplit[1])
		ret=None
		if psplit:
			for x in self.porttrees:
				# XXX Why are there errors here? XXX
				try:
					file=x+"/"+mysplit[0]+"/"+psplit[0]+"/"+mysplit[1]+".ebuild"
				except SystemExit, e:
					raise
				except Exception, e:
					print
					print "!!! Problem with determining the name/location of an ebuild."
					print "!!! Please report this on IRC and bugs if you are not causing it."
					print "!!! mycpv:  ",mycpv
					print "!!! mysplit:",mysplit
					print "!!! psplit: ",psplit
					print "!!! error:  ",e
					print
					sys.exit(17)
					
				if os.access(file, os.R_OK):
					# when found
					ret=[file, x]
		if ret:
			return ret[0], ret[1]

		# when not found
		return None, 0

	def aux_get(self,mycpv,mylist,strict=0,metacachedir=None,debug=0):
		"""stub code for returning auxilliary db information, such as SLOT, DEPEND, etc."""
		'input: "sys-apps/foo-1.0",["SLOT","DEPEND","HOMEPAGE"]'
		'return: ["0",">=sys-libs/bar-1.0","http://www.foo.com"] or raise KeyError if error'
		global auxdbkeys,auxdbkeylen

		cat,pkg = string.split(mycpv, "/", 1)

		if metacachedir:
			if cat not in self.metadb:
				self.metadb[cat] = self.metadbmodule(metacachedir,cat,auxdbkeys,uid,portage_gid)

		myebuild, mylocation=self.findname2(mycpv)

		if not myebuild:
			writemsg("!!! aux_get(): ebuild path for '%(cpv)s' not specified:\n" % {"cpv":mycpv})
			writemsg("!!!            %s\n" % myebuild)
			raise KeyError, "'%(cpv)s' at %(path)s" % {"cpv":mycpv,"path":myebuild}

		myManifestPath = string.join(myebuild.split("/")[:-1],"/")+"/Manifest"
		if "gpg" in self.mysettings.features:
			try:
				mys = portage_gpg.fileStats(myManifestPath)
				if (myManifestPath in self.manifestCache) and \
				   (self.manifestCache[myManifestPath] == mys):
					pass
				elif self.manifestVerifier:
					if not self.manifestVerifier.verify(myManifestPath):
						# Verification failed the desired level.
						raise portage_exception.UntrustedSignature, "Untrusted Manifest: %(manifest)s" % {"manifest":myManifestPath}

				if ("severe" in self.mysettings.features) and \
				   (mys != portage_gpg.fileStats(myManifestPath)):
					raise portage_exception.SecurityViolation, "Manifest changed: %(manifest)s" % {"manifest":myManifestPath}
				
			except portage_exception.InvalidSignature, e:
				if ("strict" in self.mysettings.features) or \
				   ("severe" in self.mysettings.features):
					raise
				writemsg("!!! INVALID MANIFEST SIGNATURE DETECTED: %(manifest)s\n" % {"manifest":myManifestPath})
			except portage_exception.MissingSignature, e:
				if ("severe" in self.mysettings.features):
					raise
				if ("strict" in self.mysettings.features):
					if myManifestPath not in self.manifestMissingCache:
						writemsg("!!! WARNING: Missing signature in: %(manifest)s\n" % {"manifest":myManifestPath})
						self.manifestMissingCache.insert(0,myManifestPath)
			except (OSError,portage_exception.FileNotFound), e:
				if ("strict" in self.mysettings.features) or \
				   ("severe" in self.mysettings.features):
					raise portage_exception.SecurityViolation, "Error in verification of signatures: %(errormsg)s" % {"errormsg":str(e)}
				writemsg("!!! Manifest is missing or inaccessable: %(manifest)s\n" % {"manifest":myManifestPath})

		if mylocation not in self.auxdb:
			self.auxdb[mylocation] = {}

		if not self.auxdb[mylocation].has_key(cat):
			self.auxdb[mylocation][cat] = self.auxdbmodule(self.depcachedir+"/"+mylocation,cat,auxdbkeys,uid,portage_gid)

		if os.access(myebuild, os.R_OK):
			emtime=os.stat(myebuild)[stat.ST_MTIME]
		else:
			writemsg("!!! aux_get(): ebuild for '%(cpv)s' does not exist at:\n" % {"cpv":mycpv})
			writemsg("!!!            %s\n" % myebuild)
			raise KeyError
		mydata={}

		# when mylocation is not overlay directorys and metacachedir is set,
		# we use cache files, which is usually on /usr/portage/metadata/cache/.
		if mylocation==self.mysettings["PORTDIR"] and metacachedir and self.metadb[cat].has_key(pkg):

			doregen = False

			if self.metadb[cat].get_timestamp(pkg) != self.auxdb[mylocation][cat].get_timestamp(pkg):
				doregen = True
				mydata = self.metadb[cat][pkg]
			else:
				mydata = self.metadb[cat][pkg]
				if not self.eclassdb.is_current(mylocation,cat,pkg,mydata.get("INHERITED","").split()):
					doregen = True

			if doregen:
				self.auxdb[mylocation][cat][pkg] = mydata
				self.auxdb[mylocation][cat].sync()
				self.eclassdb.update_package(mylocation,cat,pkg,mydata["INHERITED"].split())
		else:
			doregen=False
			try:
				doregen = self.auxdb[mylocation][cat].get_timestamp(pkg) != emtime
				if not doregen:
					mydata = self.auxdb[mylocation][cat][pkg]
					doregen = (not self.eclassdb.is_current(mylocation,cat, \
						pkg,mydata.get("INHERITED","").split()))
			except SystemExit,e:
				raise
			except Exception, e:
				doregen = True
				if not isinstance(e, KeyError):
					# CorruptionError is the likely candidate
					writemsg("auxdb exception: (%s): %s\n" % (mylocation+"::"+cat+"/"+pkg,str(e)))
					if self.auxdb[mylocation][cat].has_key(pkg):
						self.auxdb[mylocation][cat].del_key(pkg)
						self.auxdb[mylocation][cat].sync()

			writemsg("auxdb is valid: "+str(not doregen)+" "+str(pkg)+"\n", 2)
			if doregen:
				writemsg("doregen: %s %s\n" % (doregen,mycpv), 2)
				writemsg("Generating cache entry(0) for: "+str(myebuild)+"\n",1)

				# XXX: Part of the gvisible hack/fix to prevent deadlock
				# XXX: through doebuild. Need to isolate this somehow...
				self.mysettings.reset()

				if self.lock_held:
					raise "Lock is already held by me?"

				self.lock_held = 1

				mydata=ebuild.ebuild_handler().get_keys(myebuild,self.mysettings)
				self.lock_held = 0

				for x in auxdbkeys:
					if not mydata.has_key(x):
						mydata[x] = ""
				mydata["_mtime_"] = emtime

				self.auxdb[mylocation][cat][pkg] = mydata
				self.auxdb[mylocation][cat].sync()
				if not self.eclassdb.update_package(mylocation, cat, pkg, mydata.get("INHERITED","").split()):
					print "failed updating eclass cache"
					sys.exit(1)

		#finally, we look at our internal cache entry and return the requested data.
		returnme = []
		for x in mylist:
			if mydata.has_key(x):
				returnme.append(mydata[x])
			else:
				returnme.append("")

		return returnme

	def getfetchlist(self,mypkg,useflags=None,mysettings=None,all=0):
		if mysettings == None:
			mysettings = self.mysettings
		try:
			myuris = self.aux_get(mypkg,["SRC_URI"])[0]
		except (IOError,KeyError):
			print red("getfetchlist():")+" aux_get() error; aborting."
			sys.exit(1)

		useflags = string.split(mysettings["USE"])
		
		myurilist = portage_dep.paren_reduce(myuris)
		myurilist = portage_dep.use_reduce(myurilist,uselist=useflags,matchall=all)
		newuris = flatten(myurilist)

		myfiles = []
		for x in newuris:
			mya = os.path.basename(x)
			if not mya in myfiles:
				myfiles.append(mya)
		return [newuris, myfiles]

	def getfetchsizes(self,mypkg,useflags=None,debug=0):
		# returns a filename:size dictionnary of remaining downloads
		mydigest=self.finddigest(mypkg)
		mymd5s=digestParseFile(mydigest)
		if not mymd5s:
			if debug: print "[empty/missing/bad digest]: "+mypkg
			return None
		filesdict={}
		if useflags == None:
			myuris, myfiles = self.getfetchlist(mypkg,all=1)
		else:
			myuris, myfiles = self.getfetchlist(mypkg,useflags=useflags)
		#XXX: maybe this should be improved: take partial downloads
		# into account? check md5sums?
		for myfile in myfiles:
			if debug and myfile not in mymd5s.keys():
				print "[bad digest]: missing",myfile,"for",mypkg
			elif myfile in mymd5s.keys():
				distfile=settings["DISTDIR"]+"/"+myfile
				if not os.access(distfile, os.R_OK):
					filesdict[myfile]=int(mymd5s[myfile]["size"])
		return filesdict

	def fetch_check(self, mypkg, useflags=None, mysettings=None, all=False):
		if not useflags:
			if mysettings:
				useflags = mysettings["USE"].split()
		myuri, myfiles = self.getfetchlist(mypkg, useflags=useflags, mysettings=mysettings, all=all)
		mydigest       = self.finddigest(mypkg)
		mysums         = digestParseFile(mydigest)
		
		failures = {}
		for x in myfiles:
			if not mysums or x not in mysums:
				ok     = False
				reason = "digest missing"
			else:
				ok,reason = portage_checksum.verify_all(self.mysettings["DISTDIR"]+"/"+x, mysums[x])
			if not ok:
				failures[x] = reason
		if failures:
			return False
		return True

	def getsize(self,mypkg,useflags=None,debug=0):
		# returns the total size of remaining downloads
		#
		# we use getfetchsizes() now, so this function would be obsoleted
		#
		filesdict=self.getfetchsizes(mypkg,useflags=useflags,debug=debug)
		if filesdict==None:
			return "[empty/missing/bad digest]"
		mysize=0
		for myfile in filesdict.keys():
			mysum+=filesdict[myfile]
		return mysum

	def cpv_exists(self,mykey):
		"Tells us whether an actual ebuild exists on disk (no masking)"
		cps2=mykey.split("/")
		cps=portage_dep.catpkgsplit(mykey,silent=0)
		if not cps:
			#invalid cat/pkg-v
			return 0
		if self.findname2(cps[0]+"/"+cps2[1]):
			return 1
		else:
			return 0

	def cp_all(self):
		"returns a list of all keys in our tree"
		biglist=[]
		for x in self.mysettings.categories:
			for oroot in self.porttrees:
				for y in listdir(oroot+"/"+x,EmptyOnError=1,ignorecvs=1):
					mykey=x+"/"+y
					if not mykey in biglist:
						biglist.append(mykey)
		return biglist
	
	def p_list(self,mycp):
		returnme=[]
		for oroot in self.porttrees:
			for x in listdir(oroot+"/"+mycp,EmptyOnError=1,ignorecvs=1):
				if x[-7:]==".ebuild":
					mye=x[:-7]
					if not mye in returnme:
						returnme.append(mye)
		return returnme

	def cp_list(self,mycp,use_cache=1):
		mysplit=mycp.split("/")
		returnme=[]
		for oroot in self.porttrees:
			for x in listdir(oroot+"/"+mycp,EmptyOnError=1,ignorecvs=1):
				if x[-7:]==".ebuild":
					cp=mysplit[0]+"/"+x[:-7]
					if not cp in returnme:
						returnme.append(cp)
		return returnme

	def freeze(self):
		for x in ["list-visible","bestmatch-visible","match-visible","match-all"]:
			self.xcache[x]={}
		self.frozen=1

	def melt(self):
		self.xcache={}
		self.frozen=0

	def xmatch(self,level,origdep,mydep=None,mykey=None,mylist=None):
		"caching match function; very trick stuff"
		#if no updates are being made to the tree, we can consult our xcache...
		if self.frozen:
			try:
				return self.xcache[level][origdep]
			except KeyError:
				pass

		if not mydep:
			#this stuff only runs on first call of xmatch()
			#create mydep, mykey from origdep
			mydep=dep_expand(origdep,mydb=self)
			mykey=dep_getkey(mydep)
	
		if level=="list-visible":
			#a list of all visible packages, not called directly (just by xmatch())
			#myval=self.visible(self.cp_list(mykey))
			myval=self.gvisible(self.visible(self.cp_list(mykey)))
		elif level=="bestmatch-visible":
			#dep match -- best match of all visible packages
			myval=best(self.xmatch("match-visible",None,mydep=mydep,mykey=mykey))
			#get all visible matches (from xmatch()), then choose the best one
		elif level=="bestmatch-list":
			#dep match -- find best match but restrict search to sublist 
			myval=best(match_from_list(mydep,mylist))
			#no point is calling xmatch again since we're not caching list deps
		elif level=="match-list":
			#dep match -- find all matches but restrict search to sublist (used in 2nd half of visible())
			myval=match_from_list(mydep,mylist)
		elif level=="match-visible":
			#dep match -- find all visible matches
			myval=match_from_list(mydep,self.xmatch("list-visible",None,mydep=mydep,mykey=mykey))
			#get all visible packages, then get the matching ones
		elif level=="match-all":
			#match *all* visible *and* masked packages
			myval=match_from_list(mydep,self.cp_list(mykey))
		else:
			print "ERROR: xmatch doesn't handle",level,"query!"
			raise KeyError
		if self.frozen and (level not in ["match-list","bestmatch-list"]):
			self.xcache[level][mydep]=myval
		return myval

	def match(self,mydep,use_cache=1):
		return self.xmatch("match-visible",mydep)

	def visible(self,mylist):
		"""two functions in one.  Accepts a list of cpv values and uses the package.mask *and*
		packages file to remove invisible entries, returning remaining items.  This function assumes
		that all entries in mylist have the same category and package name."""
		if (mylist==None) or (len(mylist)==0):
			return []
		newlist=mylist[:]
		#first, we mask out packages in the package.mask file
		mykey=newlist[0]
		cpv=portage_dep.catpkgsplit(mykey)
		if not cpv:
			#invalid cat/pkg-v
			print "visible(): invalid cat/pkg-v:",mykey
			return []
		mycp=cpv[0]+"/"+cpv[1]
		maskdict=self.mysettings.pmaskdict
		unmaskdict=self.mysettings.punmaskdict
		if maskdict.has_key(mycp):
			for x in maskdict[mycp]:
				mymatches=self.xmatch("match-all",x)
				if mymatches==None:
					#error in package.mask file; print warning and continue:
					print "visible(): package.mask entry \""+x+"\" is invalid, ignoring..."
					continue
				for y in mymatches:
					unmask=0
					if unmaskdict.has_key(mycp):
						for z in unmaskdict[mycp]:
							mymatches_unmask=self.xmatch("match-all",z)
							if y in mymatches_unmask:
								unmask=1
								break
					if unmask==0:
						try:
							newlist.remove(y)
						except ValueError:
							pass

		revmaskdict=self.mysettings.prevmaskdict
		if revmaskdict.has_key(mycp):
			for x in revmaskdict[mycp]:
				#important: only match against the still-unmasked entries...
				#notice how we pass "newlist" to the xmatch() call below....
				#Without this, ~ deps in the packages files are broken.
				mymatches=self.xmatch("match-list",x,mylist=newlist)
				if mymatches==None:
					#error in packages file; print warning and continue:
					print "emerge: visible(): profile packages entry \""+x+"\" is invalid, ignoring..."
					continue
				pos=0
				while pos<len(newlist):
					if newlist[pos] not in mymatches:
						del newlist[pos]
					else:
						pos += 1
		return newlist

	def gvisible(self,mylist):
		"strip out group-masked (not in current group) entries"
		global groups
		if mylist==None:
			return []
		newlist=[]

		pkgdict = self.mysettings.pkeywordsdict
		for mycpv in mylist:
			#we need to update this next line when we have fully integrated the new db api
			auxerr=0
			try:
				myaux=db["/"]["porttree"].dbapi.aux_get(mycpv, ["KEYWORDS"])
			except (KeyError,IOError,TypeError):
				continue
			if not myaux[0]:
				# KEYWORDS=""
				#print "!!! No KEYWORDS for "+str(mycpv)+" -- Untested Status"
				continue
			mygroups=myaux[0].split()
			pgroups=groups[:]
			match=0
			cp = dep_getkey(mycpv)
			if pkgdict.has_key(cp):
				matches = match_to_list(mycpv, pkgdict[cp].keys())
				for match in matches:
					pgroups.extend(pkgdict[cp][match])
			for gp in mygroups:
				if gp=="*":
					writemsg("--- WARNING: Package '%s' uses '*' keyword.\n" % mycpv)
					match=1
					break
				elif "-"+gp in pgroups:
					match=0
					break
				elif gp in pgroups:
					match=1
					break
			else:
				if "*" in pgroups:
					for gp in mygroups:
						if not gp[0] in "~-":
							match=1
							break
				if "~*" in pgroups:
					for gp in mygroups:
						if gp[0] != "-":
							match=1
							break
			if match:
				newlist.append(mycpv)
		return newlist

class binarytree(packagetree):
	"this tree scans for a list of all packages available in PKGDIR"
	def __init__(self,root,pkgdir,virtual=None,clone=None):
		
		if clone:
			# XXX This isn't cloning. It's an instance of the same thing.
			self.root=clone.root
			self.pkgdir=clone.pkgdir
			self.dbapi=clone.dbapi
			self.populated=clone.populated
			self.tree=clone.tree
			self.remotepkgs=clone.remotepkgs
			self.invalids=clone.invalids
		else:
			self.root=root
			#self.pkgdir=settings["PKGDIR"]
			self.pkgdir=pkgdir
			self.dbapi=bindbapi(self)
			self.populated=0
			self.tree={}
			self.remotepkgs={}
			self.invalids=[]

	def move_ent(self,mylist):
		if not self.populated:
			self.populate()
		origcp=mylist[1]
		newcp=mylist[2]
		origmatches=self.dbapi.cp_list(origcp)
		if not origmatches:
			return
		for mycpv in origmatches:
			mycpsplit=portage_dep.catpkgsplit(mycpv)
			mynewcpv=newcp+"-"+mycpsplit[2]
			mynewcat=newcp.split("/")[0]
			mynewpkg=mynewcpv.split("/")[1]
			myoldpkg=mycpv.split("/")[1]
			if mycpsplit[3]!="r0":
				mynewcpv += "-"+mycpsplit[3]
			if (mynewpkg != myoldpkg) and os.path.exists(self.getname(mynewcpv)):
				writemsg("!!! Cannot update binary: Destination exists.\n")
				writemsg("!!! "+mycpv+" -> "+mynewcpv+"\n")
				continue
			tbz2path=self.getname(mycpv)
			if os.path.exists(tbz2path) and not os.access(tbz2path,os.W_OK):
				writemsg("!!! Cannot update readonly binary: "+mycpv+"\n")
				continue
			
			#print ">>> Updating data in:",mycpv
			sys.stdout.write("%")
			sys.stdout.flush()
			mytmpdir=settings["PORTAGE_TMPDIR"]+"/tbz2"
			mytbz2=xpak.tbz2(tbz2path)
			mytbz2.decompose(mytmpdir, cleanup=1)
			
			fixdbentries(origcp, newcp, mytmpdir)

			catfile=open(mytmpdir+"/CATEGORY", "w")
			catfile.write(mynewcat+"\n")
			catfile.close()
			try:
				os.rename(mytmpdir+"/"+string.split(mycpv,"/")[1]+".ebuild", mytmpdir+"/"+string.split(mynewcpv, "/")[1]+".ebuild")
			except SystemExit, e:
				raise
			except Exception, e:
				pass
				
			mytbz2.recompose(mytmpdir, cleanup=1)
			
			self.dbapi.cpv_remove(mycpv)
			if (mynewpkg != myoldpkg):
				os.rename(tbz2path,self.getname(mynewcpv))
			self.dbapi.cpv_inject(mynewcpv)
		return 1

	def move_slot_ent(self,mylist,mytmpdir):
		#mytmpdir=settings["PORTAGE_TMPDIR"]+"/tbz2"
		mytmpdir=mytmpdir+"/tbz2"
		if not self.populated:
			self.populate()
		pkg=mylist[1]
		origslot=mylist[2]
		newslot=mylist[3]
		origmatches=self.dbapi.match(pkg)
		if not origmatches:
			return
		for mycpv in origmatches:
			mycpsplit=portage_dep.catpkgsplit(mycpv)
			myoldpkg=mycpv.split("/")[1]
			tbz2path=self.getname(mycpv)
			if os.path.exists(tbz2path) and not os.access(tbz2path,os.W_OK):
				writemsg("!!! Cannot update readonly binary: "+mycpv+"\n")
				continue
			
			#print ">>> Updating data in:",mycpv
			mytbz2=xpak.tbz2(tbz2path)
			mytbz2.decompose(mytmpdir, cleanup=1)

			slot=grabfile(mytmpdir+"/SLOT");
			if (not slot):
				continue

			if (slot[0]!=origslot):
				continue

			sys.stdout.write("S")
			sys.stdout.flush()

			slotfile=open(mytmpdir+"/SLOT", "w")
			slotfile.write(newslot+"\n")
			slotfile.close()
			mytbz2.recompose(mytmpdir, cleanup=1)
		return 1

	def update_ents(self,mybiglist,mytmpdir):
		#XXX mytmpdir=settings["PORTAGE_TMPDIR"]+"/tbz2"
		if not self.populated:
			self.populate()
		for mycpv in self.dbapi.cp_all():
			tbz2path=self.getname(mycpv)
			if os.path.exists(tbz2path) and not os.access(tbz2path,os.W_OK):
				writemsg("!!! Cannot update readonly binary: "+mycpv+"\n")
				continue
			#print ">>> Updating binary data:",mycpv
			writemsg("*")
			mytbz2=xpak.tbz2(tbz2path)
			mytbz2.decompose(mytmpdir,cleanup=1)
			for mylist in mybiglist:
				mylist=string.split(mylist)
				if mylist[0] != "move":
					continue
				fixdbentries(mylist[1], mylist[2], mytmpdir)
			mytbz2.recompose(mytmpdir,cleanup=1)
		return 1

	def populate(self, getbinpkgs=0,getbinpkgsonly=0):
		"populates the binarytree"
		if (not os.path.isdir(self.pkgdir) and not getbinpkgs):
			return 0
		if (not os.path.isdir(self.pkgdir+"/All") and not getbinpkgs):
			return 0

		if (not getbinpkgsonly) and os.path.exists(self.pkgdir+"/All"):
			for mypkg in listdir(self.pkgdir+"/All"):
				if mypkg[-5:]!=".tbz2":
					continue
				mytbz2=xpak.tbz2(self.pkgdir+"/All/"+mypkg)
				mycat=mytbz2.getfile("CATEGORY")
				if not mycat:
					#old-style or corrupt package
					writemsg("!!! Invalid binary package: "+mypkg+"\n")
					self.invalids.append(mypkg)
					continue
				mycat=string.strip(mycat)
				fullpkg=mycat+"/"+mypkg[:-5]
				mykey=dep_getkey(fullpkg)
				try:
					# invalid tbz2's can hurt things.
					self.dbapi.cpv_inject(fullpkg)
				except SystemExit, e:
					raise
				except:
					continue

		if getbinpkgs and not settings["PORTAGE_BINHOST"]:
			writemsg(red("!!! PORTAGE_BINHOST unset, but use is requested.\n"))

		if getbinpkgs and settings["PORTAGE_BINHOST"] and not self.remotepkgs:
			try:
				chunk_size = long(settings["PORTAGE_BINHOST_CHUNKSIZE"])
				if chunk_size < 8:
					chunk_size = 8
			except SystemExit, e:
				raise
			except:
				chunk_size = 3000

			writemsg(green("Fetching binary packages info...\n"))
			self.remotepkgs = getbinpkg.dir_get_metadata(settings["PORTAGE_BINHOST"], chunk_size=chunk_size)
			writemsg(green("  -- DONE!\n\n"))

			for mypkg in self.remotepkgs.keys():
				if not self.remotepkgs[mypkg].has_key("CATEGORY"):
					#old-style or corrupt package
					writemsg("!!! Invalid remote binary package: "+mypkg+"\n")
					del self.remotepkgs[mypkg]
					continue
				mycat=string.strip(self.remotepkgs[mypkg]["CATEGORY"])
				fullpkg=mycat+"/"+mypkg[:-5]
				mykey=dep_getkey(fullpkg)
				try:
					# invalid tbz2's can hurt things.
					#print "cpv_inject("+str(fullpkg)+")"
					self.dbapi.cpv_inject(fullpkg)
					#print "  -- Injected"
				except SystemExit, e:
					raise
				except:
					writemsg("!!! Failed to inject remote binary package:"+str(fullpkg)+"\n")
					del self.remotepkgs[mypkg]
					continue
		self.populated=1

	def inject(self,cpv):
		return self.dbapi.cpv_inject(cpv)
	
	def exists_specific(self,cpv):
		if not self.populated:
			self.populate()
		return self.dbapi.match(dep_expand("="+cpv,mydb=self.dbapi))

	def dep_bestmatch(self,mydep):
		"compatibility method -- all matches, not just visible ones"
		if not self.populated:
			self.populate()
		writemsg("\n\n", 1)
		writemsg("mydep: %s\n" % mydep, 1)
		mydep=dep_expand(mydep,mydb=self.dbapi)
		writemsg("mydep: %s\n" % mydep, 1)
		mykey=dep_getkey(mydep)
		writemsg("mykey: %s\n" % mykey, 1)
		mymatch=best(match_from_list(mydep,self.dbapi.cp_list(mykey)))
		writemsg("mymatch: %s\n" % mymatch, 1)
		if mymatch==None:
			return ""
		return mymatch

	def getname(self,pkgname):
		"returns file location for this particular package"
		mysplit=string.split(pkgname,"/")
		if len(mysplit)==1:
			return self.pkgdir+"/All/"+self.resolve_specific(pkgname)+".tbz2"
		else:
			return self.pkgdir+"/All/"+mysplit[1]+".tbz2"

	def isremote(self,pkgname):
		"Returns true if the package is kept remotely."
		mysplit=string.split(pkgname,"/")
		remote = (not os.path.exists(self.getname(pkgname))) and self.remotepkgs.has_key(mysplit[1]+".tbz2")
		return remote
	
	def get_use(self,pkgname):
		mysplit=string.split(pkgname,"/")
		if self.isremote(pkgname):
			return string.split(self.remotepkgs[mysplit[1]+".tbz2"]["USE"][:])
		tbz2=xpak.tbz2(self.getname(pkgname))
		return string.split(tbz2.getfile("USE"))
	
	def gettbz2(self,pkgname):
		"fetches the package from a remote site, if necessary."
		print "Fetching '"+str(pkgname)+"'"
		mysplit  = string.split(pkgname,"/")
		tbz2name = mysplit[1]+".tbz2"
		if not self.isremote(pkgname):
			if (tbz2name not in self.invalids):
				return
			else:
				writemsg("Resuming download of this tbz2, but it is possible that it is corrupt.\n")
		mydest = self.pkgdir+"/All/"
		try:
			os.makedirs(mydest, 0775)
		except SystemExit, e:
			raise
		except:
			pass
		getbinpkg.file_get(settings["PORTAGE_BINHOST"]+"/"+tbz2name, mydest, fcmd=settings["RESUMECOMMAND"])
		return

	def getslot(self,mycatpkg):
		"Get a slot for a catpkg; assume it exists."
		myslot = ""
		try:
			myslot=self.dbapi.aux_get(mycatpkg,["SLOT"])[0]
		except SystemExit, e:
			raise
		except Exception, e:
			pass
		return myslot

class dblink:
	"this class provides an interface to the standard text package database"
	def __init__(self,cat,pkg,myroot,mysettings,treetype="porttree"):
		"create a dblink object for cat/pkg.  This dblink entry may or may not exist"
		self.cat     = cat
		self.pkg     = pkg
		self.mycpv   = self.cat+"/"+self.pkg
		self.mysplit = portage_dep.pkgsplit(self.mycpv)
		self.treetype = treetype

		self.dbroot   = os.path.normpath(myroot+VDB_PATH)
		self.dbcatdir = self.dbroot+"/"+cat
		self.dbpkgdir = self.dbcatdir+"/"+pkg
		self.dbtmpdir = self.dbcatdir+"/-MERGING-"+pkg
		self.dbdir    = self.dbpkgdir
		
		self.lock_pkg = None
		self.lock_tmp = None
		self.lock_num = 0    # Count of the held locks on the db.
	
		self.settings = mysettings
		if self.settings==1:
			raise ValueError
	
		self.myroot=myroot
		self.updateprotect()
		self.contentscache=[]

	def lockdb(self):
		if self.lock_num == 0:
			self.lock_pkg = portage_locks.lockdir(self.dbpkgdir)
			self.lock_tmp = portage_locks.lockdir(self.dbtmpdir)
		self.lock_num += 1
		
	def unlockdb(self):
		self.lock_num -= 1
		if self.lock_num == 0:
			portage_locks.unlockdir(self.lock_tmp)
			portage_locks.unlockdir(self.lock_pkg)

	def getpath(self):
		"return path to location of db information (for >>> informational display)"
		return self.dbdir
	
	def exists(self):
		"does the db entry exist?  boolean."
		return os.path.exists(self.dbdir)
	
	def create(self):
		"create the skeleton db directory structure.  No contents, virtuals, provides or anything.  Also will create /var/db/pkg if necessary."
		# XXXXX Delete this eventually
		raise Exception, "This is bad. Don't use it."
		if not os.path.exists(self.dbdir):
			os.makedirs(self.dbdir)
	
	def delete(self):
		"erase this db entry completely"
		if not os.path.exists(self.dbdir):
			return
		try:
			for x in listdir(self.dbdir):
				os.unlink(self.dbdir+"/"+x)
			os.rmdir(self.dbdir)
		except OSError, e:
			print "!!! Unable to remove db entry for this package."
			print "!!! It is possible that a directory is in this one. Portage will still"
			print "!!! register this package as installed as long as this directory exists."
			print "!!! You may delete this directory with 'rm -Rf "+self.dbdir+"'"
			print "!!! "+str(e)
			print
			sys.exit(1)
	
	def clearcontents(self):
		if os.path.exists(self.dbdir+"/CONTENTS"):
			os.unlink(self.dbdir+"/CONTENTS")
	
	def getcontents(self):
		if not os.path.exists(self.dbdir+"/CONTENTS"):
			return None
		if self.contentscache != []:
			return self.contentscache
		pkgfiles={}
		myc=open(self.dbdir+"/CONTENTS","r")
		mylines=myc.readlines()
		myc.close()
		pos=1
		for line in mylines:
			mydat = string.split(line)
			# we do this so we can remove from non-root filesystems
			# (use the ROOT var to allow maintenance on other partitions)
			try:
				mydat[1]=os.path.normpath(root+mydat[1][1:])
				if mydat[0]=="obj":
					#format: type, mtime, md5sum
					pkgfiles[string.join(mydat[1:-2]," ")]=[mydat[0], mydat[-1], mydat[-2]]
				elif mydat[0]=="dir":
					#format: type
					pkgfiles[string.join(mydat[1:])]=[mydat[0] ]
				elif mydat[0]=="sym":
					#format: type, mtime, dest
					x=len(mydat)-1
					if (x >= 13) and (mydat[-1][-1]==')'): # Old/Broken symlink entry
						mydat = mydat[:-10]+[mydat[-10:][stat.ST_MTIME][:-1]]
						writemsg("FIXED SYMLINK LINE: %s\n" % mydat, 1)
						x=len(mydat)-1
					splitter=-1
					while(x>=0):
						if mydat[x]=="->":
							splitter=x
							break
						x=x-1
					if splitter==-1:
						return None
					pkgfiles[string.join(mydat[1:splitter]," ")]=[mydat[0], mydat[-1], string.join(mydat[(splitter+1):-1]," ")]
				elif mydat[0]=="dev":
					#format: type
					pkgfiles[string.join(mydat[1:]," ")]=[mydat[0] ]
				elif mydat[0]=="fif":
					#format: type
					pkgfiles[string.join(mydat[1:]," ")]=[mydat[0]]
				else:
					return None
			except (KeyError,IndexError):
				print "portage: CONTENTS line",pos,"corrupt!"
			pos += 1
		self.contentscache=pkgfiles
		return pkgfiles

	def updateprotect(self):
		#do some config file management prep
		self.protect=[]
		for x in string.split(self.settings["CONFIG_PROTECT"]):
			ppath=normpath(self.myroot+x)+"/"
			if os.path.isdir(ppath):
				self.protect.append(ppath)
			
		self.protectmask=[]
		for x in string.split(self.settings["CONFIG_PROTECT_MASK"]):
			ppath=normpath(self.myroot+x)+"/"
			if os.path.isdir(ppath):
				self.protectmask.append(ppath)
			#if it doesn't exist, silently skip it

	def isprotected(self,obj):
		"""Checks if obj is in the current protect/mask directories. Returns
		0 on unprotected/masked, and 1 on protected."""
		masked=0
		protected=0
		for ppath in self.protect:
			if (len(ppath) > masked) and (obj[0:len(ppath)]==ppath):
				protected=len(ppath)
				#config file management
				for pmpath in self.protectmask:
					if (len(pmpath) >= protected) and (obj[0:len(pmpath)]==pmpath):
						#skip, it's in the mask
						masked=len(pmpath)
		return (protected > masked)

	def unmerge(self,pkgfiles=None,trimworld=1,cleanup=0):
		global dircache
		dircache={}
		
		self.lockdb()
		
		self.settings.load_infodir(self.dbdir)

		if not pkgfiles:
			print "No package files given... Grabbing a set."
			pkgfiles=self.getcontents()

		# Now, don't assume that the name of the ebuild is the same as the
		# name of the dir; the package may have been moved.
		myebuildpath=None
		
		# We should use the environement file if possible,
		# as it has all sourced files already included.
		# XXX: Need to ensure it doesn't overwrite any important vars though.
		if os.access(self.dbdir+"/environment.bz2", os.R_OK):
			portage_exec.spawn("bzip2 -d "+self.dbdir+"/environment.bz2")
		
		if not myebuildpath:
			mystuff=listdir(self.dbdir,EmptyOnError=1)
			for x in mystuff:
				if x[-7:]==".ebuild":
					myebuildpath=self.dbdir+"/"+x
					break

		#do prerm script
		if myebuildpath and os.path.exists(myebuildpath):
			a=doebuild(myebuildpath,"prerm",self.myroot,self.settings,cleanup=cleanup,use_cache=0, \
			tree=self.treetype)
			# XXX: Decide how to handle failures here.
			if a != 0:
				writemsg("!!! FAILED prerm: "+str(a)+"\n")
				sys.exit(123)

		if pkgfiles:
			mykeys=pkgfiles.keys()
			mykeys.sort()
			mykeys.reverse()

			self.updateprotect()

			#process symlinks second-to-last, directories last.
			mydirs=[]
			mysyms=[]
			modprotect="/lib/modules/"
			for obj in mykeys:
				obj=os.path.normpath(obj)
				if obj[:2]=="//":
					obj=obj[1:]
				if not os.path.exists(obj):
					if not os.path.islink(obj):
						#we skip this if we're dealing with a symlink
						#because os.path.exists() will operate on the
						#link target rather than the link itself.
						print "--- !found "+str(pkgfiles[obj][0]), obj
						continue
				# next line includes a tweak to protect modules from being unmerged,
				# but we don't protect modules from being overwritten if they are
				# upgraded. We effectively only want one half of the config protection
				# functionality for /lib/modules. For portage-ng both capabilities
				# should be able to be independently specified.
				if self.isprotected(obj) or ((len(obj) > len(modprotect)) and (obj[0:len(modprotect)]==modprotect)):
					print "--- cfgpro "+str(pkgfiles[obj][0]), obj
					continue

				lstatobj=os.lstat(obj)
				lmtime=str(lstatobj[stat.ST_MTIME])
				if (pkgfiles[obj][0] not in ("dir","fif","dev","sym")) and (lmtime != pkgfiles[obj][1]):
					print "--- !mtime", pkgfiles[obj][0], obj
					continue

				if pkgfiles[obj][0]=="dir":
					if not os.path.isdir(obj):
						print "--- !dir  ","dir", obj
						continue
					mydirs.append(obj)
				elif pkgfiles[obj][0]=="sym":
					if not os.path.islink(obj):
						print "--- !sym  ","sym", obj
						continue
					mysyms.append(obj)
				elif pkgfiles[obj][0]=="obj":
					if not os.path.isfile(obj):
						print "--- !obj  ","obj", obj
						continue
					mymd5=portage_checksum.perform_md5(obj, calc_prelink=1)

					# string.lower is needed because db entries used to be in upper-case.  The
					# string.lower allows for backwards compatibility.
					if mymd5 != string.lower(pkgfiles[obj][2]):
						print "--- !md5  ","obj", obj
						continue
					try:
						os.unlink(obj)
					except (OSError,IOError),e:
						pass		
					print "<<<       ","obj",obj
				elif pkgfiles[obj][0]=="fif":
					if not stat.S_ISFIFO(lstatobj[stat.ST_MODE]):
						print "--- !fif  ","fif", obj
						continue
					try:
						os.unlink(obj)
					except (OSError,IOError),e:
						pass
					print "<<<       ","fif",obj
				elif pkgfiles[obj][0]=="dev":
					print "---       ","dev",obj

			#Now, we need to remove symlinks and directories.  We'll repeatedly
			#remove dead symlinks, then directories until we stop making progress.
			#This is how we'll clean up directories containing symlinks pointing to
			#directories that are now empty.  These cases will require several
			#iterations through our two-stage symlink/directory cleaning loop.
	
			#main symlink and directory removal loop:
	
			#progress -- are we making progress?  Initialized to 1 so loop will start
			progress=1
			while progress:
				#let's see if we're able to make progress this iteration...
				progress=0
	
				#step 1: remove all the dead symlinks we can...
	
				pos = 0
				while pos<len(mysyms):
					obj=mysyms[pos]
					if os.path.exists(obj):
						pos += 1
					else:
						#we have a dead symlink; remove it from our list, then from existence
						del mysyms[pos]
						#we've made progress!	
						progress = 1
						try:
							os.unlink(obj)
							print "<<<       ","sym",obj
						except (OSError,IOError),e:
							print "!!!       ","sym",obj
							#immutable?
							pass
		
				#step 2: remove all the empty directories we can...
		
				pos = 0
				while pos<len(mydirs):
					obj=mydirs[pos]
					objld=listdir(obj)

					if objld == None:
						print "mydirs["+str(pos)+"]",mydirs[pos]
						print "obj",obj
						print "objld",objld
						# the directory doesn't exist yet, continue
						pos += 1
						continue

					if len(objld)>0:
						#we won't remove this directory (yet), continue
						pos += 1
						continue
					elif (objld != None):
						#zappo time
						del mydirs[pos]
						#we've made progress!
						progress = 1
						try:
							os.rmdir(obj)
							print "<<<       ","dir",obj
						except (OSError,IOError),e:
							#immutable?
							pass
					#else:
					#	print "--- !empty","dir", obj
					#	continue
			
				#step 3: if we've made progress, we'll give this another go...
	
			#step 4: otherwise, we'll print out the remaining stuff that we didn't unmerge (and rightly so!)
	
			#directories that aren't empty:
			for x in mydirs:
				print "--- !empty dir", x
				
			#symlinks whose target still exists:
			for x in mysyms:
				print "--- !targe sym", x

		#step 5: well, removal of package objects is complete, now for package *meta*-objects....

		#remove self from vartree database so that our own virtual gets zapped if we're the last node
		db[self.myroot]["vartree"].zap(self.mycpv)

		# New code to remove stuff from the world and virtuals files when unmerged.
		if trimworld:
			worldlist=grabfile(self.myroot+WORLD_FILE)
			mykey=cpv_getkey(self.mycpv)
			newworldlist=[]
			for x in worldlist:
				if dep_getkey(x)==mykey:
					matches=db[self.myroot]["vartree"].dbapi.match(x,use_cache=0)
					if not matches:
						#zap our world entry
						pass
					elif (len(matches)==1) and (matches[0]==self.mycpv):
						#zap our world entry
						pass
					else:
						#others are around; keep it.
						newworldlist.append(x)
				else:
					#this doesn't match the package we're unmerging; keep it.
					newworldlist.append(x)
			myworld=open(self.myroot+WORLD_FILE,"w")
			for x in newworldlist:
				myworld.write(x+"\n")
			myworld.close()

		#do original postrm
		if myebuildpath and os.path.exists(myebuildpath):
			# XXX: This should be the old config, not the current one.
			# XXX: Use vardbapi to load up env vars.
			a=doebuild(myebuildpath,"postrm",self.myroot,self.settings,use_cache=0,tree=self.treetype)
			# XXX: Decide how to handle failures here.
			if a != 0:
				writemsg("!!! FAILED postrm: "+str(a)+"\n")
				sys.exit(123)

		self.unlockdb()

	def isowner(self,filename,destroot):
		""" check if filename is a new file or belongs to this package
		(for this or a previous version)"""
		destfile = os.path.normpath(destroot+"/"+filename)
		if not os.path.exists(destfile):
			return True
		if self.getcontents() and filename in self.getcontents().keys():
			return True
		
		return False

	def treewalk(self,srcroot,destroot,inforoot,myebuild,cleanup=0):
		global db
		# srcroot  = ${D};
		# destroot = where to merge, ie. ${ROOT},
		# inforoot = root of db entry,
		# secondhand = list of symlinks that have been skipped due to
		#              their target not existing (will merge later),

		if not os.path.exists(self.dbcatdir):
			os.makedirs(self.dbcatdir)

		# This blocks until we can get the dirs to ourselves.
		self.lockdb()

		stopmerge=False
		do_prelink = ("prelink" in features and portage_checksum.prelink_capable)
		if "collision-protect" in features or "verify-rdepend" in features or do_prelink:
			myfilelist = listdir(srcroot, recursive=1, filesonly=1,followSymlinks=False)
			# the linkcheck only works if we are in srcroot
			try:
				mycwd = os.getcwd()
			except OSerror:
				mycwd="/"
			os.chdir(srcroot)
			mysymlinks = filter(os.path.islink, listdir(srcroot, recursive=1, filesonly=0,followSymlinks=False))
			os.chdir(mycwd)
			
		# check for package collisions
		otherversions=[]
		for v in db[self.myroot]["vartree"].dbapi.cp_list(self.mysplit[0]):
			otherversions.append(v.split("/")[1])

		if self.pkg in otherversions:
			otherversions.remove(self.pkg)	# we already checked this package

		if "collision-protect" in features:
			starttime=time.time()
			i=0

			otherpkg=[]
			mypkglist=[]

			for v in otherversions:
				# should we check for same SLOT here ?
				mypkglist.append(dblink(self.cat,v,destroot,self.settings))

			print
			print green("*")+" checking "+str(len(myfilelist))+" files for package collisions"
			for f in myfilelist:
				nocheck = False
				# listdir isn't intelligent enough to exclude symlinked dirs,
				# so we have to do it ourself
				for s in mysymlinks:
					# the length comparison makes sure that the symlink itself is checked
					if f[:len(s)] == s and len(f) > len(s):
						nocheck = True
				if nocheck:
					continue
				i=i+1
				if i % 1000 == 0:
					print str(i)+" files checked ..."
				if f[0] != "/":
					f="/"+f
				isowned = False
				for ver in [self]+mypkglist:
					if (ver.isowner(f, destroot) or ver.isprotected(f)):
						isowned = True
						break
				if not isowned:
					print "existing file "+f+" is not owned by this package"
					stopmerge=True
			print green("*")+" spent "+str(time.time()-starttime)+" seconds checking for file collisions"
			if stopmerge:
				print red("*")+" This package is blocked because it wants to overwrite"
				print red("*")+" files belonging to other packages (see messages above)."
				print red("*")+" If you have no clue what this is all about report it "
				print red("*")+" as a bug for this package on http://bugs.gentoo.org"
				print
				print red("package "+self.cat+"/"+self.pkg+" NOT merged")
				print
				# Why is the package already merged here db-wise? Shouldn't be the case
				# only unmerge if it ia new package and has no contents
				if not self.getcontents():
					self.unmerge()
					self.delete()
				self.unlockdb()
				sys.exit(1)
		
		prelink_bins = []
		if "verify-rdepend" in features or do_prelink:
			checklist=[]
			print
			print green("*")+ " grabbing %s/%s's binaries/libs" % (self.cat,self.pkg)
			for f in myfilelist:
				nocheck = False
				# listdir isn't intelligent enough to exclude symlinked dirs,
				# so we have to do it ourself
				for s in mysymlinks:
					# the length comparison makes sure that the symlink itself is checked
					if f[:len(s)] == s and len(f) > len(s):
						continue

				retval, bins=portage_exec.spawn_get_output("ldd -r %s" % f,collect_fds=[1],emulate_gso=False)
				if retval:
					continue
				for x in bins:
					y=x.split()
					if y[0][0:13] != "linux-gate.so" and y[0] not in checklist:
						checklist.append(y[0])

				prelink_bins.append(f)

		if "verify-rdepend" in features:
			starttime=time.time()
			print green("*")+ " checking %s/%s RDEPEND" % (self.cat, self.pkg)

			# Step1: filter package's provided libs first.
			candidates_checked=["%s/%s" % (self.cat,self.pkg)]
			if len(checklist):
				l=[]
				for x in myfilelist:
					l.append(x.split("/")[-1])
				#mysymlinks is pairs of src, trg.  add srcs in.
				for x in range(0,len(mysymlinks),2):
					l.append(mysymlinks[x].split("/")[-1])
				y=0
				while y < len(checklist):
					if checklist[y] in l or checklist[y] in myfilelist:
						checklist.pop(y)
					else:
						y+=1

			# Step2: filter out libs from the packages states RDEPEND
			if len(checklist):
				rdep=portage_dep.paren_reduce(db[self.myroot][self.treetype].dbapi.aux_get( \
					self.mycpv,["RDEPEND"])[0])
				rdep=portage_util.unique_array(flatten(portage_dep.use_reduce(rdep, \
					uselist=self.settings["USE"],matchall=False)))
			
				r=[]
				for x in rdep:
					r.extend(db[self.myroot]["vartree"].dbapi.match(x))
			
				rdep=r

				# filter first package rdeps, then virtual/.?libc, then gcc

				lm = db[self.myroot]["vartree"].dbapi.match("virtual/glibc")
				lm.extend(db[self.myroot]["vartree"].dbapi.match("virtual/libc"))
				lm = portage_util.unique_array(lm)
				
				for rd,msg in [(r,"%s/%s's RDEPEND" % (self.cat,self.pkg)), \
					(lm, "virtual/glibc, virtual/libc"), \
					(db[self.myroot]["vartree"].dbapi.match("gcc"), "gcc")]:

					print green("*")+" Parsing %s contents" % msg

					candidates_checked.extend(rd)

					for r in rd:
						s=catsplit(r)
#						print "%s=" % r, s
						c=dblink(s[0],s[1],self.myroot,self.settings).getcontents()
						if c == None:
							print yellow("---")+" Installed package %s seems to lack a contents file" % r
						else:
							y=0
							l=[]
							
							# build a list of obj files minus their directory.
							for x in c.keys():
								if c[x][0] in ["obj","sym"]:
									l.append(x.split("/")[-1])

							while y < len(checklist):
								if c.has_key(checklist[y]) or checklist[y] in l:
#									print "%s satisfied by %s" % (checklist[y], r)
									checklist.pop(y)
								else:
									y+=1
						if len(checklist) == 0:
							break
					if len(checklist) == 0:
						break

			# Step3: breadth then depth walk of package's RDEPEND's, RDEPEND's.
			# not much for this, since it's entirely possible invalid deps could be filtered out.
			# probably worth doing uselist=[], since at this point, a depend atom can't specify use flag.
			if len(checklist):
				# so now we recursive walk the RDEPEND's of cpv's RDEPENDS. yay.
				print green("*")+" Parsing breadth then depth of %s/%s's RDEPEND's now (libs remain)" % (self.cat,self.pkg)
				candidate=rdep

			while len(checklist) and len(candidate):
				r=candidate.pop(0)

				candidates_checked.append(r)

				s=catsplit(r)
				c=dblink(s[0],s[1],self.myroot,self.settings).getcontents()
				if c == None:
					print yellow("---")+" Installed package %s seems to lack a contents file" % r
				else:
					l=[]	

					# build a list of obj files minus their directory.
					for x in c.keys():
						if c[x][0] in ["obj","sym"]:
							l.append(x.split("/")[-1])

					y=0
					while y < len(checklist):
						if c.has_key(checklist[y]) or checklist[y] in l:
							checklist.pop(y)
						else:
							y+=1

				if len(checklist):
					# append this nodes rdepend.
					rdep,u=db[self.myroot]["vartree"].dbapi.aux_get(r,["RDEPEND","USE"])
					pd=flatten(portage_dep.use_reduce(portage_dep.paren_reduce(rdep),\
						uselist=u,matchall=False))
					pd=portage_util.unique_array(pd)
					for x in pd:
						for y in db["/"]["vartree"].dbapi.match(x):
							if y not in candidates_checked:
								candidate.append(y)
					candidate=portage_util.unique_array(flatten(candidate))
							
			# Step4: Complain.  Loudly.
			if len(checklist):
				print
				print red("!!!")+"  %s/%s has an incomplete RDEPEND: Unmatched libs:" % (self.cat, self.pkg)
				print red("!!!  ")+string.join(checklist,", ")
				print
				for x in range(0,10):
					sys.stdout.write("\a")
				if "severe" in features:
					if not self.getcontents():
						self.unmerge()
						self.delete()
					self.unlockdb()
					sys.exit(1)

			print green("*")+" spent "+str(time.time()-starttime)+" seconds verifying RDEPEND"


		if do_prelink:
			starttime=time.time()
			print
			print green("*")+ " prelinking %d binaries" % len(prelink_bins)
			c = [PRELINK_BINARY]
			if settings.has_key("PRELINK_OPTS"):
				c.extend(settings["PRELINK_OPTS"].split())

			for x in range(0,len(prelink_bins),10):
				c2=c[:]
				if x + 10 > len(prelink_bins):
					c2.extend(prelink_bins[x:])
				else:
					c2.extend(prelink_bins[x:x+10])
				try:
					portage_exec.spawn(c2)
				except SystemExit:
					raise
				except Exception,e:
					print "caught exception while prelinking",e

			print green("*")+" spent "+str(time.time()-starttime)+" seconds prelinking"
			

		# get old contents info for later unmerging
		oldcontents = self.getcontents()

		self.dbdir = self.dbtmpdir
		self.delete()
		if not os.path.exists(self.dbtmpdir):
			os.makedirs(self.dbtmpdir)
		
		print ">>> Merging",self.mycpv,"to",destroot

		# run preinst script
		if myebuild:
			# if we are merging a new ebuild, use *its* pre/postinst rather than using the one in /var/db/pkg
			# (if any).
			a=doebuild(myebuild,"preinst",root,self.settings,cleanup=0,use_cache=0, \
				use_info_env=False,tree=self.treetype)
		else:
			a=doebuild(inforoot+"/"+self.pkg+".ebuild","preinst",root,self.settings,cleanup=0, \
				use_cache=0,tree=self.treetype)

		# XXX: Decide how to handle failures here.
		if a != 0:
			writemsg("!!! FAILED preinst: "+str(a)+"\n")
			sys.exit(123)

		# copy "info" files (like SLOT, CFLAGS, etc.) into the database
		for x in listdir(inforoot):
			self.copyfile(inforoot+"/"+x)

		# get current counter value (counter_tick also takes care of incrementing it)
		# XXX Need to make this destroot, but it needs to be initialized first. XXX
		# XXX bis: leads to some invalidentry() call through cp_all().
		counter = db["/"]["vartree"].dbapi.counter_tick(self.myroot,mycpv=self.mycpv)
		# write local package counter for recording
		lcfile = open(self.dbtmpdir+"/COUNTER","w")
		lcfile.write(str(counter))
		lcfile.close()

		# open CONTENTS file (possibly overwriting old one) for recording
		outfile=open(self.dbtmpdir+"/CONTENTS","w")

		self.updateprotect()

		#if we have a file containing previously-merged config file md5sums, grab it.
		if os.path.exists(destroot+CONFIG_MEMORY_FILE):
			cfgfiledict=grabdict(destroot+CONFIG_MEMORY_FILE)
		else:
			cfgfiledict={}
		if self.settings.has_key("NOCONFMEM"):
			cfgfiledict["IGNORE"]=1
		else:
			cfgfiledict["IGNORE"]=0

		# set umask to 0 for merging; back up umask, save old one in prevmask (since this is a global change)
		mymtime    = long(time.time())
		prevmask   = os.umask(0)
		secondhand = []

		# we do a first merge; this will recurse through all files in our srcroot but also build up a
		# "second hand" of symlinks to merge later
		if self.mergeme(srcroot,destroot,outfile,secondhand,"",cfgfiledict,mymtime):
			return 1

		# now, it's time for dealing our second hand; we'll loop until we can't merge anymore.	The rest are
		# broken symlinks.  We'll merge them too.
		lastlen=0
		while len(secondhand) and len(secondhand)!=lastlen:
			# clear the thirdhand.	Anything from our second hand that
			# couldn't get merged will be added to thirdhand.

			thirdhand=[]
			self.mergeme(srcroot,destroot,outfile,thirdhand,secondhand,cfgfiledict,mymtime)

			#swap hands
			lastlen=len(secondhand)
			
			# our thirdhand now becomes our secondhand.  It's ok to throw
			# away secondhand since thirdhand contains all the stuff that
			# couldn't be merged.
			secondhand = thirdhand

		if len(secondhand):
			# force merge of remaining symlinks (broken or circular; oh well)
			self.mergeme(srcroot,destroot,outfile,None,secondhand,cfgfiledict,mymtime)
		
		#restore umask
		os.umask(prevmask)

		#if we opened it, close it
		outfile.flush()
		outfile.close()

		if (oldcontents):
			print ">>> Safely unmerging already-installed instance..."
			self.dbdir = self.dbpkgdir
			self.unmerge(oldcontents,trimworld=0)
			self.dbdir = self.dbtmpdir
			print ">>> original instance of package unmerged safely."	

		# We hold both directory locks.
		self.dbdir = self.dbpkgdir
		self.delete()
		movefile(self.dbtmpdir, self.dbpkgdir, mysettings=self.settings)

		self.unlockdb()

		#write out our collection of md5sums
		if cfgfiledict.has_key("IGNORE"):
			del cfgfiledict["IGNORE"]

		# XXXX: HACK! PathSpec is very necessary here.
		if not os.path.exists(destroot+PRIVATE_PATH):
			os.makedirs(destroot+PRIVATE_PATH)
			os.chown(destroot+PRIVATE_PATH,os.getuid(),portage_gid)
			os.chmod(destroot+PRIVATE_PATH,02770)
			dirlist = prefix_array(listdir(destroot+PRIVATE_PATH),destroot+PRIVATE_PATH+"/")
			while dirlist:
				dirlist.sort()
				dirlist.reverse() # Gets them in file-before basedir order
				x = dirlist[0]
				if os.path.isdir(x):
					dirlist += prefix_array(listdir(x),x+"/")
					continue
				os.unlink(destroot+PRIVATE_PATH+"/"+x)

		mylock = portage_locks.lockfile(destroot+CONFIG_MEMORY_FILE)
		writedict(cfgfiledict,destroot+CONFIG_MEMORY_FILE)
		portage_locks.unlockfile(mylock)
		
		#do postinst script
		if myebuild:
			# if we are merging a new ebuild, use *its* pre/postinst rather than using the one in /var/db/pkg 
			# (if any).
			a=doebuild(myebuild,"postinst",root,self.settings,use_cache=0,use_info_env=False,cleanup=0,tree=self.treetype)
		else:
			a=doebuild(inforoot+"/"+self.pkg+".ebuild","postinst",root,self.settings,use_cache=0,cleanup=0,tree=self.treetype)

		# XXX: Decide how to handle failures here.
		if a != 0:
			writemsg("!!! FAILED postinst: "+str(a)+"\n")
			sys.exit(123)

		downgrade = False
		for v in otherversions:
			if pkgcmp(portage_dep.catpkgsplit(self.pkg)[1:], portage_dep.catpkgsplit(v)[1:]) < 0:
				downgrade = True

		#update environment settings, library paths. DO NOT change symlinks.
		env_update(self.myroot,makelinks=(not downgrade))
		#dircache may break autoclean because it remembers the -MERGING-pkg file
		global dircache
		if dircache.has_key(self.dbcatdir):
			del dircache[self.dbcatdir]
		print ">>>",self.mycpv,"merged."
		
		return 0

	def mergeme(self,srcroot,destroot,outfile,secondhand,stufftomerge,cfgfiledict,thismtime):
		srcroot=os.path.normpath("///"+srcroot)+"/"
		destroot=os.path.normpath("///"+destroot)+"/"
		# this is supposed to merge a list of files.  There will be 2 forms of argument passing.
		if type(stufftomerge)==types.StringType:
			#A directory is specified.  Figure out protection paths, listdir() it and process it.
			mergelist=listdir(srcroot+stufftomerge)
			offset=stufftomerge
			# We need mydest defined up here to calc. protection paths.  This is now done once per
			# directory rather than once per file merge.  This should really help merge performance.
			# Trailing / ensures that protects/masks with trailing /'s match.
			mytruncpath="/"+offset+"/"
			myppath=self.isprotected(mytruncpath)
		else:
			mergelist=stufftomerge
			offset=""
		for x in mergelist:
			mysrc=os.path.normpath("///"+srcroot+offset+x)
			mydest=os.path.normpath("///"+destroot+offset+x)
			# myrealdest is mydest without the $ROOT prefix (makes a difference if ROOT!="/")
			myrealdest="/"+offset+x
			# stat file once, test using S_* macros many times (faster that way)
			try:
				mystat=os.lstat(mysrc)
			except SystemExit, e:
				raise
			except OSError, e:
				writemsg("\n")
				writemsg(red("!!! ERROR: There appears to be ")+bold("FILE SYSTEM CORRUPTION.")+red(" A file that is listed\n"))
				writemsg(red("!!!        as existing is not capable of being stat'd. If you are using an\n"))
				writemsg(red("!!!        experimental kernel, please boot into a stable one, force an fsck,\n"))
				writemsg(red("!!!        and ensure your filesystem is in a sane state. ")+bold("'shutdown -Fr now'\n"))
				writemsg(red("!!!        File:  ")+str(mysrc)+"\n")
				writemsg(red("!!!        Error: ")+str(e)+"\n")
				sys.exit(1)
			except Exception, e:
				writemsg("\n")
				writemsg(red("!!! ERROR: An unknown error has occurred during the merge process.\n"))
				writemsg(red("!!!        A stat call returned the following error for the following file:"))
				writemsg(    "!!!        Please ensure that your filesystem is intact, otherwise report\n")
				writemsg(    "!!!        this as a portage bug at bugs.gentoo.org. Append 'emerge info'.\n")
				writemsg(    "!!!        File:  "+str(mysrc)+"\n")
				writemsg(    "!!!        Error: "+str(e)+"\n")
				sys.exit(1)
				
				
			mymode=mystat[stat.ST_MODE]
			# handy variables; mydest is the target object on the live filesystems;
			# mysrc is the source object in the temporary install dir 
			try:
				mydmode=os.lstat(mydest)[stat.ST_MODE]
			except SystemExit, e:
				raise
			except:
				#dest file doesn't exist
				mydmode=None
			
			if stat.S_ISLNK(mymode):
				# we are merging a symbolic link
				myabsto=abssymlink(mysrc)
				if myabsto[0:len(srcroot)]==srcroot:
					myabsto=myabsto[len(srcroot):]
					if myabsto[0]!="/":
						myabsto="/"+myabsto
				myto=os.readlink(mysrc)
				if self.settings and self.settings["D"]:
					if myto.find(self.settings["D"])==0:
						myto=myto[len(self.settings["D"]):]
				# myrealto contains the path of the real file to which this symlink points.
				# we can simply test for existence of this file to see if the target has been merged yet
				myrealto=os.path.normpath(os.path.join(destroot,myabsto))
				if mydmode!=None:
					#destination exists
					if not stat.S_ISLNK(mydmode):
						if stat.S_ISDIR(mydmode):
							# directory in the way: we can't merge a symlink over a directory
							# we won't merge this, continue with next file...
							continue
						if self.isprotected(mydest):
							# Use md5 of the target in ${D} if it exists...
							if os.path.exists(os.path.normpath(srcroot+myabsto)):
								mydest = new_protect_filename(myrealdest, newmd5=portage_checksum.perform_md5(srcroot+myabsto))
							else:
								mydest = new_protect_filename(myrealdest, newmd5=portage_checksum.perform_md5(myabsto))
								
				# if secondhand==None it means we're operating in "force" mode and should not create a second hand.
				if (secondhand!=None) and (not os.path.exists(myrealto)):
					# either the target directory doesn't exist yet or the target file doesn't exist -- or
					# the target is a broken symlink.  We will add this file to our "second hand" and merge
					# it later.
					secondhand.append(mysrc[len(srcroot):])
					continue
				# unlinking no longer necessary; "movefile" will overwrite symlinks atomically and correctly
				mymtime=movefile(mysrc,mydest,newmtime=thismtime,sstat=mystat, mysettings=self.settings)
				if mymtime!=None:
					print ">>>",mydest,"->",myto
					outfile.write("sym "+myrealdest+" -> "+myto+" "+str(mymtime)+"\n")
				else:
					print "!!! Failed to move file."
					print "!!!",mydest,"->",myto
					sys.exit(1)
			elif stat.S_ISDIR(mymode):
				# we are merging a directory
				if mydmode!=None:
					# destination exists
					if not os.access(mydest, os.W_OK):
						pkgstuff = portage_dep.pkgsplit(self.pkg)
						writemsg("\n!!! Cannot write to '"+mydest+"'.\n")
						writemsg("!!! Please check permissions and directories for broken symlinks.\n")
						writemsg("!!! You may start the merge process again by using ebuild:\n")
						writemsg("!!! ebuild "+self.settings["PORTDIR"]+"/"+self.cat+"/"+pkgstuff[0]+"/"+self.pkg+".ebuild merge\n")
						writemsg("!!! And finish by running this: env-update\n\n")
						return 1

					if stat.S_ISLNK(mydmode) or stat.S_ISDIR(mydmode):
						# a symlink to an existing directory will work for us; keep it:
						print "---",mydest+"/"
					else:
						# a non-directory and non-symlink-to-directory.  Won't work for us.  Move out of the way.
						if movefile(mydest,mydest+".backup", mysettings=self.settings) == None:
							print "failed move"
							sys.exit(1)
						print "bak",mydest,mydest+".backup"
						#now create our directory
						if selinux_enabled:
							sid = selinux.get_sid(mysrc)
							selinux.secure_mkdir(mydest,sid)
						else:
							os.mkdir(mydest)
						os.chmod(mydest,mystat[0])
						lchown(mydest,mystat[4],mystat[5])
						print ">>>",mydest+"/"
				else:
					#destination doesn't exist
					if selinux_enabled:
						sid = selinux.get_sid(mysrc)
						selinux.secure_mkdir(mydest,sid)
					else:
						os.mkdir(mydest)
					os.chmod(mydest,mystat[0])
					lchown(mydest,mystat[4],mystat[5])
					print ">>>",mydest+"/"
				outfile.write("dir "+myrealdest+"\n")
				# recurse and merge this directory
				if self.mergeme(srcroot,destroot,outfile,secondhand,offset+x+"/",cfgfiledict,thismtime):
					return 1
			elif stat.S_ISREG(mymode):
				# we are merging a regular file
				mymd5=portage_checksum.perform_md5(mysrc,calc_prelink=1)
				# calculate config file protection stuff
				mydestdir=os.path.dirname(mydest)	
				moveme=1
				zing="!!!"
				if mydmode!=None:
					# destination file exists
					if stat.S_ISDIR(mydmode):
						# install of destination is blocked by an existing directory with the same name
						moveme=0
						print "!!!",mydest
					elif stat.S_ISREG(mydmode) or (stat.S_ISLNK(mydmode) and os.path.exists(mydest) and stat.S_ISREG(os.stat(mydest)[stat.ST_MODE])):
						cfgprot=0
						# install of destination is blocked by an existing regular file,
						# or by a symlink to an existing regular file;
						# now, config file management may come into play.
						# we only need to tweak mydest if cfg file management is in play.
						if myppath:
							# we have a protection path; enable config file management.
							destmd5=portage_checksum.perform_md5(mydest,calc_prelink=1)
							cycled=0
							if cfgfiledict.has_key(myrealdest):
								if destmd5 in cfgfiledict[myrealdest]:
									#cycle
									print "cycle"
									del cfgfiledict[myrealdest]
									cycled=1
							if mymd5==destmd5:
								#file already in place; simply update mtimes of destination
								os.utime(mydest,(thismtime,thismtime))
								zing="---"
								moveme=0
							elif cycled:
								#mymd5!=destmd5 and we've cycled; move mysrc into place as a ._cfg file
								moveme=1
								cfgfiledict[myrealdest]=[mymd5]
								cfgprot=1
							elif cfgfiledict.has_key(myrealdest) and (mymd5 in cfgfiledict[myrealdest]):
								#myd5!=destmd5, we haven't cycled, and the file we're merging has been already merged previously 
								zing="-o-"
								moveme=cfgfiledict["IGNORE"]
								cfgprot=cfgfiledict["IGNORE"]
							else:	
								#mymd5!=destmd5, we haven't cycled, and the file we're merging hasn't been merged before
								moveme=1
								cfgprot=1
								if not cfgfiledict.has_key(myrealdest):
									cfgfiledict[myrealdest]=[]
								if mymd5 not in cfgfiledict[myrealdest]:
									cfgfiledict[myrealdest].append(mymd5)
								#don't record more than 16 md5sums
								if len(cfgfiledict[myrealdest])>16:
									del cfgfiledict[myrealdest][0]
	
						if cfgprot:
							mydest = new_protect_filename(myrealdest, newmd5=mymd5)

				# whether config protection or not, we merge the new file the
				# same way.  Unless moveme=0 (blocking directory)
				if moveme:
					mymtime=movefile(mysrc,mydest,newmtime=thismtime,sstat=mystat, mysettings=self.settings)
					if mymtime == None:
						print "failed move"
						sys.exit(1)
					zing=">>>"
				else:
					mymtime=thismtime
					# We need to touch the destination so that on --update the
					# old package won't yank the file with it. (non-cfgprot related)
					os.utime(myrealdest,(thismtime,thismtime))
					zing="---"
				if self.settings["ARCH"] == "ppc-macos" and myrealdest[-2:] == ".a":

					# XXX kludge, bug #58848; can be killed when portage stops relying on 
					# md5+mtime, and uses refcounts
					# alright, we've fooled w/ mtime on the file; this pisses off static archives
					# basically internal mtime != file's mtime, so the linker (falsely) thinks 
					# the archive is stale, and needs to have it's toc rebuilt.

					myf=open(myrealdest,"r+")

					# ar mtime field is digits padded with spaces, 12 bytes.
					lms=str(thismtime+5).ljust(12)
					myf.seek(0)
					magic=myf.read(8)
					if magic != "!<arch>\n":
						# not an archive (dolib.a from portage.py makes it here fex)
						myf.close()
					else:
						st=os.stat(myrealdest)
						while myf.tell() < st.st_size - 12:
							# skip object name
							myf.seek(16,1)
							
							# update mtime
							myf.write(lms)
						
							# skip uid/gid/mperm
							myf.seek(20,1)
								
							# read the archive member's size
							x=long(myf.read(10))
							
							# skip the trailing newlines, and add the potential 
							# extra padding byte if it's not an even size
							myf.seek(x + 2 + (x % 2),1)
							
						# and now we're at the end. yay.
						myf.close()
						mymd5=portage_checksum.perform_md5(myrealdest,calc_prelink=1)
					os.utime(myrealdest,(thismtime,thismtime))

				if mymtime!=None:
					zing=">>>"
					outfile.write("obj "+myrealdest+" "+mymd5+" "+str(mymtime)+"\n")
				print zing,mydest
			else:
				# we are merging a fifo or device node
				zing="!!!"
				if mydmode==None:
					# destination doesn't exist
					if movefile(mysrc,mydest,newmtime=thismtime,sstat=mystat, mysettings=self.settings)!=None:
						zing=">>>"
						if stat.S_ISFIFO(mymode):
							# we don't record device nodes in CONTENTS,
							# although we do merge them.
							outfile.write("fif "+myrealdest+"\n")
					else:
						sys.exit(1)
				print zing+" "+mydest
	
	def merge(self,mergeroot,inforoot,myroot,myebuild=None,cleanup=0):
		return self.treewalk(mergeroot,myroot,inforoot,myebuild,cleanup=cleanup)

	def getstring(self,name):
		"returns contents of a file with whitespace converted to spaces"
		if not os.path.exists(self.dbdir+"/"+name):
			return ""
		myfile=open(self.dbdir+"/"+name,"r")
		mydata=string.split(myfile.read())
		myfile.close()
		return string.join(mydata," ")
	
	def copyfile(self,fname):
		shutil.copyfile(fname,self.dbdir+"/"+os.path.basename(fname))
	
	def getfile(self,fname):
		if not os.path.exists(self.dbdir+"/"+fname):
			return ""
		myfile=open(self.dbdir+"/"+fname,"r")
		mydata=myfile.read()
		myfile.close()
		return mydata

	def setfile(self,fname,data):
		myfile=open(self.dbdir+"/"+fname,"w")
		myfile.write(data)
		myfile.close()
		
	def getelements(self,ename):
		if not os.path.exists(self.dbdir+"/"+ename):
			return [] 
		myelement=open(self.dbdir+"/"+ename,"r")
		mylines=myelement.readlines()
		myreturn=[]
		for x in mylines:
			for y in string.split(x[:-1]):
				myreturn.append(y)
		myelement.close()
		return myreturn
	
	def setelements(self,mylist,ename):
		myelement=open(self.dbdir+"/"+ename,"w")
		for x in mylist:
			myelement.write(x+"\n")
		myelement.close()
	
	def isregular(self):
		"Is this a regular package (does it have a CATEGORY file?  A dblink can be virtual *and* regular)"
		return os.path.exists(self.dbdir+"/CATEGORY")

def cleanup_pkgmerge(mypkg,origdir=None):
	shutil.rmtree(settings["PORTAGE_TMPDIR"]+"/portage-pkg/"+mypkg)
	if os.path.exists(settings["PORTAGE_TMPDIR"]+"/portage/"+mypkg+"/temp/environment"):
		os.unlink(settings["PORTAGE_TMPDIR"]+"/portage/"+mypkg+"/temp/environment")
	if origdir:
		os.chdir(origdir)

def pkgmerge(mytbz2,myroot,mysettings):
	"""will merge a .tbz2 file, returning a list of runtime dependencies
		that must be satisfied, or None if there was a merge error.	This
		code assumes the package exists."""
	if mytbz2[-5:]!=".tbz2":
		print "!!! Not a .tbz2 file"
		return None
	mypkg=os.path.basename(mytbz2)[:-5]
	xptbz2=xpak.tbz2(mytbz2)
	pkginfo={}
	mycat=xptbz2.getfile("CATEGORY")
	if not mycat:
		print "!!! CATEGORY info missing from info chunk, aborting..."
		return None
	mycat=mycat.strip()
	mycatpkg=mycat+"/"+mypkg
	tmploc=mysettings["PORTAGE_TMPDIR"]+"/portage-pkg/"
	pkgloc=tmploc+"/"+mypkg+"/bin/"
	infloc=tmploc+"/"+mypkg+"/inf/"
	myebuild=tmploc+"/"+mypkg+"/inf/"+os.path.basename(mytbz2)[:-4]+"ebuild"
	if os.path.exists(tmploc+"/"+mypkg):
		shutil.rmtree(tmploc+"/"+mypkg,1)
	os.makedirs(pkgloc)
	os.makedirs(infloc)
	print ">>> extracting info"
	xptbz2.unpackinfo(infloc)
	# run pkg_setup early, so we can bail out early
	# (before extracting binaries) if there's a problem
	origdir=getcwd()
	os.chdir(pkgloc)

	mysettings.configdict["pkg"]["CATEGORY"] = mycat
	a=doebuild(myebuild,"setup",myroot,mysettings,tree="bintree")
	print ">>> extracting",mypkg
	notok=spawn("bzip2 -dqc -- '"+mytbz2+"' | tar xpf -",mysettings,free=1)
	if notok:
		print "!!! Error extracting",mytbz2
		cleanup_pkgmerge(mypkg,origdir)
		return None

	# the merge takes care of pre/postinst and old instance
	# auto-unmerge, virtual/provides updates, etc.
	mysettings.load_infodir(infloc)
	mylink=dblink(mycat,mypkg,myroot,mysettings,treetype="bintree")
	mylink.merge(pkgloc,infloc,myroot,myebuild,cleanup=1)

	if not os.path.exists(infloc+"/RDEPEND"):
		returnme=""
	else:
		#get runtime dependencies
		a=open(infloc+"/RDEPEND","r")
		returnme=string.join(string.split(a.read())," ")
		a.close()
	cleanup_pkgmerge(mypkg,origdir)
	return returnme


if os.environ.has_key("ROOT"):
	root=os.environ["ROOT"]
	if not len(root):
		root="/"
	elif root[-1]!="/":
		root=root+"/"
else:
	root="/"
if root != "/":
	if not os.path.exists(root[:-1]):
		writemsg("!!! Error: ROOT "+root+" does not exist.  Please correct this.\n")
		writemsg("!!! Exiting.\n\n")
		sys.exit(1)
	elif not os.path.isdir(root[:-1]):
		writemsg("!!! Error: ROOT "+root[:-1]+" is not a directory. Please correct this.\n")
		writemsg("!!! Exiting.\n\n")
		sys.exit(1)

#create tmp and var/tmp if they don't exist; read config
os.umask(0)
if not os.path.exists(root+"tmp"):
	writemsg(">>> "+root+"tmp doesn't exist, creating it...\n")
	os.mkdir(root+"tmp",01777)
if not os.path.exists(root+"var/tmp"):
	writemsg(">>> "+root+"var/tmp doesn't exist, creating it...\n")
	try:
		os.mkdir(root+"var",0755)
	except (OSError,IOError):
		pass
	try:
		os.mkdir(root+"var/tmp",01777)
	except SystemExit, e:
		raise
	except:
		writemsg("portage: couldn't create /var/tmp; exiting.\n")
		sys.exit(1)

os.umask(022)
profiledir=None
if os.path.exists(MAKE_DEFAULTS_FILE):
	profiledir = PROFILE_PATH
	if os.access(DEPRECATED_PROFILE_FILE, os.R_OK):
		deprecatedfile = open(DEPRECATED_PROFILE_FILE, "r")
		dcontent = deprecatedfile.readlines()
		deprecatedfile.close()
		newprofile = dcontent[0]
		writemsg(red("\n!!! Your current profile is deprecated and not supported anymore.\n"))
		writemsg(red("!!! Please upgrade to the following profile if possible:\n"))
		writemsg(8*" "+green(newprofile)+"\n")
		if len(dcontent) > 1:
			writemsg("To upgrade do the following steps:\n")
			for myline in dcontent[1:]:
				writemsg(myline)
			writemsg("\n\n")

db={}

# =============================================================================
# =============================================================================
# -----------------------------------------------------------------------------
# We're going to lock the global config to prevent changes, but we need
# to ensure the global settings are right.
settings=config(config_profile_path=PROFILE_PATH,config_incrementals=incrementals)

# useful info
settings["PORTAGE_MASTER_PID"]=str(os.getpid())
settings.backup_changes("PORTAGE_MASTER_PID")

def do_vartree(mysettings):
	global virts,virts_p
	virts=mysettings.getvirtuals("/")
	virts_p={}

	if virts:
		myvkeys=virts.keys()
		for x in myvkeys:
			vkeysplit=x.split("/")
			if not virts_p.has_key(vkeysplit[1]):
				virts_p[vkeysplit[1]]=virts[x]
	db["/"]={"virtuals":virts,"vartree":vartree("/",virts)}
	if root!="/":
		virts=mysettings.getvirtuals(root)
		db[root]={"virtuals":virts,"vartree":vartree(root,virts)}
	#We need to create the vartree first, then load our settings, and then set up our other trees

# XXX: This is a circular fix.
#do_vartree(settings)
#settings.loadVirtuals('/')
do_vartree(settings)
#settings.loadVirtuals('/')

settings.reset() # XXX: Regenerate use after we get a vartree -- GLOBAL


# XXX: Might cause problems with root="/" assumptions
portdb=portdbapi(settings["PORTDIR"])

settings.lock()
# -----------------------------------------------------------------------------
# =============================================================================
# =============================================================================


if 'selinux' in settings["USE"].split(" "):
	try:
		import selinux
		selinux_enabled=1
		portage_exec.selinux_capable = True
	except OSError, e:
		writemsg(red("!!! SELinux not loaded: ")+str(e)+"\n")
		selinux_enabled=0
	except ImportError:
		writemsg(red("!!! SELinux module not found.")+" Please verify that it was installed.\n")
		selinux_enabled=0
else:
	selinux_enabled=0

cachedirs=[CACHE_PATH]
if root!="/":
	cachedirs.append(root+CACHE_PATH)
if not os.environ.has_key("SANDBOX_ACTIVE"):
	for cachedir in cachedirs:
		if not os.path.exists(cachedir):
			os.makedirs(cachedir,0755)
			writemsg(">>> "+cachedir+" doesn't exist, creating it...\n")
		if not os.path.exists(cachedir+"/dep"):
			os.makedirs(cachedir+"/dep",2755)
			writemsg(">>> "+cachedir+"/dep doesn't exist, creating it...\n")
		try:
			os.chown(cachedir,uid,portage_gid)
			os.chmod(cachedir,0775)
		except OSError:
			pass
		try:
			mystat=os.lstat(cachedir+"/dep")
			os.chown(cachedir+"/dep",uid,portage_gid)
			os.chmod(cachedir+"/dep",02775)
			if mystat[stat.ST_GID]!=portage_gid:
				spawn("chown -R "+str(uid)+":"+str(portage_gid)+" "+cachedir+"/dep",settings,free=1)
				spawn("chmod -R u+rw,g+rw "+cachedir+"/dep",settings,free=1)
		except OSError:
			pass
	
def flushmtimedb(record):
	if mtimedb:
		if record in mtimedb.keys():
			del mtimedb[record]
			#print "mtimedb["+record+"] is cleared."
		else:
			writemsg("Invalid or unset record '"+record+"' in mtimedb.\n")

#grab mtimes for eclasses and upgrades
mtimedb={}
mtimedbkeys=[
"updates", "info",
"version", "starttime",
"resume", "ldpath"
]
mtimedbfile=root+"var/cache/edb/mtimedb"
try:
	mypickle=cPickle.Unpickler(open(mtimedbfile))
	mypickle.find_global=None
	mtimedb=mypickle.load()
	if mtimedb.has_key("old"):
		mtimedb["updates"]=mtimedb["old"]
		del mtimedb["old"]
	if mtimedb.has_key("cur"):
		del mtimedb["cur"]
except SystemExit, e:
	raise
except:
	#print "!!!",e
	mtimedb={"updates":{},"version":"","starttime":0}

for x in mtimedb.keys():
	if x not in mtimedbkeys:
		writemsg("Deleting invalid mtimedb key: "+str(x)+"\n")
		del mtimedb[x]

#,"porttree":portagetree(root,virts),"bintree":binarytree(root,virts)}
features=settings["FEATURES"].split()

do_upgrade_packagesmessage=0
def do_upgrade(mykey):
	global do_upgrade_packagesmessage
	writemsg("\n\n")
	writemsg(green("Performing Global Updates: ")+bold(mykey)+"\n")
	writemsg("(Could take a couple of minutes if you have a lot of binary packages.)\n")
	writemsg("  "+bold(".")+"='update pass'  "+bold("*")+"='binary update'  "+bold("@")+"='/var/db move'\n"+"  "+bold("s")+"='/var/db SLOT move' "+bold("S")+"='binary SLOT move' "+bold("p")+"='update /etc/portage/package.*'\n")
	processed=1
	#remove stale virtual entries (mappings for packages that no longer exist)
	
	myvirts=grabdict("/var/cache/edb/virtuals")
	
	update_files={}
	file_contents={}
	myxfiles = ["package.mask","package.unmask","package.keywords","package.use"]
	myxfiles = myxfiles + prefix_array(myxfiles, "profile/")
	for x in myxfiles:
		try:
			myfile = open("/etc/portage/"+x,"r")
			file_contents[x] = myfile.readlines()
			myfile.close()
		except IOError:
			if file_contents.has_key(x):
				del file_contents[x]
			continue

	worldlist=grabfile("/"+WORLD_FILE)
	myupd=grabfile(mykey)
	db["/"]["bintree"]=binarytree("/",settings["PKGDIR"],virts)
	for myline in myupd:
		mysplit=myline.split()
		if not len(mysplit):
			continue
		if mysplit[0]!="move" and mysplit[0]!="slotmove":
			writemsg("portage: Update type \""+mysplit[0]+"\" not recognized.\n")
			processed=0
			continue
		if mysplit[0]=="move" and len(mysplit)!=3:
			writemsg("portage: Update command \""+myline+"\" invalid; skipping.\n")
			processed=0
			continue
		if mysplit[0]=="slotmove" and len(mysplit)!=4:
			writemsg("portage: Update command \""+myline+"\" invalid; skipping.\n")
			processed=0
			continue
		sys.stdout.write(".")
		sys.stdout.flush()

		if mysplit[0]=="move":
			db["/"]["vartree"].dbapi.move_ent(mysplit)
			db["/"]["bintree"].move_ent(mysplit)
			#update world entries:
			for x in range(0,len(worldlist)):
				#update world entries, if any.
				worldlist[x]=dep_transform(worldlist[x],mysplit[1],mysplit[2])
		
			#update virtuals:
			for myvirt in myvirts.keys():
				for mypos in range(0,len(myvirts[myvirt])):
					if myvirts[myvirt][mypos]==mysplit[1]:
						#update virtual to new name
						myvirts[myvirt][mypos]=mysplit[2]

			#update /etc/portage/packages.*
			for x in file_contents:
				for mypos in range(0,len(file_contents[x])):
					line=file_contents[x][mypos]
					if line[0]=="#" or string.strip(line)=="":
						continue
					key=dep_getkey(line.split()[0])
					if key==mysplit[1]:
						file_contents[x][mypos]=string.replace(line,mysplit[1],mysplit[2])
						update_files[x]=1
						sys.stdout.write("p")
						sys.stdout.flush()

		elif mysplit[0]=="slotmove":
			db["/"]["vartree"].dbapi.move_slot_ent(mysplit)
			db["/"]["bintree"].move_slot_ent(mysplit,settings["PORTAGE_TMPDIR"]+"/tbz2")

	for x in update_files:
		mydblink = dblink('','','/',settings)
		if mydblink.isprotected("/etc/portage/"+x):
			updating_file=new_protect_filename("/etc/portage/"+x)[0]
		else:
			updating_file="/etc/portage/"+x
		try:
			myfile=open(updating_file,"w")
			myfile.writelines(file_contents[x])
			myfile.close()
		except IOError:
			continue

	# We gotta do the brute force updates for these now.
	if (settings["PORTAGE_CALLER"] in ["fixpackages"]) or \
	   ("fixpackages" in features):
		db["/"]["bintree"].update_ents(myupd,settings["PORTAGE_TMPDIR"]+"/tbz2")
	else:
		do_upgrade_packagesmessage = 1
	
	if processed:
		#update our internal mtime since we processed all our directives.
		mtimedb["updates"][mykey]=os.stat(mykey)[stat.ST_MTIME]
	myworld=open("/"+WORLD_FILE,"w")
	for x in worldlist:
		myworld.write(x+"\n")
	myworld.close()
	writedict(myvirts,"/var/cache/edb/virtuals")
	print ""

exit_callbacks = []

def portageexit():
	global uid,portage_gid,portdb,db
	global exit_callbacks
	ebuild.shutdown_all_processors()
	portage_exec.cleanup(portage_exec.spawned_pids)
	for x in exit_callbacks:
		print "calling exit callback",x
		try:
			x()
		except SystemExit:
			raise
		except Exception, e:
			print "caught exception for exit_callback func",x
			print e
			pass

	if secpass and not os.environ.has_key("SANDBOX_ACTIVE"):
		# wait child process death
		try:
			while True:
				os.wait()
		except OSError:
			#writemsg(">>> All child process are now dead.")
			pass

		close_portdbapi_caches()

		if mtimedb:
		# Store mtimedb
			mymfn=mtimedbfile
			try:
				mtimedb["version"]=VERSION
				cPickle.dump(mtimedb,open(mymfn,"w"),cPickle.HIGHEST_PROTOCOL)
				#print "*** Wrote out mtimedb data successfully."
				os.chown(mymfn,uid,portage_gid)
				os.chmod(mymfn,0664)
			except SystemExit, e:
				raise
			except Exception, e:
				pass
			try:
				os.chown(mymfn,-1,portage_gid)
				m=os.umask(0)
				os.chmod(mymfn,0664)
				os.umask(m)
			except (IOError, OSError):
				pass

atexit.register(portageexit)

if (secpass==2) and (not os.environ.has_key("SANDBOX_ACTIVE")):
	if settings["PORTAGE_CALLER"] in ["emerge","fixpackages"]:
		#only do this if we're root and not running repoman/ebuild digest
		updpath=os.path.normpath(settings["PORTDIR"]+"///profiles/updates")
		didupdate=0
		if not mtimedb.has_key("updates"):
			mtimedb["updates"]={}
		try:
			mylist=listdir(updpath,EmptyOnError=1)
			# resort the list
			mylist=[myfile[3:]+"-"+myfile[:2] for myfile in mylist]
			mylist.sort()
			mylist=[myfile[5:]+"-"+myfile[:4] for myfile in mylist]
			for myfile in mylist:
				mykey=updpath+"/"+myfile
				if not os.path.isfile(mykey):
					continue
				if (not mtimedb["updates"].has_key(mykey)) or \
					 (mtimedb["updates"][mykey] != os.stat(mykey)[stat.ST_MTIME]) or \
					 (settings["PORTAGE_CALLER"] == "fixpackages"):
					didupdate=1
					do_upgrade(mykey)
					portageexit() # This lets us save state for C-c.
		except OSError:
			#directory doesn't exist
			pass
		if didupdate:
			#make sure our internal databases are consistent; recreate our virts and vartree
			do_vartree(settings)
			if do_upgrade_packagesmessage and \
				 listdir(settings["PKGDIR"]+"/All/",EmptyOnError=1):
				writemsg("\n\n\n ** Skipping packages. Run 'fixpackages' or set it in FEATURES to fix the")
				writemsg("\n    tbz2's in the packages directory. "+bold("Note: This can take a very long time."))
				writemsg("\n")
		




#continue setting up other trees
db["/"]["porttree"]=portagetree("/",virts)
db["/"]["bintree"]=binarytree("/",settings["PKGDIR"],virts)
if root!="/":
	db[root]["porttree"]=portagetree(root,virts)
	db[root]["bintree"]=binarytree(root,settings["PKGDIR"],virts)
thirdpartymirrors=grabdict(settings["PORTDIR"]+"/profiles/thirdpartymirrors")

if not os.path.exists(settings["PORTAGE_TMPDIR"]):
	writemsg("portage: the directory specified in your PORTAGE_TMPDIR variable, \""+settings["PORTAGE_TMPDIR"]+",\"\n")
	writemsg("does not exist.  Please create this directory or correct your PORTAGE_TMPDIR setting.\n")
	sys.exit(1)
if not os.path.isdir(settings["PORTAGE_TMPDIR"]):
	writemsg("portage: the directory specified in your PORTAGE_TMPDIR variable, \""+settings["PORTAGE_TMPDIR"]+",\"\n")
	writemsg("is not a directory.  Please correct your PORTAGE_TMPDIR setting.\n")
	sys.exit(1)

# COMPATABILITY -- This shouldn't be used.
pkglines = settings.packages

groups=settings["ACCEPT_KEYWORDS"].split()
archlist=[]
for myarch in grabfile(settings["PORTDIR"]+"/profiles/arch.list"):
	archlist += [myarch,"~"+myarch]
for group in groups:
	if not archlist:
		writemsg("--- 'profiles/arch.list' is empty or not available. Empty portage tree?\n")
		break
	elif (group not in archlist) and group[0]!='-':
		writemsg("\n"+red("!!! INVALID ACCEPT_KEYWORDS: ")+str(group)+"\n")

# Clear the cache
dircache={}

fetcher=None
def get_preferred_fetcher():
	"""get the preferred fetcher.  basically an initial check to verify FETCHCOMMAND/RESUMECOMMAND
	are actually usable.
	
	If they aren't, it defaults to complaining for every request for a fetcher, and returning
	transports.bundled_lib.BundledConnection.
	This only checks the command's bin is available- it won't catch wget w/ missing libssl issues.
	That's reserved for fetch at the moment"""

	global fetcher,settings
	usable=True
	if fetcher == None:
		if not (settings.has_key("FETCHCOMMAND") and settings.has_key("RESUMECOMMAND")):
			print red("!!!")+" warning, either FETCHCOMMAND or RESUMECOMMAND aren't defined."
			print red("!!!")+" falling back to the bundled libs.  Please rectify this."
			usable=False
		else:
			f=settings["FETCHCOMMAND"].split()[0]
			r=settings["RESUMECOMMAND"].split()[0]
			usable=((os.path.exists(f) and os.access(f,os.X_OK)) or portage_exec.find_binary(f))
			if usable and r != f:
				usable=((os.path.exists(f) and os.access(f,os.X_OK)) or portage_exec.find_binary(r))

			# note this doesn't check for wget/libssl type issues.  fetch manages that.

		if usable:
			if selinux_enabled:
				selinux_context=selinux.getcontext()
				selinux_context=selinux_context.replace(settings["PORTAGE_T"], \
					settings["PORTAGE_FETCH_T"])
			else:
				selinux_context = None

			fetcher=transports.fetchcommand.CustomConnection(settings,selinux_context=selinux_context)
	if usable:
		return fetcher
	return transports.bundled_lib.BundledConnection()

if not os.path.islink(PROFILE_PATH) and os.path.exists(settings["PORTDIR"]+"/profiles"):
	writemsg(red("\a\n\n!!! "+PROFILE_PATH+" is not a symlink and will probably prevent most merges.\n"))
	writemsg(red("!!! It should point into a profile within %s/profiles/\n" % settings["PORTDIR"]))
	writemsg(red("!!! (You can safely ignore this message when syncing. It's harmless.)\n\n\n"))
	time.sleep(3)

# ============================================================================
# ============================================================================

