#! /usr/bin/python
#
# en_palmimport.py
# (c) 2009 Matt Ginzton, matt@maddogsw.com
#
# Python application to migrate notes from Palm Desktop (after using its "Export"
# function) into Evernote.
#
# Changelog:
# - basic functionality to transfer note text: 2009/06/26
# - use date stamp from Palm as date stamp on Evernote: 2009/06/27
# - use categories from Palm as tags in Evernote: 2009/06/27
# - add GUI (see wrapper EvernotePalmImporter.py): 2009/06/27
# - continue when individual note fails to upload: 2010/12/28
# - specify character encoding for Palm export file: 2010/12/28
# - refactored support for parsing command line options: 2011/01/04
# - allow locale specified on command line: 2011/01/07
# - deal with broken locale settings on Windows: 2011/01/13
# - default character encoding for Mac OS X is MacRoman: 2012/05/30
# - add OAuth and remove username-password authentication: 2012/10/16
# ------------------- to do! ----------------------
# - do something with Private flag?
# - deal with other export formats?


#
# Python modules we use
#
try:
	import json
except ImportError:
	import simplejson as json
import locale
import optparse
import os
import sys
import time
import traceback

import EvernoteManager
import PalmDesktopNoteParser


#
# Import logic, and struct to configure it, lives in this class.
#
class PalmNoteImporter:
	class Config:
		def __init__(self):
			self.enUsername = None
			self.enPassphrase = None
			self.pdExportFilename = None
			self.locale = ''
			self.interimProgress = None
			self.cancelled = False
			self.useLiveServer = True
			self.cacheLogin = False

			if sys.platform == "win32":
				self.pdExportEncoding = "windows-1252"
			elif sys.platform == "darwin":
				self.pdExportEncoding = "MacRoman"
			else:
				self.pdExportEncoding = "latin-1"

		def ParseOptions(self):
			# look on command line, then environment, to determine parameters
			parser = optparse.OptionParser()
			parser.add_option("-c", "--cachelogin", action="store_true", help="Cache OAuth login token for reuse")
			parser.add_option("-e", "--encoding", dest="encoding",
			                  help="Character encoding for export file (see http://docs.python.org/library/codecs.html#standard-encodings for valid values)")
			parser.add_option("-t", "--test", dest="testServer", action="store_true",
					  help="Connect to Evernote sandbox server")
			parser.add_option("-l", "--locale", dest="locale",
					  help="Set locale used for interpreting dates in Mac-format export files")

			(options, args) = parser.parse_args()

			self.pdExportFilename = ((len(args) and args[0]) or os.getenv("en_palmfile") or "")
			self.locale = (options.locale or self.locale)
			# Note on valid encodings: see http://docs.python.org/library/codecs.html#standard-encodings
			self.pdExportEncoding = (options.encoding or self.pdExportEncoding)
			if options.testServer:
				self.useLiveServer = False
			if options.cachelogin:
				self.cacheLogin = True

		def FinalizeNonGuiOptions(self):
			# fill in required missing parameters from raw-input
			if not len(self.pdExportFilename):
				self.pdExportFilename = raw_input("Palm Desktop memo export file: ")

	def load_cached_authtoken(self):
		# Right now the persistent settings file is used only for the oauth token, so
		# we have all the read/write code here and save_cached_authtoken instead of
		# generalizing it further, but we use json and a named parameter instead of just
		# dumping the token string there naked, to future proof ourselves if we later
		# add more persistent state.
		try:
			filename = os.path.expanduser('~/.evernote_palm_importer')
			f = open(filename)
			settings = json.load(f)
			f.close()
			return settings['oauth_token']
		except:
			return None

	def save_cached_authtoken(self, token):
		filename = os.path.expanduser('~/.evernote_palm_importer')
		f = open(filename, 'w')
		settings = { 'oauth_token' : token }
		json.dump(settings, f)
		f.close()

	def ImportNotes(self, config):
		# Do all the work.
		# Returns a string saying what happened.
		# Can also call interim progress function with text updates.
		
		#
		# Open and parse Palm import file
		#
		# First, set the user-specified locale.  (BUG: For some reason this fails on
		# Python 2.6 for Windows, even using locale names that are totally valid as far
		# as I can tell, and are in locale.locale_aliases.  So tolerate failure here.
		# (On my Windows system, getdefaultlocale() returns en_US, which maps in the
		# locale_alias table to en_US.ISO8859-1, but setlocale to either of those fails;
		# setlocale to '' to use the real default returns 'English_United States.1252'!))
		config.interimProgress("Using locale '%s' for date parsing" % config.locale)
		try:
			locale.setlocale(locale.LC_TIME, config.locale)
		except locale.Error:
			exc_value = sys.exc_info()[1]
			config.interimProgress("Failed to set locale: %s" % exc_value)
			newloc = locale.setlocale(locale.LC_TIME, "")
			config.interimProgress("Using system default locale '%s' for date parsing" % newloc)
			
		parser = PalmDesktopNoteParser.PalmDesktopNoteParser()
		error = parser.Open(config.pdExportFilename, config.pdExportEncoding)
		if error:
			return error
		config.interimProgress("Read " + str(len(parser.notes)) + " notes from export file")
		
		#
		# Connect to Evernote service
		#
		config.interimProgress("Connecting to Evernote...")
		EN = EvernoteManager.EvernoteManager(config.useLiveServer)
		(result, err) = EN.Connect()
		if not result:
			return "Failed to connect to Evernote: " + err
		# load and apply any cached login token
		cached_token = self.load_cached_authtoken()
		if cached_token:
			(result, err) = EN.AuthenticateWithCachedToken(cached_token)
		if not EN.is_authenticated():
			(result, err) = EN.AuthenticateInteractively()
		if EN.is_authenticated():
			if config.cacheLogin and not cached_token:
				self.save_cached_authtoken(EN.authToken)
		else:
			return "Failed to authenticate to Evernote: " + err
		config.interimProgress("Connected to Evernote service as %s" % EN.get_user_name())
		notebooks = EN.GetNotebooks()
		
		#
		# Create a notebook called "Palm import"
		#
		palmNotebook = EN.FindNotebook("Palm import")
		if palmNotebook:
			config.interimProgress("Reusing import notebook")
		else:
			palmNotebook = EN.CreateNotebook("Palm import")
			config.interimProgress("Created import notebook")
		
		#
		# Create a new note in that notebook for each Palm note.
		#
		# Errors here should affect only that note, not kill the
		# entire import process.
		#
		n_in = 0
		n_out = 0
		n_total = len(parser.notes)
		for palmNote in parser.notes:
			try:
				n_in = n_in + 1
				title = palmNote.title
				body = palmNote.body
				date = palmNote.dateModified * 1000
				tags = EN.LookupTags(palmNote.categories)
				# TODO: do anything with private flag?

				createdNote = EN.CreateNotePlaintext(palmNotebook, title, body, date, tags)
				n_out = n_out + 1
				config.interimProgress("Created note %d/%d: %s" % (n_in, n_total, title))
			except KeyboardInterrupt:
				config.cancelled = True
			except:
				exc_value = sys.exc_info()[1]
				msg = "Failed note %d/%d: %s (%s)" % (n_in, n_total, title, exc_value)
				sys.stderr.write("\n\n" + msg + "\n\n")
				traceback.print_exc(file=sys.stderr)
				config.interimProgress(msg)

			if config.cancelled:
				return "Import cancelled (%d/%d complete)" % (n_out, n_total)
		
		return "Import complete, %d/%d notes succeeded" % (n_out, n_total)

#
# If invoked directly, just run import logic.
#
if __name__ == "__main__":
	importer = PalmNoteImporter()
	config = importer.Config()
	config.ParseOptions()
	config.FinalizeNonGuiOptions()

	def writeln(string):
		sys.stdout.write(string + "\n")
	config.interimProgress = writeln

	result = importer.ImportNotes(config)
	print result
