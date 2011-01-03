# PalmDesktopNoteParser.py
# (c) 2009 Matt Ginzton, matt@maddogsw.com
#
# Python class to deal with text file output from Palm Desktop's "Export..." function.
# This code can handle the text formats from Palm Desktop for Mac 4.2.2, and Palm Desktop
# for Windows 6.2.2.  The export format differs substantially between these; notably,
# the Mac-exported files have timestamps, so Mac-exported files are preferred for
# conversion into other formats.
#
# Changelog:
# - basic functionality based on Palm Desktop for Mac 4.2.2 export files: 2009/06/26
# - added code to deal with dates: 2009/06/27
# - added code to deal with Palm Desktop for Windows 6.2.2 export files: 2009/07/07
# - rethought generation of note titles: 2009/07/12
# - specify character encoding for Palm export file: 2010/12/28
# ------------------- to do! ----------------------
# - deal with dates in locales other than EN_us
# - attempt autodetect of character encoding?

import sys
import time
import traceback


class PalmDesktopMacNote:
	def GenerateMonthLUT():
		def monthname(m):
			return time.strftime("%B", [0, m, 0, 0, 0, 0, 0, 0, 0])
		d = dict((monthname(m), m) for m in range(1, 13))
		return d
	monthLookup = GenerateMonthLUT()

	def __init__(self, line):
		self.happy = self.ParseOne(line)
		
	def ParseOne(self, line):
		# My version of Palm Desktop for Mac (4.2.2) offers "Tab & Return" and "Palm Desktop" export formats
		# for memos.  By default, it exports all memos.  It offers a choice of 8 columns, in any order; the
		# default is all 8 in this order:
		#
		# Values in order are: title, body text, time, date, modified, category 1, category 2, private flag
		# Dates are spelled out in English as Month DD, YYYY.  The private-flag is "Private" or "Not Private".
		# (My notes don't have values in the "time" or "date" fields, but do have a date in "modified".)
		#
		# Format is: tab separated values
		# Multiline freeform text has newlines replaced by ascii 0xa6, Mac shows this as pipelike character
		
		#self.monthLookup = self.GenerateMonthLUT()
		
		encodedEntries = line.split('\t')
		if len(encodedEntries) != 8:
			return False

		separator = chr(0xA6)
		entries = []
		for entry in encodedEntries:
			# I would do this with "replace", but I can't figure out what the encoding is to let
			# Python operate on it as unicode, and Python doesn't like high ascii as ascii, so
			# I'll just split and rejoin myself.
			#      separator = u'\xA6'
			#      entry = unicode(entry, "iso-8859-1")
			#      entry.replace(separator, '\n')
			lines = entry.split(separator)
			entry = '\n'.join(lines)
			#print "..." + entry + "..."
			entries.append(entry)
		#print "Note with " + str(len(encodedEntries)) + " fields"

		# Originally I wanted to use the first line as title, and the rest as the body.  However, this is
		# a false distinction in the Palm memos app itself; the Windows version of Palm desktop doesn't
		# even separate them in the export dump (and the Mac version does, but it's just using the first
		# line of the body); also, Palm allows you to store more text on one line of a note than Evernote
		# allows for titles.  So, we'll put the entire note text in the body, and duplicate the first
		# line (truncated if ncessary) as the title.  This is pretty much what the Evernote client apps
		# do if you enter a note without a title (though the API doesn't allow null title, and leaves
		# empty title as empty, so this really must be client app behavior).
		#
		# Old title/body separation:
		#   self.title = entries[0]
		#   self.body = entries[1]
		# New title/body separation:
		self.title = entries[0].rstrip()
		self.body = entries[0] + "\n" + entries[1]
		# Other fields:
		self.dateModified = self.ParsePalmDate(entries[4])
		self.categories = [entries[5], entries[6]]
		self.private = entries[7]
		return True

	def ParsePalmDate(self, dateString):
		# Parse a string date from the Palm format and return seconds since epoch
		# Palm dates are in format "Month DD, YYYY"
		# BUG: actually dates are localized and could be in different order or
		# use non-English month names.  I've also seen components[2] throw a
		# list-index-out-of-range exception, meaning the split didn't return
		# 3 components, meaning (a) maybe separators other than space are possible
		# and (b) maybe this was invoked on something that wasn't a date and in
		# any case is too fragile.
		components = dateString.split()
		year = int(components[2])
		day = int(components[1].rstrip(','))
		month = PalmDesktopMacNote.monthLookup[components[0]]
		return time.mktime([year, month, day, 12, 0, 0, 0, 0, -1])
		

