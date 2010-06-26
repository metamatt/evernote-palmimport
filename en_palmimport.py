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
# ------------------- to do! ----------------------
# - do something with Private flag?
# - deal with other export formats?


#
# Python modules we use
#
import os
import sys
import time
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
			self.interimProgress = None
			self.cancelled = False
			self.useLiveServer = True

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
		EN.Connect()
		if EN.Authenticate(config.enUsername, config.enPassphrase):
			config.interimProgress("Connected to Evernote as " + config.enUsername)
		else:
			return "Failed to connect to Evernote."
		notebooks = EN.GetNotebooks()
		
		#
		# Open and parse Palm import file
		#
		parser = PalmDesktopNoteParser.PalmDesktopNoteParser()
		error = parser.Open(config.pdExportFilename)
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
		# Create a new note in that notebook for each Palm note
		#
		i = 0
		n = len(parser.notes)
		for palmNote in parser.notes:
			title = palmNote.title
			body = palmNote.body
			date = palmNote.dateModified * 1000
			tags = EN.LookupTags(palmNote.categories)
			# TODO: do anything with private flag?
			createdNote = EN.CreateNotePlaintext(palmNotebook, title, body, date, tags)
			i = i + 1
			config.interimProgress("Created note %d/%d: %s" % (i, n, title))

			if config.cancelled:
				return "Import cancelled (%d/%d complete)" % (i, n)
		
		return "Import complete."

#
# If invoked directly, just run import logic.
#
if __name__ == "__main__":
	# TODO: read parameters from somewhere else instead of hardcoding
	importer = PalmNoteImporter()
	config = importer.Config()
	def writeln(string):
		sys.stdout.write(string + "\n")
	config.interimProgress = writeln

	# look on command line, then environment, then raw-input, in that order
	# to determine parameters
	parser = OptionParser()
	parser.add_option("-u", "--username", dest="username",
					  help="Evernote username")
	parser.add_option("-p", "--password", dest="password",
					  help="Evernote password")
	parser.add_option("-t", "--test", dest="testServer", action="store_true",
					  help="Connect to Evernote staging server")
	(options, args) = parser.parse_args()

	config.enUsername = (options.username or os.getenv("en_username") or
						 raw_input("Evernote username: "))
	config.enPassphrase = (options.password or os.getenv("en_password") or
						   raw_input("Evernote password: "))
	config.pdExportFilename = ((len(args) and args[0]) or
							   os.getenv("en_palmfile") or
							   raw_input("Palm Desktop memo export file: "))
	if options.testServer:
		config.useLiveServer = False

	result = importer.ImportNotes(config)
	print result
