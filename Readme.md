Synced Live Replay
==================

For the PC RTS game: Supreme Commander: Forged Alliance<sup>[1]</sup>

Features
--------

 - keeps connected replays in-sync
 - actions per minute graph
 - heatmap generator for actions target
 - map preview exporter
 - ingame chat viewer
 - replay parser
 - supports both FAF's<sup>[2]</sup> *.fafreplay* and vanilla *.SCFAreplay* files

How
---

It works with an included mods which overloads some of the game functions.

The mod adds a function to the game, which sends the clients current beatnumber and gamespeed to the replayserver.
If someone is behind in gametime the server sends a pause command to others to let the last client catch up. If the last client caught up, the server sends a resume command.

Screenshot
----------

![infotab screenshot][infotab]

Tech
----
 - [Python2.7]
 - [PyQt4]
 - [heatmap]
 - [py2exe]


Run
---
Start with
```
    python server.py
```


Build
-------
To build your own version just run:
```
    python py2exe setup.py
```

Links
--------

 - [Forum thread][forumthread]
 - [Download exe][download]


[1]:http://en.wikipedia.org/wiki/Supreme_Commander:_Forged_Alliance
[2]:http://faforever.com
[Python2.7]:http://python.org/
[PyQt4]:http://www.riverbankcomputing.com/software/pyqt/intro
[heatmap]:http://jjguy.com/heatmap/
[py2exe]:http://www.py2exe.org/
[infotab]:http://i.imgur.com/Ziw1Npb.png "Info tab screenshot"
[download]:https://bitbucket.org/fafafaf/livereplayserver/downloads
[forumthread]:http://www.faforever.com/forums/viewtopic.php?f=41&t=5774
