"""
SteamBMC: XBMC Addon to Browse and Launch Steam Games
Copyright (C) 2013 T. Oldbury

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
02110-1301, USA.
"""

import os, re, sys, shutil, urlparse, time
import xbmcplugin, xbmcgui, xbmcaddon, xbmc
import steamapi

handle = int(sys.argv[1])

addon = xbmcaddon.Addon()
addon_version = addon.getAddonInfo('version')
addon_name = addon.getAddonInfo('name')
lang = addon.getLocalizedString

ARTWORK_CACHE_DIR = xbmc.translatePath(os.path.join("special://masterprofile", "addon_data", addon_name, "artworkcache"))

"""
waitFor: Wait n seconds for a function to change state. (Useful for
         waiting for a cancel button to be pressed, etc.)

@param      secs    How long to wait, in seconds. Approximately.

@param      call    Callback to check.

@return     True if call() returned True eventually, False if it never did.
"""
def waitFor(secs, call):
    # Check every 0.1 seconds.
    while secs >= 0:
        if call():
            return True
        secs -= 0.1
        time.sleep(0.1) 
    return False

"""
checkWindowsBits: Are we running 32-bit or 64-bit Windows? 

@return     32 for 32-bit OR non-Windows, 64 for 64-bit Windows
"""
def checkWindowsBits():
    if 'PROGRAMFILES(X86)' in os.environ:
        return 64
    else:
        return 32

"""
showSettingsDialog: Launch the settings dialog for this plugin. When the dialog 
                    is closed, check the chosen settings are OK (through verifySettings.)
"""
def showSettingsDialog():
    addon.openSettings()
    verifySettings()

"""
verifySettings: Check that some of the settings that have been chosen are OK. If not, 
                show an error message.
"""
def verifySettings():
    # Check Steam bin exists
    steam_bin = addon.getSetting("steam_bin")
    if len(steam_bin.strip()) == 0:
        xbmcgui.Dialog().ok(lang(33021), lang(33023))
        return False
    elif not os.path.exists(steam_bin):
        xbmcgui.Dialog().ok(lang(33021), lang(33022) % steam_bin)
        return False
    return True

"""
setupDefaultSettings: Fill out Steam binary and other settings, for first run.
"""
def setupDefaultSettings():
    # Detect OS and fill out Steam binary
    if sys.platform.startswith("win"): 
        if checkWindowsBits() == 32:
            addon.setSetting("steam_bin", "C:\\Program Files\\Steam\\Steam.exe")
        else:
            addon.setSetting("steam_bin", "C:\\Program Files (x86)\\Steam\\Steam.exe")
    elif sys.platform.startswith("linux"): 
        addon.setSetting("steam_bin", "Linux Steam directory auto-fill TODO")

# Main entry point
if __name__ == "__main__":
    xbmc.log("SteamBMC (%s) Version %s" % (addon_name, addon_version))
    ifc = steamapi.SteamCommunityIfc(addon.getSetting("steam_publicurl"))
    cmd = urlparse.parse_qs(sys.argv[2][1:])
    xbmc.log("Our CMD : %s" % cmd, xbmc.LOGDEBUG)
    xbmc.log("Our ARGV: %s" % sys.argv, xbmc.LOGDEBUG)
    # Are we running for the first time?
    try:
        open(xbmc.translatePath(os.path.join("special://masterprofile", "addon_data", addon_name, "run_once.txt")), "r")
    except IOError:
        try:
            os.makedirs(ARTWORK_CACHE_DIR)
        except os.error: pass
        setupDefaultSettings()
        showSettingsDialog()
        fp = open(xbmc.translatePath(os.path.join("special://masterprofile", "addon_data", addon_name, "run_once.txt")), "w")
        fp.write("Delete this file to force first run actions to occur again.")
        fp.close()
    if 'do' not in cmd or len(cmd['do']) == 0:
        xbmc.log("Generating owned games list", xbmc.LOGDEBUG)
        progress = xbmcgui.DialogProgress()
        progress.create(lang(33011), lang(33015))
        progress.update(5, lang(330101))
        steamapi.steamCheck()
        # Add settings item
        listitem = xbmcgui.ListItem("Settings")
        xbmcplugin.addDirectoryItem(handle, sys.argv[0] + "?do=settings", listitem, isFolder=False)
        if not ifc.checkSteamConnectivity():
            xbmcgui.Dialog().ok(lang(33031), lang(33032) % ifc.http_code)
        else:
            try:
                ifc.getOwnedGames(prog_callback=progress)
            except RuntimeError:
                xbmcgui.Dialog().ok(lang(33041), lang(33042) % ifc.http_code)
            # Add games items
            for game in ifc.owned_games:
                listitem = xbmcgui.ListItem(game.game_name, iconImage=game.artwork_logo[0])
                if addon.getSetting("artwork_usefanart") == "true":
                    listitem.setProperty("Fanart_Image", game.artwork_promo[0])
                xbmcplugin.addDirectoryItem(handle, sys.argv[0] + "?do=game&game_id=" + str(game.game_id), listitem, isFolder=False)
        progress.update(100, lang(33016))
        xbmcplugin.endOfDirectory(handle)
        xbmc.log("Done!")
        progress.close()
    elif cmd['do'][0] == "game":
        xbmc.log("Generating owned games list", xbmc.LOGDEBUG)
        progress = xbmcgui.DialogProgress()
        progress.create(lang(33018), lang(33012))
        progress.update(50)
        try:
            ifc.getOwnedGames(get_art=False)
        except RuntimeError:
            xbmcgui.Dialog().ok(lang(33041), lang(33042) % ifc.http_code)
        for game in ifc.owned_games:
            if game.game_id == int(cmd['game_id'][0]):
                progress.update(100, lang(33019))
                if not game.launchGame():
                    progress.close()
                    if addon.getSetting("game_notify"):
                        xbmcgui.Dialog().ok(lang(33051), lang(33052))
                else:
                    if int(addon.getSetting("game_onlaunch")) == 1:
                        progress.update(100, lang(330102))
                        if not waitFor(5, progress.iscanceled):
                            xbmc.executebuiltin("Minimize()")
                    elif int(addon.getSetting("game_onlaunch")) == 2:
                        progress.update(100, lang(330103))
                        if not waitFor(5, progress.iscanceled):
                            xbmc.executebuiltin("Quit()")
                break
    elif cmd['do'][0] == "refresh_cache":
        progress = xbmcgui.DialogProgress()
        progress.create(lang(33017), lang(33012))
        ifc.getOwnedGames(art_update=True, prog_callback=progress)
        xbmc.executebuiltin(sys.argv[0])
    elif cmd['do'][0] == "settings":
        showSettingsDialog()
    sys.exit()
