#!/usr/bin/python

import socket
import sys
import struct
import datetime

gnxMagicCookie = 0x0df0c660
port = 9115
Help ='Usage: gnxtool [option] IP command \n \n \
Gnxtool is a simple command line interface for \n comunicating with a FiberXport unit. If no \n \
command is specified "status" is default. \n \n \
Commands: \n    status - Retrieve general information and port status \n \
   reload-config - Tells the unit to perform an APS request immediately \n \
   reset - Reset the CPU  \n \
   reset-hard - Reset the CPU and the Switch Chip \n \
   read-counters - Read all port counters \n \
   clear-counters - Clears all port counters\n \
   aps-status - Retrieve the latest APS status\n \
   clear-aps - Clear any stored APS configuration settings\n \
   \n Options:  \n \
    -h  Display this help text' # FINISH ME


try:
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
except socket.error:
	print 'Failed to create socket.'
	sys.exit()
s.settimeout(5)

def secondsTodhms(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, remainder = divmod(remainder, 60)

    return '{0} days {1}:{2}:{3}'.format(days, hours, minutes, remainder)

def sendData(gnxunithost, udpRequest, cmdCode):
        s.sendto(udpRequest, (gnxunithost, port))

        try:
                udpResponse, (udpAddr, udpPort) = s.recvfrom(1024)
        except socket.timeout:
                print 'No answer (timeout)'
                sys.exit()
            
        if udpAddr != gnxunithost and port != udpPort:
        #checks that the returned data is from the same address as the one transmitted to.
                print 'Unexpected respons from: {0} port {1}'.format(udpAddr, udpPort)
                return


        rspnByte, = struct.unpack_from('<B', udpResponse) #rspnByte contains the first byte received, should be the cmdcode.
            
        # checks that the first returned byte correspond to the transmitted cmdcode.
        if cmdCode != rspnByte:
                print 'Unexpected answer from: {0} port {1}, \n sent command code: {2} received command code: {3}'\
                        .format(udpAddr, udpPort,hex(cmdCode), hex(rspnByte))
                return
        
        return udpResponse

def responseCode(respCode):
        availableResponses = ['OK', 'General Error', 'Unknown or unsupported command',
                           'Error in parameter(s) for command (not enough parameters, incorrect values, etc.)',
                           'Out of resources for processing this request (try again later)']
        if respCode < len(availableResponses):
                respCode = availableResponses[respCode]
                if respCode == 'OK':
                        return True
                else:
                        print respCode
                        return False
                
	else:
                respCode = 'unknown ({0})'.format(respCode)
        
    
def getValue(gnxunithost):


    apsResponse = False
    gnxCmdGetValue = 0x47
    gnxCmdGetValueArgAll = 0x00


    # Funnily, the Genexis UDP protocol uses little-endian encodning, not network byte ordering.

    
    udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetValue, gnxCmdGetValueArgAll)
    response = sendData(gnxunithost, udpRequest, gnxCmdGetValue)
    resultTable = [[0 for x in xrange(2)] for x in xrange(8)]
    
    
    ValueName = ['Listener version (not fw version):','CPE uptime:','Time since counter reset:','Switch chip type:',\
               'Voice IPv4 address:','MAC address:','Firmware upgrade status:','Router IPv4 address: ']
    
    for y in range(0,8): # Filling portLogicVal with Y-titles
                        resultTable[y][0] = ValueName[y]
    
    
    
    valueId = response[1:2]
    valueId= 0
    if valueId == 0:       # means all values will be returned
    	valueId = 1    # but the first value will be for value id 1

    retValues = response[2:]  # skip the first two bytes
    ## retValues should now contain one 4-byte integer for each returned value.

    
    while len(retValues) >= 4:

        value, = struct.unpack_from('<I', retValues)
    	if valueId == 1:    ## Listener version
                
    	       resultTable[valueId-1][1] = value
	elif valueId == 2:
		resultTable[valueId-1][1] = secondsTodhms(value) 
	elif valueId == 3:
		resultTable[valueId-1][1] = secondsTodhms(value) 
	elif valueId == 4:
		availableTypes = ['OCG-16', 'OCG-17/18/20/1xx', 'OCG-10xx']
                if value < len(availableTypes):
			value = availableTypes[value]
		else:
			value = 'unknown ({0})'.format(value)
		resultTable[valueId-1][1] = value
	elif valueId == 5:
		## value is the ip address as an int in host byte order.
		## inet_ntoa takes a string with the ip in network byte order.
		resultTable[valueId-1][1] = socket.inet_ntoa(struct.pack('!I', value))
               
                
	elif valueId == 6:
		macHigh, = struct.unpack_from('>I', retValues)
		if len(retValues) >= 8:
			## We requested the low bytes in the same transfer, combine the output.
			retValues = retValues[4:]
			
			macLow, = struct.unpack_from('>I', retValues)
			resultTable[valueId-1][1] = '{0:0>4X}{1:0>8X}'.format(macHigh, macLow) ## 00:0f:94:1b:2d:bd
		 
	elif valueId == 7:
		availableStatus = ['Not in progress', 'In progress', 'Upgrade OK, will reset',
		                   'Upgrade initialization error', 'Upgrade transfer error',
		                   'Upgrade activation error (corrupt firmware rejected)']
                if value < len(availableStatus):
			value = availableStatus[value]
		else:
			value = 'unknown ({0})'.format(value)
		resultTable[valueId-1][1] = value
	elif valueId == 8:
                value, = struct.unpack_from('<i', retValues)

                if value == -1:
                    apsResponse = False
                        
                else:
                        apsResponse = True
                        
	elif valueId == 9:
                value, = struct.unpack_from('<I', retValues)
		## value is the ip address as an int in host byte order.
		## inet_ntoa takes a string with the ip in network byte order.
		resultTable[valueId-2][1] = socket.inet_ntoa(struct.pack('!I', value))
		
               
	## Skip handled data, and increase the value id for next iteration.
        retValues = retValues[4:]
        valueId = valueId + 1
        
    
    s = [[str(e) for e in row] for row in resultTable]
    lens = [len(max(col, key=len)) for col in zip(*s)]
    fmt = '   '.join('{{:{}}}'.format(x) for x in lens)
    table = [fmt.format(*row) for row in s]
    
    print '\n'.join(table)
    print '\n'
    getCATVStatus(gnxunithost);
    if apsResponse == False:
        print'No valid APS response received'
       
    else:
        getApsStatus(gnxunithost);
    print '\n'
    
    
    getPortStatusExt(gnxunithost)
    
    