class PalmDesktopMacNoteParser:
	def ParseMany(self, data):
		lines = data.split('\r')
		notes = []

		for line in lines:
			if (len(line) == 0):
				continue

			note = PalmDesktopMacNote(line)
			if note.happy:
				notes.append(note)
		return notes


class PalmDesktopWinNote:
	def __init__(self, strings, separator):
		self.happy = self.ParseOne(strings, separator)

	def ParseOne(self, strings, separator):
		# My version of Palm Desktop for Windows (6.2.2) offers "Tab Separated Values", "Comma Separated",
		# "Memo Pad Archive" and "Text".  MPA is apparently a Jet database; Text is not very well delimited;
		# we'll only support the other two.  (Note by default it gives them all different extensions: .tab,
		# .csv, .mpa, and .txt, respectively, though it hints that .csv and .tab can also be stored in .txt,
		# and ultimately lets you save any of them however you like.)  By default it exports only selected
		# memos if any are selected, and you have to go out of your way to select all memos (it defaults to
		# all if none are selected).
		#
		# It offers a choice of 3 columns, in any order; the default is all 3 in this order:
		# - text, private-flag (0/1), category
		#
		# Format is: quoted strings, either comma separated with embedded newlines, or tab separated with
		# embedded carriage returns (really!).  Who knows why the line-end character changes depending on
		# the separator.  Quote literals inside the quoted strings are doubled up.  Commas are allowed
		# inside a quoted string in either format; tabs are allowed in the CSV format and are turned into
		# spaces in the tab-separated format.
		#
		# This code can read either the tab-separated or comma-separated variants; comma-separated is
		# preferred because it can express embedded tabs, which the tab-separated variant cannot.
		if len(strings) == 3 and separator == '\t':
			body = strings[0].split('\r')
		elif len(strings) == 3 and separator == ',':
			body = strings[0].split('\n')
		else:
			return False

		# I don't know why \r characters survive at this point, but I don't care.  Get rid of them.
		for i in range(len(body)):
			body[i] = body[i].replace('\r', '')
		
		# Originally I wanted to use the first line as title, and the rest as the body.  However, this is
		# a false distinction in the Palm memos app itself; the Windows version of Palm desktop doesn't
		# even separate them in the export dump (and the Mac version does, but it's just using the first
		# line of the body); also, Palm allows you to store more text on one line of a note than Evernote
		# allows for titles.  So, we'll put the entire note text in the body, and duplicate the first
		# line (truncated if ncessary) as the title.  This is pretty much what the Evernote client apps
		# do if you enter a note without a title (though the API doesn't allow null title, and leaves
		# empty title as empty, so this really must be client app behavior).
		#
		# Old title/body separation:
		#   self.title = entries[0]
		#   self.body = entries[1]
		# New title/body separation:
		self.title = body[0].rstrip()
		self.body = '\n'.join(body)
		# Other fields
		if strings[1] == "1":
			self.private = "Private"
		else:
			self.private = "Not Private"
		self.categories = [strings[2]]
		self.dateModified = time.time() # Fake it and use right now, since there is no timestamp in the export data
		return True

