# portage_files.py -- access to files managed by portage...
# Copyright 1998-2003 Gentoo Technologies, Inc. and Authors
# Authors: Daniel Robbins, Nick Jones, Alain Penders
# Distributed under the GNU Public License v2


from stat import *
from commands import *
from select import *
from output import *
import string,os,types,sys,shlex,shutil,xpak,fcntl,signal,time,missingos,cPickle,atexit,grp,traceback,commands,pwd
import portage


#-----------------------------------------------------------------------------


class LastModifiedDB:
	"""This class handles storing, retreiving, and checking of last-modified times."""


	def __init__(self, ctx):
		self.ctx = ctx

		#grab mtimes for eclasses and upgrades
		self.mtimedb={}
		self.mtimedbkeys=["updates","eclass","packages","info","version","starttime","resume"]
		self.mtimedbfile=ctx.getRoot()+"var/cache/edb/mtimedb"
		try:
			self.mtimedb=cPickle.load(open(self.mtimedbfile))
			if self.mtimedb.has_key("old"):
				self.mtimedb["updates"]=self.mtimedb["old"]
				del self.mtimedb["old"]
			if self.mtimedb.has_key("cur"):
				del self.mtimedb["cur"]
		except:
			#print "!!!",e
			self.mtimedb={"updates":{},"eclass":{},"packages":[],"version":"","starttime":0}
		if self.mtimedb.has_key("version") and self.mtimedb["version"]!=portage.VERSION:
			self.remove_record("packages")
			self.remove_record("eclass")

		for x in self.mtimedb.keys():
			if x not in self.mtimedbkeys:
				print "Deleting invalid mtimedb key: "+str(x)
				del self.mtimedb[x]

		atexit.register(self.store_db)


	def remove_record(self, record):
		"""If it exists, remove the named record from the DB."""
		if self.mtimedb:
			if record in self.mtimedb.keys():
				del self.mtimedb[record]
				#print "self.mtimedb["+record+"] is cleared."
			else:
				print "Invalid or unset record '"+record+"' in mtimedb."


	def store_db(self):
		## ALAIN: FIX -- secpass, uid, and wheelgid should not be referenced like this!!!
		if portage.secpass:
			try:
				if self.mtimedb and not os.environ.has_key("SANDBOX_ACTIVE"):
					self.mtimedb["version"]=portage.VERSION
					cPickle.dump(self.mtimedb,open(self.mtimedbfile,"w"))
					print "*** Wrote out LastModifiedDB data successfully."
					os.chown(self.mtimedbfile,portage.uid,portage.wheelgid)
					os.chmod(self.mtimedbfile,0664)
			except Exception, e:
				pass


	def __getitem__(self,mykey):
		return self.mtimedb[mykey]

	def __setitem__(self,key,value):
		self.mtimedb[key]=value

	def __len__(self):
		return len(self.mtimedb)

	def __delitem__(self,key):
		del self.mtimedb[key]

	def has_key(self, key):
		return self.mtimedb.has_key(key)


