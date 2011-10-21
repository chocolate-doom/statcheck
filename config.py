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

# Path to a copy of the compet-n archive.

COMPETN_PATH = "/path/to/pub/compet-n"

# Path to the installed copy of each game.

GAME_PATHS = {
	"doom": ("/home/me/ultimate-doom", "doom.exe"),
	"doom2": ("/home/me/doom2", "doom2.exe"),
	"tnt": ("/home/me/final-doom-tnt", "doom2.exe"),
	"plutonia": ("/home/me/final-doom-plutonia", "doom2.exe"),
}

# Path to the DOSbox executable.

DOSBOX = "dosbox"

# Path to the source port executable.

PORT_EXE = "chocolate-doom"

# Extra arguments to pass to the source port.

PORT_OPTIONS = "-nodraw -nosound -window -geometry 256x200"

