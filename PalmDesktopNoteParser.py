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
# - Windows-format notes field is comma-separated list: 2011/01/06
# - more robust date parsing, attempt to deal with dates in any locale: 2011/01/07
# - added special mode to deal with CSV file where only first field is quoted: 2011/01/11
# - more robust date parsing, tested on German-locale dates: 2012/05/24
# - Mac-format encoding changes for paragraph separator: 2012/05/30
# ------------------- to do! ----------------------
# - attempt autodetect of character encoding?
# - switch over to Python's general CSV parser, instead of the hacked up
#   special purpose code here
# ---------------- known issues -------------------
# - date parsing is not fully general for arbitrary order of year/month/day: handles
#   Month DD YYYY and DD Month YYYY, but year must be last

import re
import sys
import time
import traceback


class PalmDesktopMacNote:
	def __init__(self, line, parser):
		self.monthLookup = parser.monthLookup
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
		# Multiline freeform text has newlines replaced by byte 0xA6; that's often shown as a pipe character
		# because that's what it means in latin-1 and utf-8. But in MacRoman or "macintosh" character set,
		# it's the paragraph character, which is 0xB6 in latin-1 and utf-8. I believe that the 0xA6 byte was
		# always meant as the paragraph chararacter, and Mac-format export files are usually (always?)
		# encoded in MacRoman. (Note that after decode from MacRoman, the 0xB6 byte has become U+B6, and
		# after re-encode to UTF-8 it's two bytes, \xC2\xB6, so that's what we look for here.)
		
		encodedEntries = line.split('\t')
		if len(encodedEntries) != 8:
			return False

		entries = []
		for entry in encodedEntries:
			entry = entry.replace('\xC2\xB6', '\n')
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
		if not self.dateModified:
			return False
		self.categories = [entries[5], entries[6]]
		self.private = entries[7] # BUG: this is written in the local language
		return True

	def ParsePalmDate(self, dateString):
		# Parse a string date from the Palm format and return seconds since epoch.
		#
		# I have seen the following varieties from Mac export files (Windows export
		# files contain no date at all):
		# - Month DD, YYYY (English files, month name spelled out in English)
		# - DD month YYYY (French files, month name spelled out in French)
		# - DD. month YYYY (German files, month name spelled out in German)
		# - m/d/yy (English speaker made export file, but no text; anyway this
		#   matches the default nl_langinfo(locale.D_FMT) for the "C" locale)
		# Note in the case where the month name is spelled out, not only the language
		# for the month name changed, but also the separator format and the case of
		# the month name.
		#
		# So, for now, we'll first try to parse as the C locale numeric format,
		# try both "DD Month YYYY" and "Month DD YYYY" where the separator can be
		# a comma or whitespace or both and the month name is spelled out as
		# locale would do it, which catches the first 2 cases.  I'm sure other orders
		# are possible in other locales, but for now, just assume the year comes
		# last, the fields are separated by whitespace and/or commas, and try
		# both possibilities for interpreting the first 2 fields.
		#
		# This gives us 3 cases which handle everything I've seen to date and
		# don't overlap.
		#
		# Unclear whether we should also try time.strptime(dateString, "%x");
		# that's somewhat ambiguous with the other pure-numeric form.
		try:
			return time.mktime(time.strptime(dateString, "%m/%d/%y"))
		except:
			pass

		splitter = re.compile(r'[, ] *')
		components = splitter.split(dateString)
		if len(components) != 3:
			return None
		year = int(components[2])
		month = day = None
		
		try:
			if components[0] in self.monthLookup:
				month = self.monthLookup[components[0]]
				if components[1][-1] == '.':
					components[1] = components[1][:-1]
				day = int(components[1])
			elif components[1] in self.monthLookup:
				month = self.monthLookup[components[1]]
				if components[0][-1] == '.':
					components[0] = components[0][:-1]
				day = int(components[0])
		except:
			pass
		if year and month and day:
			return time.mktime([year, month, day, 12, 0, 0, 0, 0, -1])
		else:
			return None


