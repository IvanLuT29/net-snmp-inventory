#!/usr/bin/python3
# coding=utf-8

# An inventory tool for network equipment discovery & audit, based on ICMP PING + SNMP protocols.
# Depends on external modules (see requirements.txt).

# Special script values
__author__ = "Symrak"
__version__ = "0.1"
__min_python__ = (3, 10)

# Importing libraries
from os import path
from sys import version_info, exit
from math import modf
from ping3 import ping
from pysnmp.hlapi import *
from datetime import datetime
from argparse import ArgumentParser
from pysnmp.smi.rfc1902 import ObjectIdentity
from ipaddress import IPv4Address, IPv4Network
from netaddr import IPAddress
import time, macaddress, platform

# Check Python version
if version_info < __min_python__:
    exit("\nPython %s.%s or later is required! Exiting...\n" % __min_python__)

# Get script name and working directory
scriptName = path.basename(__file__)
dirName = path.dirname(path.realpath(__file__))

# Determinating path delimiter symbol based on OS type (Windows or Linux)
pathDelimiter = "\\" if platform.system() == "Windows" else "/"

# Parsing the arguments
argParser = ArgumentParser(prog = scriptName,
	description = "NetSNMP Inventory Tool: utility for network equipment discovery & audit (v" + __version__ + " by " + __author__ + ").")
argParser.add_argument("-r", "--net", required=True, type=str, metavar="192.0.2.0/24", dest="netAddress",
	help="Network address with CIDR netmask. Example: 192.0.2.0/24")
argParser.add_argument("-sn", "--sec_name", required=True, type=str, metavar="\"snmp-user\"", dest="snmpUsername",
	help="SNMP security name (SNMPv3).")
argParser.add_argument("-ap", "--auth_proto", required=False, type=str, default="sha1", choices=["none","md5","sha1","sha224","sha256","sha384","sha512"], metavar="sha1", dest="snmpAuthProtocol",
	help="Authentication protocol (in lowercase). Supported: NONE, MD5, SHA1, SHA224, SHA256, SHA384, SHA512 (SNMPv3).")
argParser.add_argument("-aw", "--auth_passwd", required=False, type=str, metavar="\"auth-pass\"", dest="snmpAuthKey",
	help="Authentication password (SNMPv3).")
argParser.add_argument("-pp", "--priv_proto", required=False, type=str, default="aes128", choices=["none","des","3des","aes128","aes192","aes192b","aes256","aes256b"], metavar="aes128", dest="snmpPrivProtocol",
	help="Privacy protocol (in lowercase). Supported: NONE, DES, 3DES, AES128, AES192, AES192 Blumenthal, AES256, AES256 Blumenthal (SNMPv3).")
argParser.add_argument("-pw", "--priv_passwd", required=False, type=str, metavar="\"privacy-pass\"", dest="snmpPrivKey",
	help="Privacy password (SNMPv3).")
argParser.add_argument("-p", "--port", required=False, type=int, default=161, choices=range(1, 65536), metavar="(1 .. 65535)", dest="snmpPort",
	help="SNMP port number on remote host. Default: 161")
argParser.add_argument("-il", "--iter_lim", required=False, type=int, default=256, choices=[1,2,4,8,16,32,64,128,256,512,1024,2048,4096,8192,16384], metavar="(1, 2, 4 .. 8192, 16384)", dest="snmpIterMaxCount",
	help="SNMP values limit for iterable objects. Default: 256")
argParser.add_argument("-rc", "--ret_cnt", required=False, type=int, default=0, choices=range(0, 10), metavar="(0 .. 9)", dest="snmpRetriesCount",
	help="SNMP request retries count. Default: 0")
argParser.add_argument("-t", "--timeout", required=False, type=int, default=5, choices=range(0, 601), metavar="(0 .. 600)", dest="snmpTimeout",
	help="SNMP timeout in seconds. Default: 5")
argParser.add_argument("-ip", "--ign_ping", action="store_true", dest="ignorePingFlag",
	help="Ignore results of an ICMP PING scan (check every host using SNMP requests).")
argParser.add_argument("-csv", "--csv_report", required=False, type=str, metavar=".\Report.csv", dest="outFilePath",
	help="Path to CSV report output file, including extension. Default: autogenerated in work directory.")
argParser.add_argument("-dm", "--csv_delim", required=False, type=str, default=";", metavar="\";\"", dest="csvReportDelimeter",
	help="Delimiter symbol for the CSV report. Default: \";\").")
