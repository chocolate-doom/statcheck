
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
	for dirpath, dirnames, filenames in os.walk(path):
		for filename in filenames:
			if not filename.endswith(".zip"):
				continue

			try:
				zippath = os.path.join(dirpath, filename)
				process_zipfile(zippath, path, callback)
			except KeyboardInterrupt:
				raise KeyboardInterrupt()
			except Exception as e:
				print e

