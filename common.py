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
from fnmatch import fnmatch
import zipfile
import shutil
import os

from config import *

def identify_game_type(path, parent_path):

	path = os.path.relpath(path, parent_path)

	for game in GAME_PATHS.keys():
		if path.startswith(game + "/"):
			return game

	return None # unknown!

def process_zipfile(filename, parent_path, callback):

	gametype = identify_game_type(filename, parent_path)

	if not gametype:
		return

	zf = zipfile.ZipFile(filename, 'r')

	for subfile in zf.namelist():
		# Don't handle lmps in subdirs
		if "/" in subfile:
			continue

		if subfile.lower().endswith(".lmp"):
			callback(gametype, filename, zf, subfile)

	zf.close()

def process_all_zips(path, callback):

	if len(sys.argv) > 1:
		pattern = sys.argv[1]
	else:
		pattern = "*"

	for dirpath, dirnames, filenames in os.walk(path):
		for filename in filenames:
			if not filename.endswith(".zip"):
				continue

			zippath = os.path.join(dirpath, filename)

			if not fnmatch(os.path.relpath(zippath, path), pattern):
				continue

			try:
				process_zipfile(zippath, path, callback)
			except KeyboardInterrupt:
				print "*** Abort due to keyboard interrupt"
				return
			except Exception as e:
				print e