argParser.add_argument("-ev", "--empty_val", required=False, type=str, default="N/A", metavar="\"N/A\"", dest="reportEmptyValue",
	help="Empty value representation. Default: \"N/A\").")
argParser.add_argument("-v", "--verbose", action="store_true", dest="verbScanProgressFlag",
	help="Additional console output while scanning SNMP.")
argParser.add_argument("-sr", "--scan_res", action="store_true", dest="scanResultsOutputFlag",
	help="Output scan results in console (in text view).")
scriptArgs = argParser.parse_args()

# Processing input data
try:
	scanAddress = IPv4Network(scriptArgs.netAddress)
except ValueError:
	print("\nNetwork address is incorrect!\n")
	exit()
reportEmptyValue = scriptArgs.reportEmptyValue
csvReportDelimeter = scriptArgs.csvReportDelimeter
snmpPort = scriptArgs.snmpPort
snmpIterMaxCount = scriptArgs.snmpIterMaxCount
snmpRetriesCount = scriptArgs.snmpRetriesCount
snmpTimeout = scriptArgs.snmpTimeout
snmpUsername = scriptArgs.snmpUsername
snmpAuthProtoDict = {"none" : usmNoAuthProtocol, "md5" : usmHMACMD5AuthProtocol,
					 "sha1" : usmHMACSHAAuthProtocol, "sha224" : usmHMAC128SHA224AuthProtocol,
					 "sha256" : usmHMAC192SHA256AuthProtocol, "sha384" : usmHMAC256SHA384AuthProtocol,
					 "sha512" : usmHMAC384SHA512AuthProtocol}
snmpAuthProtocol = snmpAuthProtoDict[scriptArgs.snmpAuthProtocol]
snmpAuthKey = scriptArgs.snmpAuthKey
snmpPrivProtoDict = {"none" : usmNoPrivProtocol, "des" : usmDESPrivProtocol,
					 "3des" : usm3DESEDEPrivProtocol, "aes128" : usmAesCfb128Protocol,
					 "aes192" : usmAesCfb192Protocol, "aes192b" : usmAesBlumenthalCfb192Protocol,
					 "aes256" : usmAesCfb256Protocol, "aes256b" : usmAesBlumenthalCfb256Protocol}
snmpPrivProtocol = snmpPrivProtoDict[scriptArgs.snmpPrivProtocol]
snmpPrivKey = scriptArgs.snmpPrivKey
ignorePingFlag = scriptArgs.ignorePingFlag
verbScanProgressFlag = scriptArgs.verbScanProgressFlag
scanResultsOutputFlag = scriptArgs.scanResultsOutputFlag
outFilePath = (dirName + pathDelimiter + datetime.today().strftime("%Y-%m-%d") + " – net-audit-report_net-" + str(scanAddress).replace("/", "_cidr-") + ".csv") if scriptArgs.outFilePath == None else scriptArgs.outFilePath

# General variables
dataDictTemplate = {"Sysname" : None, "Manufacturer" : None, "Model" : None, "FW" : None,
					"S/N" : None, "Location" : None, "Description" : None, "Contact" : None, "Comment" : None,
					"Interfaces Count" : None, "MAC Address" : None, "IP Addresses" : None, "PING" : False, "SNMP" : False}
interfaceDictTemplate = {"Index" : None, "Name" : None, "Alias" : None, "Type" : None, "MTU" : None, "MAC Address" : None,
						 "IP Address" : None, "Netmask" : None, "Description" : None, "Admin Status" : False, "Operation Status" : False}
						 
