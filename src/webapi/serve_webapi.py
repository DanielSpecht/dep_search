# -*- coding: utf-8 -*-
import flask
import json
import sys
import subprocess as sproc
import glob
import random
import os.path
import available_corpora
import tempfile
import urllib
import os
import traceback
import swiftclient
import keystoneclient.v3 as keystoneclient
import time
import threading
import datetime
import csv
import hashlib, uuid
import re
import gzip
import shutil
from dateutil.parser import parse

DEFAULT_PORT = 45678
LAST_BACKUP = None
LAST_UPDATE = None

VERBOSE = True

THISDIR=os.path.abspath(os.path.dirname(__file__))

help_response="""\
<h1>/</h1>
<ul>
<li>search: the query to run</li>
<li>db: corpus,corpus,corpus</li>
<li>retmax: max number of results (will be capped at 100K by us)</li>
<li>dl: set headers to offer file for download</li>
<li>shuffle: randomly shuffle the tree index databases (note: trees still returned in their document order, though!)</li>
<li>i or case=False or case=false: case insensitive search</li>
<li>context: number of sentences of context to include in the result. Currently capped at 10.</li>
<li>c: indicates if the aditional comments are included</li>
</ul>
<h1>/metadata</h1>
<p>Returns a JSON with the list of available corpora, etc...</p>
<h1>/update</h1>
<p>Updates a sentence in the specified corpus. POST requests only.</p>
<ul>
<li>sent_id: The id of the sentence in the database to be updated</li>
<li>tokens: JSON of the tokens</li>
<li>comments: JSON of the comments</li>
<li>db: The db to save</li>
</ul>
<h1>/sentence</h1>
<p>Returns a sentence in JSON format</p>
<ul>
<li>sent_id: The id of the sentence in the database to be returned</li>
<li>db: The db to get the sentence from</li>
</ul>
<h1>/metadata</h1>
<p>Returns a JSON with the list of available corpora, etc...</p>
"""

app = flask.Flask(__name__)
#DB_FILE = "/data/bosque-db/trees_00000.db"
DB_FILE = "bosque_db/trees_00001.db"
#DB_CONLLU_FILE="/data/bosque-db/bosque.conllu"
DB_CONLLU_FILE="bosque_db/bosque.conllu"
ABSOLUTE_RETMAX=100000
MAXCONTEXT=10
#VOLUME_PATH = "/home/daniel/Documentos/testes/Docker_v2/dep_search/dep_search/webapi/bosque_db"
VOLUME_PATH = "/data/bosque-db"

@app.route("/metadata",methods=["GET"],strict_slashes=False)
def get_metadata():
    corpora=available_corpora.get_corpora(os.path.join(THISDIR,"corpora.yaml"))
    corpus_groups=available_corpora.get_corpus_groups(os.path.join(THISDIR,"corpus_groups.yaml"),corpora)
    res={"corpus_groups":corpus_groups}
    return json.dumps(res)

@app.route("/sentence",methods=["GET"])
def get_sentence_by_id():
    sent_id = None
    dbs=[]

    try:
        # 1 validate paremeters

        # sent_id
        if "sent_id" not in flask.request.args:
            raise Exception("No sentence id recieved")

        sent_id = flask.request.args["sent_id"]

        # db
        if "db" not in flask.request.args:
            raise Exception("No database specified")

        corpora=available_corpora.get_corpora(os.path.join(THISDIR,"corpora.yaml"))
        for corpus in flask.request.args.get("db","").split(","):
            c=corpora.get(corpus) #corpus should be the ID
            if not c: #not found? maybe it's the name!
                for some_c in corpora.itervalues():
                    if some_c["name"]==corpus:
                        c=some_c
                        break
            if not c:
                continue
            dbs.extend(c["dbs"])

        def generate():
            args=["python","get_sentence.py",sent_id,"--dblist"]+dbs

            if VERBOSE:
                print >> sys.stderr, "Running", args

            proc=sproc.Popen(args=args,cwd="..",stdout=sproc.PIPE)
            for line in proc.stdout:
                yield line

        resp=flask.Response(flask.stream_with_context(generate()),content_type="text/plain; charset=utf-8")
        if "dl" in flask.request.args:
            resp.headers["Content-Disposition"]="attachment; filename=query_result.conllu"
        return resp

    except Exception as e:
        return json.dumps({"sucess":False,"Errors":traceback.format_exc()})

