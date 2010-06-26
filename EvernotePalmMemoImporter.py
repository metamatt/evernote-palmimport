#! /usr/bin/python
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
# ------------------- to do! ----------------------
# - make prettier UI?


#
# Python modules we use
#
import sys
import traceback
from en_palmimport import PalmNoteImporter
from threading import Thread
import wx
import wx.lib
import wx.lib.filebrowsebutton


class PalmImporterUI(wx.Frame):

	THREAD_RESULT_ID = wx.NewId()

	def __init__(self, parent, id):
		wx.Frame.__init__(self, parent, id, "Evernote Palm importer")
		self.controls = []

		self.ID_USERNAME = wx.NewId()
		self.ID_PASSWORD = wx.NewId()
		self.ID_FILEBROWSE = wx.NewId()
		self.ID_IMPORT = wx.NewId()
		self.ID_STATUS = wx.NewId()

		vbox = wx.BoxSizer(wx.VERTICAL)
		panel = wx.Panel(self, -1)

		panel1 = wx.Panel(panel, -1)
		sizer1 = wx.BoxSizer(wx.HORIZONTAL)
		sizer1a = wx.StaticBoxSizer(wx.StaticBox(panel1, -1, 'Evernote credentials'))
		grid1 = wx.GridSizer(2, 2, 5, 5)
		self.controls.append(wx.StaticText(panel1, -1, "Username"))
		grid1.Add(self.controls[-1])
		self.controls.append(wx.TextCtrl(panel1, self.ID_USERNAME, ""))
		self.username = self.controls[-1]
		grid1.Add(self.controls[-1])
		self.controls.append(wx.StaticText(panel1, -1, "Password"))
		grid1.Add(self.controls[-1])
		self.controls.append(wx.TextCtrl(panel1, self.ID_PASSWORD, "",
										 style = wx.TE_PASSWORD))
		self.password = self.controls[-1]
		grid1.Add(self.controls[-1])
		sizer1a.Add(grid1)
		sizer1.Add(sizer1a, 0, wx.RIGHT, 10)
		sizer1b = wx.StaticBoxSizer(wx.StaticBox(panel1, -1, 'About this program'))
		vbox1 = wx.BoxSizer(wx.VERTICAL)
		vbox1.Add(wx.StaticText(panel1, -1, "Note importer (c) 2009 Matt Ginzton, matt@maddogsw.com."))
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
		sizer2 = wx.StaticBoxSizer(wx.StaticBox(panel2, -1, 'Palm Desktop note export location'))
		self.controls.append(wx.lib.filebrowsebutton.FileBrowseButton(panel2, self.ID_FILEBROWSE,
																	 labelText = "Exported file",
																	 changeCallback = self.OnTextFieldChange))
		self.filename = self.controls[-1]
		sizer2.Add(self.controls[-1], 1, wx.EXPAND)
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
		self.controls.append(wx.StaticText(panel4, self.ID_STATUS,
										   "Enter Evernote credentials, specify Palm Desktop export file, and press Import."))
		self.statusLabel = self.controls[-1]
		sizer4.Add(self.controls[-1], 1, wx.ALL | wx.EXPAND, 5)
		panel4.SetSizer(sizer4)
		vbox.Add(panel4, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 15)

		panel.SetSizer(vbox)
		vbox.Fit(self)
		self.Center()
		self.Show(True)

		wx.EVT_TEXT(self, self.ID_USERNAME, self.OnTextFieldChange)
		wx.EVT_TEXT(self, self.ID_PASSWORD, self.OnTextFieldChange)
		wx.EVT_BUTTON(self, self.ID_IMPORT, self.OnClickImport)
		self.importButton.SetDefault()
		self.importButton.Enable(False)
		
		self.worker = None
		self.importing = False
		self.Connect(-1, -1, PalmImporterUI.THREAD_RESULT_ID, self.OnThreadResult)
	
	def OnClickImport(self, event):
		if not self.importing:
			enUsername = self.username.GetValue()
			enPassphrase = self.password.GetValue()
			pdExportFilename = self.filename.GetValue()
			self.importButton.SetLabel("Stop importing")
			self.worker = PalmImporterUI.ImporterThread(self, enUsername, enPassphrase, pdExportFilename)
		else:
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
		self.statusLabel.SetLabel(statusMsg)
		if not self.importing:
			self.importButton.SetLabel("Import notes")
	
	class ResultEvent(wx.PyEvent):
		def __init__(self, stillGoing, statusMsg):
			wx.PyEvent.__init__(self)
			self.SetEventType(PalmImporterUI.THREAD_RESULT_ID)
			self.data = [stillGoing, statusMsg]
	
	class ImporterThread(Thread):
		def __init__(self, notifyWindow, enUsername, enPassphrase, pdExportFilename):
			Thread.__init__(self)
			self.notifyWindow = notifyWindow
			self.importer = PalmNoteImporter()
			self.config = self.importer.Config()
			self.config.cancelled = False
			self.config.enUsername = enUsername
			self.config.enPassphrase = enPassphrase
			self.config.pdExportFilename = pdExportFilename
			self.config.interimProgress = self.interimProgress
			self.start()
		
		def interimProgress(self, statusMsg):
			self.sendProgress(True, statusMsg)

		def sendProgress(self, stillGoing, statusMsg):
			wx.PostEvent(self.notifyWindow, PalmImporterUI.ResultEvent(stillGoing, statusMsg))

		def stop(self):
			self.config.cancelled = True
			
		def run(self):
			try:
				result = self.importer.ImportNotes(self.config)
				self.sendProgress(False, result)
			except:
				e = sys.exc_info()
				traceback.print_exception(e[0], e[1], e[2])
				self.sendProgress(False, "Unexpected error.")

#
# If invoked directly, create frame window to run import logic.
#
if __name__ == "__main__":
	app = wx.PySimpleApp()
	frame = PalmImporterUI(None, wx.ID_ANY)
	app.MainLoop()