def bitExtractor(data, start, mask): # mask is how many bits to select.
                                     # Returns the selected bits
        i= 0
        maskBin = 0
        while i < mask:
                maskBin += 2**i
                i +=1
                
        result = (data >> start) & maskBin
        return result

def getPortStatusExt(gnxunithost):
        gnxCmdgetPortStatusExt = 0x56

        udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdgetPortStatusExt)
        response = sendData(gnxunithost, udpRequest, gnxCmdgetPortStatusExt)
        retValues = response[1:]  # skip the first byte, skips cmdcode
        respCode, = struct.unpack_from('<B', retValues)
        portLogicVal = [[0 for x in xrange(7)] for x in xrange(9)]
        portStatusTitle=['','State','Link', 'Duplex','Speed (Mb/s)','Lflowen','Lflowasym','Rflowen','Rflowasym',]
        portTitle = ['','WAN', 'Data Port 1', 'Data Port 2', 'Data Port 3', 'Data Port 4', 'CPU',]
        if responseCode(respCode) :
                PORTVAL_LOGICALSTATE = 1
                PORTVAL_LINK= 2
                PORTVAL_DUPLEX=3
                PORTVAL_SPEED=4
                PORTVAL_LFLOWEN=5
                PORTVAL_LFLOWASYM=6
                PORTVAL_RFLOWEN=7
                PORTVAL_RFLOWASYM=8
                retValues =  retValues[3:]
                flowUp = 'Yes'  ##FIX ME: Decide what to call me.
                flowDown = 'No' ##FIX ME: Decide what to call me.


                for y in range(0,9): # Filling portLogicVal with Y-titles
                        portLogicVal[y][0] = portStatusTitle[y]
                for x in range(0,7): # Filling portLogicVal with X-titles
                        portLogicVal[0][x] = portTitle[x]
                
                i = 1
                enabled = True
                while i < 7:
                        portValue, = struct.unpack_from('<H', retValues)
                        
                        #Logicalstate
                        if bitExtractor(portValue,0,2) == 0:
                                result = 'Disabled'
                                enabled = False
                        elif bitExtractor(portValue,0,2) == 1:
                                result = 'Blocked'
                        elif bitExtractor(portValue,0,2) == 2:
                                result = '0x02(Unknown)'
                        elif bitExtractor(portValue,0,2) == 3:
                                result = 'Enabled'
                        portLogicVal[PORTVAL_LOGICALSTATE][i]= result
                        if enabled:
                                #Link
                                if bitExtractor(portValue,3,1) == 1:
                                        result = 'Up'
                                else:
                                        result = 'Down'
                                portLogicVal[PORTVAL_LINK][i]= result
                                
                                #Duplex
                                if bitExtractor(portValue,4,1) == 1:
                                        result = 'Full'
                                else:
                                        result = 'Half'
                                portLogicVal[PORTVAL_DUPLEX][i]= result
                                
                                #Speed        
                                if bitExtractor(portValue,5,2) == 0 and bitExtractor(portValue,0,2) == 3:
                                         result = '10'
                                elif bitExtractor(portValue,5,2) == 1 and bitExtractor(portValue,0,2) == 3:
                                        result = '100'
                                elif bitExtractor(portValue,5,2) == 2 and bitExtractor(portValue,0,2) == 3:
                                        result = '1000'
                             
                                portLogicVal[PORTVAL_SPEED][i]= result
                                
                                #Lflowen
                                if bitExtractor(portValue,7,1) == 1:
                                        result = flowUp
                                else:
                                        result = flowDown
                                portLogicVal[PORTVAL_LFLOWEN][i]= result
                                        
                                #Lflowasym
                                if bitExtractor(portValue,8,1) == 1:
                                        result = flowUp
                                else:
                                        result = flowDown
                                portLogicVal[PORTVAL_LFLOWASYM][i]= result
                                      
                                #Rflowen
                                if bitExtractor(portValue,10,1) == 1:
                                        result = flowUp
                                else:
                                        result = flowDown
                                portLogicVal[PORTVAL_RFLOWEN][i]= result
                                
                                #Rflowasym
                                if bitExtractor(portValue,11,1) == 1:
                                        result = flowUp
                                else:
                                        result = flowDown
                                portLogicVal[PORTVAL_RFLOWASYM][i]= result
                        else: #If the port is disabled the values is "-"
                                j = 2
                                while j < 9:
                                        portLogicVal[j][i]= '-'
                                        j += 1
                        
                        retValues = retValues[2:]
                        enabled = True
                        i += 1
                
          
                s = [[str(e) for e in row] for row in portLogicVal]
                lens = [len(max(col, key=len)) for col in zip(*s)]
                fmt = ' '.join('{{:{}}}'.format(x) for x in lens)
                table = [fmt.format(*row) for row in s]
                
                print '\n'.join(table)

