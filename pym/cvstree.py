# cvstree.py -- cvs tree utilities
# Copyright 1998-2003 Gentoo Technologies, Inc.
# Distributed under the GNU Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/cvstree.py,v 1.1 2003/04/02 07:28:42 carpaski Exp $

import string,os,time,sys
from stat import *

# [D]/Name/Version/Date/Flags/Tags

def fileat(entries, path):
	"""(entries,path)
	Returns the data(dict) for a specific file at the path specified."""
	mysplit=string.split(path,"/")
	myentries=entries
	myfile=mysplit[-1]
	mysplit=mysplit[:-1]
	for mys in mysplit:
		if myentries["dirs"].has_key(mys):
			myentries=myentries["dirs"][mys]
		else:
			return None
	return myentries["files"][myfile]

def findnew(entries,recursive=0,basedir=""):
	"""(entries,recursive=0,basedir="")
	Recurses the entries tree to find all elements that have been added but
	have not yet been committed. Returns a list of paths, optionally prepended
	with a basedir."""
	if basedir and basedir[-1]!="/":
		basedir=basedir+"/"
	mylist=[]
	for myfile in entries["files"].keys():
		if "cvs" in entries["files"][myfile]["status"]:
			if "0" == entries["files"][myfile]["revision"]:
				mylist.append(basedir+myfile)
	if recursive:
		for mydir in entries["dirs"].keys():
			mylist+=findnew(entries["dirs"][mydir],recursive,basedir+mydir)
	return mylist
					
def findchanged(entries,recursive=0,basedir=""):
	"""(entries,recursive=0,basedir="")
	Recurses the entries tree to find all elements that exist in the cvs tree
	and differ from the committed version. Returns a list of paths, optionally
	prepended with a basedir."""
	if basedir and basedir[-1]!="/":
		basedir=basedir+"/"
	mylist=[]
	for myfile in entries["files"].keys():
		if "cvs" in entries["files"][myfile]["status"]:
			if "current" not in entries["files"][myfile]["status"]:
				if "exists" in entries["files"][myfile]["status"]:
					if entries["files"][myfile]["revision"]!="0":
						mylist.append(basedir+myfile)
	if recursive:
		for mydir in entries["dirs"].keys():
			mylist+=findchanged(entries["dirs"][mydir],recursive,basedir+mydir)
	return mylist
	
def findmissing(entries,recursive=0,basedir=""):
	"""(entries,recursive=0,basedir="")
	Recurses the entries tree to find all elements that are listed in the cvs
	tree but do not exist on the filesystem. Returns a list of paths,
	optionally prepended with a basedir."""
	if basedir and basedir[-1]!="/":
		basedir=basedir+"/"
	mylist=[]
	for myfile in entries["files"].keys():
		if "cvs" in entries["files"][myfile]["status"]:
			if "exists" not in entries["files"][myfile]["status"]:
				mylist.append(basedir+myfile)
	if recursive:
		for mydir in entries["dirs"].keys():
			mylist+=findmissing(entries["dirs"][mydir],recursive,basedir+mydir)
	return mylist

def findunadded(entries,recursive=0,basedir=""):
	"""(entries,recursive=0,basedir="")
	Recurses the entries tree to find all elements that are in valid cvs
	directories but are not part of the cvs tree. Returns a list of paths,
	optionally prepended with a basedir."""
	if basedir and basedir[-1]!="/":
		basedir=basedir+"/"
	mylist=[]
	for myfile in entries["files"].keys():
		if "cvs" not in entries["files"][myfile]["status"]:
			mylist.append(basedir+myfile)
	if recursive:
		for mydir in entries["dirs"].keys():
			mylist+=findunadded(entries["dirs"][mydir],recursive,basedir+mydir)
	return mylist

def findall(entries, recursive=0, basedir=""):
	"""(entries,recursive=0,basedir="")
	Recurses the entries tree to find all new, changed, missing, and unadded
	entities. Returns a 4 element list of lists as returned from each find*()."""

	if basedir and basedir[-1]!="/":
		basedir=basedir+"/"
	mynew     = findnew(entries,recursive,basedir)
	mychanged = findchanged(entries,recursive,basedir)
	mymissing = findmissing(entries,recursive,basedir)
	myunadded = findunadded(entries,recursive,basedir)
	return [mynew, mychanged, mymissing, myunadded]

