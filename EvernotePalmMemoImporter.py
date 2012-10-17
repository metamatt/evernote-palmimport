#! /usr/bin/python2.5
#
# EvernotePalmMemoImporter.py
# (c) 2009 Matt Ginzton, matt@maddogsw.com
#
# Python application to migrate notes from Palm Desktop (after using its "Export"
# function) into Evernote.
#
# This is the GUI wrapper for en_palmimport.py.
#
# Changelog:
# - basic functionality: 2009/06/27
# - clean up layout: 2009/06/27
# - add instructions, about panel: 2009/06/27
# - tricked into running on Snow Leopard: 2010/07/08
# - added support for parsing command line options: 2011/01/04
# - added gui for character encoding: 2011/01/04
# - added gui for locale used for date parsing: 2011/01/07
# ------------------- to do! ----------------------
# - make prettier UI?


#
# Hack around py2app bug/problem (?) on Snow Leopard, where it doesn't find
# wx in the py2app-provided app-local library directory
#
# thanks to http://wiki.python-ogre.org/index.php/End-User_Distribution
#
import sys, platform
if platform.system() == 'Darwin':
	sys.path.insert(0, '../Resources/lib/python2.5/lib-dynload')
	sys.path.insert(0, '../Resources/lib/python2.5/site-packages.zip')

#
# Python modules we use
#
import locale
import sys
import traceback
from en_palmimport import PalmNoteImporter
from threading import Thread
import wx
import wx.lib
import wx.lib.filebrowsebutton


