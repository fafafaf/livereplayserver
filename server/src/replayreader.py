import heatmap
from PyQt4 import QtCore
from collections import defaultdict
import json
from datetime import datetime
from replayFormat import ECmdStreamOp,EUnitCommandType,STITARGET,LUA_TYPE

class ReplayException(Exception):
    pass

class ReplayParser(QtCore.QObject):

    replayPercentage = QtCore.pyqtSignal(int)

    def getFac(self,num):
        if num == 1.0:
            return "<img height=24 src=\"data/factions/uef.png\"/>"
        elif num == 2.0:
            return "<img height=24 src=\"data/factions/aeon.png\"/>"
        elif num == 3.0:
            return "<img height=24 src=\"data/factions/cyb.png\"/>"
        elif num == 4.0:
            return "<img height=24 src=\"data/factions/sera.png\"/>"
        else:
            return str(num)

    def returnNextString(self):
        buf = ""
        while 1:
            c = self.binary.readRawData(1)
            if c == "\0":
                break
            else:
                buf += c
        return buf.decode("utf-8")

    def parseLua(self):
        type = ord(self.binary.readUInt8())
        if type == LUA_TYPE.NUMBER:
            return self.binary.readFloat()
        elif type == LUA_TYPE.STRING:
            return self.returnNextString()
        elif type == LUA_TYPE.NIL:
            self.binary.skipRawData(1)
            return None
        elif type == LUA_TYPE.BOOL:
            return True if ord(self.binary.readUInt8()) == 1 else False
        elif type == LUA_TYPE.LUA:
            result = {}
            while ord(self.binary.readUInt8()) != LUA_TYPE.LUA_END:
                self.binary.skipRawData(-1)
                key = self.parseLua()
                value = self.parseLua()
                result[key] = value
            return result

        raise ReplayException('Error in parsing the lua table')

    def returnCheckSum(self):
        checksum = ""
        for chr in self.binary.readRawData(16):
            checksum += "%0.2x" % ord(chr)
        return checksum


    def parseHeader(self):
        self.replayPatchFieldId = self.returnNextString()
        self.binary.skipRawData(3)

        self.replayVersionId, self.map  = self.returnNextString().split("\r\n")
        self.binary.skipRawData(4)

        self.gameModsNum = self.binary.readUInt32()
        self.gameMods = self.parseLua()

        self.luaScenarioSize = self.binary.readUInt32()
        self.luaScenarioInfo = self.parseLua()

        self.numOfSources = ord(self.binary.readUInt8())

        self.players = {}
        for i in range(self.numOfSources):
            name = self.returnNextString()
            playerid = self.binary.readUInt32()
            self.players[name] = str(playerid)

        self.cheatsEnabled = ord(self.binary.readUInt8())
        self.numOfArmies = ord(self.binary.readUInt8())

        for i in range(self.numOfArmies):
            self.CPM.append(0) # create cpms

            playerDataSize = self.binary.readUInt32()
            playerData = self.parseLua()
            playerSource = ord(self.binary.readUInt8())
            self.army[playerSource] = playerData

            if playerSource != 255:
                self.binary.skipRawData(1)

        self.randomSeed = self.binary.readUInt32()

    def unpackReplay(self,rfile):
        rfile = str(rfile)
        replay = open(rfile, "rb")
        if rfile.endswith(".fafreplay"):
            self.fafInfo = json.loads(replay.readline())
            self.unpackedFile = QtCore.qUncompress(QtCore.QByteArray.fromBase64(replay.read()))
            self.binary = QtCore.QDataStream(self.unpackedFile)
            self.binary.setByteOrder(QtCore.QDataStream.LittleEndian)
            self.binary.setFloatingPointPrecision(QtCore.QDataStream.SinglePrecision)

            #w = open("out.SCFAReplay","wb")
            #w.write(self.binary)
            #w.close()
        else:
            self.unpackedFile = QtCore.QByteArray(replay.read())
            self.binary = QtCore.QDataStream(self.unpackedFile)
            self.binary.setByteOrder(QtCore.QDataStream.LittleEndian)
            self.binary.setFloatingPointPrecision(QtCore.QDataStream.SinglePrecision)

        replay.close()

    def parseTicks(self):
        prevTick = -1
        prevSum = None

        while not self.binary.atEnd():
            message_op = ord(self.binary.readUInt8())
            message_len = self.binary.readUInt16()

            if message_op == ECmdStreamOp.CMDST_Advance:
                self.ticks += self.binary.readUInt32()

            elif message_op == ECmdStreamOp.CMDST_SetCommandSource:
                player = ord(self.binary.readUInt8())

            elif message_op == ECmdStreamOp.CMDST_CommandSourceTerminated:
                self.lasttick[player] = self.ticks

            elif message_op == ECmdStreamOp.CMDST_VerifyChecksum:
                checksum = self.returnCheckSum()
                tickNum = self.binary.readUInt32()

                if tickNum == prevTick:
                    if prevSum != checksum:
                        raise ReplayException("DESYNC")

                prevTick = tickNum
                prevSum = checksum

            elif(message_op == ECmdStreamOp.CMDST_RemoveCommandFromQueue):