@app.route("/update",methods=["POST"])
def update_sentence():
    sent_id = None
    comments = None
    sentence = None
    dbs=[]
    
    temporary_file = tempfile.NamedTemporaryFile(mode="w+b", suffix=".conllu", prefix="tmp",delete=False)

    try:
        # password
        if "password" not in flask.request.form:
            raise Exception("No password recieved")

        password = urllib.unquote(flask.request.form["password"]).encode('latin1').decode('utf8')
        hashedPassword = hashPassword(password)

        # username
        if "username" not in flask.request.form:
            raise Exception("No user recieved")

        username = urllib.unquote(flask.request.form["username"]).encode('latin1').decode('utf8')

        # auth user...
        authenticate(username,password)

        # sent_id
        if "sent_id" not in flask.request.form:
            raise Exception("No sentence id recieved")

        sent_id = flask.request.form["sent_id"]

        # comments
        if "comments" not in flask.request.form:
            raise Exception("No sentence comments recieved")

        comment_list = json.loads(urllib.unquote(flask.request.form["comments"]).encode('latin1').decode('utf8'))

        # tokens
        token_list = None
        if "tokens" not in flask.request.form:
            raise Exception("No sentence tokens sent")

        token_list = json.loads(urllib.unquote(flask.request.form["tokens"]).encode('latin1').decode('utf8'))

        # db
        if "db" not in flask.request.form:
            raise Exception("No database specified")

        corpora=available_corpora.get_corpora(os.path.join(THISDIR,"corpora.yaml"))
        for corpus in flask.request.form.get("db","").split(","):
            c=corpora.get(corpus) #corpus should be the ID
            if not c: #not found? maybe it's the name!
                for some_c in corpora.itervalues():
                    if some_c["name"]==corpus:
                        c=some_c
                        break
            if not c:
                continue
            dbs.extend(c["dbs"])

        # 2 Fill the temporaty file to be sent to the update service
        for c in comment_list:
            comment = unicode(c)
            if comment:
                temporary_file.write("#"+comment.encode("utf-8")+"\n")

        for token in token_list:
            temporary_file.write(token["ID"].encode("utf-8")+"\t")
            temporary_file.write(token["FORM"].encode("utf-8")+"\t")
            temporary_file.write(token["LEMMA"].encode("utf-8")+"\t")
            temporary_file.write(token["UPOSTAG"].encode("utf-8")+"\t")
            temporary_file.write(token["XPOSTAG"].encode("utf-8")+"\t")
            temporary_file.write(token["FEATS"].encode("utf-8")+"\t")
            temporary_file.write(token["HEAD"].encode("utf-8")+"\t")
            temporary_file.write(token["DEPREL"].encode("utf-8")+"\t")
            temporary_file.write(token["DEPS"].encode("utf-8")+"\t")
            temporary_file.write(token["MISC"].encode("utf-8")+"\n")

        temporary_file.write("\n")
        temporary_file.close()
        if VERBOSE:
            print >> sys.stderr, "Temporary file created: " + temporary_file.name


        args=["python","update_sentence.py",temporary_file.name,"--sent_id",sent_id,"--dblist"]+dbs

        if VERBOSE:
            print >> sys.stderr, "Running", args

        proc=sproc.check_call(args=args,cwd="..",stdout=sproc.PIPE)

        global dbManager
        print "--------------------<<"
        print dbs
        dbManager.flagChangedDb(dbs)

        if VERBOSE:
            print >> sys.stderr, "Update success\n"

        global LAST_UPDATE
        LAST_UPDATE = datetime.datetime.now()

        return json.dumps({"sucess":True})

    except Exception as e:
        print >> sys.stderr, "----------------\n\n"
        print >> sys.stderr, traceback.format_exc()

        return json.dumps({"sucess":False,"Errors":traceback.format_exc()})

    finally:
        temporary_file.close()
        os.unlink(temporary_file.name)

