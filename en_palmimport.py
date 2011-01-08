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
# ------------------- to do! ----------------------
# - do something with Private flag?
# - deal with other export formats?


#
# Python modules we use
#
import locale
import os
import sys
import time
import traceback
from optparse import OptionParser
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

			if sys.platform == "win32":
				self.pdExportEncoding = "windows-1252"
			else:
				self.pdExportEncoding = "latin-1"

		def ParseOptions(self):
			# look on command line, then environment, to determine parameters
			parser = OptionParser()
			parser.add_option("-u", "--username", dest="username",
					  help="Evernote username")
			parser.add_option("-p", "--password", dest="password",
					  help="Evernote password")
			parser.add_option("-e", "--encoding", dest="encoding",
			                  help="Character encoding for export file (see http://docs.python.org/library/codecs.html#standard-encodings for valid values)")
			parser.add_option("-t", "--test", dest="testServer", action="store_true",
					  help="Connect to Evernote staging server")
			parser.add_option("-l", "--locale", dest="locale",
					  help="Set locale used for interpreting dates in Mac-format export files")

			(options, args) = parser.parse_args()

			self.enUsername = (options.username or os.getenv("en_username") or "")
			self.enPassphrase = (options.password or os.getenv("en_password") or "")
			self.pdExportFilename = ((len(args) and args[0]) or os.getenv("en_palmfile") or "")
			self.locale = (options.locale or self.locale)
			# Note on valid encodings: see http://docs.python.org/library/codecs.html#standard-encodings
			self.pdExportEncoding = (options.encoding or self.pdExportEncoding)
			if options.testServer:
				self.useLiveServer = False

		def FinalizeNonGuiOptions(self):
			# fill in required missing parameters from raw-input
			if not len(self.enUsername):
				self.enUsername = raw_input("Evernote username: ")
			if not len(self.enPassphrase):
				self.enPassphrase = raw_input("Evernote password: ")
			if not len(self.pdExportFilename):
				self.pdExportFilename = raw_input("Palm Desktop memo export file: ")

	def ImportNotes(self, config):
		# Do all the work.
		# Returns a string saying what happened.
		# Can also call interim progress function with text updates.
		
		#
		# Connect to Evernote service
		#
		config.interimProgress("Connecting to Evernote...")
		EN = EvernoteManager.EvernoteManager()
		if config.useLiveServer:
			EN.UseLiveServer()
		(result, err) = EN.Connect()
		if not result:
			return "Failed to connect to Evernote: " + err
		(result, err) = EN.Authenticate(config.enUsername, config.enPassphrase)
		if not result:
			return "Failed to authenticate to Evernote: " + err
		config.interimProgress("Connected to Evernote as " + config.enUsername)
		notebooks = EN.GetNotebooks()
		
		#
		# Open and parse Palm import file
		#
		sys.stdout.write("Using locale '%s' for date parsing\n" % config.locale)
		locale.setlocale(locale.LC_TIME, config.locale)
		parser = PalmDesktopNoteParser.PalmDesktopNoteParser()
		error = parser.Open(config.pdExportFilename, config.pdExportEncoding)
		if error:
			return error
		config.interimProgress("Read " + str(len(parser.notes)) + " notes from export file")
		
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
		# Errors here should affect only that note, not kill the
		# entire import process.
		#
		n_in = 0
		n_out = 0
		n_total = len(parser.notes)
		for palmNote in parser.notes:
			try:
				title = palmNote.title
				body = palmNote.body
				date = palmNote.dateModified * 1000
				tags = EN.LookupTags(palmNote.categories)
				# TODO: do anything with private flag?

				n_in = n_in + 1
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
