"""
This is a setup.py script for py2exe

Usage:
    python setupWin.py py2exe
"""

from distutils.core import setup
import py2exe

APP = ['EvernotePalmMemoImporter.py']

# I haven't figured out how to get this to find the dependent libraries in ./libs, via any of the following:
#
#   DATA_FILES = ['en_palmimport.py', 'EvernoteManager.py', 'PalmDesktopNoteParser.py', 'lib']
#   PACKAGES = ['evernote.edam.notestore.NoteStore', 'evernote.edam.type.ttypes', 'evernote.edam.userstore.UserStore', 'evernote.edam.userstore.constants', 'thrift.protocol.TBinaryProtocol', 'thrift.transport.THttpClient']
#   PACKAGES = ['lib']
#
# It works fine without any of that if the Evernote and Thrift librares are in the Python install directory.

OPTIONS = {
            "dll_excludes" : ["MSVCP90.dll"],                   # Force people to get this themselves
            "dist_dir" : "dist/EvernotePalmMemoImporter-Win32", # Keep files separate from the final dist directory
            "bundle_files" : 1,                                 # Put everything in library.zip
           	#"packages" : PACKAGES,
           	#"includes" : ['lib.evernote.edam.type.ttypes'],
          }

setup(
	windows = APP,
    zipfile = "EvernotePalmMemoImporterLibs.zip",               # Except don't call it library.zip 
	#data_files = DATA_FILES,
	options = {'py2exe' : OPTIONS},
)
