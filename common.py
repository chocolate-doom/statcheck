#
# Copyright(C) 2011 Simon Howard
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA
# 02111-1307, USA.
#

import sys
import subprocess
import fcntl
from select import select
from fnmatch import fnmatch
import zipfile
import shutil
import os

from config import *

import wx

# Simple wxPython status window, with buttons to pause and abort processing.
# The reason for having this is that many windows tend to briefly pop up
# as each demo is processed; it's therefore very difficult to get to a
# terminal to type ^Z or ^C. Having a small GUI app allows this to be
# done using the mouse.

class StatusWindow(wx.Frame):
	def __init__(self, *args):
		wx.Frame.__init__(self, *args, size=(300,100))

		panel = wx.Panel(self)
		box = wx.BoxSizer(wx.VERTICAL)

		self.status_label = wx.StaticText(panel, -1, "Processing...")
		box.Add(self.status_label, 0, wx.ALL, 10)

		buttons_box = wx.BoxSizer(wx.HORIZONTAL)

		self.pause_button = wx.Button(panel, wx.ID_CLOSE, "Pause")
		self.pause_button.Bind(wx.EVT_BUTTON, self.OnPause)
		buttons_box.Add(self.pause_button)

		stop = wx.Button(panel, wx.ID_CLOSE, "Abort")
		stop.Bind(wx.EVT_BUTTON, self.OnStop)
		buttons_box.Add(stop, 0, wx.LEFT, 10)

		box.Add(buttons_box, 0, wx.ALL, 10)

		panel.SetSizer(box)
		panel.Layout()

	def SetCallbacks(self, pause, stop):
		self.pause_callback = pause
		self.stop_callback = stop

	def SetStatus(self, label):
		self.status_label.SetLabel(label)

	def SetPauseStatus(self, paused):
		if paused:
			self.pause_button.SetLabel("Resume")
		else:
			self.pause_button.SetLabel("Pause")

	def OnPause(self, event):
		self.pause_callback()
		pass

	def OnStop(self, event):
		self.stop_callback()
		pass

class StatusApp(wx.App):
	def __init__(self, idle_callback):
		self.idle_callback = idle_callback
		self.paused = False

		# Don't redirect stdout/stderr:
		wx.App.__init__(self, False)

	def OnInit(self):
		self.window = StatusWindow(None, -1, "statcheck status")
		self.window.Show(True)

		self.SetTopWindow(self.window)
		self.Bind(wx.EVT_IDLE, self.OnIdle)
		self.window.SetCallbacks(self.PauseCallback, self.StopCallback)

		return True

	def PauseCallback(self):
		self.paused = not self.paused
		self.window.SetPauseStatus(self.paused)

	def StopCallback(self):
		self.ExitMainLoop()

	def SetStatus(self, *args):
		self.window.SetStatus(*args)

	def OnIdle(self, event):
		if not self.paused:
			self.idle_callback()

def set_nonblocking(fileno):
	fl = fcntl.fcntl(fileno, fcntl.F_GETFL)
	fcntl.fcntl(fileno, fcntl.F_SETFL, fl | os.O_NONBLOCK)

class SubCommand:
	def __init__(self, cmd):
		cmd = cmd + "; echo __END__ > /dev/stderr"
		self.p = subprocess.Popen(cmd, shell=True,
		                          stdout=subprocess.PIPE,
		                          stderr=subprocess.PIPE)
		set_nonblocking(self.p.stdout.fileno())
		set_nonblocking(self.p.stderr.fileno())
		self.stdout = ""
		self.stderr = ""
		self.exit_code = None

	def poll_output(self):
		try:
			self.stdout += self.p.stdout.read()
		except IOError:
			pass

		try:
			self.stderr += self.p.stderr.read()
		except IOError:
			pass

	def poll(self):
		if self.exit_code is None:
			self.poll_output()

			# Finished?

			if self.stderr.endswith("__END__\n"):
				self.stderr = self.stderr[:-8]
				self.exit_code = self.p.wait()
				self.p.stdout.close()
				self.p.stderr.close()

	def fds(self):
		return (self.p.stdout.fileno(), self.p.stderr.fileno())

	def has_completed(self):
		return self.exit_code is not None

