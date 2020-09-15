import sys
from PyQt4 import QtCore, QtNetwork, QtGui

import os

from win32file import CreateFile, ReadDirectoryChangesW
import win32con


PORT = 8000
DEFAULT_PATH = r"C:\ProgramData\FAForever\bin"

class FileWatcherThread(QtCore.QThread):
    fileChanged = QtCore.pyqtSignal(str)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.path_to_watch = DEFAULT_PATH

        self.hDir = CreateFile (
            self.path_to_watch,
            0x0001, # dunno, magic. FILE_LIST_DIRECTORY
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None
        )

    def setPath(self,string):
        self.path_to_watch = string

    def run(self):
        while True:
            results = ReadDirectoryChangesW (
                self.hDir,
                1024,
                False,
                win32con.FILE_NOTIFY_CHANGE_LAST_WRITE,
                None,
                None
            )
            if (3,r'game.log') in results:
                f = open(r'C:\ProgramData\FAForever\bin\game.log', "r");
                f.flush()
                foundBeat = False
                while not foundBeat:
                    try:
                        f.seek(256)
                    except IOError:
                        break
                    for line in f.readlines():
                        pos = line.find("warning: Beat:")
                        print line
                        if pos>=0:
                            foundBeat = line[pos:]
                            break
                if foundBeat:
                    self.fileChanged.emit(foundBeat[14:])
                else:
                    self.fileChanged.emit("nincsmeg")

class ReplayClient(QtGui.QMainWindow):
    def __init__(self, *args, **kwargs):
        QtGui.QMainWindow.__init__(self, *args, **kwargs)

        self.socket = QtNetwork.QTcpSocket()

        self.watcherThread = FileWatcherThread()


        self.setupGUI()

        self.watcherThread.fileChanged.connect(self.fileChanged)

    @QtCore.pyqtSlot(str)
    def fileChanged(self,string):
        self.statusBar().showMessage("Beat: " + string)

    def startWatcherThread(self):
        self.watcherThread.start()

    def setupGUI(self):
        self.setWindowTitle("ReplayCommander Client")

        self.commandLine = QtGui.QLineEdit()
        self.serverLine = QtGui.QLineEdit("localhost")
        self.connectButton = QtGui.QPushButton("Connect")

        self.startButton = QtGui.QPushButton("Start")
        self.startButton.setDisabled(True)
        self.startButton.clicked.connect(self.sendStart)

        self.stopButton = QtGui.QPushButton("Stop")
        self.stopButton.setDisabled(True)
        self.stopButton.clicked.connect(self.sendStop)

        self.connectButton.clicked.connect(self.connectToServer)
        self.commandLine.returnPressed.connect(self.issueRequest)

        self.socket.readyRead.connect(self.readFromServer)
        self.socket.disconnected.connect(self.serverHasStopped)

        self.FApathLine = QtGui.QLineEdit(os.path.join(DEFAULT_PATH,"ForgedAlliance.exe"))
        self.FApathButton = QtGui.QPushButton("find fa.exe")
        self.FApathButton.clicked.connect(self.findFa)

        self.FAlauncherButton = QtGui.QPushButton("Connect to livereplay")
        self.FAlauncherButton.clicked.connect(self.startFa)

        self.faLauncherBox = QtGui.QGroupBox("Fa launcher")
        faLauncherBoxLayout = QtGui.QGridLayout()
        faLauncherBoxLayout.addWidget(self.FApathLine,0,0)
        faLauncherBoxLayout.addWidget(self.FApathButton,0,1)
        faLauncherBoxLayout.addWidget(self.FAlauncherButton,1,0,1,2)
        self.faLauncherBox.setLayout(faLauncherBoxLayout)

        self.replayCommanderBox = QtGui.QGroupBox("Replay server manager")
        replayCommanderBoxLayout = QtGui.QGridLayout()
        replayCommanderBoxLayout.addWidget(self.startButton,0,0)
        replayCommanderBoxLayout.addWidget(self.stopButton,0,1)
        replayCommanderBoxLayout.addWidget(QtGui.QLabel(),1,0)
        replayCommanderBoxLayout.addWidget(self.serverLine,2,0)
        replayCommanderBoxLayout.addWidget(self.connectButton,2,1)
        self.replayCommanderBox.setLayout(replayCommanderBoxLayout)


        layout = QtGui.QGridLayout()
        layout.addWidget(self.faLauncherBox,0,0,1,2)
        layout.addWidget(self.replayCommanderBox,1,0,1,2)


        self.commandLine.setFocus()

        window = QtGui.QWidget()
        window.setLayout(layout)
        self.setCentralWidget(window)

    def findFa(self):
        file = QtGui.QFileDialog()
        filename = file.getOpenFileName(None,"Search ForgedAlliance.exe for me pls <3","","ForgedAlliance.exe","ForgedAlliance.exe")
        if filename:
            self.FApathLine.setText(filename)
            self.watcherThread.setPath(os.path.basename(filename))

    def startFa(self):
        sid = ""
        for i in os.urandom(3):
            sid+=str(hex(ord(i)).split("x")[1])

        command = []
        command.append(os.path.join(DEFAULT_PATH,"ForgedAlliance.exe"))
        command.append("/replay")
        command.append("gpgnet://" + str(self.serverLine.text()) + ":" + str(PORT) + "/" + sid)
        command.append("/log game.log")
        command.append("/init init_faf.lua")
        command.append("/showlog")

        import subprocess
        subprocess.Popen(command,cwd=DEFAULT_PATH)
        #self.startWatcherThread()

    def connectToServer(self):
        address = self.serverLine.text()
        if address:
            self.socket.connectToHost(address, PORT)
            if self.socket.isOpen():
                self.connectButton.setEnabled(False)
                self.serverLine.setEnabled(False)

                self.startButton.setEnabled(True)
                self.stopButton.setEnabled(True)

                self.statusBar().showMessage("Connected to: " + address + ":" + str(PORT))

    def issueRequest(self):
        command = self.commandLine.text()
        self.commandLine.clear()
        self.socket.writeData(command)

        print "Command sent: " + command

    def sendStart(self):
        self.socket.writeData("START")

    def sendStop(self):
        self.socket.writeData("STOP")

    def readFromServer(self):
        if self.socket.bytesAvailable > 0:
            data = self.socket.readAll()
            if data.startsWith("tick:"):
                seconds = 1 + int(data.split(":")[1]) / 10
                m, s = divmod(seconds, 60)
                h, m = divmod(m, 60)
                self.statusBar().showMessage("You should be at " + "%d:%02d:%02d" % (h, m, s))

    def serverHasStopped(self):
        self.socket.close()
        self.connectButton.setEnabled(True)

app = QtGui.QApplication(sys.argv)
form = ReplayClient()
form.show()
app.exec_()