class PalmDesktopMacNoteParser:
	def __init__(self):
		self.GenerateMonthLUT()

	def GenerateMonthLUT(self):
		def monthname(m):
			return time.strftime("%B", [0, m, 0, 0, 0, 0, 0, 0, 0])
		self.monthLookup = dict((monthname(m), m) for m in range(1, 13))

	def ParseMany(self, data):
		lines = data.split('\r')
		notes = []

		for line in lines:
			if (len(line) == 0):
				continue

			note = PalmDesktopMacNote(line, self)
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
		#
		# Update 2011/01/14: it looks like the CSV format doesn't always quote strings; there's a
		# dialect that only quotes strings containing newlines (or, probably, commas).  This often
		# manifests as '"note\nbody\nhere",0,Unfiled', but can also be 'simple note,0,Unfiled'.
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
		self.categories = []
		for category in strings[2].split(','):
			self.categories.append(category.strip())
		self.dateModified = time.time() # Fake it and use right now, since there is no timestamp in the export data
		return True

class PalmDesktopWinNoteParser:
	def ParseMany(self, data):
		(strings, separator, suspicious) = self.SplitQuotedStrings(data, False)
		if suspicious:
			# saw extra text outside quotes; try again in crazy mode
			# print strings
			# print "Retrying parse in crazy mode"
			(strings, separator, suspicious) = self.SplitQuotedStrings(data, True)
			# print strings
		notes = []

		for i in range(0, len(strings), 3):
			note = PalmDesktopWinNote(strings[i : i + 3], separator)
			if note.happy:
				notes.append(note)
		return notes

	def SplitQuotedStrings(self, data, crazyMode = False):
		# Finds strings enclosed in double quotes (a double double quote is treated as an escaped
		# quote literal, not the end and beginning of an enclosed string), and returns the list.
		# Also returns the first example of a separator character between the quote-delimited
		# strings.
		#
		# Bug: doesn't care if the separators aren't all the same.  (In practice, I should see
		# two commas and then a newline, or two tabs and then a newline, then repeat in clumps
		# like that.)
		#
		# Crazy bonus mode: allow files that have "field 1",field2,field3\n, which I have seen,
		# if the crazy flag is passed: by building up clumps of characters that appear outside
		# quotes and between the real separator.
		inQuote = False
		lastCharWasQuote = False
		strings = []
		string = ""
		crazyExtras = ""
		separator = None
		suspicious = False

		for char in data:
			if char == '"':
				# When starting new quoted string, flush any stored craziness
				if crazyMode and crazyExtras != "":
					strings.append(crazyExtras)
					crazyExtras = ""
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
					# in boundary between quoted items: this should be the separator character
					if separator: # if we have one we've seen before, expect to see same one again
						if char == separator or char == '\n':
							# found separator where we expected it
							# flush any stored craziness
							if crazyMode and crazyExtras != "":
								strings.append(crazyExtras)
								crazyExtras = ""
						else:
							# expected separator but got something else
							# print "Warning, mixed separators: %c%c" % (char, separator)
							suspicious = True
							if crazyMode:
								crazyExtras += char
					else:
						# first thing seen in separator position: latch it as separator
						separator = char
		# flush at EOF without CR:
		if string:
			strings.append(string)
		if crazyMode and crazyExtras != "":
			strings.append(crazyExtras)
		return (strings, separator, suspicious)


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
			# Note on good guesses: Mac would often use MacRoman; Windows would often use windows-1252; latin-1 may also be common
			try:
				data = data.decode(encoding)
			except LookupError:
				return "'%s' is not a valid encoding" % encoding
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
			traceback.print_exc(file=sys.stderr)
			print "Exception thrown"

		if len(self.notes):
			return None
		else:
			return "'%s' does not look like a Palm Desktop notes export file" % filename


# Basic unit test harness
if __name__ == "__main__":
	from optparse import OptionParser
	optparser = OptionParser()
	optparser.add_option('-l', '--locale');
	defaultLocale = 'MacRoman' if sys.platform == 'darwin' else 'latin-1'
	optparser.add_option('-e', '--encoding', default = defaultLocale);
	(options, args) = optparser.parse_args()

	if options.locale:
		import locale;
		locale.setlocale(locale.LC_ALL, options.locale)

	parser = PalmDesktopNoteParser()
	result = parser.Open(args[0], options.encoding)
	print "Opened " + str(len(parser.notes)) + " notes."
	if result:
		print result
	for note in parser.notes:
		print note.title + " (" + time.strftime("%c", time.localtime(note.dateModified)) + ")"
