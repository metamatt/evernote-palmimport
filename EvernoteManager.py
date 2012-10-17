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
# - converted to OAuth: 2012/10/15

import sys
import traceback
import webbrowser
#
# Force Python to notice local-embedded Evernote API libs
#
sys.path.append('./evernote-sdk-python/lib')
#
# Python modules we use
#
import thrift.transport.THttpClient as THttpClient
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.error.ttypes as Errors
import evernote.edam.limits.constants as Limits
import evernote.edam.type.ttypes as Types
import urllib
import urllib2
import urlparse
import xml.sax.saxutils

from oauth_receiver import OAuthReceiver


client_name = "com.maddogsw.en_palmimport/1.2; Python"
# This decodes to my consumer API key from Evernote's developer support team.
# If you're clever enough to find this, good for you.  Please get your own
# (it's not hard) or the Evernote gods may frown upon both of us.
_consumerKey = "metamatt"
_consumerSecret = "0sr93r08148qq487".encode('rot13')


class OAuthHelper:
	def __init__(self, oauth_host):
		self.oauth_host = oauth_host
		self.oauth_url = 'https://%s/oauth' % oauth_host
		
	def flow(self):
		# OAuth for fun and profit.
		# step 1: start webserver, so oauth redirect flow has somewhere to land
		self.local_server = OAuthReceiver()
		self._get_temp_credential()
		
		# step 2: invoke user's webbrowser to authorize us, passing our webserver as callback url
		if not self._authorize_temp_credential():
			return (None, None)

		# step 3: profit
		(authToken, noteStoreUrl) = self._get_real_credential()
		return (authToken, noteStoreUrl)
		
	def _get_temp_credential(self):
		# POST to request temporary credentials
		# sample request: POST to https://sandbox.evernote.com/oauth?oauth_consumer_key=en_oauth_test&oauth_signature=1ca0956605acc4f2%26&oauth_signature_method=PLAINTEXT&oauth_timestamp=1288364369&oauth_nonce=d3d9446802a44259&oauth_callback=https%3A%2F%2Ffoo.com%2Fsettings%2Findex.php%3Faction%3DoauthCallback
		# sample response: oauth_token=en_oauth_test.12BF8802654.687474703A2F2F6C6F63616C686F73742F7E736574682F4544414D576562546573742F696E6465782E7068703F616374696F6E3D63616C6C6261636B.1FFF88DC670B03799613E5AC956B6E6D&oauth_token_secret=&oauth_callback_confirmed=true
		# need to keep oauth_token value
		params = {
			'oauth_consumer_key': _consumerKey,
			'oauth_signature': _consumerSecret + '&', # Evernote does not use oauth_token_secret
			'oauth_signature_method': 'PLAINTEXT',
			'oauth_callback': self.local_server.url # The browser will redirect here upon authorization.
		}
		response = urllib2.urlopen(self.oauth_url, data = urllib.urlencode(params))
		result = urlparse.parse_qs(response.read())
		self.temp_credential = result['oauth_token'][0]

	def _authorize_temp_credential(self):
		# browse to interactive authentication webapp, to authorize the temporary credential
		# navigate to https://server/OAuth.action?oauth_token=<>
		# browser will redirect to callback_url provided in initial credential request, providing the oauth token and verifier
		self.local_server.start()
		webbrowser.open_new_tab('https://%s/OAuth.action?oauth_token=%s' % (self.oauth_host, self.temp_credential))
		(new_oauth_token, self.oauth_verifier) = self.local_server.wait()
		if new_oauth_token is None:
			return False
		assert new_oauth_token == self.temp_credential
		return True

	def _get_real_credential(self):
		# POST to exchange temporary authorized credential for real one
		# sample request: POST to https://sandbox.evernote.com/oauth?oauth_consumer_key=en_oauth_test&oauth_signature=1ca0956605acc4f2%26&oauth_signature_method=PLAINTEXT&oauth_timestamp=1288364923&oauth_nonce=755d38e6d163e820&oauth_token=en_oauth_test.12BF8888B3F.687474703A2F2F6C6F63616C686F73742F7E736574682F4544414D576562546573742F696E6465782E7068703F616374696F6E3D63616C6C6261636B.C3118B25D0F89531A375382BEEEDD421&oauth_verifier=DF427565AF5473BBE3D85D54FB4D63A4
		# (with oauth_token and oauth_verifier from authorization)
		# sample response: oauth_token=S%3Ds4%3AU%3Da1%3AE%3D12bfd68c6b6%3AC%3D12bf8426ab8%3AP%3D7%3AA%3Den_oauth_test%3AH%3D3df9cf6c0d7bc410824c80231e64dbe1&oauth_token_secret=&edam_noteStoreUrl=https%3A%2F%2Fsandbox.evernote.com%2Fedam%2Fnote%2Fshard%2Fs4&edam_userId=161
		params = {
			'oauth_consumer_key': _consumerKey,
			'oauth_signature': _consumerSecret + '&',
			'oauth_signature_method': 'PLAINTEXT',
			'oauth_token': self.temp_credential,
			'oauth_verifier': self.oauth_verifier
		}
		response = urllib.urlopen(self.oauth_url, data = urllib.urlencode(params))
		# need to url-decode and keep the oauth_token and edam_noteStoreUrl values
		result = urlparse.parse_qs(response.read())
		return (result['oauth_token'][0], result['edam_noteStoreUrl'][0])