#                    print "CMDST_RemoveCommandFromQueue",

                cmdId = self.binary.readUInt32()
                entId = self.binary.readUInt32()


            elif(message_op == ECmdStreamOp.CMDST_SetCommandTarget):
#                    print "CMDST_SetCommandTarget",

                cmdId = self.binary.readUInt32()
                stitarget = ord(self.binary.readUInt8())

                if stitarget == STITARGET.NONE:
                    pass
                elif stitarget == STITARGET.Entity:
                    entId = self.binary.readUInt32()
                elif stitarget == STITARGET.Position:
                    (x,y,z) = self.binary.readFloat(), self.binary.readFloat(), self.binary.readFloat()
                    self.pts.append((self.ticks,x,z))
                else:
                    raise ReplayException("Not valid stitarget",stitarget)

            elif message_op == ECmdStreamOp.CMDST_ProcessInfoPair:
                entId = self.binary.readUInt32()
                arg1 = self.returnNextString()
                arg2 = self.returnNextString()

                del entId, arg1, arg2

            elif(message_op == ECmdStreamOp.CMDST_LuaSimCallback):
                function = self.returnNextString()
                lua = self.parseLua()

                if function == "GiveResourcesToPlayer":
                    if "Msg" in lua:
                        if int(lua["From"])-1 == -2:
                            pass # observer talking..
                        else:
                            if self.army[int(lua["From"])-1]["PlayerName"] == lua["Sender"]:
                                self.chatLine.append("[" + self.formatSeconds(self.ticks / 10) + "] " + lua["Sender"] + " to " + lua["Msg"]["to"] + ": " + lua["Msg"]["text"])

                x = self.binary.readUInt32() # entity ids (maybe..)
                xx = []
                for i in range(x):
                    xx.append(self.binary.readUInt32())

            elif(message_op in [ECmdStreamOp.CMDST_IssueCommand, ECmdStreamOp.CMDST_IssueFactoryCommand]):

                self.CPM[player]+=1 # increase commands number

                if not player in self.cpmChart:
                    self.cpmChart.setdefault(player,[])
                self.cpmChart[player].append(int(self.ticks))

                unitNums = self.binary.readUInt32()

                entArr = []
                for i in range(unitNums):
                    entArr.append(self.binary.readUInt32())

                cmdId = self.binary.readUInt32()

                self.binary.skipRawData(4) # skip
                commandType = ord(self.binary.readUInt8())
                self.binary.skipRawData(4) # skip
                stitarget = ord(self.binary.readUInt8())


                if stitarget == STITARGET.NONE:
                    pass
                elif stitarget == STITARGET.Entity:
                    entity = self.binary.readUInt32()
                elif stitarget == STITARGET.Position:
                    (x,y,z) = self.binary.readFloat(), self.binary.readFloat(), self.binary.readFloat()
                    self.pts.append((self.ticks,x,z))

                self.binary.skipRawData(1) # 0x00
                formation = self.binary.readInt32()
                if formation != -1:
                    (w,x,y,z) = self.binary.readFloat(), self.binary.readFloat(), self.binary.readFloat(), self.binary.readFloat()
                    scale = self.binary.readFloat()

                bp = self.returnNextString()

                self.binary.skipRawData(4 + 4 + 4) # 0x0 0x0 0x0 0x0