@app.route("/",methods=["GET"])
def run_query():
    corpora=available_corpora.get_corpora(os.path.join(THISDIR,"corpora.yaml"))
    if "search" not in flask.request.args:
        return flask.Response(help_response)
    retmax=int(flask.request.args.get("retmax",1000)) #default is 1000
    retmax=min(retmax,ABSOLUTE_RETMAX)

    extra_args=[]
    if "i" in flask.request.args or flask.request.args.get("case","true").lower()=="false":
        extra_args.append("-i")

    if "c" in flask.request.args or flask.request.args.get("case","true").lower()=="false":
        extra_args.append("-c")

    ctx=flask.request.args.get("context",0)

    try:
        ctx=int(ctx)
    except ValueError:
        return "<html><body>Incorrect context value</body></html>"
    if ctx>0:
        ctx=min(ctx,MAXCONTEXT)
        extra_args.append("--context")
        extra_args.append(str(ctx))

    dbs=[]
    for corpus in flask.request.args.get("db","").split(","):
        c=corpora.get(corpus) #corpus should be the ID
        if not c: #not found? maybe it's the name!
            for some_c in corpora.itervalues():
                if some_c["name"]==corpus:
                    c=some_c
                    break
        if not c:
            continue
        dbs.extend(c["dbs"])
    if "shuffle" in flask.request.args:
        random.shuffle(dbs)
    else:
        dbs=sorted(dbs)

    def generate():
        args=["python","query.py"]+extra_args+["-m",str(retmax),flask.request.args["search"].encode("utf-8"),"--dblist"]+dbs
        print >> sys.stderr, "Running", args
        proc=sproc.Popen(args=args,cwd="..",stdout=sproc.PIPE)
        for line in proc.stdout:
            yield line

    resp=flask.Response(flask.stream_with_context(generate()),content_type="text/plain; charset=utf-8")
    if "dl" in flask.request.args:
        resp.headers["Content-Disposition"]="attachment; filename=query_result.conllu"
    return resp

def getConnection():
    credentials = json.loads(os.environ['OBJECT_STORAGE_CREDENTIALS'].replace("'",'"'))
    return swiftclient.Connection(key=credentials['password'],
                                authurl=credentials['auth_url']+"/v3",
                                auth_version='3',
                                os_options={"project_id": credentials['projectId'],
                                            "user_id": credentials['userId'],
                                            "region_name": credentials['region']})

# ACCESS CONTROL

@app.route("/adduser",methods=["POST"])
def add_user():
    try:
        # admin password
        if "adminPassword" not in flask.request.form:
            raise Exception("No password recieved")
        adminPassword = urllib.unquote(flask.request.form["adminPassword"]).encode('latin1').decode('utf8')

        # password
        if "password" not in flask.request.form:
            raise Exception("No password recieved")

        password = urllib.unquote(flask.request.form["password"]).encode('latin1').decode('utf8')
        hashedPassword = hashPassword(password)

        # user
        if "user" not in flask.request.form:
            raise Exception("No user recieved")

        user = urllib.unquote(flask.request.form["user"]).encode('latin1').decode('utf8')

        authenticateAdmin(adminPassword)

        addUser(user,password)

        return json.dumps({"sucess":True})

    except Exception as e:
        print >> sys.stderr, traceback.format_exc()
        return json.dumps({"sucess":False,"Errors":traceback.format_exc()})

