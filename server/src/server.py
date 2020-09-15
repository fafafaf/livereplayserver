
from PyQt4 import QtCore, QtNetwork, QtGui
import sys, os
from replayreader import ReplayParser, ReplayException
from replayFormat import cmdTypeToString
from GPGPacket import Pack, Unpack
from chart import ChartWidget
from range_slider import RangeSlider
import json

PORT = 8000

PlayerColors = [ # this is from faf.nxt/lua/GameColors.lua
            "#436eee",      # new blue1
            "#e80a0a",      # Cybran red
            "#616d7e",      # grey
            "#fafa00",      # new yellow
            '#FF873E',      # Nomads orange
            "#ffffff",      # white
            "#9161ff",      # purple
            "#ff88ff",      # pink
            "#2e8b57",      # new green
            "#131cd3",      # UEF blue
            "#5F01A7",      # dark purple
            "#ff32ff",      # new fuschia
            "#ffbf80",      # lt orange
            "#b76518",      # new brown
            "#901427",      # dark red
            "#2F4F4F",      # olive (dark green)
            "#40bf40",      # mid green
            "#66ffcc",      # aqua
        ]

def SecondsToHuman(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return "%d:%02d:%02d" % (h, m, s)

class ReplayLoader(QtCore.QThread):
    replayLoaded = QtCore.pyqtSignal(int)
    replayPercentage = QtCore.pyqtSignal(int)
    replayException = QtCore.pyqtSignal(str)

    def __init__(self):
        QtCore.QThread.__init__(self)
        self.filename = None
        self.replay = None

    def loadFile(self,filename):
        self.filename = filename
        self.start()

    @QtCore.pyqtSlot(int)
    def emitPercentage(self,percent):
        self.replayPercentage.emit(percent)

    def run(self):
        if self.filename:
            try:
                self.replay = ReplayParser(self.filename)
                self.replay.replayPercentage.connect(self.emitPercentage)

                time = QtCore.QTime()
                time.restart()
                self.replay.doStuff()
                self.replayLoaded.emit(time.elapsed())
                del time
            except ReplayException, e:
                self.replayException.emit(e.args[0])

class ReplayServerConnection(QtCore.QObject):
    def __init__(self,parent,socket):
        QtCore.QObject.__init__(self)

        self.parent = parent
        self.socket = socket
        self.socket.readyRead.connect(self.clientRead)
        self.socket.disconnected.connect(self.clientDisconn)

        self.needReplayPackets = False

        self.myTick = 0
        self.mySpeed = 0
        self.myId = 0

    @QtCore.pyqtSlot()
    def clientRead(self):

        if self.socket.bytesAvailable > 0:
            data = self.socket.readAll()
            if data.startsWith("G/"):
                self.parent.newConnectionSignal.emit(str(data[2:]))
#                self.catchUpWithReplay()
                self.sendAll()
                self.socket.waitForReadyRead(100)
#                self.socket.close()
            else:
                try:
                    parsed = []
                    parsed = Unpack(data=data)
                    if "BEAT" in parsed:
                        self.myTick, self.mySpeed = parsed["BEAT"][0]

                        if self.myTick == 1:
                            self.needReplayPackets = True
                            self.myId = self.parent.getConnectedGameCount()

                        minGameTick = self.parent.getLowestTick()
                        maxGameTick = self.parent.getHighestTick()
                        gameSpeed = self.parent.gameSpeed
                        needMoreNum = self.parent.needMoreNum()
                        buf = int(2**(gameSpeed/3)) * 10 if gameSpeed >= 0 else 10

                        if needMoreNum > 0:
                            self.clientSend(Pack(HasSupcom = [1])) # stop
                            self.parent.someonePaused = True
                            self.parent.replaySignal.emit("Waiting for " + str(needMoreNum) + " more connection")

                        if gameSpeed != self.mySpeed and self.myTick - self.parent.speedChangedAt > buf:
                            self.parent.broadcastPacket(Pack(HasForgedAlliance = [self.mySpeed])) # set speed
                            self.parent.gameSpeed = self.mySpeed
                            self.parent.speedChangedAt = self.myTick
                            self.parent.replaySignal.emit("GameSpeed changed to: " + str(self.mySpeed))

                        if self.myTick - minGameTick > buf:
                            self.parent.broadcastPacket(Pack(HasSupcom = [0])) # start all
                            self.clientSend(Pack(HasSupcom = [1])) # stop
                            self.parent.someonePaused = True
                            self.parent.replaySignal.emit("Replay stopped, someone at: " + SecondsToHuman(int(minGameTick/10)))
#                            print self.myTick, "min:", minGameTick, "max:", maxGameTick, "diff:", maxGameTick - minGameTick, self.parent.someonePaused, needMoreNum, self.myId, buf

                        if self.parent.someonePaused and maxGameTick - minGameTick == 0 and needMoreNum <= 0:
                            self.parent.broadcastPacket(Pack(HasSupcom = [0])) # start all
                            self.parent.someonePaused = False
                            self.parent.replaySignal.emit("Replay started, at " + SecondsToHuman(int(maxGameTick/10)))
#                            print self.myTick, "min:", minGameTick, "max:", maxGameTick, "diff:", maxGameTick - minGameTick, self.parent.someonePaused, needMoreNum, self.myId, buf


                    elif "GameState" in parsed:
                        if parsed["GameState"][0][0] == "Idle":
                            self.clientSend(Pack(CreateLobby = [0,0,"Hi!",self.parent.replay.getGameId(),0]))


                except Exception, e: # this could happen with fragmented packets
#                    print "something went wrong parsing the beat :", e , "sent data was:", data
                    pass

    @QtCore.pyqtSlot()
    def clientDisconn(self):
        self.parent.connections.remove(self)
        self.deleteLater()

    def clientSend(self,data):
        self.socket.writeData(data)

    def catchUpWithReplay(self):
        self.clientSend(self.parent.replay.getTicksToCurrentPosition())

    def sendAll(self):
        self.clientSend(self.parent.replay.getAll())



class ReplayServer(QtNetwork.QTcpServer):
    replaySignal = QtCore.pyqtSignal(str)
    newConnectionSignal = QtCore.pyqtSignal(str)
    startSignal = QtCore.pyqtSignal(str)
    replayPercentage = QtCore.pyqtSignal(int)
    replayIsLoaded = QtCore.pyqtSignal(int)
    replayError = QtCore.pyqtSignal(str)

    def __init__(self,port):
        QtNetwork.QTcpServer.__init__(self)

        self.port = port

        self.replayLoader = ReplayLoader()
        self.replayLoader.replayLoaded.connect(self.setReplay)
        self.replayLoader.replayPercentage.connect(self.emitPercentage)
        self.replayLoader.replayException.connect(self.emitError)

        if not self.listen(QtNetwork.QHostAddress.Any, port):
            return None

        self.connections = []
        self.newConnection.connect(self.addConn)
        self.replay = None

        self.waitForConnNum = 1
        self.someonePaused = False
        self.gameSpeed = 0
        self.speedChangedAt = 0

    @QtCore.pyqtSlot(int)
    def emitPercentage(self,percent):
        self.replayPercentage.emit(percent)

    @QtCore.pyqtSlot(str)
    def emitError(self,errMsg):
        self.replayError.emit(errMsg)

    def getConnectedGameCount(self):
        return sum(1 if client.needReplayPackets else 0 for client in self.connections)

    def getWaitForConnNum(self):
        return self.waitForConnNum

    def getCurrPort(self):
        return self.port

    def getLowestTick(self):
        return min(client.myTick for client in self.connections if client.needReplayPackets)

    def getHighestTick(self):
        return max(client.myTick for client in self.connections if client.needReplayPackets)

    def getLowestSpeed(self):
        return min(client.mySpeed for client in self.connections if client.needReplayPackets)

    def needMoreNum(self):
        return self.waitForConnNum - self.getConnectedGameCount()

    def setWaitForConnNum(self,num):
        self.waitForConnNum = int(num)
        if self.needMoreNum() <= 0 and self.someonePaused:
            self.broadcastPacket(Pack(HasSupcom = [0])) # start all
            self.someonePaused = False


    def broadcastPacket(self,data):
        for client in self.connections:
            if client.needReplayPackets:
                client.clientSend(data)

    @QtCore.pyqtSlot(int)
    def setReplay(self,ms):
        for conn in self.connections:
            conn.socket.writeData("\0")
            conn.socket.close()

        self.replay = self.replayLoader.replay
        self.replayIsLoaded.emit(ms)


    @QtCore.pyqtSlot()
    def addConn(self):
        socket = self.nextPendingConnection()
        if self.replay:
            self.connections.append(ReplayServerConnection(self,socket))
            self.newConnectionSignal.emit(socket.peerAddress().toString() + ":" + str(socket.peerPort()))
        else:
            socket.close()

class ReplayServerMain(QtGui.QMainWindow):
    def __init__(self, *args, **kwargs):
        QtGui.QMainWindow.__init__(self, *args, **kwargs)

        self.setBaseSize(800,700)
        self.server = None

        self.downloader = QtNetwork.QNetworkAccessManager(self)
        self.downloader.finished.connect(self.downloadFinished)

        self.downloadedFile = None

        self.frozen = getattr(sys, 'frozen', None)

        self.setWindowTitle("SyncedLiveReplay Server")
        self.setWindowIcon(QtGui.QIcon("data/showreel.png"))

        downloadAction = QtGui.QAction('Download replay',self)
        downloadAction.triggered.connect(self.downloadDialog)
        loadAction = QtGui.QAction('Load', self)
        loadAction.triggered.connect(self.selectFile)
        self.startFaAction = QtGui.QAction('Play replay',self)
        self.startFaAction.triggered.connect(self.startFa)
        self.startFaAction.setEnabled(False)
        saveModAction = QtGui.QAction('Export mod',self)
        saveModAction.triggered.connect(self.saveModFile)
        connectWindowAction = QtGui.QAction('Connect host',self)
        connectWindowAction.triggered.connect(self.connectWindow)

        changePortAction = QtGui.QAction('Change port', self)
        changePortAction.triggered.connect(self.restartReplayServer)
        self.setWaitAction = QtGui.QAction('Set minimum conn.', self)
        self.setWaitAction.triggered.connect(self.setWaitCount)
        self.aboutAction = QtGui.QAction('About', self)
        self.aboutAction.triggered.connect(self.showAbout)


        menubar = self.menuBar()
        filemenu = menubar.addMenu('&File')
        optionsmenu = menubar.addMenu('&Options')


        filemenu.addAction(loadAction)
        filemenu.addAction(saveModAction)
        filemenu.addAction(downloadAction)
        filemenu.addSeparator()
        filemenu.addAction(self.startFaAction)
        filemenu.addAction(connectWindowAction)
        optionsmenu.addAction(changePortAction)
        optionsmenu.addAction(self.setWaitAction)
        menubar.addAction(self.aboutAction)


        self.replayInfo = QtGui.QTextBrowser()
        self.replayInfo.setText("<h2>No replay loaded</h2><p>To load a replay click <b>File</b> menu <b>Load</b> option</p><p>To connect a remote replayserver choose <b>File</b> menu <b>Connect host</b> option</p>")
        self.replayInfo.setReadOnly(True)

        self.replayInfoMap = QtGui.QLabel()
        self.replayInfoMap.setAlignment(QtCore.Qt.AlignTop)

        self.settingsTab = QtGui.QTextBrowser()
        self.settingsTab.setReadOnly(True)
        self.settingsTab.setVisible(False)
        self.settingsTab.setMaximumWidth(256)

#        self.replayInfoOptions = QtGui.QLabel()

        self.replayInfoTabLayout = QtGui.QGridLayout()
        self.replayInfoTabLayout.addWidget(self.replayInfo,0,0, 2, 1)
        self.replayInfoTabLayout.addWidget(self.replayInfoMap,0,1)
        self.replayInfoTabLayout.addWidget(self.settingsTab,1,1)
#        self.replayInfoTabLayout.addWidget(self.replayInfoOptions,1,1)


        self.replayInfoTab = QtGui.QWidget()
        self.replayInfoTab.setLayout(self.replayInfoTabLayout)

        self.chatTab = QtGui.QTextEdit()
        self.chatTab.setReadOnly(True)

        self.heatmap = QtGui.QLabel()
        self.heatmapRangeSlider = RangeSlider()
        self.heatmapRangeSlider.setOrientation(QtCore.Qt.Horizontal)
        self.heatmapRangeSlider.sliderMoved.connect(self.generateNewHeatmap)
        self.heatmapSliderText = QtGui.QLabel()
        self.heatmapSliderText.setAlignment(QtCore.Qt.AlignCenter)
        self.heatmapSliderText.setMaximumHeight(12)

        self.heatmapTabLayout = QtGui.QVBoxLayout()
        self.heatmapTabLayout.addWidget(self.heatmap)
        self.heatmapTabLayout.addWidget(self.heatmapRangeSlider)
        self.heatmapTabLayout.addWidget(self.heatmapSliderText)


        self.heatmapTab = QtGui.QWidget()
        self.heatmapTab.setLayout(self.heatmapTabLayout)


        self.cpms = ChartWidget()
        self.cpms.setMaximumHeight(330)
        self.cpms.selectedTickSignal.connect(self.mouseMoved)

        self.actionsDisplay = QtGui.QTextBrowser()

        self.chartsTabLayout = QtGui.QVBoxLayout()
        self.chartsTabLayout.setAlignment(QtCore.Qt.AlignTop)
#        self.chartsTabLayout.setMargin(0)
        self.chartsTabLayout.addWidget(self.cpms)
        self.chartsTabLayout.addWidget(self.actionsDisplay)

        self.chartsTab = QtGui.QWidget()
        self.chartsTab.setLayout(self.chartsTabLayout)


        self.replayTabs = QtGui.QTabWidget()
        self.replayTabs.addTab(self.replayInfoTab,"Info")
        self.replayTabs.addTab(self.chatTab,"Chat")
        self.replayTabs.addTab(self.heatmapTab,"Heatmap")
        self.replayTabs.addTab(self.chartsTab,"Graph")
#        self.replayTabs.addTab(self.settingsTab,"Settings")

#        self.loadingBar = QtGui.QProgressBar()
#        self.loadingBar.hide()
#        self.statusBar().setSizeGripEnabled(False)
#        self.statusBar().addWidget(self.loadingBar,1)


        self.unitsdb = None
        if not self.frozen:
            self.unitsdb = json.loads(open(os.path.join(os.path.dirname(__file__),"data","unitsdb.json")).read())
        else:
            self.unitsdb = json.loads(open(os.path.join(os.path.dirname(sys.executable),"data","unitsdb.json")).read())



        self.setCentralWidget(self.replayTabs)

        self.startReplayServer()

    def showReplayExceptionMsg(self,msg):
        self.statusBar().showMessage("")
        QtGui.QMessageBox.warning(self,'Error', 'Can\'t parse this replay.<br/><br/>Error message:<br/><b>' + msg + '</b>')

    def downloadDialog(self):
        def startIt():
            try:
                id = int(replayInput.text())
                self.downloadReplay(int(replayInput.text()))
                dialog.close()
            except ValueError:
                QtGui.QMessageBox.warning(self,'Error', 'Replay id must be number')
                replayInput.clear()
                pass
        dialog = QtGui.QDialog(None,QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        dialog.setWindowTitle("Download FAF replay")
        dialogLayout = QtGui.QVBoxLayout()
        replayInput = QtGui.QLineEdit()
        replayInput.setPlaceholderText("replay id")
        replayInput.returnPressed.connect(startIt)
        connectButton = QtGui.QToolButton()
        connectButton.setText("Download")
        connectButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        connectButton.clicked.connect(startIt)
        dialogLayout.addWidget(QtGui.QLabel("Please enter the replay id"))
        dialogLayout.addWidget(replayInput)
        dialogLayout.addWidget(connectButton,0)
        dialog.setLayout(dialogLayout)
        dialog.exec_()


    def downloadReplay(self,id):
        url = "http://www.faforever.com/faf/vault/replay_vault/replay.php?id=%d" % id
        self.statusBar().showMessage("Downloading replay...")
        self.downloadedFile = self.downloader.get(QtNetwork.QNetworkRequest(QtCore.QUrl(url)))

    def downloadFinished(self):
        if (self.downloadedFile.error() == QtNetwork.QNetworkReply.NoError and self.downloadedFile.header(QtNetwork.QNetworkRequest.ContentLengthHeader).toInt() != (0,False)):
            try:
                tempFileName = "temp.fafreplay"
                f = open(tempFileName,"wb")
                f.write(self.downloadedFile.readAll())
                f.close()

                self.setWindowTitle("faf replay")
                self.statusBar().showMessage("Parsing the replay file..")
                self.server.replayLoader.loadFile(tempFileName)
            except IOError:
                QtGui.QMessageBox.warning(self,'Error', 'Can\'t write temp file')
                pass
        else:
            self.statusBar().showMessage("Download failed")
            QtGui.QMessageBox.warning(self,'Error', 'Can\'t download that replay')
        self.downloadedFile = None

    def connectWindow(self):
        def startIt():
            addr = str(addrInput.text())
            if addr:
                if addr.find(":") == -1:
                    addr += ":8000"
                    self.startFa(addr)
                dialog.close()
        dialog = QtGui.QDialog(None,QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        dialog.setWindowTitle("Connect to host")
        dialogLayout = QtGui.QVBoxLayout()
        addrInput = QtGui.QLineEdit()
        addrInput.setPlaceholderText("host address")
        addrInput.returnPressed.connect(startIt)
        connectButton = QtGui.QToolButton()
        connectButton.setText("connect")
        connectButton.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        connectButton.clicked.connect(startIt)
        dialogLayout.addWidget(QtGui.QLabel("Please enter the host's address (ip or hostname)"))
        dialogLayout.addWidget(addrInput)
        dialogLayout.addWidget(connectButton,0)
        dialog.setLayout(dialogLayout)
        dialog.exec_()

    def returnMapPreviewPixmap(self,map_path):
        try:
            mapdirs = [
                os.path.join(os.environ["USERPROFILE"],r"Documents\My Games\Gas Powered Games\Supreme Commander Forged Alliance"),
                r"C:\Program Files (x86)\THQ\Gas Powered Games\Supreme Commander - Forged Alliance",
                r"C:\Program Files\THQ\Gas Powered Games\Supreme Commander - Forged Alliance",
                r"C:\Program Files (x86)\Steam\steamapps\common\Supreme Commander Forged Alliance"
            ]

            fafPath = r"C:\ProgramData\FAForever\fa_path.lua"
            if os.path.exists(fafPath):
                try:
                    mapdir = open(fafPath,"rt").readline().split("'")[1].replace("\\\\","\\")
                    if os.path.exists(mapdir):
                        mapdirs.append(mapdir)
                except:
                    pass

            file = None
            saveFile = None
            for dirName in mapdirs:
                if os.path.exists(dirName + map_path):
                    file = os.path.join(dirName + map_path)
                    saveFile = file.replace(".scmap","_save.lua")
                    break

            if file:
                with open(file,"rb") as f:
                    f.seek(30) # scmap header
                    sizebuf = bytearray(f.read(4))
                    ddsSize = sizebuf[0] | sizebuf[1] << 8 | sizebuf[2] << 16 | sizebuf[3] << 32
                    f.seek(127,1) # dds header
                    img = bytearray(ddsSize-127)
                    f.readinto(img)
                    del img[::4]

                    size = int((len(img)/3) ** (1.0/2))

                mapImg = QtGui.QImage(img,size,size,QtGui.QImage.Format_RGB888).rgbSwapped()

                if os.path.exists(saveFile):
                        with open(saveFile,'rt') as f:
                            # find positions in mapname_save.lua file
                            armyPos = dict()
                            army = None
                            for line in f:
                                if line.find("ARMY_") > -1:
                                    army = line.strip().split("'")
                                if line.find("position") > -1 and army:
                                    if army:
                                        x,z,y = line.strip()[24:-3].split(", ",3) # ['position'] = VECTOR3(
                                        armyPos[army[1]] = float(x),float(y)
                                        army = None

                            # draw positions to the map preview image
                            acuIcon = QtGui.QPixmap("data/acu.png")
                            mask = acuIcon.createMaskFromColor(QtGui.QColor(192,165,32),QtCore.Qt.MaskOutColor)

                            p = QtGui.QPainter()
                            p.begin(mapImg)

                            for id,player in self.server.replay.army.iteritems():
                                if id != 255 and player["ArmyName"] in armyPos:
                                    x,y = armyPos[player["ArmyName"]]
                                    x *= size / float(self.server.replay.luaScenarioInfo["size"][1.0])
                                    y *= size / float(self.server.replay.luaScenarioInfo["size"][2.0])
                                    p.setPen(QtGui.QPen(QtGui.QColor(PlayerColors[int(player["PlayerColor"])-1]), 1, QtCore.Qt.SolidLine))
                                    p.drawPixmap(x-5,y-5,12,12,acuIcon)
                                    p.drawPixmap(x-5,y-5,12,12,QtGui.QPixmap(mask))
                                    p.setPen(QtGui.QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine))
                                    p.drawText(QtCore.QRectF(x-51,y+11,100,10), player["PlayerName"], QtGui.QTextOption(QtCore.Qt.AlignCenter))
                                    p.setPen(QtGui.QPen(QtCore.Qt.white, 1, QtCore.Qt.SolidLine))
                                    p.drawText(QtCore.QRectF(x-50,y+10,100,10), player["PlayerName"], QtGui.QTextOption(QtCore.Qt.AlignCenter))
                            p.end()
                return QtGui.QPixmap(mapImg)
            else:
                raise IOError
        except IOError:
            return QtGui.QPixmap("data/nomap.png")

    def startFa(self,addr=None):
        if not addr:
            addr = "localhost:8000"
        fafdir = r"C:\ProgramData\FAForever"
        if os.path.exists(os.path.join(fafdir,r"gamedata\_replaysync.nxt")) or QtGui.QMessageBox.Yes == QtGui.QMessageBox.warning(None,"Mod not found","Could not find the _replaysync.nxt in:\n" + os.path.join(fafdir,r"gamedata\_replaysync.nxt") + ".\n\nAre you sure you want to continue?",QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, QtGui.QMessageBox.No):
            (state,pid) = QtCore.QProcess().startDetached(os.path.join(fafdir,r"bin\ForgedAlliance.exe"), ["/bugreport","/syncreplay", "/gpgnet", addr], os.path.dirname(os.path.join(fafdir,r"bin\ForgedAlliance.exe")))
            if state == QtCore.QProcess.NotRunning:
                msg = QtGui.QMessageBox()
                msg.setWindowTitle("ERROR")
                msg.setText("Could not start FA")
                msg.exec_()

    def saveModFile(self):
        fileName = QtGui.QFileDialog.getSaveFileName(self, "Export mod", "C:\ProgramData\FAForever\gamedata\_replaysync.nxt", "_replaysync.nxt", "_replaysync.nxt")
        if fileName:
            confirmCopy = QtGui.QMessageBox.question(self,"Confirm copy","Are you sure you want to copy the mod to:<br/> <b>" + fileName + "</b>?",QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, QtGui.QMessageBox.Yes)
            if confirmCopy == QtGui.QMessageBox.Yes:
                if not self.frozen:
                    fromFile = os.path.join(os.path.dirname(__file__),"data","_replaysync.nxt")
                else:
                    fromFile = os.path.join(os.path.dirname(sys.executable),"data","_replaysync.nxt")

                toFile = QtCore.QFile(fileName)
                if not toFile.exists() or toFile.remove():
                    if not QtCore.QFile.copy(fromFile,fileName):
                        raise Exception("Could not copy the file")
                else:
                    raise  Exception("Could not overwrite the file")

    def showAbout(self):
        about = QtGui.QDialog(None,QtCore.Qt.WindowTitleHint | QtCore.Qt.WindowSystemMenuHint)
        about.setWindowTitle("About")
        aboutText =\
            """
                <h1>Synced Live Replay server</h1>
                <h5>by PattogoTehen in 2013</h5>
                <p>It's a livereplay server which allows players to watch a replay in-sync.</p>
                <p>The server detects when someone is behind in game and sends a pause signal to the other viewers. When the player catches up with the others, the server sends a resume signal.</p>
                <p>So it tries to make sure that everyone see the same thing at the same time</p>
                <p>How to use:
                <p>
                    Host
                    <ul>
                    <li> make sure that you have forwarded tcp port 8000
                    <li> start this program
                    <li> load a replay
                    </ul>
                </p>
                <p>
                    Clients
                    <ul>
                    <li> put '_replaysync.nxt' file to C:\ProgramData\FAForever\gamedata
                    <li> go to folder: C:\ProgramData\FAForever\\bin
                    <li> start fa with: ForgedAlliance.exe /gpgnet &lt;host_address&gt;:8000 /syncreplay
                    </ul>
                </p>
                </p>
                <p>
                    More info on faf forum: <a href="http://www.faforever.com/forums/viewtopic.php?f=41&t=5774">http://www.faforever.com/forums/viewtopic.php?f=41&t=5774</a> <br/>
                    Source available on bitbucket: <a href="https://bitbucket.org/fafafaf/livereplayserver">https://bitbucket.org/fafafaf/livereplayserver</a>
                </p>
                <p>
                    Huge thanks to Aulex and TA4Life for testing, and Domino for lua support
                </p>
            """
        aboutLabel = QtGui.QLabel(aboutText)
        aboutLabel.setWordWrap(True)
        aboutLabel.setOpenExternalLinks(True)
        aboutLabel.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.LinksAccessibleByMouse)
        aboutLayout = QtGui.QVBoxLayout()
        aboutLayout.addWidget(aboutLabel)
        about.setLayout(aboutLayout)
        about.exec_()


    def setWaitCount(self):
        num, change = QtGui.QInputDialog.getInt(self, "Wait for players", "Enter a minimal connection count:",self.server.getWaitForConnNum(),1)
        if change and num > 0:
            self.server.setWaitForConnNum(num)
            self.statusBar().showMessage("Waiting for " + str(num) + " connections")
        else:
            self.statusBar().showMessage("Wait counter not changed")

    def restartReplayServer(self):
        port, change = QtGui.QInputDialog.getInt(self, "Change port", "Enter port number:",self.server.getCurrPort(),1024,65536)
        if change and port != "" and int(port) > 1024 and port != self.server.getCurrPort():
            self.server.deleteLater()
            self.server = None
            self.replayInfo.clear()
            self.replayInfo.setText("No replay file loaded")
            self.startReplayServer(int(port))
        else:
            self.statusBar().showMessage("Port not changed")

    @QtCore.pyqtSlot(int,int)
    def generateNewHeatmap(self,lowtick,hightick):
        if self.server.replay:
            self.heatmap.setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(self.server.replay.returnHeatmap(lowtick,hightick),512,512,QtGui.QImage.Format_ARGB32)))
            self.heatmapSliderText.setText(SecondsToHuman(lowtick/10) + " (" + str(lowtick) + ") - " + SecondsToHuman(hightick/10) + " (" + str(hightick) + ")")

    @QtCore.pyqtSlot(int)
    def updatePercentage(self,percent):
 #       self.loadingBar.setValue(percent)
        pass

    @QtCore.pyqtSlot(int)
    def populatePages(self,ms):
        self.replayInfo.setText(self.server.replay.getInfo())
        self.chatTab.setText(self.server.replay.getChat())
        self.settingsTab.setVisible(True)
        self.settingsTab.setText(self.server.replay.getSettings())
        self.heatmap.setPixmap(QtGui.QPixmap.fromImage(QtGui.QImage(self.server.replay.returnHeatmap(),512,512,QtGui.QImage.Format_ARGB32)))
        self.heatmapRangeSlider.setMinimum(0)
        self.heatmapRangeSlider.setMaximum(self.server.replay.ticks)
        self.heatmapRangeSlider.setLow(0)
        self.heatmapRangeSlider.setHigh(self.server.replay.ticks)
        self.statusBar().showMessage("Replay loaded in " + str(ms) + "ms")
        self.startFaAction.setEnabled(True)
        self.replayInfoMap.setPixmap(self.returnMapPreviewPixmap(self.server.replay.luaScenarioInfo["map"]))
        self.replayInfoMap.setToolTip(self.server.replay.mapDisplayName())
        self.genChart()

    def genChart(self):

        self.actionsDisplay.clear()
        playersNumber = len(self.server.replay.cpmChart)
        ticksNumber = self.server.replay.ticks
        maxHVal = 0


        self.cpmData = [0] * playersNumber
        for i in range(playersNumber):
            self.cpmData[i] = [0] * (ticksNumber + 600)
            for tick in self.server.replay.cpmChart[i]:
                self.cpmData[i][tick] += 1

            num = sum(self.cpmData[i][0:600])
            prevNum = self.cpmData[i][0]
            for tick in range(1,ticksNumber):
                num = num - prevNum + self.cpmData[i][tick+600]
                prevNum = self.cpmData[i][tick]
                if num > maxHVal:
                    maxHVal = num
                self.cpmData[i][tick] = num

            del self.cpmData[i][ticksNumber:]
        self.cpms.graph(self.cpmData,maxHVal,PlayerColors)

    def mouseMoved(self,tick):
        ticksNum = self.server.replay.ticks
        playersNum = len(self.server.replay.cpmChart)

        filteredCommands = [None] * ticksNum
        for i in range(playersNum):
            filteredCommands[i] = []

        for action in self.server.replay.commands:
            if action["tick"] > tick and action["tick"] < tick+600:
                filteredCommands[action["player"]].append(action)

        text = "time: " + SecondsToHuman(tick/10) + " to " + SecondsToHuman((tick+600 if tick+600 < self.server.replay.ticks else self.server.replay.ticks)/10) + "<br/>"
        for playerId in range(playersNum):
            text+= "<b>" + self.server.replay.army[playerId]["PlayerName"] + "</b>: " + (str(self.cpmData[playerId][tick]) if self.cpmData[playerId][tick] else "no") + " actions<br/>"

            for action in filteredCommands[playerId]:
                text+= "" + cmdTypeToString[action["cmdType"]] + (" (" + action["lua"]["Enhancement"] + ")" if action["lua"] else "") + (" (<a title=\'" + (self.unitsdb[action["bp"]] if action["bp"] in self.unitsdb else action["bp"]) + "\'>" + action["bp"] + "</a>)" if action["bp"] else "") + ", "
            text+="<br/><br/>"

        self.actionsDisplay.setText(text)



    def startReplayServer(self,port=PORT):
        self.server = ReplayServer(port)
        self.server.replayPercentage.connect(self.updatePercentage)
        self.server.replayIsLoaded.connect(self.populatePages)
        self.server.replayError.connect(self.showReplayExceptionMsg)

        if self.server.isListening():
            self.server.newConnectionSignal.connect(self.newConnection)
            self.server.replaySignal.connect(self.replaySignal)

            self.setWaitAction.setEnabled(True)
            self.statusBar().showMessage("Listening on port: " + str(port))
        else:
            self.setWaitAction.setEnabled(False)
            self.replayInfo.clear()
            self.replayInfo.setText("Could not listen on port " + str(port) + ".\n\nTry changing the ports in Options.")
            self.statusBar().showMessage("NOT listening, try changing the port!")

    @QtCore.pyqtSlot(str)
    def replaySignal(self,string):
        self.statusBar().showMessage(string)

    @QtCore.pyqtSlot()
    def selectFile(self):
        file = QtGui.QFileDialog.getOpenFileName(None, "Select FA replay", r"C:\ProgramData\FAForever\replays","*.fafreplay;;*.SCFAReplay")
        if file:
            self.setWindowTitle(os.path.basename(str(file)))
            self.statusBar().showMessage("Parsing the replay file..")
            self.server.replayLoader.loadFile(file)

#            self.loadingBar.reset()
#            self.loadingBar.show()

    @QtCore.pyqtSlot(str)
    def newConnection(self,string):
        self.statusBar().showMessage("New connection from: " + string)

app = QtGui.QApplication(sys.argv)
form = ReplayServerMain()
form.show()
app.exec_()
