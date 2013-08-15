#!/usr/bin/python

import socket
import sys
import struct
import datetime

gnxMagicCookie = 0x0df0c660
port = 9115
Help ='Usage: gnxtool [options] IP command \n \n \
Gnxtool is a simple command line interface for \n comunicating with a FiberXport unit. If no \n \
command is specified status is default. \n \n \
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
    
    gnxCmdGetValue = 0x47
    gnxCmdGetValueArgAll = 0x00


    # Funnily, the Genexis UDP protocol uses little-endian encodning, not network byte ordering.

    
    udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetValue, gnxCmdGetValueArgAll)
    response = sendData(gnxunithost, udpRequest, gnxCmdGetValue)
    
    
    valueId = response[1:2]
    valueId= 0
    if valueId == 0:       # means all values will be returned
    	valueId = 1    # but the first value will be for value id 1

    retValues = response[2:]  # skip the first two bytes
    ## retValues should now contain one 4-byte integer for each returned value.
    
    while len(retValues) >= 4:
        value, = struct.unpack_from('<I', retValues)
    	if valueId == 1:    ## Listener version
    		print 'Listener version (not fw version):', value
	elif valueId == 2:
		print 'CPE uptime:', secondsTodhms(value)  
	elif valueId == 3:
		print 'Time since counter reset:', secondsTodhms(value) 
	elif valueId == 4:
		availableTypes = ['OCG-16', 'OCG-17/18/20/1xx', 'OCG-10xx']
                if value < len(availableTypes):
			value = availableTypes[value]
		else:
			value = 'unknown ({0})'.format(value)
		print 'Switch chip type:', value
	elif valueId == 5:
		## value is the ip address as an int in host byte order.
		## inet_ntoa takes a string with the ip in network byte order.
		print 'Voice IPv4 address:', socket.inet_ntoa(struct.pack('!I', value))
               
                
	elif valueId == 6:
		macHigh, = struct.unpack_from('>I', retValues)
		if len(retValues) >= 8:
			## We requested the low bytes in the same transfer, combine the output.
			retValues = retValues[4:]
			valueId = valueId + 1
			macLow, = struct.unpack_from('>I', retValues)
			print 'MAC address:', '{0:0>4X}{1:0>8X}'.format(macHigh, macLow) ## 00:0f:94:1b:2d:bd
		else:
			print 'MAC address high:', '{0:0>4X}'.format(macHigh) 
	elif valueId == 7:
		macLow, = struct.unpack_from('>I', retValues)
		print 'MAC address low:', '{0:0>6X}'.format(macLow)
	elif valueId == 8:
		availableStatus = ['Not in progress', 'In progress', 'Upgrade OK, will reset',
		                   'Upgrade initialization error', 'Upgrade transfer error',
		                   'Upgrade activation error (corrupt firmware rejected)']
                if value < len(availableStatus):
			value = availableStatus[value]
		else:
			value = 'unknown ({0})'.format(value)
		print 'Firmware upgrade status:', value
	elif valueId == 9:
                value, = struct.unpack_from('<i', retValues)

                if value == -1:
                        print'No valid APS response received'
                else:
                        print '\nTime since APS response:', secondsTodhms(value)
                        getApsStatus(gnxunithost);
                
	elif valueId == 10:
                value, = struct.unpack_from('<I', retValues)
		## value is the ip address as an int in host byte order.
		## inet_ntoa takes a string with the ip in network byte order.
		print 'Router IPv4 address: ', socket.inet_ntoa(struct.pack('!I', value))
		print '\n'
               
	## Skip handled data, and increase the value id for next iteration.
        retValues = retValues[4:]
        valueId = valueId + 1
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

             
            