@app.route("/removeuser",methods=["POST"])
def remove_user():
    try:
        # admin password
        if "adminPassword" not in flask.request.form:
            raise Exception("No password recieved")
        adminPassword = urllib.unquote(flask.request.form["adminPassword"]).encode('latin1').decode('utf8')

        # password
        if "password" not in flask.request.form:
            raise Exception("No password recieved")

        password = urllib.unquote(flask.request.form["password"]).encode('latin1').decode('utf8')
        hashedPassword = hashPassword(password)

        # user
        if "user" not in flask.request.form:
            raise Exception("No user recieved")

        user = urllib.unquote(flask.request.form["user"]).encode('latin1').decode('utf8')

        authenticateAdmin(adminPassword)

        removeUser(user,password)

        return json.dumps({"sucess":True})

    except Exception as e:
        print >> sys.stderr, traceback.format_exc()
        return json.dumps({"sucess":False,"Errors":traceback.format_exc()})

@app.route("/users",methods=["POST"])
def get_users():
    try:
        # admin password
        if "adminPassword" not in flask.request.form:
            raise Exception("No password recieved")
        adminPassword = urllib.unquote(flask.request.form["adminPassword"]).encode('latin1').decode('utf8')
        authenticateAdmin(adminPassword)
        return getUsers()

    except Exception as e:
        print >> sys.stderr, traceback.format_exc()
        return json.dumps({"sucess":False,"Errors":traceback.format_exc()})

def hashPassword(password):
    #salt = uuid.uuid4().hex
    #return hashlib.sha512(password + salt).hexdigest()
    return hashlib.sha512(password).hexdigest()

def authenticate(userName,password):
    users = None
    usersFilePath = os.path.join(VOLUME_PATH,"users")

    # Get users
    with open(usersFilePath, 'r') as usersFile:
        users = json.loads(usersFile.read())
    print users

    hashedPassword = hashPassword(password)

    for user in users:
        if user['userName'] == userName and user['password'] == hashedPassword:
            if VERBOSE:
                print >> sys.stderr, "User %s authenticated"%userName
            return

    raise Exception("User %s not found"%userName)

def authenticateAdmin(password):

    #AdminAuthorization
    if os.environ['ADMIN_CREDENTIALS'] != password:
        raise Exception("Access denied")

def addUser(userName,password):

    hashedPassword = hashPassword(password)
    users = None
    usersFilePath = os.path.join(VOLUME_PATH,"users")

    # Get users
    with open(usersFilePath, 'r') as usersFile:
        users = json.loads(usersFile.read())

    if any(user['userName'] == userName for user in users):
        for i in range(len(users)):
            if users[i]["userName"] == userName:
                users[i]["password"] = hashedPassword
    else:
        users.append({"userName":userName,"password":hashedPassword})

    # Save users
    with open(usersFilePath, 'w') as usersFile:
        usersFile.write(json.dumps(users))

def removeUser(userName,password):
    users = None
    usersFilePath = os.path.join(VOLUME_PATH,"users")

    # Get users
    with open(usersFilePath, 'r') as usersFile:
        users = json.loads(usersFile.read())

    # if user exists
    if any(user['userName'] == userName for user in users):
        for i in range(len(users)):
            if users[i]["userName"] == userName:
                users.pop(i)
                break

        # Save users
        with open(usersFilePath, 'w') as usersFile:
            usersFile.write(json.dumps(users))

    else:
        raise Exception("User specified for deletion not found")

def getUsers():
    users = None
    usersFilePath = os.path.join(VOLUME_PATH,"users")

    # Get users
    with open(usersFilePath, 'r') as usersFile:
        users = json.loads(usersFile.read())

    for i in range(len(users)):
        users[i]=users[i]["userName"]

    return "\n".join(users)+"\n"

def createUsersIfFileDoesntExist(filePath):
    if not os.path.isfile(filePath):
        if VERBOSE:
            print >>sys.stderr, "No users file found"
        with open(filePath, 'a') as file:
            file.write(json.dumps([]))
    else:
        if VERBOSE:
            print >> sys.stderr, "Users file found"

