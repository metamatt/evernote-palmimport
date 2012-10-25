#!/usr/bin/make

PYTHON = python2.5 # easiest way to force use of 32-bit python on Mac OS X 10.6 and later (since wxpython is distributed only as 32-bit)

default: macos-app-selfcontained

clean:
	rm -rf build dist

macos-app-selfcontained:
	$(PYTHON) setup.py py2app

macos-app-alias:
	$(PYTHON) setup.py py2app -A

source-package:
	mkdir -p dist/EvernotePalmMemoImporter-source
	cp en_palmimport.py EvernoteManager.py PalmDesktopNoteParser.py EvernotePalmMemoImporter.py oauth_receiver.py dist/EvernotePalmMemoImporter-source
	cd dist && tar czf EvernotePalmMemoImporter-source.tgz EvernotePalmMemoImporter-source

win-package: # depends on py2exe already having run from Windows
	cd dist && zip -9 EvernotePalmMemoImporter-Win32.zip EvernotePalmMemoImporter-Win32/EvernotePalmMemoImporter*

mac-package: macos-app-selfcontained
	ditto -ck --sequesterRsrc --keepParent dist/EvernotePalmMemoImporter.app dist/EvernotePalmMemoImporter-MacOSX.zip

all-packages: source-package mac-package win-package

upload:
	rsync -essh --progress index.html dist/*.zip dist/*.tgz skynet:/web/maddogsw.com/web/evernote-utilities/evernote-palm-importer

upload-beta:
	rsync -essh --progress index.html dist/*.zip dist/*.tgz skynet:/web/maddogsw.com/web/evernote-utilities/evernote-palm-importer/new