def extractValue (counterData, port, counter, chipType):
    port -= 1    #This is so the math will work 
    
    selectNum = (port*32*4) + (counter*4)   #selectNum contains a number which is the index where the desired counter is in counterData.
                                            # There are 32 counters and each counter is a 32-bit int.
                                            
    if chipType == 2 and (counter == 0 or counter == 14):
        #We requested the low and high bytes to create a 64-bit byte if counter is 0 or 14.
        portVal, = struct.unpack_from('<Q', counterData[selectNum:])
        
    else:
        portVal, = struct.unpack_from('<I', counterData[selectNum:])
    
    return portVal
    
def getPortCounters(gnxunithost, getPortArg):
        COUNTER_IN_GOOD_OCTETS = 0
        COUNTER_IN_BAD_OCTETS = 2
        COUNTER_OUT_FCS_ERRORS = 3
        COUNTER_IN_UNICASTS = 4
        COUNTER_IN_DEFERRED = 5
        COUNTER_IN_BROADCASTS = 6
        COUNTER_IN_MULTICASTS = 7
        COUNTER_INOUT_64 = 8
        COUNTER_INOUT_65_127 = 9
        COUNTER_INOUT_128_255 = 10
        COUNTER_INOUT_256_511 = 11
        COUNTER_INOUT_512_1023 = 12 
        COUNTER_INOUT_1024_MAX = 13
        COUNTER_OUT_OCTETS = 14
        COUNTER_OUT_UNICASTS = 16
        COUNTER_EXCESSIVE = 17
        COUNTER_OUT_MULTICASTS = 18
        COUNTER_OUT_BROADCASTS = 19
        COUNTER_SINGLE = 20
        COUNTER_OUT_PAUSE_FRAMES = 21
        COUNTER_IN_PAUSE_FRAMES = 22
        COUNTER_MULTIPLE = 23
        COUNTER_IN_UNDERSIZE = 24
        COUNTER_IN_FRAGMENTS = 25
        COUNTER_IN_OVERSIZE = 26
        COUNTER_IN_JABBER = 27
        COUNTER_RX_ERRORS = 28
        COUNTER_IN_FCS_ERRORS = 29
        COUNTER_COLLISIONS = 30
        COUNTER_LATE = 31
        outputData = [['' for x in xrange(7)] for x in xrange(32)]

        if getPortArg == CLEAR_COUNTERS:
                gnxCmdGetPortCounters = 0x4B
                gnxCmdGetPortCountersArg = getPortArg
        
                udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetPortCounters, gnxCmdGetPortCountersArg)
                response = sendData(gnxunithost, udpRequest, gnxCmdGetPortCounters)
                print'Expected, no response'
                
        elif getPortArg == READ_COUNTERS:
                gnxCmdGetValue = 0x47
                gnxCmdGetSwitchChipType = 0x04

                udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetValue, gnxCmdGetSwitchChipType)
                response = sendData(gnxunithost, udpRequest, gnxCmdGetValue)
                chipType, = struct.unpack_from('<B', response[2:])
                #  chipType contains which Switch Type Chip and therefore how many counters to expect.
                
                if chipType == 0:
                    print'The units Switch chip is of an older version which is not supported'
                else:

                    gnxCmdGetPortCounters = 0x4B
                    gnxCmdGetPortCountersArg = getPortArg
            
                    udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetPortCounters, gnxCmdGetPortCountersArg)
                    response = sendData(gnxunithost, udpRequest, gnxCmdGetPortCounters)   
                    inputData = response[2:]  
                    
                    
                    rowHeadings = ['Received','Transmitted','Size breakdown (in/out packets)','Errors','Other',]
                    rowTitles = ['Good octets','Unicasts','Broadcasts', 'Multicasts','Octets', 'Unicasts','Broadcasts',\
                                 'Multicasts','..64', '65..127', '128..255','256..511','512..1023','1024.. ',\
                                 'In undersize','In fragments','In oversize','In jabber','In RX errors','In FCS errors','Collisions',\
                                 'Late','In bad octets','Out FCS errors','Deferred', 'Excessive', 'Single', 'Multiple',\
                                 'Out pause frames',  'In pause frames',]
                    portTitles = ['WAN', 'DataPort 1', 'DataPort 2', 'DataPort 3', 'DataPort 4', 'CPU',]
                    
                    for y in range(1,31): # Filling outputData with Y-titles
                            outputData[y][0] = rowTitles[y-1]
                    for x in range(1,7): # Filling outputData with X-titles
                            outputData[0][x] = portTitles[x-1]
                    
                    
                    portId= 1
                    rowId= 1
                    while portId < 7:
                        
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_GOOD_OCTETS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_UNICASTS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_BROADCASTS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_MULTICASTS,chipType)
                            rowId +=1
                            
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_OUT_OCTETS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_OUT_UNICASTS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_OUT_BROADCASTS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_OUT_MULTICASTS,chipType)
                            rowId +=1
                            
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_INOUT_64,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_INOUT_65_127,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_INOUT_128_255,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_INOUT_256_511,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_INOUT_512_1023,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_INOUT_1024_MAX,chipType)
                            rowId +=1
                            
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_UNDERSIZE,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_FRAGMENTS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_OVERSIZE,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_JABBER,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_RX_ERRORS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_FCS_ERRORS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_COLLISIONS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_LATE,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_BAD_OCTETS,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_OUT_FCS_ERRORS,chipType)
                            rowId +=1
                            
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_DEFERRED,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_EXCESSIVE,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_SINGLE,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_MULTIPLE,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_OUT_PAUSE_FRAMES,chipType)
                            rowId +=1
                            outputData[rowId][portId]= extractValue(inputData, portId, COUNTER_IN_PAUSE_FRAMES,chipType)
      
                            rowId =1
                            portId += 1
                            
                    s = [[str(e) for e in row] for row in outputData]
                    lens = [len(max(col, key=len)) for col in zip(*s)]
                    fmt = ' '.join('{{:{}}}'.format(x) for x in lens)
                    table = [fmt.format(*row) for row in s]
                    
                    printI = 0
                    printHeadingI= 0
                    while printI < 31:
                        if printI == 1 or printI == 5 or printI == 9 or printI == 15 or printI == 25:
                            print '\n',rowHeadings[printHeadingI]
                            printHeadingI +=1
                        print table[printI]
                        printI += 1
    
        else:
                 print 'Unknown command, typ -h for Help'  
       
