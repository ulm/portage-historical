# portage.py -- core Portage functionality 
# Copyright 1998-2002 Daniel Robbins, Gentoo Technologies, Inc.
# Distributed under the GNU Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/portage.py,v 1.269.2.16 2003/02/24 20:34:58 alain Exp $

VERSION="2.1.0_alpha1"

from stat import *
from commands import *
from select import *
from output import *
import string,os,re,types,sys,shlex,shutil,xpak,fcntl,signal,time,missingos,cPickle,atexit,grp,traceback,commands,pwd
import portage_config
import portage_files
import log4py

#
# Definitions for access rights.
#
USER_NORMAL	= 0
USER_WHEEL	= 1
USER_ROOT	= 2


#-----------------------------------------------------------------------------

class PortageContext:
	def __init__(self):
		self.logger = self.get_logger(self)
		self.logger.debug("initializing")

		self.incrementals=["USE","FEATURES","ACCEPT_KEYWORDS","ACCEPT_LICENSE","CONFIG_PROTECT_MASK","CONFIG_PROTECT","PRELINK_PATH","PRELINK_PATH_MASK"]
		self.stickies=["KEYWORDS_ACCEPT","USE","CFLAGS","CXXFLAGS","MAKEOPTS","EXTRA_ECONF","EXTRA_EMAKE"]
		self.db = {}

		# valid end of version components; integers specify offset from release version
		# pre=prerelease, p=patchlevel (should always be followed by an int), rc=release candidate
		# all but _p (where it is required) can be followed by an optional trailing integer
		self.endversion={"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}

		# as there's no reliable way to set {}.keys() order
		# netversion_keys will be used instead of endversion.keys
		# to have fixed search order, so that "pre" is checked
		# before "p"
		self.endversion_keys = ["pre", "p", "alpha", "beta", "rc"]

		# These don't really belong here.  They're part of functions that should be classes/methods.
		self.vcmpcache={}
		self.catcache={}
		self.pkgcache={}
		self.iscache={}
		self.vercache={}
		self.dircache={}

		#
		# Initialize the access rights and find the needed userids and groupids.
		#
		self.initialize_access_rights()

		#
		# Make sure we're in a valid directory.
		#
		getcwd()

		#
		# Grab our start time, used by the eclass code.
		#
		self.starttime=long(time.time())

		#
		# Unless we're in debug mode, initialize the ^C handler.
		#
		if not os.environ.has_key("DEBUG"):
			signal.signal(signal.SIGINT,self.exithandler)

		#
		# Setup our ROOT
		#
		self.setupRoot()

		#
		# Create our tmp and cache directories
		#
		self.create_tmp_directories()
		self.create_cache_directories()

		os.umask(022)


		#
		# Setup our profiledir
		#
		if os.path.exists("/etc/make.profile"):
			self.profiledir = "/etc/make.profile"
		else:
			self.profiledir = None
			print ">>> Note: /etc/make.profile isn't available; an 'emerge sync' will probably fix this."
			self.logger.info("/etc/make.profile isn't available; an 'emerge sync' will probably fix this.")

		#
		# Load the LastModified DB
		#
		self.mtimedb = portage_files.LastModifiedDB(self)

		#
		# Load and initialize default USE values
		#
		self.setupUseDefaults()

		#
		# We need to create the vartree first, then load our settings, and then set up our other trees
		# This method creates virtualmap and virtualpkgmap
		#
		self.do_vartree()

		#
		# Set up our configuration
		#
		self.settings = portage_config.config(self)

		#
		# Apply update files if there's new ones.
		#
		self.handle_updates()

		#
		# Load the portage db
		#
		self.portdb = self.initialize_portdb()

		#
		# Set up other trees
		#
		self.db["/"]["porttree"]=portagetree(self, "/",self.virtualmap)
		self.db["/"]["bintree"]=binarytree(self, "/",self.virtualmap)
		if self.getRoot()!="/":
			self.db[self.getRoot()]["porttree"]=portagetree(self, self.getRoot(),self.virtualmap)
			self.db[self.getRoot()]["bintree"]=binarytree(self, self.getRoot(),self.virtualmap)

		#
		# Initialize list of mirrors.
		#
		self.initialize_mirrors()

		#
		# Initialize feature set
		#
		self.initialize_features()
		
		#
		# Initialize prelink support
		#
		self.initialize_prelink()

		#
		# Initialize the dependancy cache directory
		#
		self.initialize_cachedir()

		#
		# Make sure the tmpdir exists
		#
		self.check_tmpdir()

		#
		# Initialize our categories
		#
		self.initialize_categories()

		#
		# initialize the package masks (from /usr/portage/profiles/packages.mask and /etc/make.profile/packages)
		#
		self.initialize_pkgmasks()

		#
		# Initialize our groups (ACCEPT_KEYWORDS)
		#
		self.initialize_groups()

		self.logger.debug("initialization complete")


	def get_logger(self, classid):
		return log4py.Logger(log4py.TRUE,"/etc/portage/log4py.conf").get_instance(classid)

	def get_incrementals(self):
		return self.incrementals

	def get_profiledir(self):
		return self.profiledir

	def get_usesplit(self):
		return self.settings.get_usesplit()

	def do_vartree(self):
		self.logger.debug("Loading virtual(pkg)map")

		self.virtualmap=self.getvirtuals("/")
		self.virtualpkgmap={}

		if self.virtualmap:
			myvkeys=self.virtualmap.keys()
			for x in myvkeys:
				vkeysplit=x.split("/")
				if not self.virtualpkgmap.has_key(vkeysplit[1]):
					self.virtualpkgmap[vkeysplit[1]]=self.virtualmap[x]
		try:
			del x
		except:
			pass
		self.db["/"]={"virtuals":self.virtualmap,"vartree":vartree(self,"/",self.virtualmap)}
		if self.root!="/":
			self.virtualmap=self.getvirtuals(self.root)
			self.db[self.root]={"virtuals":self.virtualmap,"vartree":vartree(self,self.root,self.virtualmap)}

	def getvirtuals(self, myroot):
		"""gets virtual package settings"""
		myvirts={}
		myvirtfiles=[]
		if self.profiledir:
			myvirtfiles=[self.profiledir+"/virtuals"]
		myvirtfiles.append(myroot+"/var/cache/edb/virtuals")
		for myvirtfn in myvirtfiles:
			if not os.path.exists(myvirtfn):
				continue
			myfile=open(myvirtfn)
			mylines=myfile.readlines()
			for x in mylines:
				mysplit=string.split(x)
				if len(mysplit)<2:
					#invalid line
					continue
				myvirts[mysplit[0]]=mysplit[1]
		return myvirts

	def setupRoot(self):
		if os.environ.has_key("ROOT"):
			self.root=os.environ["ROOT"]
			if not len(self.root):
				self.root="/"
			elif self.root[-1]!="/":
				self.root=self.root+"/"
		else:
			self.root="/"
		if self.root != "/":
			if not os.path.exists(self.root[:-1]):
				self.logger.error("ROOT",self.root[:-1],"does not exist!")
				print "!!! Error: ROOT",self.root[:-1],"does not exist.  Please correct this."
				print "!!! Exiting."
				print
				sys.exit(1)
			elif not os.path.isdir(self.root[:-1]):
				self.logger.error("Root",self.root[:-1],"is not a directory.")
				print "!!! Error: ROOT",self.root[:-1],"is not a directory.  Please correct this."
				print "!!! Exiting."
				print
				sys.exit(1)

	def getRoot(self):
		return self.root

	def setupUseDefaults(self):
		if self.profiledir:
			self.usedefaults=grabfile(self.profiledir+"/use.defaults")
		else:
			self.usedefaults=[]

	def getUseDefaults(self):
		return self.usedefaults

	def key_expand(self, mykey,mydb=None):
		mysplit=mykey.split("/")
		if len(mysplit)==1:
			if mydb and type(mydb)==types.InstanceType:
				for x in self.get_categories():
					if mydb.cp_list(x+"/"+mykey):
						return x+"/"+mykey
				if self.virtualpkgmap.has_key(mykey):
					return(self.virtualpkgmap[mykey])
			return "null/"+mykey
		elif mydb:
			if type(mydb)==types.InstanceType:
				if (not mydb.cp_list(mykey)) and self.virtualmap and self.virtualmap.has_key(mykey):
					return self.virtualmap[mykey]
			return mykey

	def cpv_expand(self, mycpv,mydb=None):
		myslash=mycpv.split("/")
		mysplit=pkgsplit(self, myslash[-1])
		if len(myslash)==2:
			if mysplit:
				mykey=myslash[0]+"/"+mysplit[0]
			else:
				mykey=mycpv
			if mydb:
				if type(mydb)==types.InstanceType:
					if (not mydb.cp_list(mykey)) and self.virtualmap and self.virtualmap.has_key(mykey):
						mykey=self.virtualmap[mykey]
				#we only perform virtual expansion if we are passed a dbapi
		else:
			#specific cpv, no category, ie. "foo-1.0"
			if mysplit:
				myp=mysplit[0]
			else:
				# "foo" ?
				myp=mycpv
			mykey=None
			if mydb:
				for x in self.get_categories():
					if mydb.cp_list(x+"/"+myp):
						mykey=x+"/"+myp
			if not mykey and type(mydb)!=types.ListType:
				if self.virtualpkgmap.has_key(myp):
					mykey=self.virtualpkgmap[myp]
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

	def create_tmp_directories(self):
		"""Create the <root>tmp and <root>var/tmp directories if they don't exists.  Exit
		if creating them fails."""
		os.umask(0)
		if not os.path.exists(self.getRoot()+"tmp"):
			self.logger.info(self.getRoot()+"tmp doesn't exist, creating it...")
			print ">>> "+self.getRoot()+"tmp doesn't exist, creating it..."
			os.mkdir(self.getRoot()+"tmp",01777)
		if not os.path.exists(self.getRoot()+"var/tmp"):
			self.logger.info(self.getRoot()+"var/tmp doesn't exist, creating it...")
			print ">>> "+self.getRoot()+"var/tmp doesn't exist, creating it..."
			try:
				os.mkdir(self.getRoot()+"var",0755)
			except (OSError,IOError):
				pass
			try:
				os.mkdir(self.getRoot()+"var/tmp",01777)
			except:
				self.logger.error("Couldn't create "+self.getRoot()+"var/tmp, exiting...")
				print "portage: couldn't create "+self.getRoot()+"var/tmp; exiting."
				sys.exit(1)

	def create_cache_directories(self):
		cachedirs=["/var/cache/edb"]
		if self.getRoot()!="/":
			cachedirs.append(self.getRoot()+"var/cache/edb")
		if not os.environ.has_key("SANDBOX_ACTIVE"):
			for cachedir in cachedirs:
				if not os.path.exists(cachedir):
					self.logger.info(cachedir,"doesn't exist, creating it...")
					print ">>>",cachedir,"doesn't exist, creating it..."
					os.makedirs(cachedir,0755)
				if not os.path.exists(cachedir+"/dep"):
					self.logger.info(cachedir+"/dep doesn't exist, creating it...")
					print ">>>",cachedir+"/dep","doesn't exist, creating it..."
					os.makedirs(cachedir+"/dep",2755)
				try:
					os.chown(cachedir,self.uid,self.portage_gid)
					os.chmod(cachedir,0775)
				except OSError:
					pass
				try:
					os.chown(cachedir+"/dep",self.uid,self.portage_gid)
					os.chmod(cachedir+"/dep",02775)
				except OSError:
					pass

	def do_update(self, updatefile):
		"""This method takes an update file (e.g. /usr/portage/profiles/updates/4Q-2002),
		and updates the installed packaged in world and virtuals.  This allows packaged
		to be renamed or moved into a different category without Portage losing track
		of them."""

		# Load the world and virtuals files, as well as the file containing the changes
		# to be made.
		myvirts=grabdict("/var/cache/edb/virtuals")
		worldlist=grabfile("/var/cache/edb/world")
		myupd=grabfile(updatefile)

		processed=1

		for myline in myupd:
			mysplit=myline.split()
			if not len(mysplit):
				continue
			if mysplit[0]!="move":
				self.logger.info("do_update() - Update type \""+mysplit[0]+"\" not recognized.")
				print "portage: Update type \""+mysplit[0]+"\" not recognized."
				processed=0
				continue
			if len(mysplit)!=3:
				self.logger.info("do_update() - Update command \""+myline+"\" invalid; skipping.")
				print "portage: Update command \""+myline+"\" invalid; skipping."
				processed=0
				continue
			self.db["/"]["vartree"].dbapi.move_ent(mysplit)

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
	
		# If we processed the file correctly, update the LastModifiedDB, so that we won't
		# try to update it again.
		if processed:
			#update our internal mtime since we processed all our directives.
			self.mtimedb["updates"][updatefile]=os.stat(updatefile)[ST_MTIME]

		# Write out the modified world and virtuals files.
		myworld=open("/var/cache/edb/world","w")
		for x in worldlist:
			myworld.write(x+"\n")
		myworld.close()
		writedict(myvirts,"/var/cache/edb/virtuals")


	def handle_updates(self):
		if (self.secpass==USER_ROOT) and (not os.environ.has_key("SANDBOX_ACTIVE")):
			#only do this if we're root
			updpath=os.path.normpath(self.settings["PORTDIR"]+"/profiles/updates")
			didupdate=0
			try:
				for filename in listdir(self, updpath):
					myfile=updpath+"/"+filename
					if not os.path.isfile(myfile):
						continue
					if (not self.mtimedb["updates"].has_key(myfile)) or (self.mtimedb["updates"][myfile] != os.stat(myfile)[ST_MTIME]):
						didupdate=1
						self.do_update(myfile)
			except OSError:
				#directory doesn't exist
				pass
			if didupdate:
				#make sure our internal databases are consistent; recreate our virts and vartree
				self.do_vartree()


	def initialize_portdb(self):
		"""Load up the portage DB, and add PORTDIR_OVERLAY path to it if it's set and valid."""
		portdb=portdbapi(self)
		if self.settings["PORTDIR_OVERLAY"]:
			if os.path.isdir(self.settings["PORTDIR_OVERLAY"]):
				portdb.oroot=self.settings["PORTDIR_OVERLAY"]
			else:
				print "portage: init: PORTDIR_OVERLAY points to",self.settings["PORTDIR_OVERLAY"],"which isn't a directory. Exiting."
				sys.exit(1)
		return portdb


	def initialize_mirrors(self):
		"""Load and initialize out list of 3rd party mirrors."""
		self.thirdpartymirrors=grabdict(self.settings["PORTDIR"]+"/profiles/thirdpartymirrors")

	def get_mirror_list(self):
		"""Get our mirror list."""
		return self.thirdpartymirrors

	def initialize_features(self):
		"""Initialize the feature set we're using."""
		self.features=self.settings["FEATURES"].split()

	def has_feature(self, name):
		"""Is the named feature enabled?"""
		return (name in self.features)

	def initialize_prelink(self):
		"""Initialize prelink handling.  This checks whether or not this system supports prelinking."""
		self.prelink_capable=0
		if spawn(self, "/usr/sbin/prelink --version > /dev/null 2>&1",free=1) == 0:
			self.prelink_capable=1

	def has_prelink(self):
		"""Does this system support prelinking?  Returns true if it does."""
		return self.prelink_capable

	def initialize_cachedir(self):
		"""Make sure we have a valid PORTAGE_CACHEDIR setting for the dependancy cache."""
		self.dbcachedir=self.settings["PORTAGE_CACHEDIR"]
		if not self.dbcachedir:
			#the auxcache is the only /var/cache/edb/ entry that stays at / even when "root" changes.
			self.dbcachedir="/var/cache/edb/dep/"
			self.settings["PORTAGE_CACHEDIR"]=self.dbcachedir

	def get_cachedir(self):
		"""Get our active dependancy cache dir."""
		return self.dbcachedir

	def check_tmpdir(self):
		"""Check that PORTAGE_TMPDIR exists and is a directory."""
		# FIX: This method should return an error if it doesn't, instead of calling sys.exit(1)!
		if not os.path.exists(self.settings["PORTAGE_TMPDIR"]):
			print "portage: the directory specified in your PORTAGE_TMPDIR variable, \""+self.settings["PORTAGE_TMPDIR"]+",\""
			print "does not exist.  Please create this directory or correct your PORTAGE_TMPDIR setting."
			sys.exit(1)
		if not os.path.isdir(self.settings["PORTAGE_TMPDIR"]):
			print "portage: the directory specified in your PORTAGE_TMPDIR variable, \""+self.settings["PORTAGE_TMPDIR"]+",\""
			print "is not a directory.  Please correct your PORTAGE_TMPDIR setting."
			sys.exit(1)

	def initialize_categories(self):
		"""Retreive the categories that we support."""
		if os.path.exists(self.settings["PORTDIR"]+"/profiles/categories"):
			self.categories=grabfile(self.settings["PORTDIR"]+"/profiles/categories")
		else:
			self.categories=[]

	def get_categories(self):
		"""Get our categories map."""
		return self.categories

	def initialize_pkgmasks(self):
		"""Load and initialize our various package masks.  This includes
		/usr/portage/profiles/packages.mask and /etc/make.profile/packages."""
		pkgmasklines=grabfile(self.settings["PORTDIR"]+"/profiles/package.mask")
		self.maskdict={}
		for x in pkgmasklines:
			mycatpkg=dep_getkey(self, x)
			if not self.maskdict.has_key(mycatpkg):
				self.maskdict[mycatpkg]=[x]
			else:
				self.maskdict[mycatpkg].append(x)
		del pkgmasklines

		if self.get_profiledir():
			pkglines=grabfile(self.get_profiledir()+"/packages")
		else:
			pkglines=[]
		self.revmaskdict={}
		for x in pkglines:
			mycatpkg=dep_getkey(self, x)
			if not self.revmaskdict.has_key(mycatpkg):
				self.revmaskdict[mycatpkg]=[x]
			else:
				self.revmaskdict[mycatpkg].append(x)
		del pkglines

	def get_mask_dict(self):
		"""Returns our package mask dictionary.  (From /usr/portage/profiles/package.mask)"""
		return self.maskdict

	def get_revmask_dict(self):
		"""Returns our profile package mask dictionary.  (From /etc/make.profile/packages)"""
		return self.revmaskdict

	def initialize_groups(self):
		"""Initialize our groups (ACCEPT_KEYWORDS)."""
		self.groups=self.settings["ACCEPT_KEYWORDS"].split()

	def get_groups(self):
		"""Get our groups."""
		return self.groups

	def exithandler(self,foo,bar):
		"""Handles ^C interrupts in a sane manner"""
		#remove temp sandbox files
		#if (self.secpass==2) and ("sandbox" in features):
		#	mypid=os.fork()
		#	if mypid==0:
		#		myargs=[]
		#		mycommand="/usr/lib/portage/bin/testsandbox.sh"
		#		myargs=["testsandbox.sh","0"]
		#		myenv={}
		#		os.execve(mycommand,myargs,myenv)
		#		os._exit(1)
		#		sys.exit(1)
		#	retval=os.waitpid(mypid,0)[1]
		#	if retval==0:
		#		if os.path.exists("/tmp/sandboxpids.tmp"):
		#			os.unlink("/tmp/sandboxpids.tmp")
		if self.mtimedb:
			self.mtimedb.store_db()
		# 0=send to *everybody* in process group
		os.kill(0,signal.SIGKILL)
		sys.exit(1)


	def initialize_access_rights(self):
		"""Find the current users user id, the wheel group id, the portage user and group
		id, and determine what access rights the user has.  Three levels of access rights
		are available: root, user is a member of the wheel group, or normal user."""
		#Secpass will be set to 1 if the user is root or in the portage group.
		self.uid=os.getuid()
		self.secpass=USER_NORMAL
		if self.uid==0:
			self.secpass=USER_ROOT
		try:
			self.wheelgid=grp.getgrnam("wheel")[2]
			if (self.secpass == USER_NORMAL) and (self.wheelgid in os.getgroups()):
				self.secpass=USER_WHEEL
		except KeyError:
			print "portage initialization: your system doesn't have a \"wheel\" group."
			print "Please fix this so that Portage can operate correctly (It's normally GID 10)"
			pass

		#Discover the uid and gid of the portage user/group
		try:
			self.portage_uid=pwd.getpwnam("portage")[2]
			self.portage_gid=grp.getgrnam("portage")[2]
		except KeyError:
			self.portage_uid=0
			self.portage_gid=self.wheelgid
			print
			print   red("portage: 'portage' user or group missing. Please update baselayout")
			print   red("         and merge portage user(250) and group(250) into your passwd")
			print   red("         and group files. Non-root compilation is disabled until then.")
			print       "         Also note that non-root/wheel users will need to be added to"
			print       "         the portage group to do portage commands."
			print
			print       "         For the defaults, line 1 goes into passwd, and 2 into group."
			print green("         portage:x:250:250:portage:/var/tmp/portage:/bin/false")
			print green("         portage::250:portage")
			print

	def get_portage_uid(self):
		"""Get the portage user id."""
		return self.portage_uid

	def get_portage_gid(self):
		"""Get the portage group id."""
		return self.portage_gid

	def get_uid(self):
		"""Get the current users` user id."""
		return self.uid

	def get_wheelgid(self):
		"""Return the WHEEL group id."""
		return self.wheelgid


#-----------------------------------------------------------------------------


def getcwd():
	"this fixes situations where the current directory doesn't exist"
	try:
		return os.getcwd()
	except:
		os.chdir("/")
		return "/"


def abssymlink(symlink):
	"This reads symlinks, resolving the relative symlinks, and returning the absolute."
	mylink=os.readlink(symlink)
	if mylink[0] != '/':
		mydir=os.path.dirname(symlink)
		mylink=mydir+"/"+mylink
	return os.path.normpath(mylink)

def listdir(ctx, path):
	"""List directory contents, using cache. (from dircache module; streamlined by drobbins)
	Exceptions will be propagated to the caller."""
	try:
		cached_mtime, list = ctx.dircache[path]
	except KeyError:
		cached_mtime, list = -1, []
	mtime = os.stat(path)[8]
	if mtime != cached_mtime:
		list = os.listdir(path)
		ctx.dircache[path] = mtime, list
	return list

try:
	import fchksum
	def perform_checksum(ctx, filename, calc_prelink=0):
		if calc_prelink and ctx.has_prelink():
			# Create non-prelinked temporary file to md5sum.
			prelink_tmpfile="/tmp/portage-prelink.tmp"
			try:
				shutil.copy2(filename,prelink_tmpfile)
			except Exception,e:
				print "!!! Unable to copy file '",filename,"'."
				print "!!!",e
				sys.exit(1)
			spawn(ctx, "/usr/sbin/prelink --undo "+prelink_tmpfile+" &>/dev/null", free=1)
			retval = fchksum.fmd5t(prelink_tmpfile)
			os.unlink(prelink_tmpfile)
			return retval
		else:
			return fchksum.fmd5t(filename)
except ImportError:
	import md5
	def perform_checksum(ctx, filename, calc_prelink=0):
		prelink_tmpfile="/tmp/portage-prelink.tmp"
		myfilename=filename
		if calc_prelink and ctx.has_prelink():
			# Create non-prelinked temporary file to md5sum.
			# Raw data is returned on stdout, errors on stderr.
			# Non-prelinks are just returned.
			try:
				shutil.copy2(filename,prelink_tmpfile)
			except Exception,e:
				print "!!! Unable to copy file '",filename,"'."
				print "!!!",e
				sys.exit(1)
			spawn(ctx, "/usr/sbin/prelink --undo "+prelink_tmpfile+" &>/dev/null", free=1)
			myfilename=prelink_tmpfile

		f = open(myfilename, 'rb')
		blocksize=32768
		data = f.read(blocksize)
		size = 0L
		sum = md5.new()
		while data:
			sum.update(data)
			size = size + len(data)
			data = f.read(blocksize)
		f.close()

		if calc_prelink and ctx.has_prelink():
			os.unlink(prelink_tmpfile)
		return (sum.hexdigest(),size)
		#return (md5_to_hex(sum.digest()),size)


def tokenize(mystring):
	"""breaks a string like 'foo? (bar) oni? (blah (blah))'
	into embedded lists; returns None on paren mismatch"""
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
				print "!!! tokenizer: Unmatched left parenthesis in:\n'"+mystring+"'"
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
		print "!!! tokenizer: Exiting with unterminated parenthesis in:\n'"+mystring+"'"
		return None
	return newtokens

def evaluate(mytokens,mydefines,allon=0):
	"""removes tokens based on whether conditional definitions exist or not.
	Recognizes !"""
	pos=0
	if mytokens==None:
		return None
	while pos<len(mytokens):
		if type(mytokens[pos])==types.ListType:
			evaluate(mytokens[pos],mydefines)
			if not len(mytokens[pos]):
				del mytokens[pos]
				continue
		elif mytokens[pos][-1]=="?":
			cur=mytokens[pos][:-1]
			del mytokens[pos]
			if allon:
				if cur[0]=="!":
					del mytokens[pos]
			else:
				if cur[0]=="!":
					if ( cur[1:] in mydefines ) and (pos<len(mytokens)):
						del mytokens[pos]
						continue
				elif ( cur not in mydefines ) and (pos<len(mytokens)):
					del mytokens[pos]
					continue
		pos=pos+1
	return mytokens

def flatten(mytokens):
	"""this function now turns a [1,[2,3]] list into
	a [1,2,3] list and returns it."""
	newlist=[]
	for x in mytokens:
		if type(x)==types.ListType:
			newlist.extend(flatten(x))
		else:
			newlist.append(x)
	return newlist


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

	def allzeros(self):
		"returns all nodes with zero references, or NULL if no such node exists"
		zerolist = []
		for x in self.dict.keys():
			if self.dict[x][0]==0:
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


#parse /etc/env.d and generate /etc/profile.env
def env_update(ctx, makelinks=1):
	if not os.path.exists(ctx.getRoot()+"etc/env.d"):
		prevmask=os.umask(0)
		os.makedirs(ctx.getRoot()+"etc/env.d",0755)
		os.umask(prevmask)
	fns=listdir(ctx, ctx.getRoot()+"etc/env.d")
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

	specials={"KDEDIRS":[],"PATH":[],"CLASSPATH":[],"LDPATH":[],"MANPATH":[],"INFODIR":[],"INFOPATH":[],"ROOTPATH":[],"CONFIG_PROTECT":[],"CONFIG_PROTECT_MASK":[],"PRELINK_PATH":[],"PRELINK_PATH_MASK":[]}
	env={}

	for x in fns:
		# don't process backup files
		if x[-1]=='~' or x[-4:]==".bak":
			continue
		myconfig=ctx.settings.getconfig(ctx.getRoot()+"etc/env.d/"+x)
		if myconfig==None:
			print "!!! Parsing error in",ctx.getRoot()+"etc/env.d/"+x
			#parse error
			continue
		# process PATH, CLASSPATH, LDPATH
		for myspec in specials.keys():
			if myconfig.has_key(myspec):
 				if myspec in ["LDPATH","PATH","PRELINK_PATH","PRELINK_PATH_MASK"]:
					specials[myspec].extend(string.split(ctx.settings.varexpand(myconfig[myspec]),":"))
				else:
					specials[myspec].append(ctx.settings.varexpand(myconfig[myspec]))
				del myconfig[myspec]
		# process all other variables
		for myenv in myconfig.keys():
			env[myenv]=ctx.settings.varexpand(myconfig[myenv])
			
	if os.path.exists(ctx.getRoot()+"etc/ld.so.conf"):
		myld=open(ctx.getRoot()+"etc/ld.so.conf")
		myldlines=myld.readlines()
		myld.close()
		oldld=[]
		for x in myldlines:
			#each line has at least one char (a newline)
			if x[0]=="#":
				continue
			oldld.append(x[:-1])
		oldld.sort()
	#	os.rename(ctx.getRoot()+"etc/ld.so.conf",ctx.getRoot()+"etc/ld.so.conf.bak")
	# Where is the new ld.so.conf generated? (achim)
	else:
		oldld=None
	if (oldld!=specials["LDPATH"]):
		#ld.so.conf needs updating and ldconfig needs to be run
		newld=open(ctx.getRoot()+"etc/ld.so.conf","w")
		newld.write("# ld.so.conf autogenerated by env-update; make all changes to\n")
		newld.write("# contents of /etc/env.d directory\n")
		for x in specials["LDPATH"]:
			newld.write(x+"\n")
		newld.close()

	# Update prelink.conf if we are prelink-enabled
	if ctx.has_prelink():
		newprelink=open(ctx.getRoot()+"etc/prelink.conf","w")
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
		newprelink.close()

	# We can't update links if we haven't cleaned other versions first, as
	# an older package installed ON TOP of a newer version will cause ldconfig
	# to overwrite the symlinks we just made. -X means no links. After 'clean'
	# we can safely create links.
	print ">>> Regenerating "+ctx.getRoot()+"etc/ld.so.cache..."
	if makelinks:
		getstatusoutput("/sbin/ldconfig -r "+ctx.getRoot())
	else:
		getstatusoutput("/sbin/ldconfig -X -r "+ctx.getRoot())
	del specials["LDPATH"]

	penvnotice ="# THIS FILE IS AUTOMATICALLY GENERATED BY env-update.\n"
	penvnotice+="# DO NOT EDIT THIS FILE. CHANGES TO STARTUP PROFILES\n"
	cenvnotice=penvnotice;
	penvnotice+="# GO INTO /etc/profile NOT /etc/profile.env\n\n"
	cenvnotice+="# GO INTO /etc/csh.cshrc NOT /etc/csh.env\n\n"

	#create /etc/profile.env for bash support
	outfile=open(ctx.getRoot()+"/etc/profile.env","w")
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
	outfile=open(ctx.getRoot()+"/etc/csh.env","w")
	outfile.write(cenvnotice)
	
	for path in specials.keys():
		if len(specials[path])==0:
			continue
		outstring="setenv "+path+" '"
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

def grabfile(myfilename):
	"""This function grabs the lines in a file, normalizes whitespace and returns lines in a list; if a line
	begins with a #, it is ignored, as are empty lines"""

	try:
		myfile=open(myfilename,"r")
	except IOError:
		return []
	mylines=myfile.readlines()
	myfile.close()
	newlines=[]
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline=string.join(string.split(x))
		if not len(myline):
			continue
		if myline[0]=="#":
			continue
		newlines.append(myline)
	return newlines

def grabdict(myfilename,juststrings=0):
	"""This function grabs the lines in a file, normalizes whitespace and returns lines in a dictionary"""
	newdict={}
	try:
		myfile=open(myfilename,"r")
	except IOError:
		return newdict 
	mylines=myfile.readlines()
	myfile.close()
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline=string.split(x)
		if len(myline)<2:
			continue
		if juststrings:
			newdict[myline[0]]=string.join(myline[1:])
		else:
			newdict[myline[0]]=myline[1:]
	return newdict

def grabints(myfilename):
	newdict={}
	try:
		myfile=open(myfilename,"r")
	except IOError:
		return newdict 
	mylines=myfile.readlines()
	myfile.close()
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline=string.split(x)
		if len(myline)!=2:
			continue
		newdict[myline[0]]=string.atoi(myline[1])
	return newdict

def writeints(mydict,myfilename):
	try:
		myfile=open(myfilename,"w")
	except IOError:
		return 0
	for x in mydict.keys():
		myfile.write(x+" "+`mydict[x]`+"\n")
	myfile.close()
	return 1

def writedict(mydict,myfilename,writekey=1):
	"""Writes out a dict to a file; writekey=0 mode doesn't write out
	the key and assumes all values are strings, not lists."""
	try:
		myfile=open(myfilename,"w")
	except IOError:
		print "Failed to open file for writedict():",myfilename
		return 0
	if not writekey:
		for x in mydict.values():
			myfile.write(x+"\n")
	else:
		for x in mydict.keys():
			myfile.write(x+" ")
			for y in mydict[x]:
				myfile.write(y+" ")
			myfile.write("\n")
	myfile.close()
	return 1

# returns a tuple.  (version[string], error[string])
# They are pretty much mutually exclusive.
# Either version is a string and error is none, or
# version is None and error is a string
#
def ExtractKernelVersion(base_dir):
	pathname = os.path.join(base_dir, 'include/linux/version.h')
	try:
		lines = open(pathname, 'r').readlines()
	except OSError, details:
		return (None, str(details))
	except IOError, details:
		return (None, str(details))

	lines = map(string.strip, lines)

	version = ''

	for line in lines:
		items = string.split(line, ' ', 2)
		if items[0] == '#define' and \
			items[1] == 'UTS_RELEASE':
			version = items[2] # - may be wrapped in quotes
		break

	if version == '':
		return (None, "Unable to locate UTS_RELEASE in %s" % (pathname))

	if version[0] == '"' and version[-1] == '"':
		version = version[1:-1]
	return (version,None)

def spawn(ctx, mystring,debug=0,free=0,droppriv=0):
	"""spawn a subprocess with optional sandbox protection, 
	depending on whether sandbox is enabled.  The "free" argument,
	when set to 1, will disable sandboxing.  This allows us to 
	spawn processes that are supposed to modify files outside of the
	sandbox.  We can't use os.system anymore because it messes up
	signal handling.  Using spawn allows our Portage signal handler
	to work."""

	# useful if an ebuild or so needs to get the pid of our python process
	ctx.settings["PORTAGE_MASTER_PID"]=str(os.getpid())
	droppriv=(droppriv and (ctx.has_feature("userpriv")))
	
	mypid=os.fork()
	if mypid==0:
		myargs=[]
		if droppriv and ctx.get_portage_gid() and ctx.get_portage_uid():
			#drop root privileges, become the 'portage' user
			os.setgid(ctx.get_portage_gid())
			os.setuid(ctx.get_portage_uid())
			os.umask(002)
		else:
			if droppriv:
				print "portage: Unable to drop root for",mystring
 		ctx.settings["BASH_ENV"]="/etc/portage/bashrc"

		if ctx.has_feature("sandbox") and (not free):
			mycommand="/usr/lib/portage/bin/sandbox"
			myargs=["["+ctx.settings["PF"]+"] sandbox",mystring]
		else:
			mycommand="/bin/bash"
			if debug:
				myargs=["["+ctx.settings["PF"]+"] bash","-x","-c",mystring]
			else:
				myargs=["["+ctx.settings["PF"]+"] bash","-c",mystring]

		os.execve(mycommand,myargs,ctx.settings.environ())
		# If the execve fails, we need to report it, and exit
		# *carefully* --- report error here
		os._exit(1)
		sys.exit(1)
		return # should never get reached
	retval=os.waitpid(mypid,0)[1]
	if (retval & 0xff)==0:
		#return exit code
		return (retval >> 8)
	else:
		#interrupted by signal
		return 16

def fetch(ctx, myuris, listonly=0):
	"fetch files.  Will use digest file if available."
	if ctx.has_feature("mirror") and ("nomirror" in ctx.settings["RESTRICT"].split()):
		print ">>> \"mirror\" mode and \"nomirror\" restriction enabled; skipping fetch."
		return 1
	mymirrors=ctx.settings["GENTOO_MIRRORS"].split()
	fetchcommand=ctx.settings["FETCHCOMMAND"]
	resumecommand=ctx.settings["RESUMECOMMAND"]
	fetchcommand=string.replace(fetchcommand,"${DISTDIR}",ctx.settings["DISTDIR"])
	resumecommand=string.replace(resumecommand,"${DISTDIR}",ctx.settings["DISTDIR"])
	mydigests=None
	digestfn=ctx.settings["FILESDIR"]+"/digest-"+ctx.settings["PF"]
	if os.path.exists(digestfn):
		myfile=open(digestfn,"r")
		mylines=myfile.readlines()
		mydigests={}
		for x in mylines:
			myline=string.split(x)
			if len(myline)<4:
				#invalid line
				print "!!! The digest",digestfn,"appears to be corrupt.  Aborting."
				return 0
			try:
				mydigests[myline[2]]={"md5":myline[1],"size":string.atol(myline[3])}
			except ValueError:
				print "!!! The digest",digestfn,"appears to be corrupt.  Aborting."
	if "fetch" in ctx.settings["RESTRICT"].split():
		# fetch is restricted.	Ensure all files have already been downloaded; otherwise,
		# print message and exit.
		gotit=1
		for myuri in myuris:
			myfile=os.path.basename(myuri)
			try:
				mystat=os.stat(ctx.settings["DISTDIR"]+"/"+myfile)
			except (OSError,IOError),e:
				# file does not exist
				print "!!!",myfile,"not found in",ctx.settings["DISTDIR"]+"."
				gotit=0
		if not gotit:
			print
			print "!!!",ctx.settings["CATEGORY"]+"/"+ctx.settings["PF"],"has fetch restriction turned on."
			print "!!! This probably means that this ebuild's files must be downloaded"
			print "!!! manually.  See the comments in the ebuild for more information."
			print
			spawn(ctx, "/usr/sbin/ebuild.sh nofetch")
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
				if ctx.get_mirror_list().has_key(mirrorname):
					for locmirr in ctx.get_mirror_list()[mirrorname]:
						filedict[myfile].append(locmirr+"/"+myuri[eidx+1:])		
		else:
				filedict[myfile].append(myuri)
	for myfile in filedict.keys():
		if listonly:
			fetched=0
			print ""
		for loc in filedict[myfile]:
			if listonly:
				print loc+" ",
				continue
			try:
				mystat=os.stat(ctx.settings["DISTDIR"]+"/"+myfile)
				if mydigests!=None and mydigests.has_key(myfile):
					#if we have the digest file, we know the final size and can resume the download.
					if mystat[ST_SIZE]<mydigests[myfile]["size"]:
						fetched=1
					else:
						#we already have it downloaded, skip.
						#if our file is bigger than the recorded size, digestcheck should catch it.
						fetched=2
				else:
					#we don't have the digest file, but the file exists.  Assume it is fully downloaded.
					fetched=2
			except (OSError,IOError),e:
				fetched=0
			if fetched!=2:
				#we either need to resume or start the download
				#you can't use "continue" when you're inside a "try" block
				if fetched==1:
					#resume mode:
					print ">>> Resuming download..."
					locfetch=resumecommand
				else:
					#normal mode:
					locfetch=fetchcommand
				print ">>> Downloading",loc
				myfetch=string.replace(locfetch,"${URI}",loc)
				myfetch=string.replace(myfetch,"${FILE}",myfile)
				myret=spawn(ctx, myfetch,free=1)
				if mydigests!=None and mydigests.has_key(myfile):
					try:
						mystat=os.stat(ctx.settings["DISTDIR"]+"/"+myfile)
						# no exception?  file exists. let digestcheck() report
						# an appropriately for size or md5 errors
						if myret and (mystat[ST_SIZE]<mydigests[myfile]["size"]):
							# Fetch failed... Try the next one... Kill 404 files though.
							if (mystat[ST_SIZE]<100000) and (len(myfile)>4) and not ((myfile[-5:]==".html") or (myfile[-4:]==".htm")):
								html404=re.compile("<title>.*(not found|404).*</title>",re.I|re.M)
								try:
									if html404.search(open(ctx.settings["DISTDIR"]+"/"+myfile).read()):
										try:
											os.unlink(ctx.settings["DISTDIR"]+"/"+myfile)
											print ">>> Deleting invalid distfile. (Improper 404 redirect from server.)"
										except:
											pass
								except:
									pass
							continue
						fetched=2
						break
					except (OSError,IOError),e:
						fetched=0
				else:
					if not myret:
						fetched=2
						break
		if (fetched!=2) and not listonly:
			print '!!! Couldn\'t download',myfile+". Aborting."
			return 0
	return 1

def digestgen(ctx, myarchives,overwrite=1):
	"""generates digest file if missing.  Assumes all files are available.	If
	overwrite=0, the digest will only be created if it doesn't already exist."""
	if not os.path.isdir(ctx.settings["FILESDIR"]):
		os.makedirs(ctx.settings["FILESDIR"])
		if ctx.has_feature("cvs"):
			print ">>> Auto-adding files/ dir to CVS..."
			spawn(ctx, "cd "+ctx.settings["O"]+"; cvs add files",free=1)
	myoutfn=ctx.settings["FILESDIR"]+"/.digest-"+ctx.settings["PF"]
	myoutfn2=ctx.settings["FILESDIR"]+"/digest-"+ctx.settings["PF"]
	if (not overwrite) and os.path.exists(myoutfn2):
		return
	print ">>> Generating digest file..."

	try:
		outfile=open(myoutfn,"w")
	except IOError, e:
		print "!!! Filesystem error skipping generation. (Read-Only?)"
		print "!!! "+str(e)
		return
	
	for x in myarchives:
		myfile=ctx.settings["DISTDIR"]+"/"+x
		mymd5=perform_md5(ctx, myfile)
		mysize=os.stat(myfile)[ST_SIZE]
		#The [:-1] on the following line is to remove the trailing "L"
		outfile.write("MD5 "+mymd5+" "+x+" "+`mysize`[:-1]+"\n")	
	outfile.close()
	if not movefile(myoutfn,myoutfn2):
		print "!!! Failed to move digest."
		sys.exit(1)
	if ctx.has_feature("cvs"):
		print ">>> Auto-adding digest file to CVS..."
		spawn(ctx, "cd "+ctx.settings["FILESDIR"]+"; cvs add digest-"+ctx.settings["PF"],free=1)
	print ">>> Computed message digests."
	
def digestcheck(ctx, myarchives):
	"Checks md5sums.  Assumes all files have been downloaded."
	if not myarchives:
		#No archives required; don't expect a digest
		return 1
	digestfn=ctx.settings["FILESDIR"]+"/digest-"+ctx.settings["PF"]
	if not os.path.exists(digestfn):
		if ctx.has_feature("digest"):
			print ">>> No message digest file found:",digestfn
			print ">>> \"digest\" mode enabled; auto-generating new digest..."
			digestgen(ctx, myarchives)
			return 1
		else:
			print "!!! No message digest file found:",digestfn
			print "!!! Type \"ebuild foo.ebuild digest\" to generate a digest."
			return 0
	myfile=open(digestfn,"r")
	mylines=myfile.readlines()
	mydigests={}
	for x in mylines:
		myline=string.split(x)
		if len(myline)<2:
			#invalid line
			continue
		mydigests[myline[2]]=[myline[1],myline[3]]
	for x in myarchives:
		if not mydigests.has_key(x):
			if ctx.has_feature("digest"):
				print ">>> No message digest entry found for archive \""+x+".\""
				print ">>> \"digest\" mode enabled; auto-generating new digest..."
				digestgen(ctx, myarchives)
				return 1
			else:
				print ">>> No message digest entry found for archive \""+x+".\""
				print "!!! Most likely a temporary problem. Try 'emerge rsync' again later."
				print "!!! If you are certain of the authenticity of the file then you may type"
				print "!!! the following to generate a new digest:"
				print "!!!   ebuild /usr/portage/category/package/package-version.ebuild digest" 
				return 0
		mymd5=perform_md5(ctx, ctx.settings["DISTDIR"]+"/"+x)
		if mymd5 != mydigests[x][0]:
			print
			print "!!!",x+": message digests do not match!"
			print "!!!",x,"is corrupt or incomplete."
			print ">>> our recorded digest:",mydigests[x][0]
			print ">>>  your file's digest:",mymd5
			print ">>> Please delete",ctx.settings["DISTDIR"]+"/"+x,"and refetch."
			print
			return 0
		else:
			print ">>> md5 ;-)",x
	return 1

# parse actionmap to spawn ebuild with the appropriate args
def spawnebuild(ctx, mydo,actionmap,debug,alwaysdep=0):
	if alwaysdep or (not ctx.has_feature("noauto")):
		# process dependency first
		if "dep" in actionmap[mydo].keys():
			retval=spawnebuild(ctx, actionmap[mydo]["dep"],actionmap,debug,alwaysdep)
			if retval:
				return retval
	# spawn ebuild.sh
	mycommand="/usr/sbin/ebuild.sh "
	return spawn(ctx, mycommand + mydo,debug,
				actionmap[mydo]["args"][0],
				actionmap[mydo]["args"][1]
	)

# "checkdeps" support has been deprecated.  Relying on emerge to handle it.
def doebuild(ctx, myebuild,mydo,myroot,debug=0,listonly=0):

	if mydo not in ["help","clean","prerm","postrm","preinst","postinst","config","touch","setup",
	                "depend","fetch","digest","unpack","compile","install","rpm","qmerge","merge","package"]:
		print "!!! Please specify a valid command."
		return 1
	if not os.path.exists(myebuild):
		print "!!! doebuild:",myebuild,"not found."
		return 1
	if myebuild[-7:]!=".ebuild":
		print "!!! doebuild: ",myebuild,"does not appear to be an ebuild file."
		return 1

	ctx.settings.reset()
	ctx.settings["PORTAGE_DEBUG"]=str(debug)
	#ctx.settings["ROOT"]=ctx.getRoot()
	ctx.settings["ROOT"]=myroot
	ctx.settings["STARTDIR"]=getcwd()
	ctx.settings["EBUILD"]=os.path.abspath(myebuild)
	ctx.settings["O"]=os.path.dirname(ctx.settings["EBUILD"])
	category=ctx.settings["CATEGORY"]=os.path.basename(os.path.normpath(ctx.settings["O"]+"/.."))
	#PEBUILD
	ctx.settings["FILESDIR"]=ctx.settings["O"]+"/files"
	pf=ctx.settings["PF"]=os.path.basename(ctx.settings["EBUILD"])[:-7]
	mykey=category+"/"+pf
	ctx.settings["ECLASSDIR"]=ctx.settings["PORTDIR"]+"/eclass"
	ctx.settings["SANDBOX_LOG"]=ctx.settings["PF"]
	mysplit=pkgsplit(ctx, ctx.settings["PF"],0)
	if mysplit==None:
		print "!!! Error: PF is null; exiting."
		return 1
	ctx.settings["P"]=mysplit[0]+"-"+mysplit[1]
	ctx.settings["PN"]=mysplit[0]
	ctx.settings["PV"]=mysplit[1]
	ctx.settings["PR"]=mysplit[2]
	if mysplit[2]=="r0":
		ctx.settings["PVR"]=mysplit[1]
	else:
		ctx.settings["PVR"]=mysplit[1]+"-"+mysplit[2]
	ctx.settings["SLOT"]=""
	if ctx.settings.has_key("PATH"):
		mysplit=string.split(ctx.settings["PATH"],":")
	else:
		mysplit=[]
	if not "/usr/lib/portage/bin" in mysplit:
		ctx.settings["PATH"]="/usr/lib/portage/bin:"+ctx.settings["PATH"]

	ctx.settings["BUILD_PREFIX"]=ctx.settings["PORTAGE_TMPDIR"]+"/portage"
	ctx.settings["PKG_TMPDIR"]=ctx.settings["PORTAGE_TMPDIR"]+"/portage-pkg"
	ctx.settings["BUILDDIR"]=ctx.settings["BUILD_PREFIX"]+"/"+ctx.settings["PF"]

	#set up KV variable -- DEP SPEEDUP :: Don't waste time. Keep var persistent.
	if (mydo!="depend") or not ctx.settings.has_key("KV"):
		mykv,err1=ExtractKernelVersion(ctx.getRoot()+"usr/src/linux")
		if mykv:
			# Regular source tree
			ctx.settings["KV"]=mykv
		else:
			ctx.settings["KV"]=""

	if (mydo!="depend") or not ctx.settings.has_key("KVERS"):
		myso=getstatusoutput("uname -r")
		ctx.settings["KVERS"]=myso[1]

	try:
		if ctx.has_feature("userpriv") and ctx.get_portage_uid() and ctx.get_portage_gid():
			ctx.settings["HOME"]=ctx.settings["BUILD_PREFIX"]+"/homedir"
			if os.path.exists(ctx.settings["HOME"]):
				spawn(ctx, "rm -Rf "+ctx.settings["HOME"], free=1)
			if not os.path.exists(ctx.settings["HOME"]):
				os.makedirs(ctx.settings["HOME"])
		elif ctx.has_feature("userpriv"):
			del ctx.features[ctx.features.index("userpriv")]
	except Exception, e:
		print "!!! Couldn't empty HOME:",settings["HOME"]
		print "!!!",e

	# get possible slot information from the deps file
	if mydo=="depend":
		myso=getstatusoutput("/usr/sbin/ebuild.sh depend")
		if debug:
			print myso[1]
		return myso[0]

	try:
		# no reason to check for depend since depend returns above.
		if not os.path.exists(ctx.settings["BUILD_PREFIX"]):
			os.makedirs(ctx.settings["BUILD_PREFIX"])
		os.chown(ctx.settings["BUILD_PREFIX"],ctx.get_portage_uid(),ctx.get_portage_gid())
		if not os.path.exists(ctx.settings["BUILDDIR"]):
			os.makedirs(ctx.settings["BUILDDIR"])
		os.chown(ctx.settings["BUILDDIR"],ctx.get_portage_uid(),ctx.get_portage_gid())

		# Should be ok again to set $T, as sandbox do not depend on it
		ctx.settings["T"]=ctx.settings["BUILDDIR"]+"/temp"
		if not os.path.exists(ctx.settings["T"]):
			os.makedirs(ctx.settings["T"])
		os.chown(ctx.settings["T"],ctx.get_portage_uid(),ctx.get_portage_gid())
		os.chmod(ctx.settings["T"],06770)

		if (ctx.has_feature("userpriv")) and (ctx.has_feature("ccache")):
			if (not ctx.settings.has_key("CCACHE_DIR")) or (ctx.settings["CCACHE_DIR"]==""):
				ctx.settings["CCACHE_DIR"]=ctx.settings["PORTAGE_TMPDIR"]+"/ccache"
			if not os.path.exists(ctx.settings["CCACHE_DIR"]):
				os.makedirs(ctx.settings["CCACHE_DIR"])
				os.chown(ctx.settings["CCACHE_DIR"],ctx.get_portage_uid(),ctx.get_portage_gid())
			os.chmod(ctx.settings["CCACHE_DIR"],06770)

			if not os.path.exists(ctx.settings["HOME"]):
				os.makedirs(ctx.settings["HOME"])
			os.chown(ctx.settings["HOME"],ctx.get_portage_uid(),ctx.get_portage_gid())
			os.chmod(ctx.settings["HOME"],06770)
	except OSError, e:
		print "!!! File system problem. (ReadOnly? Out of space?)"
		print "!!! Perhaps: rm -Rf",ctx.settings["BUILD_PREFIX"]
		print "!!!",str(e)
		return 1

	ctx.settings["WORKDIR"]=ctx.settings["BUILDDIR"]+"/work"
	ctx.settings["D"]=ctx.settings["BUILDDIR"]+"/image/"

	if mydo=="unmerge": 
		return unmerge(ctx, ctx.settings["CATEGORY"],ctx.settings["PF"],ctx.getRoot())

	if ctx.settings.has_key("PORT_LOGDIR"):
		if os.access(ctx.settings["PORT_LOGDIR"]+"/",os.W_OK):
			try:
				os.chown(ctx.settings["BUILD_PREFIX"],ctx.get_portage_uid(),ctx.get_portage_gid())
				os.chmod(ctx.settings["PORT_LOGDIR"],06770)
				if not ctx.settings.has_key("LOG_PF") or (ctx.settings["LOG_PF"] != ctx.settings["PF"]):
					ctx.settings["LOG_COUNTER"]=str(counter_tick_core("/"))
			except Exception, e:
				ctx.settings["PORT_LOGDIR"]=""
				print "!!! Unable to chown/chmod PORT_LOGDIR. Disabling logging."
				print "!!!",e
		else:
			print "!!! Cannot create log... No write access / Does not exist"
			print "!!! PORT_LOGDIR:",ctx.settings["PORT_LOGDIR"]
			ctx.settings["PORT_LOGDIR"]=""
	
	# if any of these are being called, handle them -- running them out of the sandbox -- and stop now.
	if mydo in ["help","clean","setup","prerm","postrm","preinst","postinst","config"]:
		return spawn(ctx, "/usr/sbin/ebuild.sh "+mydo,debug,free=1)
	
	try: 
		ctx.settings["SLOT"], ctx.settings["RESTRICT"], myuris = ctx.db["/"]["porttree"].dbapi.aux_get(mykey,["SLOT","RESTRICT","SRC_URI"])
	except (IOError,KeyError):
		print red("doebuild():")+" aux_get() error; aborting."
		sys.exit(1)
	newuris=flatten(evaluate(tokenize(myuris),string.split(ctx.settings["USE"])))	
	alluris=flatten(evaluate(tokenize(myuris),[],1))	
	alist=[]
	aalist=[]
	#uri processing list
	upl=[[newuris,alist],[alluris,aalist]]
	for myl in upl:
		for x in myl[0]:
			mya=os.path.basename(x)
			if not mya in myl[1]:
				myl[1].append(mya)
	ctx.settings["A"]=string.join(alist," ")
	ctx.settings["AA"]=string.join(aalist," ")
	if ctx.has_feature("cvs") or ctx.has_feature("mirror"):
		fetchme=alluris
		checkme=aalist
	else:
		fetchme=newuris
		checkme=alist

	if not fetch(ctx, fetchme, listonly):
		return 1

	if mydo=="fetch":
		return 0

	if ctx.has_feature("digest"):
		#generate digest if it doesn't exist.
		if mydo=="digest":
			digestgen(ctx, checkme,overwrite=1)
			return 0
		else:
			digestgen(ctx, checkme,overwrite=0)
	elif mydo=="digest":
		#since we are calling "digest" directly, recreate the digest even if it already exists
		digestgen(ctx, checkme,overwrite=1)
		return 0
		
	if not digestcheck(ctx, checkme):
		return 1
	
	#initial dep checks complete; time to process main commands

	nosandbox=(not ctx.has_feature("usersandbox"))
	actionmap={
			  "setup": {                 "args":(1,0)},         # without  / root
			 "unpack": {"dep":"setup",   "args":(0,1)},         # sandbox  / portage
			"compile": {"dep":"unpack",  "args":(nosandbox,1)}, # optional / portage
			"install": {"dep":"compile", "args":(0,0)},         # sandbox  / root
			    "rpm": {"dep":"install", "args":(0,0)},         # sandbox  / root
		    	"package": {"dep":"install", "args":(0,0)},         # sandbox  / root
	}

	if mydo in actionmap.keys():
		if mydo=="package":
			for x in ["","/"+ctx.settings["CATEGORY"],"/All"]:
				if not os.path.exists(ctx.settings["PKGDIR"]+x):
					os.makedirs(ctx.settings["PKGDIR"]+x)
		# REBUILD CODE FOR TBZ2 --- XXXX
		return spawnebuild(ctx, mydo,actionmap,debug)
	elif mydo=="qmerge": 
		#qmerge is specifically not supposed to do a runtime dep check
		return merge(ctx, ctx.settings["CATEGORY"],ctx.settings["PF"],ctx.settings["D"],ctx.settings["BUILDDIR"]+"/build-info",myroot)
	elif mydo=="merge":
		retval=spawnebuild(ctx, "install",actionmap,debug,1)
		if retval: return retval
		return merge(ctx, ctx.settings["CATEGORY"],ctx.settings["PF"],ctx.settings["D"],ctx.settings["BUILDDIR"]+"/build-info",myroot,myebuild=ctx.settings["EBUILD"])
	else:
		print "!!! Unknown mydo:",mydo
		sys.exit(1)


def movefile(src,dest,newmtime=None,sstat=None):
	"""moves a file from src to dest, preserving all permissions and attributes; mtime will
	be preserved even when moving across filesystems.  Returns true on success and false on
	failure.  Move is atomic."""
	#print "movefile("+src+","+dest+","+str(newmtime)+","+str(sstat)+")"
	try:
		if not sstat:
			sstat=os.lstat(src)
	except Exception, e:
		print "!!! Stating source file failed... movefile()"
		print "!!!",e
		return None

	destexists=1
	try:
		dstat=os.lstat(dest)
	except:
		dstat=os.lstat(os.path.dirname(dest))
		destexists=0

	if destexists:
		if S_ISLNK(dstat[ST_MODE]):
			try:
				os.unlink(dest)
				destexists=0
			except Exception, e:
				pass

	if S_ISLNK(sstat[ST_MODE]):
		try:
			target=os.readlink(src)
			if destexists and not S_ISDIR(dstat[ST_MODE]):
				os.unlink(dest)
			os.symlink(target,dest)
			missingos.lchown(dest,sstat[ST_UID],sstat[ST_GID])
			return os.lstat(dest)
		except Exception, e:
			print "!!! failed to properly create symlink:"
			print "!!!",dest,"->",target
			print "!!!",e
			return None

	renamefailed=1
	if sstat[ST_DEV]==dstat[ST_DEV]:
		try:
			ret=os.rename(src,dest)
			renamefailed=0
		except Exception, e:
			import errno
			if e[0]!=errno.EXDEV:
				# Some random error.
				print "!!! Failed to move",src,"to",dest
				print "!!!",e
				return None
			# Invalid cross-device-link 'bind' mounted or actually Cross-Device

	if renamefailed:
		didcopy=0
		if S_ISREG(sstat[ST_MODE]):
			try: # For safety copy then move it over.
				shutil.copyfile(src,dest+"#new")
				os.rename(dest+"#new",dest)
				didcopy=1
			except Exception, e:
				print '!!! copy',src,'->',dest,'failed.'
				print "!!!",e
				return None
		else:
			#we don't yet handle special, so we need to fall back to /bin/mv
			a=getstatusoutput("/bin/mv -f "+"'"+src+"' '"+dest+"'")
			if a[0]!=0:
				print "!!! Failed to move special file:"
				print "!!! '"+src+"' to '"+dest+"'"
				print "!!!",a
				return None # failure
		try:
			if didcopy:
				missingos.lchown(dest,sstat[ST_UID],sstat[ST_GID])
				os.chmod(dest, S_IMODE(sstat[ST_MODE])) # Sticky is reset on chown
				os.unlink(src)
		except Exception, e:
			print "!!! Failed to chown/chmod/unlink in movefile()"
			print "!!!",dest
			print "!!!",e
			return None

	if newmtime:
		os.utime(dest,(newmtime,newmtime))
	else:
		os.utime(dest, (sstat[ST_ATIME], sstat[ST_MTIME]))
		newmtime=sstat[ST_MTIME]
	return newmtime

def perform_md5(ctx, x, calc_prelink=0):
	return perform_checksum(ctx, x, calc_prelink)[0]

def merge(ctx, mycat,mypkg,pkgloc,infloc,myroot,myebuild=None):
	mylink=dblink(ctx, mycat,mypkg,myroot)
	if not mylink.exists():
		mylink.create()
		#shell error code
	return mylink.merge(pkgloc,infloc,myroot,myebuild)
	
def unmerge(ctx, cat,pkg,myroot):
	mylink=dblink(ctx, cat,pkg,myroot)
	if mylink.exists():
		mylink.unmerge()
	mylink.delete()

def relparse(ctx, myver):
	"converts last version part into three components"
	number=0
	p1=0
	p2=0
	mynewver=string.split(myver,"_")
	if len(mynewver)==2:
		#an endversion
		number=string.atof(mynewver[0])
		match=0
		for x in ctx.endversion_keys:
			elen=len(x)
			if mynewver[1][:elen] == x:
				match=1
				p1=ctx.endversion[x]
				try:
					p2=string.atof(mynewver[1][elen:])
				except:
					p2=0
				break
		if not match:	
			#normal number or number with letter at end
			divider=len(myver)-1
			if myver[divider:] not in "1234567890":
				#letter at end
				p1=ord(myver[divider:])
				number=string.atof(myver[0:divider])
			else:
				number=string.atof(myver)		
	else:
		#normal number or number with letter at end
		divider=len(myver)-1
		if myver[divider:] not in "1234567890":
			#letter at end
			p1=ord(myver[divider:])
			number=string.atof(myver[0:divider])
		else:
			number=string.atof(myver)  
	return [number,p1,p2]


#returns 1 if valid version string, else 0
# valid string in format: <v1>.<v2>...<vx>[a-z,_{endversion}[vy]]
# ververify doesn't do package rev.
def ververify(ctx, myorigval,silent=1):	
	try:
		return ctx.vercache[myorigval]
	except KeyError:
		pass
	if len(myorigval)==0:
		if not silent:
			print "!!! Name error: package contains empty \"-\" part."
		return 0
	myval=string.split(myorigval,'.')
	if len(myval)==0:
		if not silent:
			print "!!! Name error: empty version string."
		ctx.vercache[myorigval]=0
		return 0
	#all but the last version must be a numeric
	for x in myval[:-1]:
		if not len(x):
			if not silent:
				print "!!! Name error in",myorigval+": two decimal points in a row"
			ctx.vercache[myorigval]=0
			return 0
		try:
			foo=string.atoi(x)
		except:
			if not silent:
				print "!!! Name error in",myorigval+": \""+x+"\" is not a valid version component."
			ctx.vercache[myorigval]=0
			return 0
	if not len(myval[-1]):
			if not silent:
				print "!!! Name error in",myorigval+": two decimal points in a row"
			ctx.vercache[myorigval]=0
			return 0
	try:
		foo=string.atoi(myval[-1])
		ctx.vercache[myorigval]=1
		return 1
	except:
		pass
	#ok, our last component is not a plain number or blank, let's continue
	if myval[-1][-1] in string.lowercase:
		try:
			foo=string.atoi(myval[-1][:-1])
			return 1
			ctx.vercache[myorigval]=1
			# 1a, 2.0b, etc.
		except:
			pass
	#ok, maybe we have a 1_alpha or 1_beta2; let's see
	#ep="endpart"
	ep=string.split(myval[-1],"_")
	if len(ep)!=2:
		if not silent:
			print "!!! Name error in",myorigval
		ctx.vercache[myorigval]=0
		return 0
	try:
		foo=string.atoi(ep[0])
	except:
		#this needs to be numeric, i.e. the "1" in "1_alpha"
		if not silent:
			print "!!! Name error in",myorigval+": characters before _ must be numeric"
		ctx.vercache[myorigval]=0
		return 0
	for mye in ctx.endversion_keys:
		if ep[1][0:len(mye)]==mye:
			if len(mye)==len(ep[1]):
				#no trailing numeric; ok
				ctx.vercache[myorigval]=1
				return 1
			else:
				try:
					foo=string.atoi(ep[1][len(mye):])
					ctx.vercache[myorigval]=1
					return 1
				except:
					#if no endversions work, *then* we return 0
					pass	
	if not silent:
		print "!!! Name error in",myorigval
	ctx.vercache[myorigval]=0
	return 0

def isjustname(ctx, mypkg):
	myparts=string.split(mypkg,'-')
	for x in myparts:
		if ververify(ctx, x):
			return 0
	return 1

def isspecific(ctx, mypkg):
	"now supports packages with no category"
	try:
		return ctx.iscache[mypkg]
	except:
		pass
	mysplit=string.split(mypkg,"/")
	if not isjustname(ctx, mysplit[-1]):
			ctx.iscache[mypkg]=1
			return 1
	ctx.iscache[mypkg]=0
	return 0


# This function can be used as a package verification function, i.e.
# "pkgsplit("foo-1.2-1") will return None if foo-1.2-1 isn't a valid
# package (with version) name.	If it is a valid name, pkgsplit will
# return a list containing: [ pkgname, pkgversion(norev), pkgrev ].
# For foo-1.2-1, this list would be [ "foo", "1.2", "1" ].  For 
# Mesa-3.0, this list would be [ "Mesa", "3.0", "0" ].
def pkgsplit(ctx, mypkg,silent=1):
	try:
		return ctx.pkgcache[mypkg]
	except KeyError:
		pass
	myparts=string.split(mypkg,'-')
	if len(myparts)<2:
		if not silent:
			print "!!! Name error in",mypkg+": missing a version or name part." 
		ctx.pkgcache[mypkg]=None
		return None
	for x in myparts:
		if len(x)==0:
			if not silent:
				print "!!! Name error in",mypkg+": empty \"-\" part."
			ctx.pkgcache[mypkg]=None
			return None
	#verify rev
	revok=0
	myrev=myparts[-1]
	if len(myrev) and myrev[0]=="r":
		try:
			string.atoi(myrev[1:])
			revok=1
		except: 
			pass
	if revok:
		if ververify(ctx, myparts[-2]):
			if len(myparts)==2:
				ctx.pkgcache[mypkg]=None
				return None
			else:
				for x in myparts[:-2]:
					if ververify(ctx, x):
						ctx.pkgcache[mypkg]=None
						return None
						#names can't have versiony looking parts
				myval=[string.join(myparts[:-2],"-"),myparts[-2],myparts[-1]]
				ctx.pkgcache[mypkg]=myval
				return myval
		else:
			ctx.pkgcache[mypkg]=None
			return None

	elif ververify(ctx, myparts[-1],silent):
		if len(myparts)==1:
			if not silent:
				print "!!! Name error in",mypkg+": missing name part."
			ctx.pkgcache[mypkg]=None
			return None
		else:
			for x in myparts[:-1]:
				if ververify(ctx, x):
					if not silent:
						print "!!! Name error in",mypkg+": multiple version parts."
					ctx.pkgcache[mypkg]=None
					return None
			myval=[string.join(myparts[:-1],"-"),myparts[-1],"r0"]
			ctx.pkgcache[mypkg]=myval
			return myval
	else:
		ctx.pkgcache[mypkg]=None
		return None

def catpkgsplit(ctx, mydata,silent=1):
	"returns [cat, pkgname, version, rev ]"
	try:
		return ctx.catcache[mydata]
	except KeyError:
		pass
	mysplit=mydata.split("/")
	p_split=None
	if len(mysplit)==1:
		retval=["null"]
		p_split=pkgsplit(ctx, mydata,silent)
	elif len(mysplit)==2:
		retval=[mysplit[0]]
		p_split=pkgsplit(ctx, mysplit[1],silent)
	if not p_split:
		ctx.catcache[mydata]=None
		return None
	retval.extend(p_split)
	ctx.catcache[mydata]=retval
	return retval

# vercmp:
# This takes two version strings and returns an integer to tell you whether
# the versions are the same, val1>val2 or val2>val1.
def vercmp(ctx, val1,val2):
	if val1==val2:
		#quick short-circuit
		return 0
	valkey=val1+" "+val2
	try:
		return ctx.vcmpcache[valkey]
		try:
			return -ctx.vcmpcache[val2+" "+val1]
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
		cmp1=relparse(ctx, val1[x])
		cmp2=relparse(ctx, val2[x])
		for y in range(0,3):
			myret=cmp1[y]-cmp2[y]
			if myret != 0:
				ctx.vcmpcache[valkey]=myret
				return myret
	ctx.vcmpcache[valkey]=0
	return 0


def pkgcmp(ctx, pkg1,pkg2):
	"""if returnval is less than zero, then pkg2 is newer than pkg1, zero if equal and positive if older."""
	mycmp=vercmp(ctx, pkg1[1],pkg2[1])
	if mycmp>0:
		return 1
	if mycmp<0:
		return -1
	r1=string.atoi(pkg1[2][1:])
	r2=string.atoi(pkg2[2][1:])
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
					mysplit=dep_parenreduce(mysplit,mypos)
				mypos=mypos+1
		mypos=mypos+1
	return mysplit

def dep_opconvert(ctx, mysplit,myuse):
	"Does dependency operator conversion"
	mypos=0
	newsplit=[]
	while mypos<len(mysplit):
		if type(mysplit[mypos])==types.ListType:
			newsplit.append(dep_opconvert(ctx, mysplit[mypos],myuse))
			mypos += 1
		elif mysplit[mypos]==")":
			#mismatched paren, error
			return None
		elif mysplit[mypos]=="||":
			if ((mypos+1)>=len(mysplit)) or (type(mysplit[mypos+1])!=types.ListType):
				# || must be followed by paren'd list
				return None
			try:
				mynew=dep_opconvert(ctx, mysplit[mypos+1],myuse)
			except Exception, e:
				print "!!! Unable to satisfy OR dependency:",string.join(mysplit," || ")
				raise e
			mynew[0:0]=["||"]
			newsplit.append(mynew)
			mypos += 2
		elif mysplit[mypos][-1]=="?":
			#uses clause, i.e "gnome? ( foo bar )"
			#this is a quick and dirty hack so that repoman can enable all USE vars:
			if (len(myuse)==1) and (myuse[0]=="*"):
				# enable it even if it's ! (for repoman) but kill it if it's
				# an arch variable that isn't for this arch. XXX Sparc64?
				if (mysplit[mypos][:-1] not in ctx.settings.usemask) or \
						(mysplit[mypos][:-1]==ctx.settings["ARCH"]):
					enabled=1
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
						newsplit.append(dep_opconvert(ctx, mysplit[mypos+1],myuse))
					else:
						newsplit.append(mysplit[mypos+1])
				else:
					#choose the alternate option
					if type(mysplit[mypos+1])==types.ListType:
						newsplit.append(dep_opconvert(ctx, mysplit[mypos+3],myuse))
					else:
						newsplit.append(mysplit[mypos+3])
				mypos += 4
			else:
				#normal use mode
				if enabled:
					if type(mysplit[mypos+1])==types.ListType:
						newsplit.append(dep_opconvert(ctx, mysplit[mypos+1],myuse))
					else:
						newsplit.append(mysplit[mypos+1])
				#otherwise, continue.
				mypos += 2
		else:
			#normal item
			newsplit.append(mysplit[mypos])
			mypos += 1
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

def dep_zapdeps(unreduced,reduced):
	"""Takes an unreduced and reduced deplist and removes satisfied dependencies.
	Returned deplist contains steps that must be taken to satisfy dependencies."""
	if unreduced==[]:
		return None
	if unreduced[0]=="||":
		if dep_eval(reduced):
			#deps satisfied, return None
			return None
		else:
			#try to satisfy first dep
			return unreduced[1]
	else:
		if dep_eval(reduced):
			#deps satisfied, return None
			return None
		else:
			returnme=[]
			x=0
			while x<len(reduced):
				if type(reduced[x])==types.ListType:
					myresult=dep_zapdeps(unreduced[x],reduced[x])
					if myresult:
						returnme.append(myresult)
				else:
					if reduced[x]==0:
						returnme.append(unreduced[x])
				x += 1
			return returnme

def dep_listcleanup(deplist):
	"remove unnecessary clutter from deplists.  Remove multiple list levels, empty lists"
	newlist=[]
	if (len(deplist)==1):
		#remove multiple-depth lists
		if (type(deplist[0])==types.ListType):
			for x in deplist[0]:
				if type(x)==types.ListType:
					if len(x)!=0:
						newlist.append(dep_listcleanup(x))
				else:
					newlist.append(x)
		else:
			#unembed single nodes
			newlist.append(deplist[0])
	else:
		for x in deplist:
			if type(x)==types.ListType:
				if len(x)==1:
					newlist.append(x[0])
				elif len(x)!=0:
					newlist=newlist+dep_listcleanup(x)
			else:
				newlist.append(x)
	return newlist

def dep_getjiggy(mydep):
	pos=0
	# first, we fill in spaces where needed (for "()[]" chars)
	while pos<len(mydep):
		if (mydep[pos] in "()[]"):
			if (pos>0) and (mydep[pos-1]!=" "):
				mydep=mydep[0:pos]+" "+mydep[pos:]
				pos += 1
			if (pos+1<len(mydep)) and (mydep[pos+1]!=" "):
				mydep=mydep[0:pos+1]+" "+mydep[pos+1:]
				pos += 1
		pos += 1
	# next, we split our dependency string into tokens
	mysplit=mydep.split()
	# next, we parse our tokens and create a list-based dependency structure
	return dep_parenreduce(mysplit)

def dep_getkey(ctx, mydep):
	if not len(mydep):
		return mydep
	if mydep[0]=="*":
		mydep=mydep[1:]
	if mydep[-1]=="*":
		mydep=mydep[:-1]
	if mydep[:2] in [ ">=", "<=" ]:
		mydep=mydep[2:]
	elif mydep[:1] in "=<>~!":
		mydep=mydep[1:]
	if isspecific(ctx, mydep):
		mysplit=catpkgsplit(ctx, mydep)
		if not mysplit:
			return mydep
		return mysplit[0]+"/"+mysplit[1]
	else:
		return mydep

def dep_getcpv(mydep):
	if not len(mydep):
		return mydep
	if mydep[0]=="*":
		mydep=mydep[1:]
	if mydep[-1]=="*":
		mydep=mydep[:-1]
	if mydep[:2] in [ ">=", "<=" ]:
		mydep=mydep[2:]
	elif mydep[:1] in "=<>~!":
		mydep=mydep[1:]
	return mydep

def cpv_getkey(ctx, mycpv):
	myslash=mycpv.split("/")
	mysplit=pkgsplit(ctx, myslash[-1])
	mylen=len(myslash)
	if mylen==2:
		return myslash[0]+"/"+mysplit[0]
	elif mylen==1:
		return mysplit[0]
	else:
		return mysplit

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

def dep_expand(ctx, mydep,mydb=None):
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
	return prefix+ctx.cpv_expand(mydep,mydb)+postfix

def dep_check(ctx, depstring,mydbapi,use="yes",mode=None):
	"""Takes a depend string and parses the condition."""
	if use=="all":
		#enable everything (for repoman)
		myusesplit=["*"]
	elif use=="yes":
		#default behavior
		myusesplit=ctx.get_usesplit()
	else:
		#we are being run by autouse(), don't consult USE vars yet.
		myusesplit=[]
	mysplit=string.split(depstring)
	#convert parenthesis to sublists
	mysplit=dep_parenreduce(mysplit)
	#mysplit can't be None here, so we don't need to check
	mysplit=dep_opconvert(ctx, mysplit,myusesplit)
	#if mysplit==None, then we have a parse error (paren mismatch or misplaced ||)
	#up until here, we haven't needed to look at the database tree
	
	if mysplit==None:
		return [0,"Parse Error (parenthesis mismatch?)"]
	elif mysplit==[]:
		#dependencies were reduced to nothing
		return [1,[]]
	mysplit2=mysplit[:]
	mysplit2=dep_wordreduce(mysplit2,mydbapi,mode)
	if mysplit2==None:
		return [0,"Invalid token"]
	myeval=dep_eval(mysplit2)
	if myeval:
		return [1,[]]
	else:
		mylist=flatten(dep_listcleanup(dep_zapdeps(mysplit,mysplit2)))
		#remove duplicates
		mydict={}
		for x in mylist:
			mydict[x]=1
		return [1,mydict.keys()]

def dep_wordreduce(mydeplist,mydbapi,mode):
	"Reduces the deplist to ones and zeros"
	mypos=0
	deplist=mydeplist[:]
	while mypos<len(deplist):
		if type(deplist[mypos])==types.ListType:
			#recurse
			deplist[mypos]=dep_wordreduce(deplist[mypos],mydbapi,mode)
		elif deplist[mypos]=="||":
			pass
		else:
			if mode:
				mydep=mydbapi.xmatch(mode,deplist[mypos])
			else:
				mydep=mydbapi.match(deplist[mypos])
			if mydep!=None:
				deplist[mypos]=(len(mydep)>=1)
			else:
				#encountered invalid string
				return None
		mypos=mypos+1
	return deplist


class packagetree:
	def __init__(self, ctx, virtual, clone=None):
		self.ctx = ctx
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
		return self.ctx.key_expand(mykey,self.dbapi)
	
	def dep_nomatch(self,mypkgdep):
		mykey=dep_getkey(self.ctx, mypkgdep)
		nolist=self.dbapi.cp_list(mykey)
		mymatch=self.dbapi.match(mypkgdep)
		if not mymatch:
			return nolist
		for x in mymatch:
			if x in nolist:
				nolist.remove(x)
		return nolist

	def depcheck(self,mycheck,use="yes"):
		return dep_check(self.ctx, mycheck,self.dbapi,use=use)

	def populate(self):
		"populates the tree with values"
		populated=1
		pass


def best(ctx, mymatches):
	"accepts None arguments; assumes matches are valid."
	if mymatches==None:
		return "" 
	if not len(mymatches):
		return "" 
	bestmatch=mymatches[0]
	p2=catpkgsplit(ctx, bestmatch)[1:]
	for x in mymatches[1:]:
		p1=catpkgsplit(ctx, x)[1:]
		if pkgcmp(ctx, p1,p2)>0:
			bestmatch=x
			p2=catpkgsplit(ctx, bestmatch)[1:]
	return bestmatch		


class portagetree:
	def __init__(self, ctx, root="/", virtual=None, clone=None):
		self.ctx = ctx
		if clone:
			self.root=clone.root
			self.portroot=clone.portroot
			self.pkglines=clone.pkglines
		else:
			self.root=root
			self.portroot=self.ctx.settings["PORTDIR"]
			self.virtual=virtual
			self.dbapi=self.ctx.portdb

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
		psplit=pkgsplit(self.ctx, mysplit[1])
		return self.portroot+"/"+mysplit[0]+"/"+psplit[0]+"/"+mysplit[1]+".ebuild"

	def resolve_specific(self,myspec):
		cps=catpkgsplit(self.ctx, myspec)
		if not cps:
			return None
		mykey=self.ctx.key_expand(cps[0]+"/"+cps[1],self.dbapi)
		mykey=mykey+"-"+cps[2]
		if cps[3]!="r0":
			mykey=mykey+"-"+cps[3]
		return mykey

	def depcheck(self,mycheck,use="yes"):
		return dep_check(self.ctx, mycheck,self.dbapi,use=use)


class dbapi:
	def __init__(self, ctx):
		self.ctx = ctx
		pass
	
	def cp_list(self,cp):
		return

	def aux_get(self,mycpv,mylist):
		"stub code for returning auxiliary db information, such as SLOT, DEPEND, etc."
		'input: "sys-apps/foo-1.0",["SLOT","DEPEND","HOMEPAGE"]'
		'return: ["0",">=sys-libs/bar-1.0","http://www.foo.com"] or [] if mycpv not found'
		pass

	def match(self,origdep):
		mydep=dep_expand(self.ctx, origdep,self)
		mykey=dep_getkey(self.ctx, mydep)
		mycat=mykey.split("/")[0]
		return self.match2(mydep,mykey,self.cp_list(mykey))
		
	def match2(self,mydep,mykey,mylist):
		"Notable difference to our match() function is that we don't return None. Ever.  Just empty list."
		mycpv=dep_getcpv(mydep)
		if isspecific(self.ctx, mycpv):
			cp_key=catpkgsplit(self.ctx, mycpv)
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
				except:
					#erp, error.
					return [] 
				mynodes=[]
				cmp1=cp_key[1:]
				cmp1[1]=cmp1[1]+"_alpha0"
				cmp2=[cp_key[1],new_v,"r0"]
				for x in mylist:
					cp_x=catpkgsplit(self.ctx, x)
					if cp_x==None:
						#hrm, invalid entry.  Continue.
						continue
					#skip entries in our list that do not have matching categories
					if cp_key[0]!=cp_x[0]:
						continue
					# ok, categories match. Continue to next step.	
					if ((pkgcmp(self.ctx, cp_x[1:],cmp1)>=0) and (pkgcmp(self.ctx, cp_x[1:],cmp2)<0)):
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
				cp_x=catpkgsplit(self.ctx, x)
				if cp_x==None:
					#invalid entry; continue.
					continue
				if cp_key[0]!=cp_x[0]:
					continue
				if eval("pkgcmp(self.ctx, cp_x[1:],cp_key[1:])"+cmpstr+"0"):
					mynodes.append(x)
			return mynodes
		elif mydep[0]=="~":
			if cp_key==None:
				return []
			myrev=-1
			for x in mylist:
				cp_x=catpkgsplit(self.ctx, x)
				if cp_x==None:
					#invalid entry; continue
					continue
				if cp_key[0]!=cp_x[0]:
					continue
				if cp_key[2]!=cp_x[2]:
					#if version doesn't match, skip it
					continue
				if string.atoi(cp_x[3][1:])>myrev:
					myrev=string.atoi(cp_x[3][1:])
					mymatch=x
			if myrev==-1:
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
				cp_x=catpkgsplit(self.ctx, x)
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


class fakedbapi(dbapi):
	"This is a dbapi to use for the emptytree function.  It's empty, but things can be added to it."
	def __init__(self, ctx):
		self.ctx = ctx
		self.cpvdict={}
		self.cpdict={}

	#this needs to be here for emerge --emptytree that uses fakedbapi for /var
	#we should remove this requirement soon.
	def counter_tick(self):
		return counter_tick_core("/")
	
	def cpv_exists(self,mycpv):
		return self.cpvdict.has_key(mycpv)

	def cp_list(self,mycp):
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
		mycp=cpv_getkey(self.ctx, mycpv)
		self.cpvdict[mycpv]=1
		if not self.cpdict.has_key(mycp):
			self.cpdict[mycp]=[]
		if not mycpv in self.cpdict[mycp]:
			self.cpdict[mycp].append(mycpv)

def counter_tick_core(myroot):
		"This method will grab the next COUNTER value and record it back to the global file.  Returns new counter value."
		cpath=myroot+"var/cache/edb/counter"

		#We write our new counter value to a new file that gets moved into
		#place to avoid filesystem corruption on XFS (unexpected reboot.)
		if os.path.exists(cpath):
			cfile=open(cpath, "r")
			try:
				counter=long(cfile.readline())
			except (ValueError,OverflowError):
				try:
					counter=long(commands.getoutput("for FILE in $(find /var/db/pkg -type f -name COUNTER); do cat ${FILE}; echo; done | sort -n | tail -n1 | tr -d '\n'"))
					print "portage: COUNTER was corrupted; resetting to value of",counter
				except (ValueError,OverflowError):
					print red("portage:")+" COUNTER data is corrupt in pkg db. The values need to be"
					print red("portage:")+" corrected/normalized so that portage can operate properly."
					print red("portage:")+" A simple solution is not yet available so try #gentoo on IRC."
					sys.exit(2)
			cfile.close()
		else:
			try:
				counter=long(commands.getoutput("for FILE in $(find /var/db/pkg -type f -name COUNTER); do cat ${FILE}; echo; done | sort -n | tail -n1 | tr -d '\n'"))
				print red("portage:")+" Global counter missing. Regenerated from counter files to:",counter
			except:
				print red("portage:")+" Initializing global counter."
				counter=long(0)
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


class vardbapi(dbapi):
	def __init__(self, ctx, root):
		self.ctx = ctx
		self.root=root
		#cache for category directory mtimes
		self.mtdircache={}
		#cache for dependency checks
		self.matchcache={}
		#cache for cp_list results
		self.cpcache={}	

	def cpv_exists(self,mykey):
		"Tells us whether an actual ebuild exists on disk (no masking)"
		return os.path.exists(self.root+"var/db/pkg/"+mykey)

	def counter_tick(self):
		return counter_tick_core(self.root)

	def cpv_counter(self,mycpv):
		"This method will grab the next COUNTER value and record it back to the global file.  Returns new counter value."
		cpath=self.root+"var/db/pkg/"+mycpv+"/COUNTER"

		#We write our new counter value to a new file that gets moved into
		#place to avoid filesystem corruption on XFS (unexpected reboot.)
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
		os.makedirs(self.root+"var/db/pkg/"+mycpv)	
		counter=self.ctx.db[self.root]["vartree"].dbapi.counter_tick()
		# write local package counter so that emerge clean does the right thing
		lcfile=open(self.root+"var/db/pkg/"+mycpv+"/COUNTER","w")
		lcfile.write(str(counter))
		lcfile.close()

	def move_ent(self,mylist):
		origcp=mylist[1]
		newcp=mylist[2]
		origmatches=self.cp_list(origcp)
		if not origmatches:
			return
		for mycpv in origmatches:
			mycpsplit=catpkgsplit(self.ctx, mycpv)
			mynewcpv=newcp+"-"+mycpsplit[2]
			mynewcat=newcp.split("/")[0]
			if mycpsplit[3]!="r0":
				mynewcpv += "-"+mycpsplit[3]
			origpath=self.root+"var/db/pkg/"+mycpv
			if not os.path.exists(origpath):
				continue
			if not os.path.exists(self.root+"var/db/pkg/"+mynewcat):
				#create the directory
				os.makedirs(self.root+"var/db/pkg/"+mynewcat)	
			newpath=self.root+"var/db/pkg/"+mynewcpv
			if os.path.exists(newpath):
				#dest already exists; keep this puppy where it is.
				continue
			spawn(self.ctx, "/bin/mv "+origpath+" "+newpath, free=1)

	def cp_list(self,mycp):
		mysplit=mycp.split("/")
		try:
			mystat=os.stat(self.root+"var/db/pkg/"+mysplit[0])[ST_MTIME]
		except OSError:
			mystat=0
		if self.cpcache.has_key(mycp):
			cpc=self.cpcache[mycp]
			if cpc[0]==mystat:
				return cpc[1]
		try:
			list=listdir(self.ctx, self.root+"var/db/pkg/"+mysplit[0])
		except OSError:
			return []
		returnme=[]
		for x in list:
			ps=pkgsplit(self.ctx, x)
			if not ps:
				print "!!! Invalid db entry:",self.root+"var/db/pkg/"+mysplit[0]+"/"+x
				continue
			if ps[0]==mysplit[1]:
				returnme.append(mysplit[0]+"/"+x)	
		self.cpcache[mycp]=[mystat,returnme]
		return returnme

	def cp_all(self):
		returnme=[]
		for x in self.ctx.get_categories():
			try:
				mylist=listdir(self.ctx, self.root+"var/db/pkg/"+x)
			except OSError:
				mylist=[]
			for y in mylist:
				mysplit=pkgsplit(self.ctx, y)
				if not mysplit:
					print "!!! Invalid db entry:",self.root+"var/db/pkg/"+x+"/"+y
					continue
				mykey=x+"/"+mysplit[0]
				if not mykey in returnme:
					returnme.append(mykey)
		return returnme

	def match(self,origdep):
		"caching match function"
		mydep=dep_expand(self.ctx, origdep,self)
		mykey=dep_getkey(self.ctx, mydep)
		mycat=mykey.split("/")[0]
		try:
			curmtime=os.stat(self.root+"var/db/pkg/"+mycat)
		except:
			curmtime=0
		if self.matchcache.has_key(mydep):
			if self.mtdircache[mycat]==curmtime:
				return self.matchcache[mydep]
		#generate new cache entry
		mymatch=self.match2(mydep,mykey,self.cp_list(mykey))
		self.mtdircache[mycat]=curmtime
		self.matchcache[mydep]=mymatch
		return mymatch
		

class vartree(packagetree):
	"this tree will scan a var/db/pkg database located at root (passed to init)"
	def __init__(self, ctx, root="/", virtual=None, clone=None):
		self.ctx = ctx
		if clone:
			self.root=clone.root
			self.dbapi=clone.dbapi
			self.populated=1
		else:
			self.root=root
			self.dbapi=vardbapi(self.ctx, self.root)
			self.populated=1

	def zap(self,foo):
		return

	def inject(self,foo):
		return
	
	def dep_bestmatch(self,mydep):
		"compatibility method -- all matches, not just visible ones"
		#mymatch=best(match(dep_expand(self.ctx, mydep,self.dbapi),self.dbapi))
		mymatch=best(self.ctx, self.dbapi.match(dep_expand(self.ctx, mydep,self.dbapi)))
		if mymatch==None:
			return ""
		else:
			return mymatch
			
	def dep_match(self,mydep):
		"compatibility method -- we want to see all matches, not just visible ones"
		#mymatch=match(mydep,self.dbapi)
		mymatch=self.dbapi.match(mydep)
		if mymatch==None:
			return []
		else:
			return mymatch

	def exists_specific(self,cpv):
		return self.dbapi.cpv_exists(cpv)

	def getallnodes(self):
		"""new behavior: these are all *unmasked* nodes.  There may or may not be available
		masked package for nodes in this nodes list."""
		return self.dbapi.cp_all()

	def exists_specific_cat(self,cpv):
		cpv=self.ctx.key_expand(cpv,self.dbapi)
		a=catpkgsplit(self.ctx, cpv)
		if not a:
			return 0
		try:
			mylist=listdir(self.ctx, self.root+"var/db/pkg/"+a[0])
		except OSError:
			return 0
		for x in mylist:
			b=pkgsplit(self.ctx, x)
			if not b:
				print "!!! Invalid db entry:",self.root+"var/db/pkg/"+a[0]+"/"+x
				continue
			if a[1]==b[0]:
				return 1
		return 0
			
	def getebuildpath(self,fullpackage):
		cat,package=fullpackage.split("/")
		return self.root+"var/db/pkg/"+fullpackage+"/"+package+".ebuild"

	def getnode(self,mykey):
		mykey=self.ctx.key_expand(mykey,self.dbapi)
		if not mykey:
			return []
		mysplit=mykey.split("/")
		try:
			mydirlist=listdir(self.ctx, self.root+"var/db/pkg/"+mysplit[0])
		except:
			return []
		returnme=[]
		for x in mydirlist:
			mypsplit=pkgsplit(self.ctx, x)
			if not mypsplit:
				print "!!! Invalid db entry:",self.root+"var/db/pkg/"+mysplit[0]+"/"+x
				continue
			if mypsplit[0]==mysplit[1]:
				appendme=[mysplit[0]+"/"+x,[mysplit[0],mypsplit[0],mypsplit[1],mypsplit[2]]]
				returnme.append(appendme)
		return returnme

	
	def getslot(self,mycatpkg):
		"Get a slot for a catpkg; assume it exists."
		try:
			myslotfile=open(self.root+"var/db/pkg/"+mycatpkg+"/SLOT","r")
			myslotvar=string.split(myslotfile.readline())
			myslotfile.close()
			if len(myslotvar):
				return myslotvar[0]
		except:
			pass
		return ""
	
	def hasnode(self,mykey):
		"""Does the particular node (cat/pkg key) exist?"""
		mykey=self.ctx.key_expand(mykey,self.dbapi)
		mysplit=mykey.split("/")
		try:
			mydirlist=listdir(self.ctx, self.root+"var/db/pkg/"+mysplit[0])
		except:
			return 0
		for x in mydirlist:
			mypsplit=pkgsplit(self.ctx, x)
			if not mypsplit:
				print "!!! Invalid db entry:",self.root+"var/db/pkg/"+mysplit[0]+"/"+x
				continue
			if mypsplit[0]==mysplit[1]:
				return 1
		return 0
	
	def populate(self):
		self.populated=1


# ----------------------------------------------------------------------------


def eclass(ctx, myeclass=None,mycpv=None,mymtime=None):
	"""Caches and retrieves information about ebuilds that use eclasses
	Returns: Is the ebuild current with the eclass? (true/false)"""
	#print "eclass("+str(myeclass)+","+str(mycpv)+","+str(mymtime)+")"

	if not ctx.mtimedb.has_key("eclass") or type(ctx.mtimedb["eclass"]) is not types.DictType:
		ctx.mtimedb["eclass"]={}
		ctx.mtimedb["packages"]=[]
	if not ctx.mtimedb.has_key("packages") or type(ctx.mtimedb["packages"]) is not types.ListType:
		ctx.mtimedb["packages"]=[]
	
	if not ctx.mtimedb.has_key("starttime") or (ctx.mtimedb["starttime"]!=ctx.starttime):
		ctx.mtimedb["starttime"]=ctx.starttime
		# Update the cache
		for x in [ctx.settings["PORTDIR"]+"/eclass", ctx.settings["PORTDIR_OVERLAY"]+"/eclass"]:
			if x and os.path.exists(x):
				dirlist = listdir(ctx, x)
				for y in dirlist:
					if y[-len(".eclass"):]==".eclass":
						try:
							ys=y[:-len(".eclass")]
							ymtime=os.stat(x+"/"+y)[ST_MTIME]
							if ctx.mtimedb["eclass"].has_key(ys):
								if ymtime!=ctx.mtimedb["eclass"][ys][0]:
									# The mtime changed on the eclass
									ctx.mtimedb["eclass"][ys]=[ymtime,x+"/"+y,ctx.mtimedb["eclass"][ys][2]]
								else:
									# nothing changed
									pass
							else:
								# New eclass
								ctx.mtimedb["eclass"][ys]=[ymtime,x+"/"+y, {}]
						except Exception, e:
							print "!!! stat exception:",e
							continue
	if myeclass != None:
		if not ctx.mtimedb["eclass"].has_key(myeclass):
			# Eclass doesn't exist.
			print "!!! eclass does not exist:",myeclass
			return None
		else:
			if (mycpv!=None) and (mymtime!=None):
				if mycpv not in ctx.mtimedb["packages"]:
					ctx.mtimedb["packages"].append(mycpv)
				if ctx.mtimedb["eclass"][myeclass][2].has_key(mycpv):
					# Check if the ebuild mtime changed OR if the mtime for the eclass
					# has changed since it was last updated.
					#print "test:",mymtime!=mtimedb["eclass"][myeclass][2][mycpv][1],mtimedb["eclass"][myeclass][0]!=mtimedb["eclass"][myeclass][2][mycpv][0]
					if (mymtime!=ctx.mtimedb["eclass"][myeclass][2][mycpv][1]) or (ctx.mtimedb["eclass"][myeclass][0]!=ctx.mtimedb["eclass"][myeclass][2][mycpv][0]):
						# Store the new mtime before we expire the cache so we don't
						# repeatedly regen this entry.
						#print " regen --",myeclass,"--",mymtime,mtimedb["eclass"][myeclass][2][mycpv][1],"--",mtimedb["eclass"][myeclass][0],mtimedb["eclass"][myeclass][2][mycpv][0]
						ctx.mtimedb["eclass"][myeclass][2][mycpv]=[ctx.mtimedb["eclass"][myeclass][0],mymtime]
						# Expire the cache. mtimes don't match.
						return 0
					else:
						# Matches
						#print "!regen --",myeclass,"--",mymtime,mtimedb["eclass"][myeclass][2][mycpv][1],"--",mtimedb["eclass"][myeclass][0],mtimedb["eclass"][myeclass][2][mycpv][0]
						return 1
				else:
					# Don't have an entry... Must be new.
					#print "*regen --",myeclass,"--",mymtime,mtimedb["eclass"][myeclass][2][mycpv][1],"--",mtimedb["eclass"][myeclass][0],mtimedb["eclass"][myeclass][2][mycpv][0]
					ctx.mtimedb["eclass"][myeclass][2][mycpv]=[ctx.mtimedb["eclass"][myeclass][0],mymtime]
					return 0
			else:
				# We're missing some vital parts.
				raise KeyError
	else:
		# Recurse without explicit eclass. (Recurse all)
		if mycpv in ctx.mtimedb["packages"]:
			for myeclass in ctx.mtimedb["eclass"].keys():
				if ctx.mtimedb["eclass"][myeclass][2].has_key(mycpv):
					if (mymtime!=ctx.mtimedb["eclass"][myeclass][2][mycpv][1]) or (ctx.mtimedb["eclass"][myeclass][0]!=ctx.mtimedb["eclass"][myeclass][2][mycpv][0]):
						#print " regen mtime:",mymtime,mtimedb["eclass"][myeclass][2][mycpv][1],"--",mtimedb["eclass"][myeclass][0],mtimedb["eclass"][myeclass][2][mycpv][0]
						#mtimes do not match
						return 0
		#print "!regen mtime"
		return 1


# ----------------------------------------------------------------------------


class portdbapi(dbapi):
	"this tree will scan a portage directory located at root (passed to init)"
	def __init__(self, ctx):
		self.ctx = ctx
		self.root=self.ctx.settings["PORTDIR"]
		self.auxcache={}
		#if the portdbapi is "frozen", then we assume that we can cache everything (that no updates to it are happening)
		self.xcache={}
		self.frozen=0
		#oroot="overlay root"
		self.oroot=None

		self.auxdbkeys=['DEPEND','RDEPEND','SLOT','SRC_URI','RESTRICT','HOMEPAGE','LICENSE','DESCRIPTION','KEYWORDS','INHERITED','IUSE','CDEPEND','PDEPEND']
		self.auxdbkeylen=len(self.auxdbkeys)

	def findname(self,mycpv):
		"returns file location for this particular package"
		if not mycpv:
			return ""
		mysplit=mycpv.split("/")
		psplit=pkgsplit(self.ctx, mysplit[1])
		if self.oroot:
			myloc=self.oroot+"/"+mysplit[0]+"/"+psplit[0]+"/"+mysplit[1]+".ebuild"
			try:
				os.stat(myloc)
				return myloc
			except (OSError,IOError):
				pass
		return self.root+"/"+mysplit[0]+"/"+psplit[0]+"/"+mysplit[1]+".ebuild"

	def aux_get(self,mycpv,mylist,strict=0,metacachedir=None):
		"stub code for returning auxilliary db information, such as SLOT, DEPEND, etc."
		'input: "sys-apps/foo-1.0",["SLOT","DEPEND","HOMEPAGE"]'
		'return: ["0",">=sys-libs/bar-1.0","http://www.foo.com"] or raise KeyError if error'
		dmtime=0
		emtime=0
		doregen=0
		doregen2=0
		mylines=[]
		stale=0
		usingmdcache=0
		myebuild=self.findname(mycpv)
		mydbkey=self.ctx.get_cachedir()+"/"+mycpv
		mymdkey=None
		if metacachedir and os.access(metacachedir, os.R_OK):
			mymdkey=metacachedir+"/"+mycpv

		#print "statusline1:",doregen,dmtime,emtime,mycpv
		try:
			emtime=os.stat(myebuild)[ST_MTIME]
		except:
			return None
		
		# first, we take a look at the size of the ebuild/cache entry to ensure we
		# have a valid data, then we look at the mtime of the ebuild and the
		# cache entry to see if we need to regenerate our cache entry.
		try:
			mydbkeystat=os.stat(mydbkey)
			if mydbkeystat[ST_SIZE] == 0:
				doregen=1
				dmtime=0
			else:
				dmtime=mydbkeystat[ST_MTIME]
				if dmtime!=emtime:
					doregen=1
		except OSError:
			doregen=1

		#print "statusline2:",doregen,dmtime,emtime,mycpv
		if doregen or not eclass(self.ctx, None, mycpv, dmtime):
			stale=1
			#print "doregen:",doregen,mycpv
			if mymdkey and os.access(mymdkey, os.R_OK):
					#sys.stderr.write("+")
					#sys.stderr.flush()
					try:
						mydir=os.path.dirname(mydbkey)
						if not os.path.exists(mydir):
							os.makedirs(mydir, 2775)
							os.chown(mydir,self.ctx.get_uid(),self.ctx.get_portage_gid())
						shutil.copy2(mymdkey, mydbkey)
						usingmdcache=1
					except Exception,e:
						print "!!! Unable to copy '"+mymdkey+"' to '"+mydbkey+"'"
						print "!!!",e
			else:
				if doebuild(self.ctx, myebuild,"depend","/"):
					#depend returned non-zero exit code...
					if strict:
						sys.stderr.write(str(red("\naux_get():")+" (0) Error in",mycpv,"ebuild.\n"))
						raise KeyError

			doregen2=1
			dmtime=0
			try:
				os.utime(mydbkey,(emtime,emtime))
				mydbkeystat=os.stat(mydbkey)
				if mydbkeystat[ST_SIZE] == 0:
					#print "!!! <-- Size 0 -->"
					pass
				else:
					dmtime=mydbkeystat[ST_MTIME]
					doregen2=0
			except OSError:
				#print "doregen1 failed."
				pass
			
		#print "--doregen"
		#Now, our cache entry is possibly regenerated.  It could be up-to-date, but it may not be...
		#If we regenerated the cache entry or we don't have an internal cache entry or or cache entry
		#is stale, then we need to read in the new cache entry.

		#print "statusline3:",doregen,dmtime,emtime,mycpv
		if (not self.auxcache.has_key(mycpv)) or (not self.auxcache[mycpv].has_key("mtime")) or (self.auxcache[mycpv]["mtime"]!=dmtime):
			#print "stale auxcache"
			stale=1

		try:
			#print "grab cent"
			mycent=open(mydbkey,"r")
			mylines=mycent.readlines()
			mycent.close()
		except (IOError, OSError):
			print red("\n\naux_get():")+" (1) couldn't open cache entry for",mycpv
			print "               Check for syntax error or corruption in the ebuild."
			print 
			raise KeyError

		#We now have the db
		myeclasses=[]
		#if we regenerated our cache entry earlier, there's no point in
		#checking all this as we know we are up-to-date.  Otherwise....
		if not mylines:
			print "no mylines"
			pass
		elif doregen2 or len(mylines)<len(self.auxdbkeys):
			doregen2=1
			#print "too few auxdbkeys / invalid generation"
		elif mylines[self.auxdbkeys.index("INHERITED")]!="\n":
			#print "inherits"
			#Verify if this ebuild is current against the eclasses it uses.
			#eclass() -> Loads, checks, and returns 1 if it's current.
			myeclasses=mylines[self.auxdbkeys.index("INHERITED")].split()
			#print "))) 002"
			for myeclass in myeclasses:
				myret=eclass(self.ctx, myeclass,mycpv,dmtime)
				#print "eclass '",myeclass,"':",myret,doregen,doregen2
				if myret==None:
					print red("\n\naux_get():")+' eclass "'+myeclass+'" from',mydbkey,"not found."
					print "!!! Eclass '"+myeclass+"'not found."
					doregen2=1
					break
				if myret==0 and not usingmdcache:
					#print "((( 002 0"
					#we set doregen2 to regenerate this entry in case it was fixed
					#in the ebuild/eclass since the cache entry was created.
					#print "Old cache entry. Regen."
					doregen2=1
					break

		#print "doregen2: pre"
		if doregen2:
			#sys.stderr.write("-")
			#sys.stderr.flush()
			#print "doregen2"
			stale=1
			#old cache entry, needs updating (this could raise IOError)

			try:
				# Can't set the mtime of a file we don't own, so to ensure that it
				# is owned by the running user, we delete the file so we recreate it.
				os.unlink(mydbkey)
			except:
				pass
			
			if doebuild(self.ctx, myebuild,"depend","/"):
				#depend returned non-zero exit code...
				if strict:
					print red("\n\naux_get():")+" (0) Error in",mycpv,"ebuild."
					raise KeyError
			try:
				os.utime(mydbkey,(emtime,emtime))
				mycent=open(mydbkey,"r")
			except (IOError, OSError):
				print red("\n\naux_get():")+" (2) couldn't open cache entry for",mycpv
				print "               Check for syntax error or corruption in the ebuild."
				raise KeyError
			mylines=mycent.readlines()
			mycent.close()

		#print "stale: pre"
		if stale:
			#print "stale: in"
			# due to a stale or regenerated cache entry,
			# we need to update our internal dictionary....
			try:
				# Set the dep entry to the ebuilds mtime.
				self.auxcache[mycpv]={"mtime": emtime}
				myeclasses=mylines[self.auxdbkeys.index("INHERITED")].split()
			except Exception, e:
				print red("\n\naux_get():")+" stale entry was not regenerated for"
				print "           "+mycpv+"; deleting and exiting."
				print "!!!",e
				os.unlink(mydbkey)
				sys.exit(1)
			for myeclass in myeclasses:
				eclass(self.ctx, myeclass,mycpv,emtime)
			try:
				for x in range(0,len(self.auxdbkeys)):
					self.auxcache[mycpv][self.auxdbkeys[x]]=mylines[x][:-1]
			except IndexError:
				print red("\n\naux_get():")+" error processing",self.auxdbkeys[x],"for",mycpv
				print "           Expiring the cache entry and exiting."
				os.unlink(mydbkey)
				sys.exit(1)
		#finally, we look at our internal cache entry and return the requested data.
		returnme=[]
		for x in mylist:
			if self.auxcache[mycpv].has_key(x):
				returnme.append(self.auxcache[mycpv][x])
			else:
				returnme.append("")
		return returnme
		
	def cpv_exists(self,mykey):
		"Tells us whether an actual ebuild exists on disk (no masking)"
		cps2=mykey.split("/")
		cps=catpkgsplit(self.ctx, mykey,0)
		if not cps:
			#invalid cat/pkg-v
			return 0
		if self.oroot:
			if os.path.exists(self.oroot+"/"+cps[0]+"/"+cps[1]+"/"+cps2[1]+".ebuild") or os.path.exists(self.oroot+"/"+cps[0]+"/"+cps[1]+"/"+cps2[1]+".ebuild"):
				return 1
		elif os.path.exists(self.root+"/"+cps[0]+"/"+cps[1]+"/"+cps2[1]+".ebuild"):
			return 1
		return 0

	def cp_all(self):
		"returns a list of all keys in our tree"
		biglist=[]
		for x in self.ctx.get_categories():
			try:
				for y in listdir(self.ctx, self.root+"/"+x):
					if y=="CVS":
						continue
					biglist.append(x+"/"+y)
			except:
				#category directory doesn't exist
				pass
			if self.oroot:
				try:
					for y in listdir(self.ctx, self.oroot+"/"+x):
						if y=="CVS":
							continue
						mykey=x+"/"+y
						if not mykey in biglist:
							biglist.append(mykey)
				except:
					pass
		return biglist
	
	def p_list(self,mycp):
		returnme=[]
		try:
			for x in listdir(self.ctx, self.root+"/"+mycp):
				if x[-7:]==".ebuild":
					returnme.append(x[:-7])	
		except (OSError,IOError),e:
			pass
		if self.oroot:
			try:
				for x in listdir(self.ctx, self.oroot+"/"+mycp):
					if x[-7:]==".ebuild":
						mye=x[:-7]
						if not mye in returnme:
							returnme.append(mye)
			except (OSError,IOError),e:
				pass
		return returnme

	def cp_list(self,mycp):
		mysplit=mycp.split("/")
		returnme=[]
		try:
			for x in listdir(self.ctx, self.root+"/"+mycp):
				if x[-7:]==".ebuild":
					returnme.append(mysplit[0]+"/"+x[:-7])	
		except (OSError,IOError),e:
			pass
		if self.oroot:
			try:
				for x in listdir(self.ctx, self.oroot+"/"+mycp):
					if x[-7:]==".ebuild":
						mycp=mysplit[0]+"/"+x[:-7]
						if not mycp in returnme:
							returnme.append(mycp)
			except (OSError,IOError),e:
				pass
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
			mydep=dep_expand(self.ctx, origdep,self)
			mykey=dep_getkey(self.ctx, mydep)
	
		if level=="list-visible":
			#a list of all visible packages, not called directly (just by xmatch())
			#myval=self.visible(self.cp_list(mykey))
			myval=self.gvisible(self.visible(self.cp_list(mykey)))
		elif level=="bestmatch-visible":
			#dep match -- best match of all visible packages
			myval=best(self.ctx, self.xmatch("match-visible",None,mydep,mykey))
			#get all visible matches (from xmatch()), then choose the best one
		elif level=="bestmatch-list":
			#dep match -- find best match but restrict search to sublist 
			myval=best(self.ctx, self.match2(mydep,mykey,mylist))
			#no point is calling xmatch again since we're not caching list deps
		elif level=="match-list":
			#dep match -- find all matches but restrict search to sublist (used in 2nd half of visible())
			myval=self.match2(mydep,mykey,mylist)
		elif level=="match-visible":
			#dep match -- find all visible matches
			myval=self.match2(mydep,mykey,self.xmatch("list-visible",None,mydep,mykey))
			#get all visible packages, then get the matching ones
		elif level=="match-all":
			#match *all* visible *and* masked packages
			myval=self.match2(mydep,mykey,self.cp_list(mykey))
		else:
			print "ERROR: xmatch doesn't handle",level,"query!"
			raise KeyError
		if self.frozen and (level not in ["match-list","bestmatch-list"]):
			self.xcache[level][mydep]=myval
		return myval

	def match(self,mydep):
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
		cpv=catpkgsplit(self.ctx, mykey)
		if not cpv:
			#invalid cat/pkg-v
			print "visible(): invalid cat/pkg-v:",mykey
			return []
		mycp=cpv[0]+"/"+cpv[1]
		if self.ctx.get_mask_dict().has_key(mycp):
			for x in self.ctx.get_mask_dict()[mycp]:
				mymatches=self.xmatch("match-all",x)
				if mymatches==None:
					#error in package.mask file; print warning and continue:
					print "visible(): package.mask entry \""+x+"\" is invalid, ignoring..."
					continue
				for y in mymatches:
					while y in newlist:
						newlist.remove(y)
		if self.ctx.get_revmask_dict().has_key(mycp):
			for x in self.ctx.get_revmask_dict()[mycp]:
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
		if mylist==None:
			return []
		newlist=[]
		for mycpv in mylist:
			#we need to update this next line when we have fully integrated the new db api
			auxerr=0
			try:
				myaux=self.ctx.db["/"]["porttree"].dbapi.aux_get(mycpv, ["KEYWORDS"])
			except (KeyError,IOError):
				return []
			if not myaux[0]:
				# KEYWORDS=""
				#print "!!! No KEYWORDS for "+str(mycpv)+" -- Untested Status"
				continue
			mygroups=myaux[0].split()
			match=0
			for gp in mygroups:
				if gp=="*":
					match=1
					break
				elif "-"+gp in self.ctx.get_groups():
					match=0
					break
				elif gp in self.ctx.get_groups():
					match=1
					break
			if match:
				newlist.append(mycpv)
		return newlist

		
class binarytree(packagetree):
	"this tree scans for a list of all packages available in PKGDIR"
	def __init__(self, ctx, root="/", virtual=None, clone=None):
		self.ctx = ctx
		if clone:
			self.root=clone.root
			self.pkgdir=clone.pkgdir
			self.dbapi=clone.dbapi
			self.populated=clone.populated
			self.tree=clone.tree
		else:
			self.root=root
			self.pkgdir=self.ctx.settings["PKGDIR"]
			self.dbapi=fakedbapi(self.ctx)
			self.populated=0
			self.tree={}
	
	def populate(self):
		"populates the binarytree"
		if (not os.path.isdir(self.pkgdir)):
			return 0
		if (not os.path.isdir(self.pkgdir+"/All")):
			return 0
		for mypkg in listdir(self.ctx, self.pkgdir+"/All"):
			if mypkg[-5:]!=".tbz2":
				continue
			mytbz2=xpak.tbz2(self.pkgdir+"/All/"+mypkg)
			mycat=mytbz2.getfile("CATEGORY")
			if not mycat:
				#old-style or corrupt package
				continue
			mycat=string.strip(mycat)
			fullpkg=mycat+"/"+mypkg[:-5]
			mykey=dep_getkey(self.ctx, fullpkg)
			try:
				# invalid tbz2's can hurt things.
				self.dbapi.cpv_inject(fullpkg)
			except:
				continue
		self.populated=1

	def inject(self,cpv):
		return self.dbapi.cpv_inject(cpv)
	
	def exists_specific(self,cpv):
		if not self.populated:
			self.populate()
		return self.dbapi.match(dep_expand(self.ctx, "="+cpv,self.dbapi))

	def dep_bestmatch(self,mydep):
		"compatibility method -- all matches, not just visible ones"
		if not self.populated:
			self.populate()
		mydep=dep_expand(self.ctx, mydep,self.dbapi)
		mykey=dep_getkey(self.ctx, mydep)
		mymatch=best(self.ctx, self.dbapi.match2(mydep,mykey,self.dbapi.cp_list(mykey)))
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

class dblink:
	"this class provides an interface to the standard text package database"
	def __init__(self, ctx, cat,pkg,myroot):
		"create a dblink object for cat/pkg.  This dblink entry may or may not exist"
		self.logger = ctx.get_logger(self)
		self.ctx = ctx
		self.cat=cat
		self.pkg=pkg
		self.dbdir=myroot+"/var/db/pkg/"+cat+"/"+pkg
		self.myroot=myroot

	def getpath(self):
		"return path to location of db information (for >>> informational display)"
		return self.dbdir
	
	def exists(self):
		"does the db entry exist?  boolean."
		return os.path.exists(self.dbdir)
	
	def create(self):
		"create the skeleton db directory structure.  No contents, virtuals, provides or anything.  Also will create /var/db/pkg if necessary."
		if not os.path.exists(self.dbdir):
			os.makedirs(self.dbdir)
	
	def delete(self):
		"erase this db entry completely"
		if not os.path.exists(self.dbdir):
			return
		try:
			for x in listdir(self.ctx, self.dbdir):
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
		self.logger.debug("Getting CONTENTS for "+self.dbdir)
		if not os.path.exists(self.dbdir+"/CONTENTS"):
			return None
		pkgfiles={}
		myc=open(self.dbdir+"/CONTENTS","r")
		mylines=myc.readlines()
		myc.close()
		pos=1
		for line in mylines:
			self.logger.debug("read line: "+line)
			mydat=string.split(line)
			# we do this so we can remove from non-root filesystems
			# (use the ROOT var to allow maintenance on other partitions)
			try:
				mydat[1]=os.path.normpath(self.ctx.getRoot()+mydat[1][1:])
				if mydat[0]=="obj":
					#format: type, mtime, md5sum
					pkgfiles[string.join(mydat[1:-2]," ")]=[mydat[0], mydat[-1], mydat[-2]]
					self.logger.debug("(obj) pkgfiles['"+string.join(mydat[1:-2]," ")+"'] = ["+mydat[0]+","+mydat[-1]+","+mydat[2]+"]")
				elif mydat[0]=="dir":
					#format: type
					pkgfiles[string.join(mydat[1:])]=[mydat[0] ]
					self.logger.debug("(dir) pkgfiles['"+string.join(mydat[1:])+"'] = ["+mydat[0]+"]")
				elif mydat[0]=="sym":
					#format: type, mtime, dest
					x=len(mydat)-1
					splitter=-1
					while(x>=0):
						if mydat[x]=="->":
							splitter=x
							break
						x=x-1
					if splitter==-1:
						self.logger.error("can't find -> in sym entry, returning None")
						return None
					pkgfiles[string.join(mydat[1:splitter]," ")]=[mydat[0], mydat[-1], string.join(mydat[(splitter+1):-1]," ")]
					self.logger.debug("(obj) pkgfiles['"+string.join(mydat[1:splitter]," ")+"'] = ["+mydat[0]+","+mydat[-1]+","+string.join(mydat[(splitter+1):-1]," ")+"]")
				elif mydat[0]=="dev":
					#format: type
					pkgfiles[string.join(mydat[1:]," ")]=[mydat[0] ]
					self.logger.debug("(dev) pkgfiles['"+string.join(mydat[1:]," ")+"'] = ["+mydat[0]+"]")
				elif mydat[0]=="fif":
					#format: type
					pkgfiles[string.join(mydat[1:]," ")]=[mydat[0]]
					self.logger.debug("(dev) pkgfiles['"+string.join(mydat[1:]," ")+"'] = ["+mydat[0]+"]")
				else:
					self.logger.error("found unknown entry type ("+mydat[0]+"), returning None")
					return None
			except (KeyError,IndexError):
				self.logger.error("exception was thrown while handling line '"+line+"', file positon:",pos)
				print "portage: CONTENTS line",pos,"corrupt!"
			pos += 1
		return pkgfiles

	def updateprotect(self):
		#do some config file management prep
		self.protect=[]
		for x in string.split(self.ctx.settings["CONFIG_PROTECT"]):
			ppath=os.path.normpath(self.myroot+"/"+x)+"/"
			if os.path.isdir(ppath):
				self.protect.append(ppath)
			
		self.protectmask=[]
		for x in string.split(self.ctx.settings["CONFIG_PROTECT_MASK"]):
			ppath=os.path.normpath(self.myroot+"/"+x)+"/"
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

	def unmerge(self,pkgfiles=None,trimworld=1):
		if not pkgfiles:
			print "No package files given... Grabbing a set."
			pkgfiles=self.getcontents()
			if not pkgfiles:
				return
		#Now, don't assume that the name of the ebuild is the same as the name of the dir;
		#the package may have been moved.
		myebuildpath=None
		mystuff=listdir(self.ctx, self.dbdir)
		for x in mystuff:
			if x[-7:]==".ebuild":
				myebuildpath=self.dbdir+"/"+x
				break
		#do prerm script
		if myebuildpath and os.path.exists(myebuildpath):
			a=doebuild(self.ctx, myebuildpath,"prerm",self.myroot)

		mykeys=pkgfiles.keys()
		mykeys.sort()
		mykeys.reverse()

		self.updateprotect()

		#process symlinks second-to-last, directories last.
		mydirs=[]
		mysyms=[]
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
			if self.isprotected(obj):
				print "--- cfgpro "+str(pkgfiles[obj][0]), obj
				continue

			lstatobj=os.lstat(obj)
			lmtime=str(lstatobj[ST_MTIME])
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
				mymd5=perform_md5(self.ctx, obj, calc_prelink=1)
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
				if not S_ISFIFO(lstatobj[ST_MODE]):
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
				if listdir(self.ctx, obj):
					#we won't remove this directory (yet), continue
						pos += 1
						continue
				else:
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
		self.ctx.db[self.myroot]["vartree"].zap(self.cat+"/"+self.pkg)
		#remove stale virtual entries (mappings for packages that no longer exist)
		newvirts={}
		myvirts=grabdict(self.myroot+"var/cache/edb/virtuals")
		for myvirt in myvirts.keys():
			newvirts[myvirt]=[]
			for mykey in myvirts[myvirt]:
				if self.ctx.db[self.myroot]["vartree"].hasnode(mykey):
					newvirts[myvirt].append(mykey)
			if newvirts[myvirt]==[]:
				del newvirts[myvirt]
		writedict(newvirts,self.myroot+"var/cache/edb/virtuals")
	
		#new code to remove stuff from the world file when it's unmerged.
		if trimworld:
			worldlist=grabfile(self.myroot+"var/cache/edb/world")
			mycpv=self.cat+"/"+self.pkg
			mykey=cpv_getkey(self.ctx, mycpv)
			newworldlist=[]
			for x in worldlist:
				if dep_getkey(self.ctx, x)==mykey:
					matches=self.ctx.db[self.myroot]["vartree"].dbapi.match(x)
					if not matches:
						#zap our world entry
						pass
					elif (len(matches)==1) and (matches[0]==mycpv):
						#zap our world entry
						pass
					else:
						#others are around; keep it.
						newworldlist.append(x)
				else:
					#this doesn't match the package we're unmerging; keep it.
					newworldlist.append(x)
			myworld=open(self.myroot+"var/cache/edb/world","w")
			for x in newworldlist:
				myworld.write(x+"\n")
			myworld.close()

		#do original postrm
		if myebuildpath and os.path.exists(myebuildpath):
			a=doebuild(self.ctx, myebuildpath,"postrm",self.myroot)

	def treewalk(self,srcroot,destroot,inforoot,myebuild):
		# srcroot = ${D}; destroot=where to merge, ie. ${ROOT}, inforoot=root of db entry,
		# secondhand = list of symlinks that have been skipped due to their target not existing (will merge later),
		"this is going to be the new merge code"
		if not os.path.exists(self.dbdir):
			self.create()
		
		# before merging, it's *very important* to touch all the files
		# this ensures that their mtime is current and unmerging works correctly
		# spawn("(cd "+srcroot+"; for x in `find`; do  touch -c $x 2>/dev/null; done)",free=1)
		print ">>> Merging",self.cat+"/"+self.pkg,"to",destroot
		# get current counter value (counter_tick also takes care of incrementing it)
		counter=self.ctx.db[destroot]["vartree"].dbapi.counter_tick()
		# write local package counter for recording
		lcfile=open(inforoot+"/COUNTER","w")
		lcfile.write(str(counter))
		lcfile.close()
		# get old contents info for later unmerging
		oldcontents=self.getcontents()
		# run preinst script
		if myebuild:
			# if we are merging a new ebuild, use *its* pre/postinst rather than using the one in /var/db/pkg 
			# (if any).
			a=doebuild(self.ctx, myebuild,"preinst",self.ctx.getRoot())
		else:
			a=doebuild(self.ctx, inforoot+"/"+self.pkg+".ebuild","preinst",self.ctx.getRoot())
		# open CONTENTS file (possibly overwriting old one) for recording
		outfile=open(inforoot+"/CONTENTS","w")

		self.updateprotect()

		#if we have a file containing previously-merged config file md5sums, grab it.
		if os.path.exists(destroot+"/var/cache/edb/config"):
			cfgfiledict=grabdict(destroot+"/var/cache/edb/config")
		else:
			cfgfiledict={}
		if self.ctx.settings.has_key("NOCONFMEM"):
			cfgfiledict["IGNORE"]=1
		else:
			cfgfiledict["IGNORE"]=0

		# set umask to 0 for merging; back up umask, save old one in prevmask (since this is a global change)
		mymtime=long(time.time())
		prevmask=os.umask(0)
		secondhand=[]	
		# we do a first merge; this will recurse through all files in our srcroot but also build up a
		# "second hand" of symlinks to merge later
		if self.mergeme(srcroot,destroot,outfile,secondhand,"",cfgfiledict,mymtime):
			return 1
		# now, it's time for dealing our second hand; we'll loop until we can't merge anymore.	The rest are
		# broken symlinks.  We'll merge them too.
		lastlen=0
		while len(secondhand) and len(secondhand)!=lastlen:
			# clear the thirdhand.	Anything from our second hand that couldn't get merged will be
			# added to thirdhand.
			thirdhand=[]
			self.mergeme(srcroot,destroot,outfile,thirdhand,secondhand,cfgfiledict,mymtime)
			#swap hands
			lastlen=len(secondhand)
			# our thirdhand now becomes our secondhand.  It's ok to throw away secondhand since 
			# thirdhand contains all the stuff that couldn't be merged.
			secondhand=thirdhand
		if len(secondhand):
			# force merge of remaining symlinks (broken or circular; oh well)
			self.mergeme(srcroot,destroot,outfile,None,secondhand,cfgfiledict,mymtime)
		
		#restore umask
		os.umask(prevmask)
		#if we opened it, close it	
		outfile.close()
		print
		if (oldcontents):
			print ">>> Safely unmerging already-installed instance..."
			self.unmerge(oldcontents,trimworld=0)
			print ">>> original instance of package unmerged safely."	
		# copy "info" files (like SLOT, CFLAGS, etc.) into the database
		for x in listdir(self.ctx, inforoot):
			self.copyfile(inforoot+"/"+x)

		#write out our collection of md5sums
		if cfgfiledict.has_key("IGNORE"):
			del cfgfiledict["IGNORE"]
		writedict(cfgfiledict,destroot+"/var/cache/edb/config")
		
		#create virtual links
		myprovides=self.getelements("PROVIDE")
		if myprovides:
			myvkey=self.cat+"/"+pkgsplit(self.ctx, self.pkg)[0]
			myvirts=grabdict(destroot+"var/cache/edb/virtuals")
			for mycatpkg in self.getelements("PROVIDE"):
				if isspecific(self.ctx, mycatpkg):
					#convert a specific virtual like dev-lang/python-2.2 to dev-lang/python
					mysplit=catpkgsplit(self.ctx, mycatpkg)
					if not mysplit:
						print "treewalk(): skipping invalid PROVIDE entry:",mycatpkg
						continue
					mycatpkg=mysplit[0]+"/"+mysplit[1]
				if myvirts.has_key(mycatpkg):
					if myvkey not in myvirts[mycatpkg]:
						myvirts[mycatpkg][0:0]=[myvkey]
				else:
					myvirts[mycatpkg]=[myvkey]
			writedict(myvirts,destroot+"var/cache/edb/virtuals")
		
		#do postinst script
		if myebuild:
			# if we are merging a new ebuild, use *its* pre/postinst rather than using the one in /var/db/pkg 
			# (if any).
			a=doebuild(self.ctx, myebuild,"postinst",self.ctx.getRoot())
		else:
			a=doebuild(self.ctx, inforoot+"/"+self.pkg+".ebuild","postinst",self.ctx.getRoot())
	
		#update environment settings, library paths. DO NOT change symlinks.
		env_update(self.ctx, makelinks=0)
		print ">>>",self.cat+"/"+self.pkg,"merged."
		
	def mergeme(self,srcroot,destroot,outfile,secondhand,stufftomerge,cfgfiledict,thismtime):
		srcroot=os.path.normpath(srcroot)+"/"
		if srcroot[:2]=="//":
			srcroot=srcroot[1:]
		destroot=os.path.normpath(destroot)+"/"
		if destroot[:2]=="//":
			destroot=destroot[1:]
		# this is supposed to merge a list of files.  There will be 2 forms of argument passing.
		if type(stufftomerge)==types.StringType:
			#A directory is specified.  Figure out protection paths, listdir() it and process it.
			mergelist=listdir(self.ctx, srcroot+stufftomerge)
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
			mysrc=os.path.normpath(srcroot+offset+x)
			mydest=os.path.normpath(destroot+offset+x)
			# myrealdest is mydest without the $ROOT prefix (makes a difference if ROOT!="/")
			myrealdest="/"+offset+x
			# stat file once, test using S_* macros many times (faster that way)
			mystat=os.lstat(mysrc)
			mymode=mystat[ST_MODE]
			# handy variables; mydest is the target object on the live filesystems;
			# mysrc is the source object in the temporary install dir 
			try:
				mydmode=os.lstat(mydest)[ST_MODE]
			except:
				#dest file doesn't exist
				mydmode=None
			
			if S_ISLNK(mymode):
				# we are merging a symbolic link
				myabsto=abssymlink(mysrc)
				if myabsto[0:len(srcroot)]==srcroot:
					myabsto=myabsto[len(srcroot):]
					if myabsto[0]!="/":
						myabsto="/"+myabsto
				myto=os.readlink(mysrc)
				# myrealto contains the path of the real file to which this symlink points.
				# we can simply test for existence of this file to see if the target has been merged yet
				myrealto=os.path.normpath(os.path.join(destroot,myabsto))
				if mydmode!=None:
					#destination exists
					if (not S_ISLNK(mydmode)) and (S_ISDIR(mydmode)):
						# directory in the way: we can't merge a symlink over a directory
						print "!!!",mydest,"->",myto
						# we won't merge this, continue with next file...
						continue
				# if secondhand==None it means we're operating in "force" mode and should not create a second hand.
				if (secondhand!=None) and (not os.path.exists(myrealto)):
					# either the target directory doesn't exist yet or the target file doesn't exist -- or
					# the target is a broken symlink.  We will add this file to our "second hand" and merge
					# it later.
					secondhand.append(mysrc[len(srcroot):])
					continue
				# unlinking no longer necessary; "movefile" will overwrite symlinks atomically and correctly
				mymtime=movefile(mysrc,mydest,thismtime,mystat)
				if mymtime!=None:
					print ">>>",mydest,"->",myto
					outfile.write("sym "+myrealdest+" -> "+myto+" "+str(mymtime)+"\n")
				else:
					print "!!! Failed to move file."
					print "!!!",mydest,"->",myto
					sys.exit(1)
			elif S_ISDIR(mymode):
				# we are merging a directory
				if mydmode!=None:
					# destination exists
					if not os.access(mydest, os.W_OK):
						pkgstuff = pkgsplit(self.ctx, self.pkg)
						sys.stderr.write("\n!!! Cannot write to '"+mydest+"'.\n")
						sys.stderr.write("!!! Please check permissions and directories for broken symlinks.\n")
						sys.stderr.write("!!! You may start the merge process again by using ebuild:\n")
						sys.stderr.write("!!! ebuild "+self.ctx.settings["PORTDIR"]+"/"+self.cat+"/"+pkgstuff[0]+"/"+self.pkg+".ebuild merge\n")
						sys.stderr.write("!!! And finish by running this: env-update\n\n")
						return 1

					if S_ISLNK(mydmode) or S_ISDIR(mydmode):
						# a symlink to an existing directory will work for us; keep it:
						print "---",mydest+"/"
					else:
						# a non-directory and non-symlink-to-directory.  Won't work for us.  Move out of the way.
						movefile(mydest,mydest+".backup")
						print "bak",mydest,mydest+".backup"
						#now create our directory
						os.mkdir(mydest)
						os.chmod(mydest,mystat[0])
						os.chown(mydest,mystat[4],mystat[5])
						print ">>>",mydest+"/"
				else:
					#destination doesn't exist
					os.mkdir(mydest)
					os.chmod(mydest,mystat[0])
					os.chown(mydest,mystat[4],mystat[5])
					print ">>>",mydest+"/"
				outfile.write("dir "+myrealdest+"\n")
				# recurse and merge this directory
				if self.mergeme(srcroot,destroot,outfile,secondhand,offset+x+"/",cfgfiledict,thismtime):
					return 1
			elif S_ISREG(mymode):
				# we are merging a regular file
				mymd5=perform_md5(self.ctx, mysrc)
				# calculate config file protection stuff
				mydestdir=os.path.dirname(mydest)	
				moveme=1
				zing="!!!"
				if mydmode!=None:
					# destination file exists
					if S_ISDIR(mydmode):
						# install of destination is blocked by an existing directory with the same name
						moveme=0
						print "!!!",mydest
					elif S_ISREG(mydmode):
						cfgprot=0
						# install of destination is blocked by an existing regular file;
						# now, config file management may come into play.
						# we only need to tweak mydest if cfg file management is in play.
						if myppath:
							# we have a protection path; enable config file management.
							destmd5=perform_md5(self.ctx, mydest)
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
							pnum=-1
							# set pmatch to the literal filename only
							pmatch=os.path.basename(mydest)
							# config protection filename format:
							# ._cfg0000_foo
							# positioning (for reference):
							# 0123456789012
							mypfile=""
							for pfile in listdir(self.ctx, mydestdir):
								if pfile[0:5]!="._cfg":
									continue
								if pfile[10:]!=pmatch:
									continue
								try:
									newpnum=string.atoi(pfile[5:9])
									if newpnum>pnum:
										pnum=newpnum
									mypfile=pfile
								except:
									continue
							pnum=pnum+1
							# mypfile is set to the name of the most recent cfg management file currently on disk.
							# if their md5sums match, we overwrite the mypfile rather than creating a new .cfg file.
							# this keeps on-disk cfg management clutter to a minimum.
							cleanup=0
							if mypfile:
								pmd5=perform_md5(self.ctx, mydestdir+"/"+mypfile)
								if mymd5==pmd5:
									mydest=(mydestdir+"/"+mypfile)
									cleanup=1
							if not cleanup:
								# md5sums didn't match, so we create a new name for merging.
								# we now have pnum set to the official 4-digit config that
								# should be used for the file we need to install.  Set mydest
								# to this new value.
								mydest=os.path.normpath(mydestdir+"/._cfg"+string.zfill(pnum,4)+"_"+pmatch)
							# add to our md5 list for future reference
							# (will get written to /var/cache/edb/config)

				# whether config protection or not, we merge the new file the
				# same way.  Unless moveme=0 (blocking directory)
				if moveme:
					mymtime=movefile(mysrc,mydest,thismtime,mystat)
					zing=">>>"
				else:
					mymtime=thismtime
					# We need to touch the destination so that on --update the
					# old package won't yank the file with it. (non-cfgprot related)
					os.utime(myrealdest,(thismtime,thismtime))
					zing="---"
				if mymtime!=None:
					zing=">>>"
					outfile.write("obj "+myrealdest+" "+mymd5+" "+str(mymtime)+"\n")
				print zing,mydest
			else:
				# we are merging a fifo or device node
				zing="!!!"
				if mydmode==None:
					# destination doesn't exist
					if movefile(mysrc,mydest,thismtime,mystat)!=None:
						zing=">>>"
						if S_ISFIFO(mymode):
							# we don't record device nodes in CONTENTS,
							# although we do merge them.
							outfile.write("fif "+myrealdest+"\n")
				print zing+" "+mydest
	
	def merge(self,mergeroot,inforoot,myroot,myebuild=None):
		return self.treewalk(mergeroot,myroot,inforoot,myebuild)

	def getstring(self,name):
		"returns contents of a file with whitespace converted to spaces"
		if not os.path.exists(self.dbdir+"/"+name):
			return ""
		myfile=open(self.dbdir+"/"+name,"r")
		mydata=string.split(myfile.read())
		myfile.close()
		return string.join(mydata," ")
	
	def copyfile(self,fname):
		if not os.path.exists(self.dbdir):
			self.create()
		shutil.copyfile(fname,self.dbdir+"/"+os.path.basename(fname))
	
	def getfile(self,fname):
		if not os.path.exists(self.dbdir+"/"+fname):
			return ""
		myfile=open(self.dbdir+"/"+fname,"r")
		mydata=myfile.read()
		myfile.close()
		return mydata

	def setfile(self,fname,data):
		if not os.path.exists(self.dbdir):
			self.create()
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
		if not os.path.exists(self.dbdir):
			self.create()
		myelement=open(self.dbdir+"/"+ename,"w")
		for x in mylist:
			myelement.write(x+"\n")
		myelement.close()
	
	def isregular(self):
		"Is this a regular package (does it have a CATEGORY file?  A dblink can be virtual *and* regular)"
		return os.path.exists(self.dbdir+"/CATEGORY")


def cleanup_pkgmerge(ctx, mypkg,origdir):
	shutil.rmtree(ctx.settings["PORTAGE_TMPDIR"]+"/portage-pkg/"+mypkg)
	os.chdir(origdir)

def pkgmerge(ctx, mytbz2,myroot):
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
	tmploc=ctx.settings["PORTAGE_TMPDIR"]+"/portage-pkg/"
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
	print ">>> extracting",mypkg
	notok=spawn(ctx, "cat "+mytbz2+"| bzip2 -dq | tar xpf -",free=1)
	if notok:
		print "!!! Error extracting",mytbz2
		cleanup_pkgmerge(ctx, mypkg,origdir)
		return None
	# the merge takes care of pre/postinst and old instance
	# auto-unmerge, virtual/provides updates, etc.
	mylink=dblink(ctx, mycat,mypkg,myroot)
	if not mylink.exists():
		mylink.create()
		#shell error code
	mylink.merge(pkgloc,infloc,myroot,myebuild)
	if not os.path.exists(infloc+"/RDEPEND"):
		returnme=""
	else:
		#get runtime dependencies
		a=open(infloc+"/RDEPEND","r")
		returnme=string.join(string.split(a.read())," ")
		a.close()
	cleanup_pkgmerge(ctx, mypkg,origdir)
	return returnme






##
## Set up our context -- all data used by this instance should be inside this context!
##
## Eventually (after all global stuff is gone), this should be setup by main() and passed
## in parameters instead of being a global.
##
##ctx = PortageContext()


