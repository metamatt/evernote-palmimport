"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup
import sys
sys.path.append('./evernote-sdk-python/lib')

APP = ['EvernotePalmMemoImporter.py']
PLIST = { 'CFBundleIdentifier' : 'com.maddogsw.evernote-palm-importer',
          'CFBundleShortVersionString': '1.1.1' }
OPTIONS = {'argv_emulation': True,
           'plist': PLIST }

setup(
    app = APP,
    options = {'py2app': OPTIONS},
    setup_requires = ['py2app'],
)