def reloadConfig(gnxunithost):
    gnxCmdPushConfig = 0x48

    udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdPushConfig)
    s.sendto(udpRequest, (gnxunithost, port))
    print'Expected, no response'

def getApsStatus(gnxunithost):
    gnxCmdGetApsStatus = 0x54

    udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdGetApsStatus)
    response = sendData(gnxunithost, udpRequest, gnxCmdGetApsStatus)
    retValues = response[1:]  # skip the first byte
    value, = struct.unpack_from('<i', retValues)
    if value == -1:
            print'\nNo valid APS response received'
    else:
            print '\nTime since APS response:', secondsTodhms(value)
    retValues = response[5:]  # skip the first five byte
    value, = struct.unpack_from('<B', retValues)
    bitfieldIndx = 0
    bitState = False
    prevBitState = False
        
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState == 1:
            print 'Changes detected in the last APS refresh'
    else:
            print 'No changes detected in the last APS refresh'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState == 1:
            print 'Some changes are still pending.'
    else:
            print 'No changes pending'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState == 1:
            prevBitState = True
    else:
            print 'No scheduled reset'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState == 1 and prevBitState:
            print 'A hard reset is scheduled because of the APS process'
    elif prevBitState:
            print 'A reset is scheduled because of the APS process'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState == 1 :
            print 'The CPE is using locally stored settings'
    else:
            print 'The CPE is not using locally stored settings'
    