# Functions definitions
# Collecting SNMP data
def snmpAudit(snmpHost, pingStatus, snmpUsername, snmpAuthKey, snmpPrivKey, dataDict, valuesDelimeter=";", snmpAuthProtocol=usmHMACSHAAuthProtocol, snmpPrivProtocol=usmAesCfb128Protocol, snmpPort=161, snmpIterMaxCount=256, snmpRetriesCount=0, snmpTimeout=5):
	# Function variables
	snmpDataDict = {snmpHost : dataDict.copy()}
	snmpDataDict[snmpHost]["IP Addresses"] = []
	snmpDataDict[snmpHost]["PING"] = pingStatus
	# Authentication data
	snmpAuth = UsmUserData (
		userName = snmpUsername,
		authKey = snmpAuthKey,
		authProtocol = snmpAuthProtocol,
		privKey = snmpPrivKey,
		privProtocol = snmpPrivProtocol
	)
	# SNMP GET requests payload & processing
	# General information collecting
	snmpRequest = getCmd (
		SnmpEngine (),
		snmpAuth,
		UdpTransportTarget ((snmpHost, snmpPort), retries=snmpRetriesCount, timeout=float(snmpTimeout)),
		ContextData (),
		# System Name @ sysName!@#.iso.org.dod.internet.mgmt.mib-2.system.sysName (.1.3.6.1.2.1.1.5.0)
		ObjectType(ObjectIdentity("SNMPv2-MIB", "sysName", 0)),
		# Manufacturer @ entPhysicalMfgName!@#.iso.org.dod.internet.mgmt.mib-2.entityMIB.entityMIBObjects.entityPhysical.entPhysicalTable.entPhysicalEntry.entPhysicalMfgName
		ObjectType(ObjectIdentity("ENTITY-MIB", "entPhysicalMfgName", 1)),
		# Model @ entPhysicalName!@#.iso.org.dod.internet.mgmt.mib-2.entityMIB.entityMIBObjects.entityPhysical.entPhysicalTable.entPhysicalEntry.entPhysicalName
		ObjectType(ObjectIdentity("ENTITY-MIB", "entPhysicalModelName", 1)),
		# Software Revision @ entPhysicalSoftwareRev!@#.iso.org.dod.internet.mgmt.mib-2.entityMIB.entityMIBObjects.entityPhysical.entPhysicalTable.entPhysicalEntry.entPhysicalSoftwareRev
		ObjectType(ObjectIdentity("ENTITY-MIB", "entPhysicalSoftwareRev", 1)),
		# Serial Number @ entPhysicalSerialNum!@#.iso.org.dod.internet.mgmt.mib-2.entityMIB.entityMIBObjects.entityPhysical.entPhysicalTable.entPhysicalEntry.entPhysicalSerialNum
		ObjectType(ObjectIdentity("ENTITY-MIB", "entPhysicalSerialNum", 1)),
		# Location @ sysLocation!@#.iso.org.dod.internet.mgmt.mib-2.system.sysLocation
		ObjectType(ObjectIdentity("SNMPv2-MIB", "sysLocation", 0)),
		# Description @ sysDescr!@#.iso.org.dod.internet.mgmt.mib-2.system.sysDescr
		ObjectType(ObjectIdentity("SNMPv2-MIB", "sysDescr", 0)),
		# Contact @ sysContact!@#.iso.org.dod.internet.mgmt.mib-2.system.sysContact
		ObjectType(ObjectIdentity("SNMPv2-MIB", "sysContact", 0)),
		# System logical description @ entLogicalDescr!@#.iso.org.dod.internet.mgmt.mib-2.entityMIB.entityMIBObjects.entityLogical.entLogicalTable.entLogicalEntry.entLogicalDescr
		ObjectType(ObjectIdentity("ENTITY-MIB", "entLogicalDescr", 1)),
		# Interfaces count @ ifNumber!@#.iso.org.dod.internet.mgmt.mib-2.interfaces.ifNumber
		ObjectType(ObjectIdentity("IF-MIB", "ifNumber", 0)),
		lookupMib = True,
		lexicographicMode = False
	)
	errorIndication, errorStatus, errorIndex, varBinds = next(snmpRequest)
	if errorIndication:
		if verbScanProgressFlag:
			print("\t[WARN!] IP %s [SNMP - General Info] - %s" % (snmpHost, errorIndication))
	elif errorStatus:
		print("\t[ERROR!] %s at %s" % (errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1][0] or "?"))
	else:
		# Array for storing SNMP values
		varBindValues = []
		# Extracting SNMP OIDs and their values
		for varBind in varBinds:
			### DEBUG: Pretty output of SNMP library
			# print(" = ".join([x.prettyPrint() for x in varBind]))
			name, value = varBind
			value = str(value).replace("\n\r", " ")
			value = str(value).replace("\n", " ")
			value = str(value).replace("\r", " ")
			value = str(value).replace(valuesDelimeter, " ")
			varBindValues.append(value)
			### DEBUG: OID and value output
			# print("\tOID = %s" % name)
			# print("\tValue = %s" % value)
		# Filling-up dictionary with array values
		valuesCount = len(varBindValues)
		i = 0
		for key in snmpDataDict[snmpHost]:
			value = varBindValues[i]
			if ((value) != None and len(value) > 0):
				snmpDataDict[snmpHost][key] = value
			if i < valuesCount-1:
				i += 1
			else:
				break
		# Changing SNMP iteration count based on interfaces count
		snmpIterMaxCount = snmpDataDict[snmpHost]["Interfaces Count"] if isinstance(snmpDataDict[snmpHost]["Interfaces Count"], int) else scriptArgs.snmpIterMaxCount
		# Flipping SNMP state flag
		snmpDataDict[snmpHost]["SNMP"] = True
	# Vendor-specific information collecting
	# Forinet Fortigate
	if snmpDataDict[snmpHost]["Manufacturer"] == "Fortinet":
		# FortiGate devices
		if (("FortiGate" in snmpDataDict[snmpHost]["Comment"]) or ("FortiGate" in snmpDataDict[snmpHost]["FW"])):
			snmpRequest = getCmd (
				SnmpEngine (),
				snmpAuth,
				UdpTransportTarget ((snmpHost, snmpPort), retries=snmpRetriesCount, timeout=float(snmpTimeout)),
				ContextData (),
				# FortiGate Software Version @ fgSysVersion!@#.iso.org.dod.internet.private.enterprises.fortinet.fnFortiGateMib.fgSystem.fgSystemInfo.fgSysVersion
				ObjectType(ObjectIdentity(".1.3.6.1.4.1.12356.101.4.1.1.0")),	
				# FortiGate Serial Number @ fnSysSerial!@#.iso.org.dod.internet.private.enterprises.fortinet.fnCoreMib.fnCommon.fnSystem.fnSysSerial
				ObjectType(ObjectIdentity(".1.3.6.1.4.1.12356.100.1.1.1.0")),
				lookupMib = True,
				lexicographicMode = False
			)
			errorIndication, errorStatus, errorIndex, varBinds = next(snmpRequest)
			if errorIndication:
				if verbScanProgressFlag:
					print("\t[WARN!] IP %s [SNMP - Vendor Info] - %s" % (snmpHost, errorIndication))
			elif errorStatus:
				print("\t[ERROR!] %s at %s" % (errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1][0] or "?"))
			else:
				# Array for storing SNMP values
				varBindValues = []
				# Extracting SNMP OIDs and their values
				for varBind in varBinds:
					### DEBUG: Pretty output of SNMP library
					# print(" = ".join([x.prettyPrint() for x in varBind]))
					name, value = varBind
					varBindValues.append(str(value).replace("\n", " "))
					### DEBUG: OID and value output
					# print("\tOID = %s" % name)
					# print("\tValue = %s" % value)
				# Re-filling some dictionary values with array values
				keysDictionary = {0 : "FW", 1 : "S/N"}
				for arrayKey, dictKey in keysDictionary.items():
					value = varBindValues[arrayKey]
					if ((value) != None and len(value) > 0):
						snmpDataDict[snmpHost][dictKey] = value
	# SNMP GET-NEXT requests payload & processing
	# Interfaces object dictionary
	interfaceDict = {}
	# MAC address collecting (only interface #1)
	snmpRequest = nextCmd (
		SnmpEngine (),
		snmpAuth,
		UdpTransportTarget ((snmpHost, snmpPort), retries=snmpRetriesCount, timeout=float(snmpTimeout)),
		ContextData (),
		# MAC address @ ifPhysAddress!@#.iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifPhysAddress
		ObjectType(ObjectIdentity("IF-MIB", "ifPhysAddress")),
		lookupMib = True,
		lexicographicMode = False
	)
	errorIndication, errorStatus, errorIndex, varBinds = next(snmpRequest)
	if errorIndication:
		if verbScanProgressFlag:
			print("\t[WARN!] IP %s [SNMP - MAC Addresses] - %s" % (snmpHost, errorIndication))
	elif errorStatus:
		print("\t[ERROR!] %s at %s" % (errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1][0] or "?"))
	else:
		# Extracting SNMP OIDs and their values
		for varBind in varBinds:
			### DEBUG: Pretty output of SNMP library
			# print(" = ".join([x.prettyPrint() for x in varBind]))
			name, value = varBind
			snmpDataDict[snmpHost]["MAC Address"] = str(macaddress.MAC(bytes(value))).replace("-", ":").lower()
			### DEBUG: OID and MAC value output
			# print("\tOID = %s" % name)
			# print("\tValue = %s" % str(macaddress.MAC(bytes(value))).replace("-", ":"))
		# Flipping SNMP state flag
		snmpDataDict[snmpHost]["SNMP"] = True
	# Interface's physical data collecting
	snmpRequest = nextCmd (
		SnmpEngine (),
		snmpAuth,
		UdpTransportTarget ((snmpHost, snmpPort), retries=snmpRetriesCount, timeout=float(snmpTimeout)),
		ContextData (),
		# Interface index @ ifIndex!@#.iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifIndex
		ObjectType(ObjectIdentity("IF-MIB", "ifIndex")),
		# Interface description @ ifDescr!@#.iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifDescr
		ObjectType(ObjectIdentity("IF-MIB", "ifDescr")),
		# Interface type @ ifType!@#.iso.org.dod.internet.mgmt.mib-2.interfaces.ifTable.ifEntry.ifType
		ObjectType(ObjectIdentity("IF-MIB", "ifType")),
		lookupMib = True,
		lexicographicMode = False
	)
	snmpIterCount = 0
	while(snmpIterCount < snmpIterMaxCount):
		try:
			errorIndication, errorStatus, errorIndex, varBinds = next(snmpRequest)
			if errorIndication:
				if verbScanProgressFlag:
					print("\t[WARN!] IP %s [SNMP - IP Addresses] - %s" % (snmpHost, errorIndication))
			elif errorStatus:
				print("\t[ERROR!] %s at %s" % (errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1][0] or "?"))
			else:
				# Extracting SNMP OIDs and their values
				intNumber = None
				for varBind in varBinds:
					### DEBUG: Pretty output of SNMP library
					# print(" = ".join([x.prettyPrint() for x in varBind]))
					name, value = varBind
					# Storing interface index number
					if isinstance(value, Integer32) and ("ifIndex" in name.prettyPrint()):
						intNumber = int(value)
						if intNumber not in interfaceDict.keys():
							interfaceDict.update({intNumber : interfaceDictTemplate.copy()})
							interfaceDict[intNumber]["Index"] = intNumber
					# Storing interface data
					### TODO: Add more values processing
					# Interface description
					if isinstance(value, OctetString) and ("ifDescr" in name.prettyPrint()) and (len(value) > 0):
						interfaceDict[intNumber]["Description"] = str(value)
					# Interface type
					if isinstance(value, Integer32) and ("ifType" in name.prettyPrint()):
						interfaceDict[intNumber]["Type"] = value.prettyPrint()
					### DEBUG: OID and its value output
					# print("\tOID = %s" % name)
					# print("\tValue = %s" % value)
			snmpIterCount += 1
		except StopIteration:
			break
	# Interface's logical data collecting
	snmpRequest = nextCmd (
		SnmpEngine (),
		snmpAuth,
		UdpTransportTarget ((snmpHost, snmpPort), retries=snmpRetriesCount, timeout=float(snmpTimeout)),
		ContextData (),
		# IP interface index @ ipAdEntIfIndex!@#.iso.org.dod.internet.mgmt.mib-2.ip.ipAddrTable.ipAddrEntry.ipAdEntIfIndex
		ObjectType(ObjectIdentity("IP-MIB", "ipAdEntIfIndex")),
		# IP interface address @ ipAdEntAddr!@#.iso.org.dod.internet.mgmt.mib-2.ip.ipAddrTable.ipAddrEntry.ipAdEntAddr
		ObjectType(ObjectIdentity("IP-MIB", "ipAdEntAddr")),
		# IP interface netmask @ ipAdEntNetMask!@#.iso.org.dod.internet.mgmt.mib-2.ip.ipAddrTable.ipAddrEntry.ipAdEntNetMask
		ObjectType(ObjectIdentity("IP-MIB", "ipAdEntNetMask")),
		lookupMib = True,
		lexicographicMode = False
	)
	snmpIterCount = 0
	while(snmpIterCount < snmpIterMaxCount):
		try:
			errorIndication, errorStatus, errorIndex, varBinds = next(snmpRequest)
			if errorIndication:
				if verbScanProgressFlag:
					print("\t[WARN!] IP %s [SNMP - IP Addresses] - %s" % (snmpHost, errorIndication))
			elif errorStatus:
				print("\t[ERROR!] %s at %s" % (errorStatus.prettyPrint(), errorIndex and varBinds[int(errorIndex)-1][0] or "?"))
			else:
				# Extracting SNMP OIDs and their values
				for varBind in varBinds:
					### DEBUG: Pretty output of SNMP library
					# print(" = ".join([x.prettyPrint() for x in varBind]))
					name, value = varBind
					# Storing interface index number
					if isinstance(value, Integer32):
						intNumber = int(value)
						if intNumber not in interfaceDict.keys():
							interfaceDict.update({intNumber : interfaceDictTemplate.copy()})
							interfaceDict[intNumber]["Index"] = intNumber
					# Storing interface address and network mask
					elif isinstance(value, IpAddress):
						ipAddressObject = IPv4Address(value.asOctets())
						objType = "Netmask" if IPAddress(str(ipAddressObject)).is_netmask() else "IP Address"
						interfaceDict[intNumber][objType] = ipAddressObject if (intNumber != None) else None
					### DEBUG: OID and IP value output
					# print("\tOID = %s" % name)
					# print("\tIP = %s" % IPv4Address(value.asOctets()))
				# Storing an IP address with network mask in CIDR notation
				snmpDataDict[snmpHost]["IP Addresses"].append(str(interfaceDict[intNumber]["IP Address"]) + "/" + str(IPv4Network((0, str(interfaceDict[intNumber]["Netmask"]))).prefixlen))
			snmpIterCount += 1
		except StopIteration:
			break
	### DEBUG
	### TODO: Not sorting by key values
	# Sorting interfaces dictionary
	# interfaceDict.update(sorted(interfaceDict.items()))
	### DEBUG
	# Interfaces dictionary output
	print("\n\nInterfaces dictionary:")
	print(interfaceDict)
	# Filling-ip IP address with None if there are no any addresses
	if len(snmpDataDict[snmpHost]["IP Addresses"]) == 0:
		snmpDataDict[snmpHost]["IP Addresses"] = None
	else:
		# Flipping SNMP state flag
		snmpDataDict[snmpHost]["SNMP"] = True
	return snmpDataDict