# Database manager

class DatabaseBackupManager():

    def __init__(self,
                 volumeDir,
                 objectStoragecredentials,
                 backupCheckTime = 15*60,
                 containerName = "bosque-UD",
                 volumeConlluFilesFolder = "conllu_files",
                 volumeDBMountFolder="databases",
                 versionSeparator="_",
                 compressedExtension = ".zip",
                 verbose=False):

        self.versionSeparator = versionSeparator

        self.compressedExtension = compressedExtension

        self.databases = []

        self.backupCheckTime = backupCheckTime

        self.containerName = containerName

        self.storageManager = ObjectStorageManager(objectStoragecredentials,True)

        self.verbose = verbose

        self.dbMountFolder = os.path.join(volumeDir,volumeDBMountFolder)
        if not os.path.exists(self.dbMountFolder):
            os.makedirs(self.dbMountFolder)

        self.conlluFilesFolder = os.path.join(volumeDir,volumeConlluFilesFolder)
        if not os.path.exists(self.conlluFilesFolder):
            os.makedirs(self.conlluFilesFolder)

    def startUp(self):
        self._defineDatabases()
        self._downloadConlluFiles()
        self._mountDatabases()
        self._configureApplication()
        self._startBackUpCheckLoop()

    def flagChangedDb(self,dbs):
        databases = [database for database in self.databases if database.dbFilePath in dbs]

        for database in databases:
            if self.verbose:
                print >> sys.stderr, "\nDatabase %s changed.\n"%database.dbName

            database.flagUpdate()

    def _startBackUpCheckLoop(self):
        threading.Thread(target=self._backupCheckLoop, args=()).start()

    def _backupCheckLoop(self):
        while True:
            time.sleep(self.backupCheckTime)
            self._backupCheck()

    def _backupCheck(self):
        if self.verbose:
            print >> sys.stderr,"Checking for changes in databases"

        for database in self.databases:
            if database.needsBackup():
                
                if self.verbose:
                    print >> sys.stderr,"\t - Changes detected in %s database"%(database.dbName)
                
                self._backupDB(database)

            elif self.verbose:
                print >> sys.stderr,"\t - No changes in %s database"%(database.dbName)

        if self.verbose: # Format line
            print >> sys.stderr,""  
                
    def _backupDB(self,database):
        if self.verbose:
            print >> sys.stderr, "Backing up the database %s.\n"%(database.dbName)
        
        self._updateConlluFileFromDB(database)
        self.storageManager.backupFile(database.conlluFilePath,self.containerName,database.conlluFileName)
        database.flagBackup()

    def _updateConlluFileFromDB(self,database):
        while True:
            try:
                if self.verbose:
                    print >> sys.stderr, "Updating file %s.\n"%(database.dbName)

                # Gets a conllu file with all the sentences of the database
                myurl = "".join(["http://localhost:",str(DEFAULT_PORT),"/?search=_","&db=",database.prefix,"&c","&retmax=",str(ABSOLUTE_RETMAX)])
                response = urllib.urlopen(myurl)
                fileContents = response.read()

                with open(database.conlluFilePath,"w") as conlluFile:
                    conlluFile.write(fileContents)
                break

            except:
                if self.verbose:
                    print >> sys.stderr, "Error Updating file %s. Trying again.\n"%(database.dbName)
                    print >> sys.stderr, traceback.format_exc()
                    time.sleep(10)
                continue

    def _configureApplication(self):
        if self.verbose:
            print >> sys.stderr,"Creating configuration file corpora.yaml.\n"

        with open("corpora.yaml","w") as corpora:
            for database in self.databases:
                lines =["%s:\n"%database.prefix,
                        "  paths: %s\n"%database.dbFilePath,
                        '  name: "%s"\n'%database.prefix]

                corpora.writelines(lines)

        if self.verbose:
            print >> sys.stderr,"Creating configuration file corpus_groups.yaml.\n"

        with open("corpus_groups.yaml","w") as corpus_groups:
            lines = ["-\n",
                     "  name: Bosque\n",
                     "  corpora: .*\n"]

            corpus_groups.writelines(lines)

    def _mountDatabases(self):
        # Mount the databases
        for database in self.databases:
            if not database.isMounted():
                self._mountDatabase(database)
            else:
                if self.verbose:
                    print >> sys.stderr,"Database %s already mounted. Skipping.\n"%(database.dbName)

        for unmountedDatabase in [database for database in self.databases if not database.isMounted()]:
            self._mountDatabase(unmountedDatabase)

    def _defineDatabases(self):
        fileNames = self.storageManager.getFileNamesOfContainer(self.containerName)
        databaseFilePattern = ".+%s$"%("\.conllu")
        dbsFileNames = [fileName for fileName in fileNames if re.match(databaseFilePattern,fileName)]

        if self.verbose:
            print >> sys.stderr,"Found %s files for building databases:"%(len(dbsFileNames))
            
            for fileName in dbsFileNames:
                print >> sys.stderr,"\t - %s"%(fileName) 

            print >> sys.stderr,"" # Format line

        # Get the files from the repository
        for dbName in dbsFileNames:
            conlluFilePath = os.path.join(self.conlluFilesFolder,dbName)
            self.databases.append(dep_search_database(conlluFilePath,self.dbMountFolder))

    def _downloadConlluFiles(self):
        # Get the files from the repository
        for database in self.databases:
            if not database.isDownloaded():
                self.storageManager.getFile(database.conlluFilePath,self.containerName,database.conlluFileName)
            else:
                print >> sys.stderr,"File %s already downloaded. Skipping.\n"%(database.conlluFileName)

    def _mountDatabase(self,database):

        if VERBOSE:
            print >> sys.stderr, "Building database from file %s\n"%(database.conlluFilePath)

        command = ["cat",database.conlluFilePath,"|","python","../build_index.py","--wipe","-d",database.directory,"--prefix",database.prefix]

        os.system(" ".join(command))

        if VERBOSE:
            print >> sys.stderr, "Build complete\n"