def clearAPS(gnxunithost):
        gnxCmdClearAPS = 0x52

        udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdClearAPS)
        response = sendData(gnxunithost, udpRequest, gnxCmdClearAPS)
        retValues = response[1:]  # skip the first byte
        value, = struct.unpack_from('<B', retValues)

        if value == 0:
                print'No stored settings were present to be cleared'
        elif value == 1:
                print 'Stored settings have been cleared'
        elif value == 2:
                print 'Error occurred during clear operation'
        else:
                print 'Unknown response: ', value
                
def reset(gnxunithost):
     gnxCmdSoftReset = 0x49

     udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdSoftReset)
     response = sendData(gnxunithost, udpRequest, gnxCmdSoftReset)

     retValues = response[1:]  # skip the first byte
     value, = struct.unpack_from('<B', retValues)

     if value == 1:
             print 'FiberXport {0} will reset'.format(gnxunithost)
     elif value == 0:
             print 'FiberXport {0} will NOT reset'.format(gnxunithost)
     else:
             print' Unexpected response: ', value

def resetHard(gnxunithost):
        gnxCmdHardReset = 0x51

        udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdHardReset)
        response = sendData(gnxunithost, udpRequest, gnxCmdHardReset)
        retValues = response[1:]  # skip the first byte

        value, = struct.unpack_from('<B', retValues)

        if value == 1:
                print 'FiberXport {0} will hard-reset'.format(gnxunithost)
        elif value == 0:
                print 'FiberXport {0} will NOT hard-reset'.format(gnxunithost)
        else:
                print' Unexpected response: ', value
          