# Converting an execution time into human readable format
def convertTime(timeInSeconds):
	if not timeInSeconds == None:
		if timeInSeconds >= 0:
			frac, days = modf(timeInSeconds/86400)
			frac, hours = modf((frac*86400)/3600)
			frac, minutes = modf((frac*3600)/60)
			frac, seconds = modf((frac*60))
			return ("%d day(s) %d hour(s) %d min(s) and %d second(s)" % (days, hours, minutes, seconds))
	return ("N/A")

# CSV generation function
def generateCSVReport(inputDict, netAddress, templateDict, csvDelimeter=",", emptyValue="N/A"):
	# Processing data
	reportContent = ""
	### HEADER DATA
	if ((templateDict != None) and isinstance(templateDict, dict) and (len(templateDict)) > 0):
		# Generating header row
		csvFileHeader = ["Network", "Host"]
		# Parsing columns data array
		for key in templateDict:
			csvFileHeader.append(key)
		# Filling table header row with data
		csvRowData = ""
		for value in csvFileHeader:
			csvRowData += value + csvDelimeter
		csvRowData = csvRowData.removesuffix(csvDelimeter)
		csvRowData += "\n"
		reportContent += csvRowData
	### CONTENT DATA
	# Filling table rows with data
	if ((inputDict != None) and isinstance(inputDict, dict) and (len(inputDict)) > 0):
		for host in inputDict:
			csvRowData = ""
			# Injecting additional columns into CSV
			csvRowData += netAddress + csvDelimeter
			csvRowData += host + csvDelimeter
			# Processing multiple values from dictionary
			for element in inputDict[host]:
				# Processing multiple IP addresses values
				if (element == "IP Addresses" and inputDict[host][element] != None):
					elementValue = ""
					for ipAddress in inputDict[host][element]:
						elementValue += str(ipAddress) + ", "
					elementValue = elementValue.removesuffix(", ")
				# Processing any non-zero values
				elif inputDict[host][element] != None:
					elementValue = str(inputDict[host][element])
				# None-values processing
				else:
					elementValue = emptyValue
				csvRowData += elementValue + csvDelimeter
			csvRowData = csvRowData.removesuffix(csvDelimeter)
			csvRowData += "\n"
			reportContent += csvRowData
	return reportContent

