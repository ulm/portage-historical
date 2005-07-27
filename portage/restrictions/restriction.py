# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/restrictions/restriction.py,v 1.4 2005/07/27 02:26:49 ferringb Exp $

import re, logging

class base(object):
	"""base restriction matching object; overrides setattr to provide the usual write once trickery
	all derivatives *must* be __slot__ based"""

	__slots__ = ["negate"]

	def __init__(self, negate=False):
		self.negate = negate

#	def __setattr__(self, name, value):
#		import traceback;traceback.print_stack()
#		object.__setattr__(self, name, value)
#		try:	getattr(self, name)
#			
#		except AttributeError:
#			object.__setattr__(self, name, value)
#		else:	raise AttributeError

	def match(self, *arg, **kwargs):
		raise NotImplementedError

	def intersect(self, other):
		raise NotImplementedError

class AlwaysBoolMatch(base):
	__slots__ = base.__slots__
	def match(self, *a, **kw):
		return self.negate

AlwaysFalse = AlwaysBoolMatch(False)
AlwaysTrue  = AlwaysBoolMatch(True)


class VersionRestriction(base):
	"""use this as base for version restrictions, gives a clue to what the restriction does"""
	pass


class StrMatch(base):
	""" Base string matching restriction.  all derivatives must be __slot__ based classes"""
	__slots__ = ["flags"] + base.__slots__
	pass


class StrRegexMatch(StrMatch):
	#potentially redesign this to jit the compiled_re object
	__slots__ = tuple(["regex", "compiled_re"] + StrMatch.__slots__)

	def __init__(self, regex, CaseSensitive=True, **kwds):
		super(StrRegexMatch, self).__init__(**kwds)
		self.regex = regex
		flags = 0
		if not CaseSensitive:
			flags = re.I
		self.flags = flags
		self.compiled_re = re.compile(regex, flags)


	def match(self, value):
		return (self.compiled_re.match(str(value)) != None) ^ self.negate


	def intersect(self, other):
		if self.regex == other.regex and self.negate == other.negate and self.flags == other.flags:
			return self
		return None


class StrExactMatch(StrMatch):
	__slots__ = tuple(["exact", "flags"] + StrMatch.__slots__)

	def __init__(self, exact, CaseSensitive=True, **kwds):
		super(StrExactMatch, self).__init__(**kwds)
		if not CaseSensitive:
			self.flags = re.I
			self.exact = str(exact).lower()
		else:
			self.flags = 0
			self.exact = str(exact)


	def match(self, value):
		if self.flags & re.I:	return (self.exact == str(value).lower()) ^ self.negate
		else:			return (self.exact == str(value)) ^ self.negate


	def intersect(self, other):
		s1, s2 = self.exact, other.exact
		if other.flags and not self.flags:
			s1 = s1.lower()
		elif self.flags and not other.flags:
			s2 = s2.lower()
		if s1 == s2 and self.negate == other.negate:
			if other.flags:
				return other
			return self
		return None


class StrSubstringMatch(StrMatch):
	__slots__ = tuple(["substr"] + StrMatch.__slots__)

	def __init__(self, substr, CaseSensitive=True, **kwds):
		super(StrSubString, self).__init__(**kwds)
		if not CaseSensitive:
			self.flags = re.I
			self.substr = str(substr).lower()
		else:
			self.flags = 0
			self.substr = str(substr)


	def match(self, value):
		if self.flags & re.I:	value = str(value).lower()
		else:			value = str(value)
		return (value.find(self.substr) != -1) ^ self.negate


	def intersect(self, other):
		if self.negate == other.negate:
			if self.substr == other.substr and self.flags == other.flags:
				return self
		else:
			return None
		s1, s2 = self.substr, other.substr
		if other.flags and not self.flags:
			s1 = s1.lower()
		elif self.flags and not other.flags:
			s2 = s2.lower()
		if s1.find(s2) != -1:
			return self
		elif s2.find(s1) != -1:
			return other
		return None			


class StrGlobMatch(StrMatch):
	__slots__ = tuple(["glob"] + StrMatch.__slots__)
	def __init__(self, glob, CaseSensitive=True, **kwds):
		super(StrGlobMatch, self).__init__(**kwds)
		if not CaseSensitive:
			self.flags = re.I
			self.glob = str(glob).lower()
		else:
			self.flags = 0
			self.glob = str(glob)


	def match(self, value):
		value = str(value)
		if self.flags & re.I:	value = value.lower()
		return value.startswith(self.glob) ^ self.negate


	def intersect(self, other):
		if self.match(other.glob):
			if self.negate == other.negate:
				return other
		elif other.match(self.glob):
			if self.negate == other.negate:
				return self
		return None


class PackageRestriction(base):
	"""cpv data restriction.  Inherit for anything that's more then cpv mangling please"""

	__slots__ = tuple(["attr", "strmatch"] + base.__slots__)

	def __init__(self, attr, StrMatchInstance, **kwds):
		super(PackageRestriction, self).__init__(**kwds)
		self.attr = attr.split(".")
		self.strmatch = StrMatchInstance

	def match(self, packageinstance):
		try:
			o = packageinstance
			for x in self.attr:
				o = getattr(o, x)
			return self.strmatch.match(o) ^ self.negate

		except AttributeError,ae:
			logging.debug("failed getting attribute %s from %s, exception %s" % \
				(".".join(self.attr), str(packageinstance), str(ae)))
			return self.negate


	def intersect(self, other):
		if self.negate != other.negate or self.attr != other.attr:
			return None
		if isinstance(self.strmatch, other.strmatch.__class__):
			s = self.strmatch.intersect(other.strmatch)
		elif isinstance(other.strmatch, self.strmatch.__class__):
			s = other.strmatch.intersect(self.strmatch)
		else:	return None
		if s == None:
			return None
		if s == self.strmatch:		return self
		elif s == other.strmatch:	return other

		# this can probably bite us in the ass self or other is a derivative, and the other isn't.
		return self.__class__(self.attr, s)