def ipFormatValidation(inIp):     #checks for valid IP format
    validIP = False
    try:     
       socket.inet_aton(inIp)
       #print 'Good IP'
       validIP = True
       
    except socket.error:
       print 'Not a valid IP adress, typ -h for more information'
    return validIP
def getCATVStatus(gnxunithost):
    
     gnxCmdgetCATVStatus = 0x4D

     udpRequest = struct.pack('<IB', gnxMagicCookie, gnxCmdgetCATVStatus)
     response = sendData(gnxunithost, udpRequest, gnxCmdgetCATVStatus)
     
     retValues = response[1:]  # skip the first byte
     value, = struct.unpack_from('<B', retValues)
     if value == 0x00:
         print 'CATV off or the device has an optional CATV receiver \nmodule which is not installed'
     elif value == 0x01:
         print'CATV on'
     elif value == 0xFE:
         print 'No CATV port on this device'
     elif value == 0xFF:
         print 'Unknown status (status retrieval not supported by hardware)'
     else:
         print' Unexpected response: ', value
         

indexArg = 1
argHost= 0
command ='status'

if len(sys.argv) == 1:
        print'Type -h for Help'

while len(sys.argv)> indexArg:
    currentArg = sys.argv[indexArg]
    if currentArg[:1] =='-':    # Option
        if len(currentArg) == 2: # Valid option
                if currentArg[1:].lower() == 'h':
                        print Help
                        argHost = 0 # This will override a valid command if a flag is detected.
                        indexArg = len(sys.argv)
                else:
                        print 'Option "{0}" doesn\'t exist, typ -h for Help'.format(currentArg)
                        indexArg = len(sys.argv)
        else:
                print 'Not a valid Option, typ -h for Help'
                indexArg = len(sys.argv)
                
                
    elif argHost == 0:  # Checks that there is not already an IP saved.
        if ipFormatValidation(currentArg):  # Checks if currentArg is an IP adress
            argHost= currentArg     # Saves IP in argHost
        else: indexArg = len(sys.argv)
        
    else:
        command= currentArg
        # If there is more then two arguments the rest is discarded
        indexArg = len(sys.argv)      
    indexArg +=1
 
READ_COUNTERS = 1
CLEAR_COUNTERS = 0

if argHost != 0:
        
        if command.lower() == 'status':
                       print 'Sending request to {0} port {1}\n'.format(argHost, port)
                       getValue(argHost);
                       
        elif command.lower() == 'reload-config':
                print 'Sending reload-config request to {0} port {1}\n'.format(argHost, port)
                reloadConfig(argHost);
        elif command.lower() == 'reset':
                print 'Sending reset request to {0} port {1}\n'.format(argHost, port)
                reset(argHost);
        elif command.lower() == 'read-counters':
                print 'Sending read-counters request to {0} port {1}\n'.format(argHost, port)
                getPortCounters(argHost, READ_COUNTERS);
        elif command.lower() == 'clear-counters':
                print 'Sending clear-counters to request {0} port {1}\n'.format(argHost, port)
                getPortCounters(argHost, CLEAR_COUNTERS);
                
        elif command.lower() == 'reset-hard':
                print 'Sending reset-hard request to {0} port {1}\n'.format(argHost, port)
                resetHard(argHost);
        elif command.lower() == 'aps-status':
                print 'Sending aps-status request to {0} port {1}\n'.format(argHost, port)
                getApsStatus(argHost);
        elif command.lower() == 'clear-aps':
                print 'Sending clear-aps request to {0} port {1}\n'.format(argHost, port)
                clearAPS(argHost);
        elif command.lower() == 'catv-status':
                print 'Sending catv-status request to {0} port {1}\n'.format(argHost, port)
                getCATVStatus(argHost);
        else:
                print 'Not a valid command, type -h for Help'
        

            
