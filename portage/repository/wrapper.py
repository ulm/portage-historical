# Copyright: 2005 Gentoo Foundation
# Author(s): Brian Harring (ferringb@gentoo.org)
# License: GPL2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/portage/repository/wrapper.py,v 1.1 2005/08/09 08:01:11 ferringb Exp $

# icky.
# ~harring
import prototype, errors

class wrapperTree(prototype.tree):
	"""wrap an existing repository filtering results based upon passed in restrictions."""
	def __init__(self, repo, package_class):
		self.raw_repo = repo
		if not isinstance(self.raw_repo, prototype.tree):
			raise errors.InitializationError("%s is not a repository tree derivative" % str(self.raw_repo))
		self.package_class = package_class
