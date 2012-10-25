"""
This is a setup.py script for both py2app and py2exe

Usage (to generate Mac .app):
    python setup.py py2app
Usage (to generate Windows .exe):
    python setup.py py2exe
"""

import platform
import sys
sys.path.append('./evernote-sdk-python/lib')

if platform.system() == 'Darwin':
	from setuptools import setup
else:
	from distutils.core import setup
	import py2exe


APP = ['EvernotePalmMemoImporter.py']

if platform.system() == 'Darwin':
	PLIST = {
		'CFBundleIdentifier' : 'com.maddogsw.evernote-palm-importer',
		'CFBundleShortVersionString': '1.2.0'
	}
	OPTIONS = {
		'argv_emulation': True,
		'plist': PLIST
	}

	setup(app = APP,
	      options = {'py2app': OPTIONS},
	      setup_requires = ['py2app'])
else:
	OPTIONS = {
		"dll_excludes" : ["MSVCP90.dll"],                   # Force people to get this themselves
		"dist_dir" : "dist/EvernotePalmMemoImporter-Win32", # Keep files separate from the final dist directory
		"bundle_files" : 1                                  # Put dependencies in a single archive (library.zip by default, but see below)
	}

	setup(windows = APP,
		  zipfile = None,                                   # Instead of creating library.zip, bundle dependencies into main .exe
		  options = {'py2exe' : OPTIONS})
