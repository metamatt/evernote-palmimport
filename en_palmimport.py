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
	class ExportFileDetails:
		def __init__(self, filename, locale, encoding):
			if sys.platform == "win32":
				default_encoding = "windows-1252"
			elif sys.platform == "darwin":
				default_encoding = "MacRoman"
			else:
				default_encoding = "latin-1"

			self.filename = filename or None
			self.locale = locale or ''
			self.encoding = encoding or default_encoding

	class Config:
		def __init__(self):
			self.interimProgress = None
			self.cancelled = False
			self.useLiveServer = True
			self.cacheLogin = False

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

			if options.testServer:
				self.useLiveServer = False
			if options.cachelogin:
				self.cacheLogin = True
				
			palm_filename = ((len(args) and args[0]) or os.getenv('en_palmfile') or '')
			details = PalmNoteImporter.ExportFileDetails(palm_filename, options.locale, options.encoding)
			return details

		def FinalizeNonGuiOptions(self, export_details):
			# fill in required missing parameters from raw-input
			if not export_details.filename:
				export_details.filename = raw_input("Palm Desktop memo export file: ")

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
		
	def __init__(self, config):
		self.config = config
		self.connect_to_evernote()
		
	def ImportNotes(self, details):
		# Legacy monolithic one-shot import: Do all the work.
		# Returns a string saying what happened.
		# Can also call interim progress function with text updates.
		if self.EN:
			self.load_notes_file(details)
			self.authenticate_to_evernote()
			return self.import_notes()
		else:
			return 'Not connected to Evernote service'

	def load_notes_file(self, details):
		# Open and parse Palm import file
		#
		# First, set the user-specified locale.  (BUG: For some reason this fails on
		# Python 2.6 for Windows, even using locale names that are totally valid as far
		# as I can tell, and are in locale.locale_aliases.  So tolerate failure here.
		# (On my Windows system, getdefaultlocale() returns en_US, which maps in the
		# locale_alias table to en_US.ISO8859-1, but setlocale to either of those fails;
		# setlocale to '' to use the real default returns 'English_United States.1252'!))
		self.config.interimProgress('Opening export file "%s" with encoding "%s"' % (details.filename, details.encoding))
		self.config.interimProgress('Using locale "%s" for date parsing' % details.locale)
		try:
			locale.setlocale(locale.LC_TIME, details.locale)
		except locale.Error:
			exc_value = sys.exc_info()[1]
			self.config.interimProgress('Failed to set locale: %s' % exc_value)
			newloc = locale.setlocale(locale.LC_TIME, "")
			self.config.interimProgress('Using system default locale "%s" for date parsing' % newloc)

		# Read in the notes.
		parser = PalmDesktopNoteParser.PalmDesktopNoteParser()
		error = parser.Open(details.filename, details.encoding)
		if error:
			return (False, error)
		self.config.interimProgress('Read %d notes from export file "%s"' % (len(parser.notes), details.filename))
		self.parser = parser
		return (True, self.number_of_notes_loaded())
		
	def number_of_notes_loaded(self):
		if self.parser:
			return len(self.parser.notes)
		return 0
		
	def connect_to_evernote(self):
		# Connect to Evernote service
		self.config.interimProgress("Connecting to Evernote...")
		EN = EvernoteManager.EvernoteManager(self.config.useLiveServer)
		(result, details) = EN.Connect()
		if not result:
			return "Failed to connect to Evernote: " + details
		self.config.interimProgress("Connected to Evernote service at " + details)
		self.EN = EN

	def authenticate_to_evernote(self):
		# Load and apply any cached login token. Then if we need to, invoke interactive OAuth flow.
		cached_token = self.load_cached_authtoken()
		if cached_token:
			(result, err) = self.EN.AuthenticateWithCachedToken(cached_token)
		if not self.EN.is_authenticated():
			(result, err) = self.EN.AuthenticateInteractively()
		if self.EN.is_authenticated():
			if self.config.cacheLogin and not cached_token:
				self.save_cached_authtoken(self.EN.authToken)
			self.config.interimProgress("Authenticated to Evernote service as %s" % self.EN.get_user_name())
			return True
		else:
			self.config.interimProgress("Failed to authenticate to Evernote: %s" % err)
			return False

	def discard_authentication(self):
		self.EN.DiscardAuthentication()
		
	def is_authenticated(self):
		return self.EN and self.EN.is_authenticated()

	def import_notes(self):
		# Assumes note-loading and service-authentication already happened.
		EN = self.EN
		parser = self.parser

		notebooks = EN.GetNotebooks()
		#
		# Create a notebook called "Palm import"
		#
		palmNotebook = EN.FindNotebook("Palm import")
		if palmNotebook:
			self.config.interimProgress("Reusing import notebook")
		else:
			palmNotebook = EN.CreateNotebook("Palm import")
			self.config.interimProgress("Created import notebook")
		
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
				self.config.interimProgress("Created note %d/%d: %s" % (n_in, n_total, title))
			except KeyboardInterrupt:
				self.config.cancelled = True
			except:
				exc_value = sys.exc_info()[1]
				msg = "Failed note %d/%d: %s (%s)" % (n_in, n_total, title, exc_value)
				sys.stderr.write("\n\n" + msg + "\n\n")
				traceback.print_exc(file=sys.stderr)
				self.config.interimProgress(msg)

			if self.config.cancelled:
				return "Import cancelled (%d/%d complete)" % (n_out, n_total)
		
		return "Import complete, %d/%d notes succeeded" % (n_out, n_total)

#
# If invoked directly, just run import logic.
#
if __name__ == "__main__":
	config = PalmNoteImporter.Config()
	export_details = config.ParseOptions()
	config.FinalizeNonGuiOptions(export_details)
	config.interimProgress = lambda s: sys.stdout.write(s + '\n')

	importer = PalmNoteImporter(config)
	result = importer.ImportNotes(export_details)
	print result
