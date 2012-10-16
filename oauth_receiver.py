# oauth_receiver.py
# (c) 2012 Matt Ginzton, matt@maddogsw.com
#
# Python class to implement a short-lived HTTP server suitable for embedding
# in a local application that needs to receive an OAuth callback.
#
# Changelog:
# - basic functionality: 2012/10/15


import BaseHTTPServer
import threading
import time
import urllib
import urlparse


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
	def do_GET(self):
		request = urlparse.urlparse(self.path)
		(response, body) = (404, None)
		if request.path == '/oauth_receiver':
			query = urlparse.parse_qs(request.query)
			try:
				self.oauth_token = query['oauth_token'][0]
				self.oauth_verifier = query['oauth_verifier'][0]
				(response, body) = (200, '<html><body>Thanks! Evernote Palm Importer is authorized to do what it needs. You may close this browser tab or window now.</body></html>')
				# Since that succeeded, copy answers up to owning object
				self.server.oauth_token = self.oauth_token
				self.server.oauth_verifier = self.oauth_verifier
			except:
				response = 400 # Bad request

		self.send_response(response)
		self.end_headers()
		if body:
			self.wfile.write(body)
		

class ReceiverThread(threading.Thread):
	daemon = True
	running = True
	
	def __init__(self, httpd):
		super(ReceiverThread, self).__init__(name = 'oauth_receiver')
		self.httpd = httpd

	def run(self):
		while self.running:
			self.httpd.handle_request()


class OAuthReceiver:
	def __init__(self):
		self.oauth_token = None
		self.oauth_verifier = None
		local_address = ('127.0.0.1', 0)
		self.httpd = BaseHTTPServer.HTTPServer(local_address, RequestHandler)
		self.url = 'http://%s:%d/oauth_receiver' % (self.httpd.server_address[0], self.httpd.server_port)
		self.thread = None
	
	def start(self):
		print 'listening as %s' % self.url
		self.thread = ReceiverThread(self.httpd)
		self.thread.start()
		
	def wait(self):
		try:
			while True:
				if hasattr(self.httpd, 'oauth_token') and hasattr(self.httpd, 'oauth_verifier'):
					return (self.httpd.oauth_token, self.httpd.oauth_verifier)
				print 'waiting for authorization...'
				time.sleep(1)
		except KeyboardInterrupt:
			print 'Interrupted; never mind'
			return (None, None)
		finally:
			self.thread.running = False
			urllib.urlopen(self.url + '/hangup') # bogus request to trigger shutdown


# unit test harness
if __name__ == '__main__':
	receiver = OAuthReceiver()
	receiver.start()
	receiver.wait()
