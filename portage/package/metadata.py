# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/package/metadata.py,v 1.2 2005/07/13 05:51:35 ferringb Exp $

import weakref
from cpv import CPV

class package(CPV):
	def __init__(self, cpv, parent_repository):
		super(package,self).__init__(cpv)
		self.__dict__["_cpv_finalized"] = False
#		self.__dict__["_finalized"] = False
		self.__dict__["_parent"] = parent_repository
        

	def __setattr__(self, *args, **kwargs):
		raise AttributeError


	def __delattr__(self, *args, **kwargs):
		raise AttributeError


	def __getitem__(self, key):
		try:	return getattr(self,key)
		except AttributeError:
			raise KeyError(key)


	def __getattr__(self, attr):
		if not self._cpv_finalized:
			try:	return super(package,self).__getattr__(attr)
			except AttributeError:	
				#enable this when CPV does it.
				#self.__cpv_finalized = True
				pass

		# assuming they're doing super, if it ain't data it's an error (no other jit attr)
		if attr != "data":
			raise AttributeError, attr
#		if self._finalized:
#			raise AttributeError, attr

		# if we've made it here, then more is needed.
		data = self._fetch_metadata()
		self.__dict__["data"] = data
		return data

#		self.__dict__["_finalized"] = True
#		if attr in self.__dict__:
#			return self.__dict__[attr]
#		raise AttributeError,attr


	def _fetch_metadata(self):
		raise NotImplementedError


class factory(object):
	child_class = package
	def __init__(self, parent_repo):
		self._parent_repo = parent_repo
		self._cached_instances = weakref.WeakValueDictionary()
	
	def new_package(self, cpv):
		if cpv in self._cached_instances:
			return self._cached_instances[cpv]
		d = self._get_new_child_data(cpv)
		m = self.child_class(cpv, self, *d[0], **d[1])
		self._cached_instances[cpv] = m
		return m

	def clear(self):
		self._cached_instances.clear()

	def _load_package_metadata(self, inst):
		raise NotImplementedError

	def __del__(self):
		self.clear()

	def _get_metadata(self, *args):
		raise NotImplementedError

	def _update_metadata(self, *args):
		raise NotImplementedError

	def _get_new_child_data(self, cpv):
		"""return pargs,kwargs for any new children generated by this factory.
		defaults to [], {}
		Probably will be rolled into a class/instance attribute whenever someone cleans this up"""
		return ([],{})