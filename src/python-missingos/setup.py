#! /usr/bin/env python2.2
# $Header: /local/data/ulm/cvs/history/var/cvsroot/gentoo-src/portage/src/python-missingos/setup.py,v 1.5 2003/03/22 14:24:38 carpaski Exp $

from os import chdir, stat
from distutils.core import setup, Extension

setup (# Distribution meta-data
        name = "python-missingos",
        version = "0.2",
        description = "",
        author = "Jonathon D Nelson",
        author_email = "jnelson@gentoo.org",
       	license = "",
        long_description = \
         '''''',
        ext_modules = [ Extension(
                            "missingos",
                            ["missingos.c"],
                            libraries=[],
                        ) 
                      ],
        url = "",
      )

