from PyQt4 import QtGui, QtCore

def SecondsToHuman(seconds):
        m, s = divmod(seconds, 60)
        h, m = divmod(m, 60)
        return "%dh%02dm%02ds" % (h, m, s) if h else "%2dm%02ds" % (m, s) if m else "%2ds" % s


class ChartWidget(QtGui.QWidget):
    selectedTickSignal = QtCore.pyqtSignal(int)
    def __init__(self):
        QtGui.QWidget.__init__(self)

        self.setMouseTracking(True)

        self.lMargin = 38
        self.tMargin = 10
        self.rMargin = 3
        self.bMargin = 20

        self.mousePos = 0
        self.prevMousePos = 0
        self.selectedTick = 0

        self.maxHVal = 0
        self.maxVVal = 0

        self.data = None
        self.colors = None


    def sizeHint(self):
        return QtCore.QSize(600,200)

    def mouseMoveEvent(self, e):
        if self.data:
            index = e.pos().x()
            if self.lMargin <= index < self.geometry().width() - self.rMargin:
                self.mousePos = index - self.lMargin
                self.update()
                self.selectedTickSignal.emit(self.selectedTick)


    def graph(self, data, maxHVal, colors):
        self.maxHVal = maxHVal
        self.data = data
        self.colors = colors
        self.update()

    def paintEvent(self, e):
        if self.data:
            maxH,maxW = self.geometry().height(), self.geometry().width()

            numOfDataNeed = maxW-self.lMargin-self.rMargin
            numOfSources = len(self.data)
            numOfData = len(self.data[0])

            spaceBetweenXaxisText = 30
            spaceBetweenYaxisText = 60

            small = [] * numOfSources
            for i in range(numOfSources):
                small.append([])

            numOfSample = int(1.0* numOfData / numOfDataNeed)

            self.selectedTick = self.mousePos * numOfSample

            for i in range(numOfDataNeed):
                for j in range(numOfSources):
                    small[j].append(1.0 * sum(self.data[j][i*numOfSample:(i+1)*numOfSample])/numOfSample)

            p = QtGui.QPainter()
            p.begin(self)

            if self.mousePos != self.prevMousePos and self.mousePos < maxW - self.rMargin:
                p.drawLine(self.lMargin + self.mousePos, self.tMargin, self.lMargin + self.mousePos, maxH - self.bMargin)
            else:
                self.mousePos = 0

            for i in range(numOfSources):
                path = QtGui.QPainterPath()
                path.moveTo(self.lMargin,maxH-self.bMargin)
                for j in range(maxW-self.lMargin-self.rMargin):
                    path.lineTo(self.lMargin+j, maxH - self.bMargin + (-1.0*small[i][j] / self.maxHVal * (maxH - self.tMargin - self.bMargin)))

                p.setPen(QtGui.QPen(QtGui.QColor(self.colors[i])))
                p.drawPath(path)

            p.setPen(QtGui.QPen(QtCore.Qt.black, 1, QtCore.Qt.SolidLine))
            p.drawRect(self.lMargin,self.tMargin, maxW-self.rMargin-self.lMargin, maxH-self.tMargin-self.bMargin)


            for i in range((numOfDataNeed / spaceBetweenYaxisText) + 1):
                p.drawText(QtCore.QRectF(self.lMargin-50 + (i*spaceBetweenYaxisText),maxH-self.bMargin + 5,100,10), SecondsToHuman(i*spaceBetweenYaxisText*numOfSample/10), QtGui.QTextOption(QtCore.Qt.AlignCenter))
                p.drawLine(self.lMargin + (i*spaceBetweenYaxisText),maxH-self.bMargin + 2,self.lMargin + (i*spaceBetweenYaxisText),maxH-self.bMargin - 2)

            for i in range((maxH-self.bMargin-self.tMargin)/spaceBetweenXaxisText + 1):
                p.drawText(QtCore.QRectF(self.lMargin - 40,maxH-self.bMargin - 5 - i*spaceBetweenXaxisText,35,10), "%.2f" % (self.maxHVal * i*spaceBetweenXaxisText * 1.0 /(maxH-self.tMargin-self.bMargin)), QtGui.QTextOption(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter))
                p.drawLine(self.lMargin - 2,maxH-self.bMargin - i*spaceBetweenXaxisText,self.lMargin + 2,maxH-self.bMargin - i*spaceBetweenXaxisText)

            p.end()
