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

from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals

import sys
import subprocess
import fcntl
from select import select
import fnmatch
import zipfile
import shutil
import os
import re

from config import *

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

def find_from_prefix(set, filename):
	for prefix in set.keys():
		if filename.startswith(prefix + "/"):
			return prefix

	return None # unknown!

def identify_game_type(filename):
	gametype = find_from_prefix(GAME_PATHS, filename)

	if gametype is not None:
		return gametype

	# Might be a PWAD:

	pwad = find_from_prefix(PWADS, filename)

	if pwad is not None:
		filename, gametype = PWADS[pwad]

		return gametype

	# Unknown!

	return None

def get_pwad_filename(filename):
	pwad = find_from_prefix(PWADS, filename)

	if pwad is None:
		return None
	else:
		filename, gametype = PWADS[pwad]

		return filename

def process_zipfile(filename, dir, callback):

	gametype = identify_game_type(filename)

	if not gametype:
		return

	pwad = get_pwad_filename(filename)

	fullpath = os.path.join(dir, filename)

	zf = zipfile.ZipFile(fullpath, 'r')

	for subfile in zf.namelist():
		# Don't handle lmps in subdirs
		if "/" in subfile:
			continue

		if subfile.lower().endswith(".lmp"):
			callback(gametype, fullpath, zf, subfile, pwad)

	zf.close()

def patterns_to_regexp(patterns):
	"""Given a list of patterns, make a regexp that matches any one."""
	regexps = [fnmatch.translate(p) for p in patterns]
	return re.compile("(%s)" % ("|".join(regexps)))

def find_all_zips(path, regexp):
	"""Find .zip files in given path matching the given regexp."""
	result = []

	for dirpath, dirnames, filenames in os.walk(path):
		for filename in filenames:
			if not filename.endswith(".zip"):
				continue

			zippath = os.path.join(dirpath, filename)
			relpath = os.path.relpath(zippath, path)

			if identify_game_type(relpath) is None:
				continue

			if regexp.match(relpath):
				yield relpath

def process_all_zips(path, callback):

	if len(sys.argv) > 1:
		patterns = sys.argv[1:]
	else:
		patterns = ["*"]

	# Find the ZIP files to process.

	regexp = patterns_to_regexp(patterns)
	zips = list(find_all_zips(path, regexp))

	# Processing function. Each time this is called, another ZIP
	# file will be processed.

	for zippath in zips:
		try:
			process_zipfile(zippath, path, callback)
		except KeyboardInterrupt as e:
			raise e
		except Exception as e:
			print(e)

