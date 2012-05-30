# EvernoteManager.py
# (c) 2009 Matt Ginzton, matt@maddogsw.com
#
# Python class to wrap some of the details of connecting to the Evernote
# service.
#
# Changelog:
# - basic functionality: 2009/06/26
# - added tag functionality: 2009/06/27
# - taught to force well-formed note titles: 2009/07/12


import sys
import traceback
#
# Force Python to notice local-embedded Evernote API libs
#
sys.path.append('./lib')
#
# Python modules we use
#
import thrift.transport.THttpClient as THttpClient
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.limits.constants as limits
import evernote.edam.type.ttypes as Types
import xml.sax.saxutils

class EvernoteManager:
	def __init__(self, useLiveServer = False):
		# Initialize the Evernote manager object, by default talking to their
		# test/staging server.  Call UseLiveServer before Connect if you want
		# the real server.
		self._edamHost = "sandbox.evernote.com"
		self._consumerKey = "mginzton"
		# This decodes to my consumer API key from Evernote's developer support team.
		# If you're clever enough to find this, good for you.  Please get your own
		# (it's not hard) or the Evernote gods may frown upon both of us.
		self._consumerSecret = "28r08r681646o421".encode('rot13')
		self._tags = None
		self.userStore = None
		self.authResult = None
		self.noteStore = None
		
	def UseLiveServer(self):
		# Call this before Connect if you want to use the production servers.
		# Side effects: will connect to the production, not stage, Evernote service.
		# Result: None.
		self._edamHost = "www.evernote.com"

	def Connect(self):
		# Connect to Evernote and check version
		# Side effects: caches user store
		# Result: tuple with success/fail as true/false, followed by error message if any
		try:
			userStoreUri = "https://" + self._edamHost + "/edam/user"
			print "Evernote service URL: " + userStoreUri
			userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
			userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
			self.userStore = UserStore.Client(userStoreProtocol)
		
			versionOK = self.userStore.checkVersion("com.maddogsw.en_palmimport",
								UserStoreConstants.EDAM_VERSION_MAJOR,
								UserStoreConstants.EDAM_VERSION_MINOR)
		except:
			traceback.print_exc(file=sys.stderr)
			return [False, str(sys.exc_info()[1])]
			
		print "Is my EDAM protocol version up to date? ", str(versionOK)
		return [versionOK, "API version error"]

	def Authenticate(self, username, password):
		# Authenticate against userStore
		# Side effects: caches auth token
		# Result: tuple with success/fail as true/false, followed by error message if any
		try:
			self.authResult = self.userStore.authenticate(username, password,
								      self._consumerKey, self._consumerSecret)
		except:
			traceback.print_exc(file=sys.stderr)
			return [False, str(sys.exc_info()[1])]

		user = self.authResult.user
		authToken = self.authResult.authenticationToken
		print "Authentication was successful for " + user.username
		print "Authentication token = " + authToken
		return [True, ""]

	def GetNoteStore(self):
		# Returns note store
		# Side effects: if note store not cached, opens it and caches result
		# Result: note store
		if not self.noteStore:
			self._OpenNoteStore()
		return self.noteStore
		
	def _OpenNoteStore(self):
		# Opens the note store (assumes not open)
		# Side effecs: caches result
		# Result: none
		user = self.authResult.user
		noteStoreUri = "http://" + self._edamHost + "/edam/note/" + user.shardId
		noteStoreHttpClient = THttpClient.THttpClient(noteStoreUri)
		noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
		self.noteStore = NoteStore.Client(noteStoreProtocol)
		
	def GetNotebooks(self):
		# Returns notebooks for user after Connect and Authenticate
		# Side effects: none
		# Result: notebooks
		noteStore = self.GetNoteStore()
		token = self.authResult.authenticationToken
		notebooks = noteStore.listNotebooks(token)
		return notebooks
		
	def CreateNotebook(self, name):
		noteStore = self.GetNoteStore()
		token = self.authResult.authenticationToken

		notebook = Types.Notebook()
		notebook.name = name
		
		createdNotebook = noteStore.createNotebook(token, notebook)
		return createdNotebook
		
	def FindNotebook(self, name):
		noteStore = self.GetNoteStore()
		token = self.authResult.authenticationToken
		
		notebooks = noteStore.listNotebooks(token)
		for notebook in notebooks:
			if notebook.name == name:
				return notebook
		return None

	def CreateNotePlaintext(self, notebook, title, body, date, tags):
		# Evernote API expects that strings are XML-escaped UTF-8; we'll do the XML
		# escaping here, but we expect that title and body are already well-formed
		# Unicode strings encoded in UTF-8.
		noteStore = self.GetNoteStore()
		token = self.authResult.authenticationToken
		
		# Need to convert body to well-formed XML:
		# - escape entities, etc
		# - change \n to <br/>
		# (Note that title remains a literal string, not XML.)
		bodyXML = ""
		for line in body.split('\n'):
			bodyXML += xml.sax.saxutils.escape(line) + "<br/>"

		note = Types.Note()
		note.notebookGuid = notebook.guid
		note.title = self._MakeEvernoteTitle(title)
		note.content = '<?xml version="1.0" encoding="UTF-8"?>'
		note.content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">'
		note.content += '<en-note>'
		note.content += bodyXML
		note.content += '</en-note>'
		note.created = date
		note.updated = date
		note.tagGuids = tags

		createdNote = noteStore.createNote(token, note)
		return createdNote

	def LookupTags(self, tagNameList):
		# Returns GUIDs of existing tags by name (input is list of strings, output is list of GUIDs)
		# Side effects: creates any tags that didn't exist
		# Return value: list of GUIDs, suitable for passing to CreateNotePlaintext
		guids = []
		for tagName in tagNameList:
			if len(tagName) == 0: # allow and ignore list to contain empty tag names
				continue
			# This is O(M*N), M is number of tags in EN account, N is number of tags in incoming list
			# Could be made O(N) but doesn't seem worth the trouble.
			guid = self.FindTagByName(tagName)
			if not guid:
				guid = self.CreateTagByName(tagName)
			guids.append(guid)
		return guids
		
	def FindTagByName(self, tagName):
		# Looks for existing tag by name; returns its GUID
		# Side effects: populates tag cache
		# Return value: GUID of existing tag, or None
		tags = self._GetTags()
		for tag in tags:
			# Note that Evernote tags are not case sensitive
			if tag.name.lower() == tagName.lower():
				return tag.guid
		return None

	def CreateTagByName(self, tagName):
		# Creates a new tag by name; returns its GUID
		# Side effects: creates tag, adjusts tag cache
		# Return value: GUID of new tag
		noteStore = self.GetNoteStore()
		token = self.authResult.authenticationToken

		tag = Types.Tag()
		tag.name = tagName
		tag = noteStore.createTag(token, tag)

		tags = self._GetTags()
		tags.append(tag)
		return tag.guid
		
	def _GetTags(self):
		# Returns tags for note store
		# Side effects: caches tags
		# Result: tag list
		if self._tags == None:
			noteStore = self.GetNoteStore()
			token = self.authResult.authenticationToken
			self._tags = noteStore.listTags(token)
		return self._tags

	def _MakeEvernoteTitle(self, title):
		# input: string (probably first line of note)
		# output: string, legal as Evernote title
		# Evernote's "Struct: Note" docs for the title field say:
		#    The subject of the note. Can't begin or end with a space. 
		#    Length: EDAM_NOTE_TITLE_LEN_MIN - EDAM_NOTE_TITLE_LEN_MAX
		title = title.strip()
		if len(title) < limits.EDAM_NOTE_TITLE_LEN_MIN:
			return "(Untitled)"
		
		if len(title) > limits.EDAM_NOTE_TITLE_LEN_MAX:
			title = title[ : limits.EDAM_NOTE_TITLE_LEN_MAX]
		
		return title


# Basic unit test harness
if __name__ == "__main__":
	EN = EvernoteManager()
	EN.Connect()
	EN.Authenticate("metamatt", "metamatt")
	notebooks = EN.GetNotebooks()
	print str(len(notebooks)) + " notebooks found"
	for n in notebooks:
		print "Notebook: " + n.name
	tags = EN._GetTags()
	print str(len(tags)) + " tags found"
	for t in tags:
		print "Tag: " + t.name