#                x1 = self.binary.readUInt32() # 1
#                x2 = self.binary.readUInt32() # 1

                upgradeLua = self.parseLua()
                if upgradeLua:
                    #luaInt8 = ord(self.binary.readUInt8())
                    self.binary.skipRawData(1) # 1

                self.commands.append({'player': player, 'tick': self.ticks, 'cmdType': commandType, 'bp': bp, 'lua': upgradeLua})

            elif message_op in [ECmdStreamOp.CMDST_Resume,ECmdStreamOp.CMDST_RequestPause,ECmdStreamOp.CMDST_EndGame]:
                pass
            elif message_op == ECmdStreamOp.CMDST_SetCommandType:
                cmdId = self.binary.readUInt32()
                cmdtype = self.binary.readUInt32()

            elif(message_op in [ECmdStreamOp.CMDST_DecreaseCommandCount,ECmdStreamOp.CMDST_IncreaseCommandCount]):
                cmdId = self.binary.readUInt32()
                countDelta = self.binary.readInt32()

            else:
                print "not parsed:", message_op
                self.binary.skipRawData(message_len-3)
        self.replayPercentage.emit(100)

    def toReadableDate(self,timestamp):
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")

    def realTime(self):
        try:
            start = self.fafInfo["game_time"]
            end = self.fafInfo["game_end"]

            if datetime.fromtimestamp(start).day == datetime.fromtimestamp(end).day:
                return datetime.fromtimestamp(start).strftime("%Y-%m-%d (%A)<br/> %H:%M:%S") + " - " + datetime.fromtimestamp(end).strftime("%H:%M:%S") + " (UTC)"
            else:
                return self.toReadableDate(self.fafInfo["game_time"]) + " - " + self.toReadableDate(self.fafInfo["game_end"]) + " (UTC)"
        except: # sometimes theres no such info
            return ""


    def SecondsToHuman(self,seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return "%dh %02dm %02ds" % (h, m, s) if h else "%2dm %02ds" % (m, s) if m else "%2ds" % s

    def formatSeconds(self,seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return "%d:%02d:%02d" % (h, m, s)

    def getInfo(self):
        teams = defaultdict(list)
        for id,player in self.army.iteritems():
            if id != 255:
                teams[player["Team"]].append(id)

        tmp = "<center><h2>" + self.replayPatchFieldId + "</h2>"

        if self.fafInfo:
            tmp += "<h3>" + self.fafInfo["title"] + "</h3>"

        tmp += "<h3>" + self.SecondsToHuman(self.ticks / 10) + "</h3>" \
              "<h4>" + self.realTime() + "</h4></center>"

#        if "Ranked" in self.luaScenarioInfo["Options"]:
#            tmp += "\nRanked: " + ("yes" if self.luaScenarioInfo["Options"]["Ranked"] == True else "no")

        if self.gameMods:
            tmp += "<h3>Mods</h3> "
            for mod in self.gameMods.values():
                tmp += "" + mod["name"] + "<br/>"

        teamid = 0
        tmp += "<p><table width=100%>"
        for team in teams.items():
            teamid +=1
            tmp += "<tr><th bgcolor=grey colspan=5><font color=white>team "+ str(teamid)+ "</font></th></tr>"
            for id in team[1]:
                tmp+= "<tr><td>" + self.getFac(self.army[id]["Faction"]) + "</td>"
                if 'COUNTRY' in self.army[id]:
                    tmp+= "<td><img src=\"data/flags/" + self.army[id]['COUNTRY'] + ".png\" title=\"" + self.army[id]['COUNTRY'] + "\"/></td>"
                tmp += "<td><b>" + self.army[id]["PlayerName"] + "</b><br/>"
                if 'MEAN' in self.army[id] and 'DEV' in self.army[id]:
                    tmp+= "Rating: " + str(int(self.army[id]['MEAN'] - 3*self.army[id]['DEV']))
                # Commands per minute
                if self.ticks:
                    tmp+= " apm:"
                    if id in self.lasttick: # player dies before the game ends
                        tmp += " %.2f" % (self.CPM[id] / (self.lasttick[id] * 1.0 / 10 / 60))
                    else:
                        tmp += " %.2f" % (self.CPM[id] / (self.ticks * 1.0 / 10 / 60))
                tmp += "</td></tr>"
            tmp += "<tr><td>&nbsp;</td></tr>"

        tmp += "</table></p>"
        return tmp

    def mapDisplaySize(self):
        (a,b) = self.luaScenarioInfo["size"][1.0],self.luaScenarioInfo["size"][2.0]

        if (a,b) == (256.0,256.0):
            return "5km"
        elif (a,b) == (512.0,512.0):
            return "10km"
        elif (a,b) == (1024.0,1024.0):
            return "20km"
        elif (a,b) == (2048.0,2048.0):
            return "40km"
        elif (a,b) == (4096.0,4096.0):
            return "81km"
        else:
            return str(int(a)) + "x" + str(int(b))

    def mapDisplayName(self):
        return self.luaScenarioInfo["name"]

    def getChat(self):
        tmp = ""
        for line in self.chatLine:
            tmp += line + "\n"
        return tmp

    def returnPts(self,fromTick,toTick):
        return [(x,y) for (tick,x,y) in self.pts if (tick < toTick and tick > fromTick) or (toTick==-1)]

    def returnHeatmap(self,fromTick=0,toTick=-1):
        pts = self.returnPts(fromTick,toTick)
        if len(pts) == 0:
            return
        else:
            hm = heatmap.Heatmap()
            img = hm.heatmap(pts,dotsize=20,size=(512,512),area=((0,0),(self.luaScenarioInfo["size"][1.0],self.luaScenarioInfo["size"][2.0])))
            return img.tostring("raw","BGRA",0,-1)

    def getSettings(self):
        tmp = "<center><h2>" + self.mapDisplayName() + "</h2><h4>" + self.mapDisplaySize() + "</h4></center><table>"
        for k,v in self.luaScenarioInfo["Options"].iteritems():
            if k not in ["Ratings","ScenarioFile","ReplayID"]:
                if type(v) != dict:
                    tmp += "<tr><td><b>" + str(k) + " </b></td><td> " + str(v) + "</td></tr>"
                else:
                    tmp += "<tr><td><b>" + str(k) + "</b></td><td>&nbsp;</td></tr>"
                    for k2,v2 in v.iteritems():
                        tmp += "<tr><td><i>" + str(k2) + "</i></td><td>" + str(v2) + "</td></tr>"
        tmp += "</table>"
        return tmp

    def getAll(self):
        return self.unpackedFile

    def getGameId(self):
        return self.fafInfo["uid"] if self.fafInfo and "uid" in self.fafInfo else 0

    def __init__(self,replayFile):
        QtCore.QObject.__init__(self)

        self.unpackedFile = None
        self.binary = None

        self.fafInfo = None
        self.ticks = 0
        self.lasttick = {}
        self.army = {}
        self.pts = []

        self.CPM = []
        self.chatLine = []

        self.filename = replayFile
        self.size = 0

        self.cpmChart = {}

        self.commands = []

    def doStuff(self):
        self.unpackReplay(self.filename)
        if self.unpackedFile:
            self.parseHeader()
            self.parseTicks()
            #self.genHeatmap(replayFile)
        else:
            raise ReplayException("Invalid File Format")