class dep_search_database():
    def __init__(self,conlluFilePath, databasesDirectory):

        self.conlluFilePath = conlluFilePath # i.e. a/b/file.conllu
        self.conlluFileName = os.path.basename(self.conlluFilePath) # i.e. file.conllu, a/b/file.conllu -> file.conllu
        self.prefix = os.path.splitext(self.conlluFileName)[0] # i.e. file, file.conllu -> file
        
        self.dbName = self.prefix+"_00000.db"
        self.directory = os.path.join(databasesDirectory, self.prefix)
        self.dbFilePath = os.path.join(self.directory, self.dbName)

        now = datetime.datetime.now()
        self.lastBackup = now
        self.lastUpdate = now

    def flagBackup(self):
        self.lastBackup = datetime.datetime.now()

    def flagUpdate(self):
        self.lastUpdate = datetime.datetime.now()

    def isDownloaded(self):
        return os.path.isfile(self.conlluFilePath)

    def isMounted(self):
        return os.path.isfile(self.dbFilePath)

    def needsBackup(self):
        return self.lastBackup < self.lastUpdate

class ObjectStorageManager:
    def __init__(self, credentials, verbose=False,maxVersions=2,compressedExtension=".zip"):
        self.verbose = verbose
        self.credentials = credentials
        self.maxVersions = maxVersions
        # The following lines stabilish that the file versions will be saved in the format: file_[version num].zip
        self.versionSeparator="_"
        self.compressedExtension = compressedExtension

    def _getConnection(self):
        return swiftclient.Connection(key=self.credentials['password'],
                                        authurl=self.credentials['auth_url']+"/v3",
                                        auth_version='3',
                                        os_options={"project_id": self.credentials['projectId'],
                                                    "user_id": self.credentials['userId'],
                                                    "region_name": self.credentials['region']})

    def backupFile(self,filePath,storageContainer,baseFileName):

        storageFileName = self._getVersionedNameForBackup(storageContainer = storageContainer,
                                                          baseFileName = baseFileName)


        self._tryUntilSucced(function = lambda: self._backupFile(filePath,storageContainer, storageFileName))

    # Returns the match of the regex indication if the fileName is a version of the baseFileName
    # Matches the file version number in group(2)
    def _matchFileVersion(self, baseFileName, fileName):
        pattern = "%s(%s(\d+))?%s"%(baseFileName,self.versionSeparator,self.compressedExtension) #i.e. [basename]_1.zip
        return re.match(pattern,fileName)

    def _getFileBaseName(self,fileName):
        pattern = "(.+)%s\d+%s$|(.+)%s$"%(self.versionSeparator,self.compressedExtension,self.compressedExtension)         
        matches = re.match(pattern,fileName)
        return matches.group(1) if matches.group(1) else matches.group(2)

    def _getVersionedNameForBackup(self,storageContainer,baseFileName):
        versions = self._getFileVersions(storageContainer,baseFileName)

        def makeVersionName(name,versionNum):
            return name+self.versionSeparator+str(versionNum)+self.compressedExtension

        if len(versions) == 0:
            return baseFileName

        # If the max number of versions is not met yet, build another version
        # The version name is generated like: file file_1 file _2
        elif len(versions) < self.maxVersions:
            return makeVersionName(baseFileName,len(versions))

        # If we have the maximum amount of copies, override the oldest
        else:
            lastVersion = None

            for version in versions:
                
                if not lastVersion:
                    lastVersion = version
                    continue

                if parse(version["last_modified"]) < parse(lastVersion["last_modified"]):
                    lastVersion = version

            return lastVersion['name']

    def _getFileVersions(self,storageContainer,baseFileName):
        files = self._getFilesOfContainer(storageContainer)
        if self.verbose:
            print >> sys.stderr,"Getting %s file versions\n"%(baseFileName)

        versions = [file for file in files if self._matchFileVersion(baseFileName,file['name'])]

        if self.verbose:
            print >> sys.stderr,"Found %s file versions"%(str(len(versions)))

            for version in versions:
                print >> sys.stderr , "\t - %s - %s"%(version['last_modified'],version['name'])

            print >> sys.stderr,""  

        return versions

    def _backupFile(self, filePath,storageContainer, storageFileName):
        tempFolder = tempfile.mkdtemp()
    
        try:
            if self.verbose:
                print "Sending local file %s file to storage as %s\n"%(filePath,storageFileName)

            #TODO - Make it better

            # Get file contents
            content = None
            with open(filePath, 'r') as file:
                content = file.read()

            # Write compressed contents in temporary file
            tempFilePath = os.path.join(tempFolder,"TemporaryCompressed")

            with gzip.open(tempFilePath, 'wr') as tempFile:
                tempFile.write(content)

            # Get temporary file compressed contents
            compressedContents = None
            with open(tempFilePath,'r') as compressedFile:
                compressedContents = compressedFile.read()

            self._getConnection().put_object(storageContainer,storageFileName,contents = compressedContents)

            if self.verbose:
                print "File %s compressed and sent successfully as %s\n"%(filePath,storageFileName)
        finally:
            shutil.rmtree(tempFolder)

    def getFile(self,savePath,container,fileName):
        content = self._tryUntilSucced(function = lambda: self._getFile(savePath, fileName, container))

    def _getFile(self,savePath,fileName,container):
        tempFolder = tempfile.mkdtemp()

        try:
            if self.verbose:
                print >> sys.stderr , "Getting %s file from storage\n"%(fileName)

            # Get the newest version of the file
            versions = self._getFileVersions(container,fileName)
            latestVersion = None
            for version in versions:
                if not latestVersion:
                    latestVersion = version
                    continue

                elif parse(version["last_modified"]) > parse(latestVersion["last_modified"]):
                    latestVersion = version
            
            if self.verbose:
                print >> sys.stderr, "Latest version: %s - %s\n"%(latestVersion['last_modified'],latestVersion['name'])

            lastVersionName = latestVersion['name']

            # Download an object and save it
            content = self._getConnection().get_object(container, lastVersionName)[1]

            # Write compressed contents in temporary file
            tempFilePath = os.path.join(tempFolder,"TemporaryCompressed")

            with open(tempFilePath, 'w') as compressedFile:
                compressedFile.write(content)

            with open(savePath,'w') as file:
                with gzip.open(tempFilePath, 'rb') as uncompressedFile:
                    file.write(uncompressedFile.read())

            if self.verbose:
                print >> sys.stderr, "File %s downloaded successfully, uncompressed and saved as %s\n" % (fileName,savePath)
        
        finally:
            shutil.rmtree(tempFolder)

    def _tryUntilSucced(self, function):
        while True:
            try:
                return function()
            except:
                if self.verbose:
                    print >> sys.stderr, "Error in object storage operation\n"
                    print >> sys.stderr, "Trying again\n"
                    print >> sys.stderr, traceback.format_exc()
                time.sleep(10)
                continue

    def getFilesOfContainer (self,containerName):
        return self._tryUntilSucced(function = lambda: self._getFilesOfContainer(containerName))

    def _getFilesOfContainer (self, containerName):
        if self.verbose:
            print >> sys.stderr, "Getting files from container %s\n"%(containerName)
        connection = self._getConnection()
        return connection.get_container(containerName)[1]

    def getFileNamesOfContainer(self,containerName):
        files = self.getFilesOfContainer(containerName)
        fileNames = [file['name'] for file in files]
        #Get Base names
        filesBaseNames = []
        
        for fileName in fileNames:
            baseFileName = self._getFileBaseName(fileName)
            if baseFileName not in filesBaseNames:
                filesBaseNames.append(baseFileName)

        return filesBaseNames