class EvernoteManager:
	def __init__(self, live = False):
		# Instance variables
		self.userStore = None    # UserStore.Client we create to talk to UserStore service (before authentication)
		self.authToken = None    # Token returned from OAuth authentication and used for all NoteStore API calls
		self.noteStoreUrl = None # URL for the specific user's NoteStore, encoding shard ID
		self.noteStore = None    # NoteStore.Client we create to talk to NoteStore service (after authentication)
		self._tags = None        # Memo-ized list of tags, built on demand in _GetTags
		# Initialize the Evernote manager object, by default talking to Evernote's
		# sandbox (testing) server. Specify live = True if you want the real server.
		self._evernoteBaseHost = 'www.evernote.com' if live else 'sandbox.evernote.com'

	def Connect(self):
		# Connect to Evernote and check version
		# Side effects: caches user store
		# Result: tuple with success/fail as true/false, followed by error message if any
		try:
			userStoreUri = "https://" + self._evernoteBaseHost + "/edam/user"
			print "Evernote service URL: " + userStoreUri
			userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
			#userStoreHttpClient.setCustomHeader('User-Agent', client_name) # XXX not available in evernote-python-sdk?
			userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
			self.userStore = UserStore.Client(userStoreProtocol)
		
			versionOK = self.userStore.checkVersion(client_name,
								UserStoreConstants.EDAM_VERSION_MAJOR,
								UserStoreConstants.EDAM_VERSION_MINOR)
		except:
			traceback.print_exc(file=sys.stderr)
			return [False, str(sys.exc_info()[1])]
			
		print "Is my EDAM protocol version up to date? ", str(versionOK)
		return [versionOK, "API version error"]
		
	def is_authenticated(self):
		if self.authToken:
			try:
				user = self.userStore.getUser(self.authToken)
				return True
			except Errors.EDAMUserException, ex:
				print 'Authentication error: %d' % ex.errorCode
		return False

	def AuthenticateWithCachedToken(self, cached_token):
		self.authToken = cached_token
		self.noteStoreUrl = self.userStore.getNoteStoreUrl(self.authToken)
		if self.is_authenticated():
			return [True, '']
		else:
			return [False, 'authentication failure']
	
	def AuthenticateInteractively(self):
		auth_helper = OAuthHelper(self._evernoteBaseHost)
		(self.authToken, self.noteStoreUrl) = auth_helper.flow() # XXX GUI version should make this async and allow cancel
		if self.is_authenticated():
			return [True, '']
		else:
			return [False, 'authentication failure']
		
	def get_user_name(self):
		user = self.userStore.getUser(self.authToken)
		return user.username
	
	def GetNoteStore(self):
		# Returns note store
		# Side effects: if note store not cached, opens it and caches result
		# Result: note store
		if not self.noteStore:
			self._OpenNoteStore()
		return self.noteStore
		
	def _OpenNoteStore(self):
		# Opens the note store (assumes not open)
		# Side effects: caches result
		# Result: none
		noteStoreHttpClient = THttpClient.THttpClient(self.noteStoreUrl)
		noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
		self.noteStore = NoteStore.Client(noteStoreProtocol)
		
	def GetNotebooks(self):
		# Returns notebooks for user after Connect and Authenticate
		# Side effects: none
		# Result: notebooks
		noteStore = self.GetNoteStore()
		notebooks = noteStore.listNotebooks(self.authToken)
		return notebooks
		
	def CreateNotebook(self, name):
		noteStore = self.GetNoteStore()

		notebook = Types.Notebook()
		notebook.name = name
		
		createdNotebook = noteStore.createNotebook(self.authToken, notebook)
		return createdNotebook
		
	def FindNotebook(self, name):
		noteStore = self.GetNoteStore()
		
		notebooks = noteStore.listNotebooks(self.authToken)
		for notebook in notebooks:
			if notebook.name == name:
				return notebook
		return None

	def CreateNotePlaintext(self, notebook, title, body, date, tags):
		# Evernote API expects that strings are XML-escaped UTF-8; we'll do the XML
		# escaping here, but we expect that title and body are already well-formed
		# Unicode strings encoded in UTF-8.
		noteStore = self.GetNoteStore()
		
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

		createdNote = noteStore.createNote(self.authToken, note)
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

		tag = Types.Tag()
		tag.name = tagName
		tag = noteStore.createTag(self.authToken, tag)

		tags = self._GetTags()
		tags.append(tag)
		return tag.guid
		
	def _GetTags(self):
		# Returns tags for note store
		# Side effects: caches tags
		# Result: tag list
		if self._tags == None:
			noteStore = self.GetNoteStore()
			self._tags = noteStore.listTags(self.authToken)
		return self._tags

	def _MakeEvernoteTitle(self, title):
		# input: string (probably first line of note)
		# output: string, legal as Evernote title
		# Evernote's "Struct: Note" docs for the title field say:
		#    The subject of the note. Can't begin or end with a space. 
		#    Length: EDAM_NOTE_TITLE_LEN_MIN - EDAM_NOTE_TITLE_LEN_MAX
		title = title.strip()
		if len(title) < Limits.EDAM_NOTE_TITLE_LEN_MIN:
			return "(Untitled)"
		
		if len(title) > Limits.EDAM_NOTE_TITLE_LEN_MAX:
			title = title[ : Limits.EDAM_NOTE_TITLE_LEN_MAX]
		
		return title


# Basic unit test harness
if __name__ == "__main__":
	EN = EvernoteManager()
	EN.Connect()
	EN.AuthenticateInteractively()
	notebooks = EN.GetNotebooks()
	print str(len(notebooks)) + " notebooks found"
	for n in notebooks:
		print "Notebook: " + n.name
	tags = EN._GetTags()
	print str(len(tags)) + " tags found"
	for t in tags:
		print "Tag: " + t.name