# Function for flushing content from memory to file
def flushMemContentToFile(filePath, memContent):
	if memContent == None:
		print("Nothing to flush to the file!")
		sys.exit()		
	else:
		try:
			print("Flushing data to the file \"%s\"..." % filePath)
			file = open(filePath, "w+", encoding="utf8")
			file.writelines(memContent)
			file.close()
		except:
			print("Failed to flush to the output file!")
			sys.exit()

### Main code block
# Determinating the time of start	
startTime = time.time()
print("\nNetSNMP Inventory Tool v" + __version__ + " by " + __author__ + ".")

# Calculating the network
netAddress = scanAddress.network_address
netBroadcastAddress = scanAddress.broadcast_address
netPrefixLen = scanAddress.prefixlen
netDescription = str(netAddress) + "/" + str(netPrefixLen)
netAddressesCount = 1 if (netPrefixLen == 32) else (scanAddress.num_addresses - 2)
print("\nThe given network is %s (%s), consists of %d host(s).\n" % (netDescription, scanAddress.netmask, netAddressesCount))
if netAddressesCount <= 0:
	print("There are no hosts to scan! Exiting...\n")
	exit()

# Generating host dictionary
netScanDict = {netDescription : {}}
if netPrefixLen == 32:
	hostAddress = netAddress
	netScanDict[netDescription].update({str(hostAddress) : dataDictTemplate.copy()})
