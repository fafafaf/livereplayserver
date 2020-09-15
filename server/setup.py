from distutils.core import setup
import py2exe
import shutil
import sys
import os
from datetime import date

def copydir(s,d):
    for f in os.listdir(s):
        if not os.path.isdir(d):
            os.mkdir(d)
        shutil.copy(s + f,d)

sys.path.append('src/')

shutil.rmtree('SyncedLiveReplay')

setup(      
      windows = [{
                  "script":"src/server.py",
		          "dest_base":"ReplayServer",
                  "version": str(date.today()).replace("-","."),
                  "name": "SyncedLiveReplay",
                  "icon_resources": [(1, "src/data/showreel.ico")]
		}],
      version = "0.1",
      description = "SyncedLiveReplay Server",
      name = "SyncedLiveReplay Server",
      options = {
                 "py2exe": {
                            'dist_dir': "SyncedLiveReplay",
                            'optimize': 2,
                            "includes":["sip", "PyQt4.QtNetwork", "replayreader","GPGPacket","heatmap"],
                            'bundle_files': 3,
                            'compressed': 0,
                            "skip_archive": 1,
                            "dll_excludes": ["MSVCP90.dll"],
			    'excludes': [
                                'PyQt4.uic.port_v3',
                                'tcl','Tkinter',
                                '_gtkagg', '_tkagg',"OpenGL", "PySide"],                          
                           }
                }, 
      zipfile = "data/"
    )

shutil.rmtree('build')
shutil.copy("C:\Python27\Lib\site-packages\cHeatmap-x64.dll", "SyncedLiveReplay/data/")
shutil.copy("src/data/_replaysync.nxt","SyncedLiveReplay/data/")
shutil.copy("src/data/showreel.png","SyncedLiveReplay/data/")
shutil.copy("src/data/unitsdb.json","SyncedLiveReplay/data/")
shutil.copy("src/data/nomap.png","SyncedLiveReplay/data/")
shutil.copy("src/data/acu.png","SyncedLiveReplay/data/")

copydir("src/data/flags/","SyncedLiveReplay/data/flags/")
copydir("src/data/factions/","SyncedLiveReplay/data/factions/")