class PalmDesktopWinNoteParser:
	def ParseMany(self, data):
		(strings, separator) = self.SplitQuotedStrings(data)
		notes = []

		for i in range(0, len(strings), 3):
			note = PalmDesktopWinNote(strings[i : i + 3], separator)
			if note.happy:
				notes.append(note)
		return notes

	def SplitQuotedStrings(self, data):
		# Finds strings enclosed in double quotes (a double double quote is treated as an escaped
		# quote literal, not the end and beginning of an enclosed string), and returns the list.
		# Also returns the first example of a separator character between the quote-delimited
		# strings.
		#
		# Bug: doesn't care if the separators aren't all the same.  (In practice, I should see
		# two commas and then a newline, or two tabs and then a newline, then repeat in clumps
		# like that.)
		inQuote = False
		lastCharWasQuote = False
		strings = []
		string = ""
		separator = None

		for char in data:
			if char == '"':
				# Found a quote; what to do depends on previous character
				if lastCharWasQuote:
					# Found repeated doublequote -- push single doublequote onto string to build
					string += char
					lastCharWasQuote = False
				else:
					# Found non-repeated double-quote -- can't do anything now, depends on whether
					# next character is quote or not; just latch
					lastCharWasQuote = True
			else:
				# process any latched quote left over from previous character
				if lastCharWasQuote:
					if inQuote:
						# Closing quote; save string
						strings.append(string)
						string = ""
						inQuote = False
					else:
						# Opening quote
						inQuote = True
					lastCharWasQuote = False
				# Found non-quote character.  Are we in quotes now?
				if inQuote:
					# in middle of string -- push onto string to build
					string += char
				else:
					# in boundary, this is the separator
					if separator:
						#if char != separator:
						#	print "Warning, mixed separators: %c%c" % (char, separator)
						pass
					else:
						separator = char
		return (strings, separator)


class PalmDesktopNoteParser:
	def __init__(self):
		self.file = None
		self.notes = []
		
	def __del__(self):
		if self.file:
			self.file.close()

	def RemoveControlChars(self, s):
		# Palm Desktop export files are either in ASCII or some unspecified local
		# encoding; Evernote wants to see valid UTF-8; even after dealing with
		# character encodings some low-ASCII character equivalents may remain
		# which Evernote won't like, so let's strip low-ASCII characters not
		# allowed by XML.
		#
		# That is, \n, \r and \t are allowed, anything else < 0x20 should be
		# stripped.
		bad = ''.join([chr(c) for c in xrange(32)])
		actuallyGood = '\n\r\t'
		bad = ''.join([c for c in bad if c not in actuallyGood])

		def SanitizeString(s):
			return ''.join([c for c in s if c not in bad])

		return SanitizeString(s)
		
	def Open(self, filename, encoding):
		# Returns a string explaining any problems that happened
		# Otherwise populates self.notes
		try:
			self.file = open(filename, "r")
		except:
			return "Unable to open '%s': %s" % (filename, sys.exc_info()[1])
		
		try:
			print "Reading export file '%s' with encoding '%s'" % (filename, encoding)
			data = self.file.read()
			# Need to know data encoding so we can transform to utf-8
			# Note on good guesses: latin-1 and windows-1252 will be common
			data = data.decode(encoding)
			data = data.encode('utf-8')
			data = self.RemoveControlChars(data)
			
			# first try to parse Mac format
			macNoteParser = PalmDesktopMacNoteParser()
			macNotes = macNoteParser.ParseMany(data)

			# then try to parse Win format
			winNoteParser = PalmDesktopWinNoteParser()
			winNotes = winNoteParser.ParseMany(data)

			# then see what we found
			if len(macNotes) and len(winNotes):
				print "Found %s notes in Mac format and %d notes in Win format" % (len(macNotes), len(winNotes))
			else:
				if len(macNotes):
					self.notes = macNotes
				else:
					self.notes = winNotes
		except:
			e = sys.exc_info()
			traceback.print_exception(e[0], e[1], e[2])
			print "Exception thrown"

		if len(self.notes):
			return None
		else:
			return "'%s' does not look like a Palm Desktop notes export file" % filename


# Basic unit test harness
if __name__ == "__main__":
	parser = PalmDesktopNoteParser()
	result = parser.Open(sys.argv[1])
	print "Opened " + str(len(parser.notes)) + " notes."
	if result:
		print result
	for note in parser.notes:
		print note.title + " (" + time.strftime("%c", time.localtime(note.dateModified)) + ")"