else:
	for hostAddress in scanAddress:
		if ((hostAddress != netAddress) and (hostAddress != netBroadcastAddress)):
			netScanDict[netDescription].update({str(hostAddress) : dataDictTemplate.copy()})

# Performing host discovery & SNMP audit
currentAddressNumber = 1
print("Scanning hosts (ICMP PING discovery + SNMP requests):")
for hostAddress in netScanDict[netDescription]:
	# Performing ICMP PING host discovery
	print("\tProgress: IP %s [PING] - %s of %s (%.2f%%)" % (hostAddress, currentAddressNumber, netAddressesCount, currentAddressNumber/netAddressesCount*100), end="\r")
	checkResult = ping(hostAddress)
	### DEBUG: PING value output in miliseconds
	# print(round(checkResult, 2))
	hostIsActive = True if isinstance(checkResult, float) else False
	netScanDict[netDescription][hostAddress]["PING"] = hostIsActive
	# Performing SNMP host audit
	if hostIsActive or ignorePingFlag:
		print("\tProgress: IP %s [SNMP] - %d of %d (%.2f%%)" % (hostAddress, currentAddressNumber, netAddressesCount, currentAddressNumber/netAddressesCount*100), end="\r")
		netScanDict[netDescription].update(snmpAudit(hostAddress, hostIsActive, snmpUsername, snmpAuthKey, snmpPrivKey, dataDictTemplate, csvReportDelimeter, snmpAuthProtocol, snmpPrivProtocol, snmpPort, snmpIterMaxCount, snmpRetriesCount, snmpTimeout))
	# Incrementing address number
	currentAddressNumber += 1

