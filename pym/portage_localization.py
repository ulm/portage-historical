# portage_localization.py -- Code to manage/help portage localization.
# Copyright 2004 Gentoo Foundation
# Distributed under the terms of the GNU General Public License v2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/portage_localization.py,v 1.3 2005/02/26 06:35:20 jstubbs Exp $
cvs_id_string="$Id: portage_localization.py,v 1.3 2005/02/26 06:35:20 jstubbs Exp $"[5:-2]


# We define this to make the transition easier for us.
def _(mystr):
	return mystr


def localization_example():
	# Dict references allow translators to rearrange word order.
	print _("You can use this string for translating.")
	print _("Strings can be formatted with %(mystr)s like this.") % {"mystr": "VALUES"}

	a_value = "value.of.a"
	b_value = 123
	c_value = [1,2,3,4]
	print _("A: %(a)s -- B: %(b)s -- C: %(c)s") % {"a":a_value,"b":b_value,"c":c_value}

