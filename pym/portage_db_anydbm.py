# Copyright 2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/Attic/portage_db_anydbm.py,v 1.9 2004/10/04 14:07:40 vapier Exp $

import anydbm,cPickle,types,os

import portage_db_template

class database(portage_db_template.database):
	def module_init(self):
		prevmask=os.umask(0)
		if not os.path.exists(self.path):
			current_path="/"
			for mydir in self.path.split("/"):
				current_path += "/"+mydir
				if not os.path.exists(current_path):
					os.mkdir(current_path)

		self.filename = self.path + "/" + self.category + ".anydbm"
		
		try:
			# open it read/write
			self.db = anydbm.open(self.filename, "c", 0664)
		except:
			# Create a new db... DB type not supported anymore?
			self.db = anydbm.open(self.filename, "n", 0664)

		os.umask(prevmask)

	def has_key(self,key):
		self.check_key(key)
		if self.db.has_key(key):
			return 1
		return 0
		
	def keys(self):
		return self.db.keys()
	
	def get_values(self,key):
		self.check_key(key)
		if self.db.has_key(key):
			myval = cPickle.loads(self.db[key])
			return myval
		return None
	
	def set_values(self,key,val):
		self.check_key(key)
		self.db[key] = cPickle.dumps(val)
	
	def del_key(self,key):
		if self.has_key(key):
			del self.db[key]
			return True
		return False
			
	def sync(self):
		self.db.sync()
	
	def close(self):
		self.db.close()
	
