# by "Neruz", Posted: 24 Nov, 2008 on GPGNET forum: http://forums.gaspowered.com/viewtopic.php?f=19&t=33010


# Sorry for the lack of comments, but the variable names and prints should give you some clue whats going on
# GpgNetSend strips all \n, \t and such characters, so it's advised you replace them with /t and /n, this script will
# turn them back into \n and \t
# I know that the unpack / pack method doesn't follow the same structure, but since you can only send 1 packet per send it's enough
# moho can send multiple packets in 1 recv if GpgNetSend was called in the same beat.

import struct


def Unpack(data):
    unpacked = {}
    while data:
        headerSize = struct.unpack("i", data[:4])[0]
        headerPackStr = "<i" + str(headerSize) + "si"
#            print 'header ', data[:headerSize+8], headerPackStr
        header = struct.unpack(headerPackStr, data[:headerSize+8])
        headerStr = header[1].replace("/t","\t").replace("/n","\n")
        if not unpacked.has_key(header[1]):
            unpacked[headerStr] = []
        chunkSize = header[2]
        data = data[headerSize+8:]
#            print 'chunkSize ', chunkSize
        chunk = []
        for i in range(chunkSize):
            fieldType = struct.unpack("b", data[:1])[0]
            if fieldType is 0:
#                    print 'number ', data[1:5]
                number = struct.unpack("i", data[1:5])[0]
                chunk.append(number)
                data = data[5:]
            else:
                fieldSize = struct.unpack("i", data[1:5])[0]
                packStr = str(fieldSize) + "s"
#                    print 'string ', data[5:fieldSize+5] , packStr, fieldSize
                string = struct.unpack(packStr, data[5:fieldSize+5])[0]
                fixedStr = string.replace("/t","\t").replace("/n","\n")
                chunk.append(fixedStr)
                data = data[fieldSize+5:]
        unpacked[headerStr].extend([chunk])
    return unpacked


def Pack(*values, **kwvalues):
    data = ""
    for i, chunk in kwvalues.iteritems():
        headerSize = len(str(i))
        headerField = str(i).replace("\t","/t").replace("\n","/n")
        chunkSize = len(chunk)
        headerPackStr = "<i" + str(headerSize) + "si"
#            print 'header ', headerField, headerPackStr, chunkSize
        data += struct.pack(headerPackStr, headerSize, headerField, chunkSize)
        chunkType = type(chunk)
        if chunkType is list:
            for field in chunk:
                fieldType = 0 if type(field) is int else 1
                chunkPackStr = ""
                fields = []
                if fieldType is 1:
                    fieldSize = len(field)
                    chunkPackStr += "<bi" + str(fieldSize) + "s"
                    fieldStr = field.replace("\t","/t").replace("\n","/n")
#                        print 'string ', fieldStr, chunkPackStr, fieldSize
                    fields.extend([fieldType, fieldSize, fieldStr])
                elif fieldType is 0:
                    chunkPackStr += "<bi"
#                        print 'number ', field, chunkPackStr
                    fields.extend([fieldType, field])
                data += struct.pack(chunkPackStr, *fields)
    return data