# Printing out the results
if scanResultsOutputFlag:
	print("\n\nThe scan results for network %s are:" % (netDescription))
	for hostAddress in netScanDict[netDescription]:
		resultString = "\t " + hostAddress + ": "
		for element in netScanDict[netDescription][hostAddress]:
			# Processing multiple IP addresses values
			if (element == "IP Addresses" and netScanDict[netDescription][hostAddress][element] != None):
				elementValue = ""
				# IP addresses arrays
				for ipAddress in netScanDict[netDescription][hostAddress][element]:
					elementValue += str(ipAddress) + ", "
				elementValue = elementValue.removesuffix(", ")
			# Any non-zero values
			elif netScanDict[netDescription][hostAddress][element] != None:
				elementValue = str(netScanDict[netDescription][hostAddress][element])
			# None-values
			else:
				elementValue = reportEmptyValue
			resultString = resultString + element + " = " + elementValue + "; "
		print(resultString.removesuffix(" "))

# Determinating the time of end
endTime = time.time()

# Statistic printing and exiting
if not scanResultsOutputFlag:
	print()
print("\n%d hosts have been scanned in %s." % (netAddressesCount, convertTime(endTime-startTime)))
print()

# Generating CSV file content
outFileContent = generateCSVReport(netScanDict[netDescription], netDescription, dataDictTemplate, csvReportDelimeter, reportEmptyValue)

### DEBUG: CSV report printing
# print("Results output in CSV format:")
# print(outFileContent)

# Flushing data into file
print("Exporting CSV report into file...")
flushMemContentToFile(outFilePath, outFileContent)

print("\nDone!\n")