# A pipeline of commands allows multiple commands to be run in parallel.

class CommandPipeline:
	def __init__(self, pipeline_size):
		self.pipeline_size = pipeline_size
		self.pipeline = []

	# Return the number of processes that have not yet completed.

	def active_processes(self):
		result = 0

		for p, callback in self.pipeline:
			if not p.has_completed():
				result += 1

		return result

	# Periodically service the queue. This checks for output and
	# completions, and invokes the callback functions.

	def poll(self):
		for p, callback in self.pipeline:
			p.poll()

		# Check for completed commands and invoke callbacks.
		# Callback is only invoked for a command when all
		# previous commands have also completed.

		while len(self.pipeline) > 0 \
		  and self.pipeline[0][0].has_completed():
			p, callback = self.pipeline[0]
			self.pipeline = self.pipeline[1:]

			callback(p.exit_code, p.stdout, p.stderr)

	# Block until one of the subprocesses outputs something.

	def select(self):
		rlist = []

		for p, callback in self.pipeline:
			if not p.has_completed():
				rlist += p.fds()

		if len(rlist) > 0:
			select(rlist, (), ())

	# Block until there is space in the pipeline:

	def wait_for_space(self):
		while self.active_processes() >= self.pipeline_size:
			self.select()
			self.poll()

	# Run the specified command, invoking the callback when the
	# command completes.

	def call(self, cmd, callback):

		# Don't create more processes than will fit in the pipeline.
		# Block until there is space.

		self.wait_for_space()

		p = SubCommand(cmd)

		self.pipeline.append((p, callback))

	# Block until all outstanding commands complete and callbacks
	# are invoked.

	def finish(self):
		while self.active_processes() > 0:
			self.select()
			self.poll()

	def is_empty(self):
		return len(self.pipeline) == 0

def identify_game_type(filename):

	for game in GAME_PATHS.keys():
		if filename.startswith(game + "/"):
			return game

	return None # unknown!

def process_zipfile(filename, dir, callback):

	gametype = identify_game_type(filename)

	if not gametype:
		return

	fullpath = os.path.join(dir, filename)

	zf = zipfile.ZipFile(fullpath, 'r')

	for subfile in zf.namelist():
		# Don't handle lmps in subdirs
		if "/" in subfile:
			continue

		if subfile.lower().endswith(".lmp"):
			callback(gametype, fullpath, zf, subfile)

	zf.close()

def find_all_zips(path, pattern):

	result = []

	for dirpath, dirnames, filenames in os.walk(path):
		for filename in filenames:
			if not filename.endswith(".zip"):
				continue

			zippath = os.path.join(dirpath, filename)
			relpath = os.path.relpath(zippath, path)

			if identify_game_type(relpath) is None:
				continue

			if fnmatch(relpath, pattern):
				result.append(relpath)

	return result

def process_all_zips(path, callback):

	if len(sys.argv) > 1:
		pattern = sys.argv[1]
	else:
		pattern = "*"

	# Find the ZIP files to process.

	zips = find_all_zips(path, pattern)

	# Variables used by the processing function.

	container = {
		"processed": 0
	}

	zip_iterator = iter(zips)

	# Processing function. Each time this is called, another ZIP
	# file will be processed.

	def walk_next():
		try:
			zippath = zip_iterator.next()
		except StopIteration:
			app.ExitMainLoop()
			return

		try:
			process_zipfile(zippath, path, callback)
		except KeyboardInterrupt as e:
			raise e
		except Exception as e:
			print e
		finally:
			container["processed"] += 1

			pct = float(container["processed"]) * 100 / len(zips)

			app.SetStatus("%i / %i ZIP files processed (%i%%)" % (
				container["processed"],
				len(zips),
				pct))

	# Create the GUI app. The walk_next function above will be called
	# as an idle function by the GUI main loop, to process the ZIPs.

	app = StatusApp(walk_next)
	app.MainLoop()

