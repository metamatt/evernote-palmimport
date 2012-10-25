"""
This is a setup.py script for py2exe

Usage:
    python setupWin.py py2exe
"""

from distutils.core import setup
import py2exe
import sys
sys.path.append('./evernote-sdk-python/lib')

APP = ['EvernotePalmMemoImporter.py']

OPTIONS = {
            "dll_excludes" : ["MSVCP90.dll"],                   # Force people to get this themselves
            "dist_dir" : "dist/EvernotePalmMemoImporter-Win32", # Keep files separate from the final dist directory
            "bundle_files" : 1                                 # Put dependencies in a single archive (library.zip by default, but see below)
          }

setup(
	windows = APP,
	zipfile = None,                                              # Instead of creating library.zip, bundle dependencies into main .exe
	options = {'py2exe' : OPTIONS},
)
