# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/ebuild/ebuild_package.py,v 1.3 2005/07/20 14:33:12 ferringb Exp $

import os
from portage import package
from conditionals import DepSet
from portage.package.atom import atom
#from portage.fetch import fetchable
#from digest import parse_digest
from portage.util.dicts import LazyValDict
from portage.restrictions.restriction import PackageRestriction, StrExactMatch
from portage.restrictions.restrictionSet import AndRestrictionSet, OrRestrictionSet

class EbuildPackage(package.metadata.package):

	def __getattr__(self, key):
		val = None
		if key == "path":
			val = os.path.join(self.__dict__["_parent"].base, self.category, self.package, \
				"%s-%s.ebuild" % (self.package, self.fullver))
		elif key == "_mtime_":
			#XXX wrap this.
			val = long(os.stat(self.path).st_mtime)
		elif key == "P":
			val = self.package + "-" + self.version
		elif key == "PN":
			val = self.package
		elif key == "PR":
			val = "-r"+str(self.revision)
		elif key in ("depends", "rdepends", "bdepends"):
			# drop the s, and upper it.
			val = DepSet(self.data[key.upper()[:-1]], atom)
		elif key == "uri":
			val = DepSet(self.data["SRC_URI"], str, operators={})
		elif key == "license":
			val = DepSet(self.data["LICENSE"], str)
		else:
			return super(EbuildPackage, self).__getattr__(key)
		self.__dict__[key] = val
		return val

	def _fetch_metadata(self):
#		import pdb;pdb.set_trace()
		data = self._parent._get_metadata(self)
		doregen = False
		if data == None:
			doregen = True

		# got us a dict.  yay.
		if not doregen:
			if self._mtime_ != data.get("_mtime_"):
				doregen = True
			elif data.get("_eclasses_") != None and not self._parent._ecache.is_eclass_data_valid(data["_eclasses_"]):
				doregen = True

		if doregen:
			# ah hell.
			data = self._parent._update_metadata(self)

#		for k,v in data.items():
#			self.__dict__[k] = v

#		self.__dict__["_finalized"] = True
		return data


class EbuildFactory(package.metadata.factory):
	child_class = EbuildPackage

	def __init__(self, parent, cachedb, eclass_cache, *args,**kwargs):
		super(EbuildFactory, self).__init__(parent, *args,**kwargs)
		self._cache = cachedb
		self._ecache = eclass_cache
		self.base = self._parent_repo.base

	def _get_metadata(self, pkg):
		if self._cache != None:
			try:
				return self._cache[pkg.cpvstr]
			except KeyError:
				pass
		return None

	def _update_metadata(self, pkg):

		import processor
		ebp=processor.request_ebuild_processor()
		mydata = ebp.get_keys(pkg, self._ecache)
		processor.release_ebuild_processor(ebp)

		mydata["_mtime_"] = pkg._mtime_
		if mydata.get("INHERITED", False):
			mydata["_eclasses_"] = self._ecache.get_eclass_data(mydata["INHERITED"].split() )
			del mydata["INHERITED"]
		else:
			mydata["_eclasses_"] = {}

		if self._cache != None:
			self._cache[pkg.cpvstr] = mydata

		return mydata


class ConfiguredEbuild(package.metadata.package):

	def __init__(self, pkg, use_flags):
		self.__dict__["use"] = dict(zip(use_flags, [True]*len(use_flags)))
		self.__dict__["pkg"] = pkg


	def __getattr__(self, attr):
		if attr in ("depends", "rdepends", "bdepends", "uri", "license", "restrict"):
			val = getattr(self.pkg, attr).evaluate_depset(self.use)
		else:
			return getattr(self.pkg, attr)
		self.__dict__[attr] = val
		return val
