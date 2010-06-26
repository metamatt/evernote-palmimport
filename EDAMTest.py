#
# Force Python to notice local-embedded Evernote API libs
#
import sys
sys.path.append('./lib')

import time
import thrift.transport.THttpClient as THttpClient
import thrift.protocol.TBinaryProtocol as TBinaryProtocol
import evernote.edam.userstore.UserStore as UserStore
import evernote.edam.userstore.constants as UserStoreConstants
import evernote.edam.notestore.NoteStore as NoteStore
import evernote.edam.type.ttypes as Types

#
# Configure these based on the API key you received from Evernote
#
consumerKey = "mginzton"
consumerSecret = "28e08e681646b421"
username = "metamatt"
password = "metamatt"

edamHost = "stage.evernote.com"

userStoreUri = "https://" + edamHost + "/edam/user"
userStoreHttpClient = THttpClient.THttpClient(userStoreUri)
userStoreProtocol = TBinaryProtocol.TBinaryProtocol(userStoreHttpClient)
userStore = UserStore.Client(userStoreProtocol)

versionOK = userStore.checkVersion("Python EDAMTest",
                                   UserStoreConstants.EDAM_VERSION_MAJOR,
                                   UserStoreConstants.EDAM_VERSION_MINOR)

print "Is my EDAM protocol version up to date? ", str(versionOK)
if not versionOK:
    exit(1)

authResult = userStore.authenticate(username, password,
                                    consumerKey, consumerSecret)
user = authResult.user
authToken = authResult.authenticationToken
print "Authentication was successful for ", user.username
print "Authentication token = ", authToken

noteStoreUri = "http://" + edamHost + "/edam/note/" + user.shardId
noteStoreHttpClient = THttpClient.THttpClient(noteStoreUri)
noteStoreProtocol = TBinaryProtocol.TBinaryProtocol(noteStoreHttpClient)
noteStore = NoteStore.Client(noteStoreProtocol)

notebooks = noteStore.listNotebooks(authToken)
print "Found ", len(notebooks), " notebooks:"
for notebook in notebooks:
    print "  * ", notebook.name
    if notebook.defaultNotebook:
        defaultNotebook = notebook

print
print "Creating a new note in default notebook: ", defaultNotebook.name
print
note = Types.Note()
note.notebookGuid = defaultNotebook.guid
note.title = raw_input("Note title?  ").strip()
note.content = '<?xml version="1.0" encoding="UTF-8"?>'
note.content += '<!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml.dtd">'
note.content += '<en-note>'
note.content += raw_input("Well-formed XHTML note content?  ").strip()
note.content += '</en-note>'
note.created = int(time.time() * 1000)
note.updated = note.created

createdNote = noteStore.createNote(authToken, note)

print "Created note: ", str(createdNote)