if __name__=="__main__":
    try:
        global manager
        credentials = json.loads(os.environ['OBJECT_STORAGE_CREDENTIALS'].replace("'",'"'))

        manager = ObjectStorageManager(credentials,True)

        global dbManager
        dbManager = DatabaseBackupManager(volumeDir=VOLUME_PATH,objectStoragecredentials=credentials, verbose=True,backupCheckTime = 15*60)
        dbManager.startUp()

        # fileName = "testfile.txt"
        # with open(os.path.join(VOLUME_PATH,fileName),"w") as file:
        #     file.write("Teste, comoção.")

        # manager.backupFile(os.path.join(VOLUME_PATH,fileName),"bosque-UD",fileName)
        # manager.getFile(os.path.join(VOLUME_PATH,fileName),"bosque-UD",fileName)

        #exit(0)

        # Backup startup
        global LAST_BACKUP
        global LAST_UPDATE

        date = datetime.datetime.now()
        LAST_BACKUP = date
        LAST_UPDATE = date

        # Create file for users storage
        createUsersIfFileDoesntExist(os.path.join(VOLUME_PATH,"users"))

        # System startup
        #DEFAULT_PORT set at the top of this file, defaults to 45678
        host='0.0.0.0'

        app.run(host=host, port=DEFAULT_PORT, debug=False, use_reloader=False)

    except:
        print >> sys.stderr,"Error starting the system:"
        print >> sys.stderr,traceback.format_exc()

#curl -d "adminPassword=123&password=password&user=user" -X POST http://localhost:45678/adduser
#curl -d "adminPassword=123&password=password&user=user" -X POST http://localhost:45678/removeuser
#curl -d "adminPassword=123&password=password&user=user" -X POST http://localhost:45678/users