def getentries(mydir,recursive=0):
	"""(basedir,recursive=0)
	Scans the given directory and returns an datadict of all the entries in
	the directory seperated as a dirs dict and a files dict."""
	myfn=mydir+"/CVS/Entries"
	# entries=[dirs, files]
	entries={"dirs":{},"files":{}}
	if not os.path.exists(mydir):
		return entries
	try:
		myfile=open(myfn, "r")
		mylines=myfile.readlines()
		myfile.close()
	except:
		mylines=[]
	for line in mylines:
		if line and line[-1]=="\n":
			line=line[:-1]
		if not line:
			continue
		if line=="D": # End of entries file
			break
		mysplit=string.split(line, "/")
		if len(mysplit)!=6:
			print "Confused:",mysplit
			continue
		if mysplit[0]=="D":
			entries["dirs"][mysplit[1]]={"dirs":{},"files":{},"status":[]}
			entries["dirs"][mysplit[1]]["status"]=["cvs"]
			if os.path.isdir(mydir+"/"+mysplit[1]):
				entries["dirs"][mysplit[1]]["status"]+=["exists"]
				entries["dirs"][mysplit[1]]["flags"]=mysplit[2:]
				if recursive:
					rentries=getentries(mydir+"/"+mysplit[1],recursive)
					#print rentries.keys()
					#print entries["files"].keys()
					#print entries["files"][mysplit[1]]
					entries["dirs"][mysplit[1]]["dirs"]=rentries["dirs"]
					entries["dirs"][mysplit[1]]["files"]=rentries["files"]
		else:
			# [D]/Name/revision/Date/Flags/Tags
			entries["files"][mysplit[1]]={}
			entries["files"][mysplit[1]]["revision"]=mysplit[2]
			entries["files"][mysplit[1]]["date"]=mysplit[3]
			entries["files"][mysplit[1]]["flags"]=mysplit[4]
			entries["files"][mysplit[1]]["tags"]=mysplit[5]
			entries["files"][mysplit[1]]["status"]=["cvs"]
	for file in os.listdir(mydir):
		if file=="CVS":
			continue
		if file=="digest-framerd-2.4.3":
			print mydir,file
		if os.path.isdir(mydir+"/"+file):
			if not entries["dirs"].has_key(file):
				entries["dirs"][file]={"dirs":{},"files":{}}
			if entries["dirs"][file].has_key("status"):
				if "exists" not in entries["dirs"][file]["status"]:
					entries["dirs"][file]["status"]+=["exists"]
			else:
				entries["dirs"][file]["status"]=["exists"]
		elif os.path.isfile(mydir+"/"+file):
			if file=="digest-framerd-2.4.3":
				print "isfile"
			if not entries["files"].has_key(file):
				entries["files"][file]={"revision":"","date":"","flags":"","tags":""}
			if entries["files"][file].has_key("status"):
				if file=="digest-framerd-2.4.3":
					print "has status"
				if "exists" not in entries["files"][file]["status"]:
					if file=="digest-framerd-2.4.3":
						print "no exists in status"
					entries["files"][file]["status"]+=["exists"]
			else:
				if file=="digest-framerd-2.4.3":
					print "no status"
				entries["files"][file]["status"]=["exists"]
			try:
				if file=="digest-framerd-2.4.3":
					print "stat'ing"
				mystat=os.stat(mydir+"/"+file)
				mytime=time.asctime(time.gmtime(mystat[ST_MTIME]))
				if not entries["files"][file].has_key("status"):
					if file=="digest-framerd-2.4.3":
						print "status not set"
					entries["files"][file]["status"]=[]
				if file=="digest-framerd-2.4.3":
					print "date:",entries["files"][file]["date"]
					print "sdate:",mytime
				if mytime==entries["files"][file]["date"]:
					entries["files"][file]["status"]+=["current"]
				if file=="digest-framerd-2.4.3":
					print "stat done"
				
				del mystat
			except Exception, e:
				print "failed to stat",file
				print e
				return
				
		else:
			print
			print "File of unknown type:",mydir+"/"+file
			print
	return entries

#class cvstree:
#	def __init__(self,basedir):
#		self.refdir=os.cwd()
#		self.basedir=basedir
#		self.entries={}
#		self.entries["dirs"]={}
#		self.entries["files"]={}
#		self.entries["dirs"][self.basedir]=getentries(self.basedir)
#		self.getrealdirs(self.dirs, self.files)
#	def getrealdirs(self,dirs,files):
#		for mydir in dirs.keys():
#			list = os.listdir(
			
		