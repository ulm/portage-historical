# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/repository/visibility.py,v 1.2 2005/07/13 05:51:35 ferringb Exp $

# icky.
# ~harring
import prototype, errors

class filterTreee(prototype.tree):
	"""wrap an existing repository filtering results based upon passed in restrictions."""
	def __init__(self, repo, restrictions):
		self.raw_repo = repo
		if not isinstance(self.raw_repo, prototype.tree):
			raise errors.InitializationError("%s is not a repository tree derivative" % str(self.raw_repo))
		if not isinstance(restrictions, list):
			restrictions = [restrictions]
		self._restrictions = restrictions

	def itermatch(self, atom):
		for cpv in self.raw_repo.itermatch(atom):
			for r in self._restrictions:
				if not r.match(cpv):
					yield cpv