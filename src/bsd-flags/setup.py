#! /usr/bin/env python
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/src/bsd-flags/setup.py,v 1.2 2005/02/26 07:23:49 jstubbs Exp $

from os import chdir, stat
from distutils.core import setup, Extension

setup (# Distribution meta-data
        name = "bsd-chflags",
        version = "0.1",
        description = "",
        author = "Stephen Bennett",
        author_email = "spb@gentoo.org",
       	license = "",
        long_description = \
         '''''',
        ext_modules = [ Extension(
                            "chflags",
                            ["chflags.c"],
                            libraries=[],
                        ) 
                      ],
        url = "",
      )

