#!/usr/bin/python -O
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/pym/Attic/portage_db_test.py,v 1.2 2004/03/22 01:40:58 carpaski Exp $

import portage
import portage_db_template
import portage_db_anydbm
import portage_db_flat
import portage_db_cpickle

import os

uid = os.getuid()
gid = os.getgid()

portage_db_template.test_database(portage_db_flat.database,"/var/cache/edb/dep",   "sys-apps",portage.auxdbkeys,uid,gid)
portage_db_template.test_database(portage_db_cpickle.database,"/var/cache/edb/dep","sys-apps",portage.auxdbkeys,uid,gid)
portage_db_template.test_database(portage_db_anydbm.database,"/var/cache/edb/dep", "sys-apps",portage.auxdbkeys,uid,gid)

