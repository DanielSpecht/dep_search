import os
import datetime
import threading
import json

lock = threading.Lock()

def createDBCopy(file):
    myurl = "".join(["http://localhost:","45678","/?search=_","&db=Bosque","&c","&retmax=","100000"])
    response = urllib.urlopen(myurl)  
    fileContents = response.read()
    with open(file.getFilePath(),"w") as DBfile:
        DBfile.write(fileContents)

def updateOrAddLineToJson():
    pass

def addLineToJsonFile(file,line):
    lines = None

    with open(file.getFilePath(),"r" ) as file:
        lines = json.loads(file.read())

    lines.append(line)

    with open(file.getFilePath(),"w" ) as file:
        file.write(json.dumps(lines))

def readContents(file):
    with open(file.getFilePath(),"r" ) as file:
        return file.read()

class objectFile:
    def __init__ (self, name, folder, container,verbose=True,backupAccessor=readContents):
        self.name = name
        self.folder = folder
        self.container = container
        
        startupDate = datetime.datetime.now()
        self.lastUpdate = startupDate
        self.lastBackup = startupDate

        self.backupAccessor = backupAccessor
        self.verbose=verbose


    def getFilePath(self):
        return os.path.join(self.folder,self.name)

    def accessContents(self,accessFunction,args):
        global lock
        # only 1 access at all times
        with lock:
            accessFunction(self,*args)

    def createItself(self,createType="json"):
        if os.path.isfile(self.getFilePath()):
            raise Exception("File already exists!")
        else:
            pass

    def needsBackup(self):
        return self.lastBackup < self.lastUpdate

    def backedUp(self):
        self.lastBackup = datetime.datetime.now()

    def _updated(self):
        self.lastUpdate = datetime.datetime.now()

class Mounter:
    def __init__ (self, credentials,volumePath,minutes,files = []):
        self.credentials = credentials
        self.connection = self._getConnection(credentials)
        self.files= files
        self.minutes = minutes

    def _getConnection(self,credentials):
        return swiftclient.Connection(key=credentials['password'],
                                    authurl=credentials['auth_url']+"/v3",
                                    auth_version='3',
                                    os_options={"project_id": credentials['projectId'],
                                                "user_id": credentials['userId'],
                                                "region_name": credentials['region']})

    def backupFile(self,file):
        print "Sending %s file"%file.name
        self.connection.put_object(file.container,file.name,contents = file.getFileContents())

    def getFile(self,file):
            try:
                if self.verbose:
                    print >> sys.stderr , "%s file not found."%(file.name)
                    print >> sys.stderr , "Getting %s file for the DB."%(file.name)

                # Download an object and save it
                obj = self.connection.get_object(file.container, file.name)
                file.saveFileContents(obj[1])

                if self.verbose:
                    print >> sys.stderr, "File %s downloaded successfully." % (file.name)

            except:
                if self.verbose:
                    print >> sys.stderr,"Error getting the %s file."%(file.name)
                    print >> sys.stderr,traceback.format_exc()

    def ensure(self,function,actionDescription,wait=10):
        while True:
            try:
                function()
                break
            except:
                if self.verbose:
                    print >> sys.stderr,traceback.format_exc()
                    print >> sys.stderr, "Trying %s again..."%(actionDescription)
                time.sleep(wait)
                continue

    def addFile(self,file):
        
        # Check if file exists
        if os.path.isfile(file.getFilePath()):
            self.files.append(file)
            return
        elif containerHasFile(file):
            pass
        else:
            file.createItself()

    def containerHasFile(self,file):
        pass