def getPortCounters(gnxunithost, getPortArg):

        if getPortArg == 0:
                gnxCmdGetPortCounters = 0x4B
                gnxCmdGetPortCountersArg = getPortArg
        
                udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetPortCounters, gnxCmdGetPortCountersArg)
                response = sendData(gnxunithost, udpRequest, gnxCmdGetPortCounters)
                print'Expected, no response'
                
        elif getPortArg == 1:
                gnxCmdGetValue = 0x47
                gnxCmdGetSwitchChipType = 0x04

                udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetValue, gnxCmdGetSwitchChipType)
                response = sendData(gnxunithost, udpRequest, gnxCmdGetValue)
                chipType, = struct.unpack_from('<B', response[2:])
                #  chipType contains which Switch Type Chip and therefore how many counters to expect.

                
                countersTypeA = ['In unicasts', 'In broadcasts', 'In pause frames','In multicasts','In FCS errors',
                                 'In align errors', 'In good octets','Inbad octets','In undersize','In fragments',
                                 'In 64 octets', 'In 65..127 octets', 'In 128..255 octets','In 256..511 octets',
                                 'In 512..1023 octets', 'In 1024..max octets','In jabber','In oversize','In discards',
                                 'In filtered','In unicasts', 'Out broadcasts', 'Out pause frames', 'Out multicasts',
                                 'Out FCS errors','Out octets','Out 64 octets', 'Out 65..127 octets', 'Out 128..255 octets',
                                 'Out 256..511 octets','Out 512..1023 octets','Out 1024..max octets','Collisions', 'Late',
                                 'Excessive', 'Multiple', 'Single', 'Deferred', 'Out filtered']

                countersTypeB = ['In good octets', 'In good octets', 'In bad octets','Out FCS errors','In unicasts','Deferred',
                                 'In broadcasts', 'In multicasts','In/out 64 octets', 'In/out 65..127 octets', 'In/out 128..255 octets',
                                 'In/out 256..511 octets','In/out 512..1023 octets','In/out 1024..max octets', 'Out octets','Out octets',
                                 'Out unicasts', 'Excessive', 'Out multicasts','Out broadcasts', 'Single','Out pause frames',
                                 'In pause frames','Multiple','In undersize','In fragments','In oversize','In jabber','In RX errors',
                                 'In FCS errors','Collisions','Late']
                counters = []
                if chipType == 1 or 2: # Chip type 1 and two has 32 counter and type 0 has 39
                        N = 32
                        counters = countersTypeB    
                else:
                        N = 39
                        counters = countersTypeA
        
                gnxCmdGetPortCounters = 0x4B
                gnxCmdGetPortCountersArg = getPortArg
        
                udpRequest = struct.pack('<IBB', gnxMagicCookie, gnxCmdGetPortCounters, gnxCmdGetPortCountersArg)
                response = sendData(gnxunithost, udpRequest, gnxCmdGetPortCounters)   
                retValues = response[2:]  
                portTitle = ['WAN', 'Data Port 1', 'Data Port 2', 'Data Port 3', 'Data Port 4', 'CPU','']
                ctrNum = 0
                index= 0
                print portTitle[0]
                while len(retValues) >= 4:
                        value, = struct.unpack_from('<I', retValues)
                        
                        
                        if ((ctrNum ==0 or ctrNum == 14) and chipType == 2):
                                #We requested the low and high bytes to create a 64-bit byte if ctrNum is 0 or 14.
                                octets64Bit, = struct.unpack_from('<Q', retValues)
                                print '{0}:...... {1}'.format(counters[ctrNum], octets64Bit)
                                ctrNum += 1
                                retValues = retValues[4:]
                        elif ((ctrNum ==0 or ctrNum == 14) and chipType == 1):
                                print '{0}:...... {1}'.format(counters[ctrNum], value)
                                ctrNum += 1
                                retValues = retValues[4:]                     
                        else:
                                print '{0}:...... {1}'.format(counters[ctrNum], value)
                                 
                                 
                        
                        if ctrNum == N-1: # Skips to the next port
                                ctrNum=0
                                index +=1
                                print '\n', portTitle[index]
                        else:
                                ctrNum += 1
                        retValues = retValues[4:]
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
            print'No valid APS response received'
    else:
            print '\nTime since APS response:', secondsTodhms(value)
    retValues = response[5:]  # skip the first five byte
    value, = struct.unpack_from('<B', retValues)
    bitfieldIndx = 0
    bitState = False
    prevBitState = False
        
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState:
            print 'Changes detected in the last APS refresh'
    else:
            print 'No changes detected in the last APS refresh'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState:
            print 'Some changes are still pending.'
    else:
            print 'No changes pending'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState:
            prevBitState = True
    else:
            print 'No scheduled reset'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState and prevBitState:
            print 'A hard reset is scheduled because of the APS process'
    else:
            print 'A reset is scheduled because of the APS process'
    bitfieldIndx += 1
    
    bitState = bitExtractor(value, bitfieldIndx, 1);
    if bitState:
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
                print 'No stored settings were present to be cleared'
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
                getPortCounters(argHost,1);
        elif command.lower() == 'clear-counters':
                print 'Sending clear-counters to request {0} port {1}\n'.format(argHost, port)
                getPortCounters(argHost,0);
                
        elif command.lower() == 'reset-hard':
                print 'Sending reset-hard request to {0} port {1}\n'.format(argHost, port)
                resetHard(argHost);
        elif command.lower() == 'aps-status':
                print 'Sending aps-status request to {0} port {1}\n'.format(argHost, port)
                getApsStatus(argHost);
        elif command.lower() == 'clear-aps':
                print 'Sending clear-aps request to {0} port {1}\n'.format(argHost, port)
                clearAPS(argHost);
        else:
                print 'Not a valid command, type -h for Help'
        

            