class PalmImporterUI(wx.Frame):

	THREAD_RESULT_ID = wx.NewId()

	def __init__(self, parent, id, config):
		self.config = config
		self.InitLocale()
		wx.Frame.__init__(self, parent, id, "Evernote Palm importer")

		# IDs used for controls we'll interact with more than once
		self.ID_USERNAME = wx.NewId()
		self.ID_PASSWORD = wx.NewId()
		self.ID_FILEBROWSE = wx.NewId()
		self.ID_IMPORT = wx.NewId()
		self.ID_STATUS = wx.NewId()
		self.ID_ENCODING = wx.NewId()
		self.ID_LOCALE = wx.NewId()

		# create and lay out GUI controls
		self.controls = []
		vbox = wx.BoxSizer(wx.VERTICAL)
		panel = wx.Panel(self, -1)

		panel1 = wx.Panel(panel, -1)
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer1a = wx.StaticBoxSizer(wx.StaticBox(panel1, -1, 'Evernote credentials'))
		grid1 = wx.GridSizer(2, 2, 5, 5)
		self.controls.append(wx.StaticText(panel1, -1, "Username"))
		grid1.Add(self.controls[-1])
		self.controls.append(wx.TextCtrl(panel1, self.ID_USERNAME, 'XXX'))
		self.username = self.controls[-1]
		grid1.Add(self.controls[-1])
		self.controls.append(wx.StaticText(panel1, -1, "Password"))
		grid1.Add(self.controls[-1])
		self.controls.append(wx.TextCtrl(panel1, self.ID_PASSWORD, 'XXX',
						 style = wx.TE_PASSWORD))
		self.password = self.controls[-1]
		grid1.Add(self.controls[-1])
		sizer1a.Add(grid1)
		sizer1.Add(sizer1a, 0, wx.RIGHT, 10)
		sizer1b = wx.StaticBoxSizer(wx.StaticBox(panel1, -1, 'About this program'))
		vbox1 = wx.BoxSizer(wx.VERTICAL)
		vbox1.Add(wx.StaticText(panel1, -1, "Note importer (c) 2012 Matt Ginzton, matt@maddogsw.com."))
		vbox1.Add(wx.StaticText(panel1, -1, "Palm and Evernote may be trademarks of their respective companies."))
		vbox1Links = wx.BoxSizer(wx.HORIZONTAL)
		#vbox1Links.Add(wx.StaticText(panel1, -1, "Like this? "))
		#self.feedbackLink = wx.HyperlinkCtrl(panel1, -1, "Let me know", "mailto:matt@maddogsw.com?subject=Palm/Evernote%20importer")
		#vbox1Links.Add(self.feedbackLink)
		#vbox1Links.Add(wx.StaticText(panel1, -1, ". Like it a lot? "))
		#self.donateLink = wx.HyperlinkCtrl(panel1, -1, "Donate", "https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=6435444")
		#vbox1Links.Add(self.donateLink)
		#vbox1Links.Add(wx.StaticText(panel1, -1, "."))
		vbox1Links.Add(wx.StaticText(panel1, -1, "Read the "))
		self.usageLink = wx.HyperlinkCtrl(panel1, -1, "usage instructions", "http://www.maddogsw.com/evernote-utilities/evernote-palm-importer/")
		vbox1Links.Add(self.usageLink)
		vbox1Links.Add(wx.StaticText(panel1, -1, " to learn how to export your notes from Palm Desktop."))
		vbox1.Add(vbox1Links)
		sizer1b.Add(vbox1)
		sizer1.Add(sizer1b)
		panel1.SetSizer(sizer1)
		vbox.Add(panel1, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, 15)

		panel2 = wx.Panel(panel, -1)
		sizer2 = wx.StaticBoxSizer(wx.StaticBox(panel2, -1, 'Palm Desktop note export location'), wx.VERTICAL)
		sizer2a = wx.BoxSizer(wx.VERTICAL)
		self.filename = wx.lib.filebrowsebutton.FileBrowseButton(panel2, self.ID_FILEBROWSE,
									 labelText = "Exported file",
									 changeCallback = self.OnTextFieldChange)
		sizer2a.Add(self.filename, 0, wx.EXPAND)
		sizer2aa = wx.BoxSizer(wx.HORIZONTAL)
		sizer2aa.Add(wx.StaticText(panel2, -1, "Character encoding"))
		self.encoding = wx.TextCtrl(panel2, self.ID_ENCODING, config.pdExportEncoding)
		sizer2aa.Add(self.encoding, 1, wx.EXPAND)
		self.encodingLink = wx.HyperlinkCtrl(panel2, -1, "list of valid encodings", "http://docs.python.org/library/codecs.html#standard-encodings")
		sizer2aa.Add(self.encodingLink)
		sizer2a.Add(sizer2aa, 0, wx.EXPAND)
		sizer2ab = wx.BoxSizer(wx.HORIZONTAL)
		sizer2ab.Add(wx.StaticText(panel2, -1, "Locale used for date parsing"))
		self.locale = wx.Choice(panel2, self.ID_LOCALE, choices=self.validLocales)
		self.locale.SetSelection(self.locale.FindString(self.defaultLocale))
		sizer2ab.Add(self.locale, 0, wx.EXPAND)
		sizer2a.Add(sizer2ab, 0, wx.EXPAND)
		sizer2.Add(sizer2a, 0, wx.EXPAND)
		panel2.SetSizer(sizer2)
		vbox.Add(panel2, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)

		panel3 = wx.Panel(panel, -1)		
		sizer3 = wx.BoxSizer(wx.HORIZONTAL)
		self.controls.append(wx.Button(panel3, self.ID_IMPORT, "Import notes"))
		self.importButton = self.controls[-1]
		sizer3.Add(self.controls[-1], 1, wx.BOTTOM | wx.EXPAND, 5)
		panel3.SetSizer(sizer3)
		vbox.Add(panel3, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)

		panel4 = wx.Panel(panel, -1)
		sizer4 = wx.StaticBoxSizer(wx.StaticBox(panel4, -1, 'Status'))
		self.statusLabel = wx.ListBox(panel4, self.ID_STATUS)
		sizer4.Add(self.statusLabel, 1, wx.ALL | wx.EXPAND, 5)
		self.Report("Enter Evernote credentials, specify Palm Desktop export file, and press Import.")
		panel4.SetSizer(sizer4)
		vbox.Add(panel4, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)

		panel.SetSizer(vbox)
		vbox.Fit(self)
		self.Center()
		self.Show(True)

		wx.EVT_TEXT(self, self.ID_USERNAME, self.OnTextFieldChange)
		wx.EVT_TEXT(self, self.ID_PASSWORD, self.OnTextFieldChange)
		wx.EVT_BUTTON(self, self.ID_IMPORT, self.OnClickImport)
		self.importButton.SetDefault()
		self.importButton.Enable(False)

		self.filename.SetValue(config.pdExportFilename)

		self.worker = None
		self.importing = False
		self.Connect(-1, -1, PalmImporterUI.THREAD_RESULT_ID, self.OnThreadResult)
	
	def InitLocale(self):
		# Build list of locales, and figure out which one is current.  A little tricky since perhaps
		# no locale is current, in which case we need to make the default effective, and there might
		# be no available default.  And either the default or the specified one could be an alias for
		# a longer name found in the aliases table.
		self.validLocales = sorted(list(set(locale.locale_alias.values())))

		if self.config.locale and self.config.locale != "":
			defLocale = self.config.locale
		else:
			defLocale = locale.getdefaultlocale()[0]
			if not defLocale:
				defLocale = "C"
		# locale.locale_alias uses lowercase keys
		defLocale = defLocale.lower()
		# Accept both aliases and real names -- if alias convert to real name, else just assume
		# it's a real name and woe betide user who specifies something that's neither.
		if locale.locale_alias.has_key(defLocale):
			self.defaultLocale = locale.locale_alias[defLocale]
		else:
			self.defaultLocale = defLocale

	def Report(self, status):
		self.statusLabel.AppendAndEnsureVisible(status)

	def OnClickImport(self, event):
		if not self.importing:
			config = self.config
			config.enUsername = self.username.GetValue()
			config.enPassphrase = self.password.GetValue()
			config.pdExportFilename = self.filename.GetValue()
			config.pdExportEncoding = self.encoding.GetValue()
			config.locale = str(self.locale.GetStringSelection())
			self.Report("Import process beginning.")
			self.importButton.SetLabel("Stop importing")
			self.worker = PalmImporterUI.ImporterThread(self, config)
		else:
			self.Report("Cancelling import process.")
			self.importButton.SetLabel("Cancelling...")
			self.worker.stop()
			
	def OnTextFieldChange(self, event):
		if len(self.username.GetValue()) and len(self.password.GetValue()) and len(self.filename.GetValue()):
			self.importButton.Enable(True)
		else:
			self.importButton.Enable(False)
		
	def OnThreadResult(self, event):
		(stillGoing, statusMsg) = event.data
		self.importing = stillGoing
		self.Report(statusMsg)
		if not self.importing:
			self.Report("Import process complete.")
			self.importButton.SetLabel("Import notes")
	
	class ResultEvent(wx.PyEvent):
		def __init__(self, stillGoing, statusMsg):
			wx.PyEvent.__init__(self)
			self.SetEventType(PalmImporterUI.THREAD_RESULT_ID)
			self.data = [stillGoing, statusMsg]
	
	class ImporterThread(Thread):
		def __init__(self, notifyWindow, config):
			Thread.__init__(self)
			self.notifyWindow = notifyWindow
			self.importer = PalmNoteImporter()
			self.config = config
			self.config.cancelled = False
			self.config.interimProgress = self.interimProgress
			self.start()
		
		def interimProgress(self, statusMsg):
			self.sendProgress(True, statusMsg)

		def sendProgress(self, stillGoing, statusMsg):
			# incoming status messages are UTF-8, but UI might not be -- send as Python unicode
			msg = statusMsg.decode("utf-8")
			wx.PostEvent(self.notifyWindow, PalmImporterUI.ResultEvent(stillGoing, msg))

		def stop(self):
			self.config.cancelled = True
			
		def run(self):
			try:
				result = self.importer.ImportNotes(self.config)
				self.sendProgress(False, result)
			except:
				e = sys.exc_info()
				traceback.print_exc(file=sys.stderr)
				self.sendProgress(False, "Unexpected error.")

#
# If invoked directly, create frame window to run import logic.
#
if __name__ == "__main__":
	app = wx.PySimpleApp()

	config = PalmNoteImporter().Config()
	config.ParseOptions()

	frame = PalmImporterUI(None, wx.ID_ANY, config)

	app.MainLoop()
