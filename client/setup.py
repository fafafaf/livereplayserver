from distutils.core import setup
import py2exe
import os

t1 = {
      "script":"src/client.py",
      "dest_base":"ReplayCommander",
      }


setup(      
      windows = [t1], # targets to build
      version = "0.1",
      description = "LiveReplay ClientCommander",
      name = "LiveReplay ClientCommander",
      options = {
                 "py2exe": {
                            'dist_dir': "client",
                            'optimize': 2,
                            "includes":["sip", "PyQt4.QtNetwork"], "dll_excludes": ["MSVCP90.dll", "POWRPROF.dll", "API-MS-Win-Core-LocalRegistry-L1-1-0.dll", "MPR.dll"],
			    'excludes': [
                                'PyQt4.uic.port_v3',
                                'tcl','Tkinter',
                                '_gtkagg', '_tkagg',"OpenGL", "PySide"],                          
                           }
                },
      zipfile = "replayClient.lib"
    )

