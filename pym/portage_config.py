# portage.py -- core Portage functionality 
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


class config:
	def __init__(self, ctx):
		self.ctx = ctx

		self.usesplit=[]
		self.cexpand={}

		self.usemask=[]
		self.configlist=[]
		self.backupenv={}
		# back up our incremental variables:
		self.configdict={}
		# configlist will contain: [ globals, (optional) profile, make.conf, backupenv (incrementals), origenv ]

		#get the masked use flags
		if os.path.exists("/etc/make.profile/use.mask"):
			self.usemask=grabfile("/etc/make.profile/use.mask")
		if os.path.exists("/etc/portage/use.mask"):
			self.usemask=self.usemask+grabfile("/etc/portage/use.mask")

		self.mygcfg=self.getconfig("/etc/make.globals")
		if self.mygcfg==None:
			print "!!! Parse error in /etc/make.globals. NEVER EDIT THIS FILE."
			print "!!! Incorrect multiline literals can cause this. Do not use them."
			print "!!! Errors in this file should be reported on bugs.gentoo.org."
			sys.exit(1)
		self.configlist.append(self.mygcfg)
		self.configdict["globals"]=self.configlist[-1]

		# Does /etc/make.profile/make.defaults exist?
		if self.ctx.getProfileDir():
			self.mygcfg=self.getconfig("/etc/make.profile/make.defaults")
			if self.mygcfg==None:
				print "!!! Parse error in /etc/make.defaults. Never modify this file."
				print "!!! 'emerge sync' may fix this. If it does not then please report"
				print "!!! this to bugs.gentoo.org and, if possible, a dev on #gentoo (IRC)"
				sys.exit(1)
			self.configlist.append(self.mygcfg)
			self.configdict["defaults"]=self.configlist[-1]

		self.mygcfg=self.getconfig("/etc/make.conf")
		if self.mygcfg==None:
			print "!!! Parse error in /etc/make.conf."
			print "!!! Incorrect multiline literals can cause this. Do not use them."
			sys.exit(1)
		self.configlist.append(self.mygcfg)
		self.configdict["conf"]=self.configlist[-1]

		for x in self.ctx.getIncrementals():
			if os.environ.has_key(x):
				self.backupenv[x]=os.environ[x]
		#auto-use:
		self.configlist.append({})
		self.configdict["auto"]=self.configlist[-1]
		#backup-env (for recording our calculated incremental variables:)
		self.configlist.append(self.backupenv)
		self.configlist.append(os.environ.copy())
		self.configdict["env"]=self.configlist[-1]
		self.lookuplist=self.configlist[:]
		self.lookuplist.reverse()
	
		useorder=self["USE_ORDER"]
		if not useorder:
			#reasonable defaults; this is important as without USE_ORDER, USE will always be "" (nothing set)!
			useorder="env:conf:auto:defaults"
		usevaluelist=useorder.split(":")
		self.uvlist=[]
		for x in usevaluelist:
			if self.configdict.has_key(x):
				#prepend db to list to get correct order
				self.uvlist[0:0]=[self.configdict[x]]		
		self.regenerate()
	
	def regenerate(self,useonly=0):
		if useonly:
			myincrementals=["USE"]
		else:
			myincrementals=self.ctx.getIncrementals()
		for mykey in myincrementals:
			if mykey=="USE":
				mydbs=self.uvlist
				self.configdict["auto"]["USE"]=self.autouse(self.ctx.db[self.ctx.getRoot()]["vartree"])
			else:
				mydbs=self.configlist[:-1]
			mysetting=[]
			for curdb in mydbs:
				if not curdb.has_key(mykey):
					continue
				#variables are already expanded
				mysplit=curdb[mykey].split()
				for x in mysplit:
					if x=="-*":
						# "-*" is a special "minus" var that means "unset all settings".  so USE="-* gnome" will have *just* gnome enabled.
						mysetting=[]
						continue
					add=x
					if x[0]=="-":
						remove=x[1:]
					else:
						remove=x
					#remove any previous settings of this variable
					dellist=[]
					for y in range(0,len(mysetting)):
						if mysetting[y]==remove:
							#we found a previously-defined variable; add it to our dellist for later removal.
							dellist.append(mysetting[y])
					for y in dellist:
						while y in mysetting:
							mysetting.remove(y)
					#now append our new setting
					if add:
						mysetting.append(add)
			#store setting in last element of configlist, the original environment:
			self.configlist[-1][mykey]=string.join(mysetting," ")
		#cache split-up USE var in a global
		self.usesplit=[]
		for x in string.split(self.configlist[-1]["USE"]):
			if x not in self.usemask:
				self.usesplit.append(x)
		
		# Pre-Pend ARCH variable to USE settings so '-*' in env doesn't kill arch.
		if self.ctx.getProfileDir():
			if self.configdict["defaults"].has_key("ARCH"):
				if self.configdict["defaults"]["ARCH"]:
					if self.configdict["defaults"]["ARCH"] not in self.usesplit:
						self.usesplit.insert(0,self.configdict["defaults"]["ARCH"])
						self.configlist[-1]["USE"]=string.join(self.usesplit," ")

	def getUseSplit(self):
		return self.usesplit
	
	def __getitem__(self,mykey):
		if mykey=="CONFIG_PROTECT_MASK":
			suffix=" /etc/env.d"
		else:
			suffix=""
		for x in self.lookuplist:
			if x == None:
				print "!!! lookuplist is null."
			elif x.has_key(mykey):
				return x[mykey]+suffix
		return suffix

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
		self.configdict["env"][mykey]=myvalue
	
	def reset(self):
		"reset environment to original settings"
		#for x in self.backupenv.keys():
		#	self.configdict["env"][x]==self.backupenv[x]
		#self.regenerate(useonly=1)
		pass

	def environ(self):
		"return our locally-maintained environment"
		mydict={}
		for x in self.keys(): 
			mydict[x]=self[x]
		if not mydict.has_key("HOME") and mydict.has_key("BUILD_PREFIX"):
			print "*** HOME not set. Setting to",mydict["BUILD_PREFIX"]
			mydict["HOME"]=mydict["BUILD_PREFIX"]
		return mydict

	def getconfig(self, mycfg, tolerant=0):
		mykeys={}
		f=open(mycfg,'r')
		lex=shlex.shlex(f)
		lex.wordchars=string.digits+string.letters+"~!@#$%*_\:;?,./-+{}"     
		lex.quotes="\"'"
		while 1:
			key=lex.get_token()
			if (key==''):
				#normal end of file
				break;
			equ=lex.get_token()
			if (equ==''):
				#unexpected end of file
				#lex.error_leader(self.filename,lex.lineno)
				if not tolerant:
					print "!!! Unexpected end of config file: variable",key
					return None
				else:
					return mykeys
			elif (equ!='='):
				#invalid token
				#lex.error_leader(self.filename,lex.lineno)
				if not tolerant:
					print "!!! Invalid token (not \"=\")",equ
					return None
				else:
					return mykeys
			val=lex.get_token()
			if (val==''):
				#unexpected end of file
				#lex.error_leader(self.filename,lex.lineno)
				if not tolerant:
					print "!!! Unexpected end of config file: variable",key
					return None
				else:
					return mykeys
			mykeys[key]=self.varexpand(val,mykeys)
		return mykeys

	def varexpand(self, mystring, mydict={}):
		try:
			return self.cexpand[" "+mystring]
		except KeyError:
			pass
		"""
		new variable expansion code.  Removes quotes, handles \n, etc.
		This code is used by the configfile code, as well as others (parser)
		This would be a good bunch of code to port to C.
		"""
		numvars=0
		mystring=" "+mystring
		#in single, double quotes
		insing=0
		indoub=0
		pos=1
		newstring=" "
		while (pos<len(mystring)):
			if (mystring[pos]=="'") and (mystring[pos-1]!="\\"):
				if (indoub):
					newstring=newstring+"'"
				else:
					insing=not insing
				pos=pos+1
				continue
			elif (mystring[pos]=='"') and (mystring[pos-1]!="\\"):
				if (insing):
					newstring=newstring+'"'
				else:
					indoub=not indoub
				pos=pos+1
				continue
			if (not insing): 
				#expansion time
				if (mystring[pos]=="\n"):
					#convert newlines to spaces
					newstring=newstring+" "
					pos=pos+1
				elif (mystring[pos]=="\\"):
					#backslash expansion time
					if (pos+1>=len(mystring)):
						newstring=newstring+mystring[pos]
						break
					else:
						a=mystring[pos+1]
						pos=pos+2
						if a=='a':
							newstring=newstring+chr(007)
						elif a=='b':
							newstring=newstring+chr(010)
						elif a=='e':
							newstring=newstring+chr(033)
						elif (a=='f') or (a=='n'):
							newstring=newstring+chr(012)
						elif a=='r':
							newstring=newstring+chr(015)
						elif a=='t':
							newstring=newstring+chr(011)
						elif a=='v':
							newstring=newstring+chr(013)
						else:
							#remove backslash only, as bash does: this takes care of \\ and \' and \" as well
							newstring=newstring+mystring[pos-1:pos]
							continue
				elif (mystring[pos]=="$") and (mystring[pos-1]!="\\"):
					pos=pos+1
					if (pos+1)>=len(mystring):
						self.cexpand[mystring]=""
						return ""
					if mystring[pos]=="{":
						pos=pos+1
						terminus="}"
					else:
						terminus=string.whitespace
					myvstart=pos
					while mystring[pos] not in terminus:
						if (pos+1)>=len(mystring):
							self.cexpand[mystring]=""
							return ""
						pos=pos+1
					myvarname=mystring[myvstart:pos]
					pos=pos+1
					if len(myvarname)==0:
						self.cexpand[mystring]=""
						return ""
					numvars=numvars+1
					if mydict.has_key(myvarname):
						newstring=newstring+mydict[myvarname] 
				else:
					newstring=newstring+mystring[pos]
					pos=pos+1
			else:
				newstring=newstring+mystring[pos]
				pos=pos+1
		if numvars==0:
			self.cexpand[mystring]=newstring[1:]
		return newstring[1:]	

	def autouse(self, myvartree):
		"""returns set of USE variables auto-enabled due to packages being installed"""
		myusevars=""
		for x in self.ctx.getUseDefaults():
			mysplit=string.split(x)
			if len(mysplit)<2:
				#invalid line
				continue
			myuse=mysplit[0]
			mydep=x[len(mysplit[0]):]
			#check dependencies; tell depcheck() to ignore settings["USE"] since we are still forming it.
			myresult=portage.dep_check(mydep,myvartree.dbapi,use="no")
			if myresult[0]==1 and not myresult[1]:
				#deps satisfied, add USE variable...
				myusevars=myusevars+" "+myuse
		return myusevars

