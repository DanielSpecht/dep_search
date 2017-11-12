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
VOLUME_PATH = "/home/daniel/Documentos/testes/Docker_v2/dep_search/dep_search/webapi/bosque_db"
#VOLUME_PATH = "/data/bosque-db"

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
        # # password
        # if "password" not in flask.request.form:
        #     raise Exception("No password recieved")

        # password = urllib.unquote(flask.request.form["password"]).encode('latin1').decode('utf8')
        # hashedPassword = hashPassword(password)

        # # username
        # if "username" not in flask.request.form:
        #     raise Exception("No user recieved")

        # username = urllib.unquote(flask.request.form["username"]).encode('latin1').decode('utf8')

        # # auth user...
        # authenticate(username,password)

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

        if VERBOSE:
            print >> sys.stderr, "\n UPDATE SUCESS \n"

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

# BACKUP

def backupCheck():
    minutes = 5
    while True:

        time.sleep(60*minutes)
        print >> sys.stderr,"Checking changes in database."
        global LAST_BACKUP
        global LAST_UPDATE
        if VERBOSE:
            print LAST_BACKUP
            print LAST_UPDATE
            print LAST_BACKUP<LAST_UPDATE
        if LAST_BACKUP < LAST_UPDATE:
            print >> sys.stderr,"Changes detected on database"
            backupDB()

def backupDB():
    while True:
        try:
            print >> sys.stderr, "Backing up the DB."
            createDBCopy()
            sendDBCopy()
            global LAST_BACKUP
            LAST_BACKUP = datetime.datetime.now()

            break
        except:
            print >> sys.stderr,"Error backing up the DB:"
            print >> sys.stderr,traceback.format_exc()
            print >> sys.stderr,"Trying backing up the DB again..."
            time.sleep(5)
            continue

def createDBCopy():
    myurl = "".join(["http://localhost:",str(DEFAULT_PORT),"/?search=_","&db=Bosque","&c","&retmax=",str(ABSOLUTE_RETMAX)])
    response = urllib.urlopen(myurl)
    fileContents = response.read()
    with open(DB_CONLLU_FILE,"w") as DBfile:
        DBfile.write(fileContents)

def sendDBCopy():
    print "Sending file conll-u file"
    conn = getConnection()
    containerName = "bosque-UD"
    with open(DB_CONLLU_FILE, 'r') as DBfile:
        conn.put_object(containerName,
        os.path.basename(DB_CONLLU_FILE),
        contents= DBfile.read())

# Get The DB

def getConlluDBFile():
    if not os.path.isfile(DB_CONLLU_FILE):
        while True:
            try:
                if VERBOSE:
                    print >> sys.stderr , "Conllu file not found."
                    print >> sys.stderr , " Getting the conllu file for the DB."

                conn = getConnection()
                # Download an object and save it
                obj = conn.get_object("bosque-UD", os.path.basename(DB_CONLLU_FILE))
                with open(DB_CONLLU_FILE, 'w') as DBfile:
                    DBfile.write(obj[1])

                if VERBOSE:
                    print >> sys.stderr, "Database file %s downloaded successfully." % (DB_CONLLU_FILE)
                break

            except:
                print >> sys.stderr,"Error getting DB file:"
                print >> sys.stderr,traceback.format_exc()
                print >> sys.stderr, "Trying getting the DB again..."
                time.sleep(5)
                continue
    else:
        if VERBOSE:
            print >> sys.stderr, "Conllu file found."


def buildDB():
    while True:
        try:
            if VERBOSE:
                print >> sys.stderr, "Building database from file."

            command = ["cat",DB_CONLLU_FILE,"|","python","../build_index.py","--wipe","-d",os.path.dirname(DB_CONLLU_FILE)]
            os.system(" ".join(command))
            break
        except:
            print >> sys.stderr,"Error building the DB file:"
            print >> sys.stderr,traceback.format_exc()
            print >> sys.stderr, "Trying building the DB again..."
            time.sleep(5)
            continue

def getDB():
    if not os.path.isfile(DB_FILE):
        if VERBOSE:
            print >> sys.stderr, "No database found."
            print >> sys.stderr, "Building database..."

        getConlluDBFile()
        buildDB()
    else:
        if VERBOSE:
            print >> sys.stderr, "Database found."

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
                 VolumeConlluFilesFolder = "conllu_files",
                 VolumeDBMountFolder="databases",
                 verbose=False):
        
        self.databases = []

        self.backupCheckTime = backupCheckTime

        self.containerName = containerName

        self.storageManager = ObjectStorageManager(objectStoragecredentials,True)

        self.verbose = verbose

        self.dbMountFolder = os.path.join(volumeDir,VolumeDBMountFolder)
        if not os.path.exists(self.dbMountFolder):
            os.makedirs(self.dbMountFolder)

        self.conlluFilesFolder = os.path.join(volumeDir,VolumeConlluFilesFolder)
        if not os.path.exists(self.conlluFilesFolder):
            os.makedirs(self.conlluFilesFolder)

    def startUp(self):
        self._defineDatabases()
        self._downloadConlluFiles()
        self._mountDatabases()
        self._configureApplication()

    def _startBackUpCheckLoop(self):
        while True:
            time.sleep(self.backupCheckTime)
            self._backupCheck()

    def _backupCheck(self):
        if self.verbose:
            print >> sys.stderr,"\nChecking changes in databases\n"

        for database in self.databases:
            if database.needsBackup():
                
                if self.verbose:
                    print >> sys.stderr,"\Changes detected in %s database\n"%(database.dbName)
                
                self._backupDB(database)

    def _backupDB(self,database):
        if self.verbose:
            print >> sys.stderr, "\nBacking up the database %s.\n"%(database.dbName)
        
        self._updateConlluFileFromDB(database)
        self.storageManager.backupFile(database.conlluFilePath,self.containerName,database.conlluFileName)

    def _updateConlluFileFromDB(self,database):
        while True:
            try:
                if self.verbose:
                    print >> sys.stderr, "\n Updating file %s.\n"%(database.dbName)

                # Gets a conllu file with all the sentences of the database
                myurl = "".join(["http://localhost:",str(DEFAULT_PORT),"/?search=_","&db=",database.prefix,"&c","&retmax=",str(ABSOLUTE_RETMAX)])
                response = urllib.urlopen(myurl)
                fileContents = response.read()

                with open(database.conlluFilePath,"w") as conlluFile:
                    conlluFile.write(fileContents)

                break
            except:
                if self.verbose:
                    print >> sys.stderr, "\n Error Updating file %s. Trying again.\n"%(database.dbName)
                    print >> sys.stderr, traceback.format_exc()
                    time.sleep(10)
                continue



    def _configureApplication(self):
        if self.verbose:
            print >> sys.stderr,"\n Creating configuration file corpora.yaml.\n"

        with open("corpora.yaml","w") as corpora:
            for database in self.databases:
                lines =["%s:\n"%database.prefix,
                        "  paths: %s\n"%database.dbFilePath,
                        '  name: "%s"\n'%database.prefix]

                corpora.writelines(lines)

        if self.verbose:
            print >> sys.stderr,"\n Creating configuration file corpus_groups.yaml.\n"

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
                    print >> sys.stderr,"\n Database %s already mounted. Skipping.\n"%(database.dbName)

        for unmountedDatabase in [database for database in self.databases if not database.isMounted()]:
            self._mountDatabase(unmountedDatabase)

    def _defineDatabases(self):
        fileNames = self.storageManager.getFileNamesOfContainer(self.containerName)
        dbsFileNames = [fileName for fileName in fileNames if re.match(".*\.conllu.zip",fileName)]

        if self.verbose:
            print >> sys.stderr,"\nFound %s files for building databases:\n"%(len(dbsFileNames))
            
            for fileName in dbsFileNames:
                print >> sys.stderr,"\t - %s\n"%(fileName) 

        # Get the files from the repository
        for dbName in dbsFileNames:
            # Remove the ".zip" in the end i.e. file.conllu.zip -> file.conllu
            conllufileName = os.path.splitext(dbName)[0]
            conlluFilePath = os.path.join(self.conlluFilesFolder,conllufileName)
            self.databases.append(dep_search_database(conlluFilePath,self.dbMountFolder))

    def _downloadConlluFiles(self):
        # Get the files from the repository
        for database in self.databases:
            if not database.isDownloaded():
                self.storageManager.getFile(database.conlluFilePath,self.containerName,database.objectStorageFileName)
            else:
                print >> sys.stderr,"\n File %s already downloaded. Skipping.\n"%(database.conlluFileName)

    def _mountDatabase(self,database):

        if VERBOSE:
            print >> sys.stderr, "\nBuilding database from file %s\n"%(database.conlluFilePath)

        command = ["cat",database.conlluFilePath,"|","python","../build_index.py","--wipe","-d",database.directory,"--prefix",database.prefix]

        os.system(" ".join(command))

        if VERBOSE:
            print >> sys.stderr, "\nBuild complete\n"

class dep_search_database():
    def __init__(self,conlluFilePath, databasesDirectory):

        self.conlluFilePath = conlluFilePath # i.e. a/b/file.conllu
        self.conlluFileName = os.path.basename(self.conlluFilePath) # i.e. file.conllu
        self.prefix = os.path.splitext(self.conlluFileName)[0] # i.e. file

        self.objectStorageFileName = self.conlluFileName+".zip"


        self.dbName = self.prefix+"_00000.db"
        self.directory = os.path.join(databasesDirectory, self.prefix)
        self.dbFilePath = os.path.join(self.directory, self.dbName)

        now = datetime.datetime.now()
        self.lastBackup = now
        self.lastUpdate = now

    def isDownloaded(self):
        return os.path.isfile(self.conlluFilePath)

    def isMounted(self):
        return os.path.isfile(self.dbFilePath)

    def needsBackup(self):
        return self.lastBackup < self.lastUpdate

class ObjectStorageManager:
    def __init__(self, credentials, verbose=False):
        self.verbose = verbose
        self.credentials = credentials

    def _getConnection(self):
        return swiftclient.Connection(key=self.credentials['password'],
                                        authurl=self.credentials['auth_url']+"/v3",
                                        auth_version='3',
                                        os_options={"project_id": self.credentials['projectId'],
                                                    "user_id": self.credentials['userId'],
                                                    "region_name": self.credentials['region']})

    def backupFile(self,filePath,storageContainer,storageFileName):
        self._tryUntilSucced(function = lambda: self._backupFile(filePath,storageContainer, storageFileName))

    def _backupFile(self, filePath,storageContainer, storageFileName):
        
        tempFolder = tempfile.mkdtemp()
    
        try:
            if self.verbose:
                print "\nSending local file %s file to storage as %s\n"%(filePath,storageFileName)

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
                print "\nFile %s compressed and sent successfully as %s\n"%(filePath,storageFileName)
        finally:
            shutil.rmtree(tempFolder)

    def getFile(self,savePath,container,fileName):
        content = self._tryUntilSucced(function = lambda: self._getFile(savePath, fileName,container))

    def _getFile(self,savePath,fileName,container):
        tempFolder = tempfile.mkdtemp()
        try:
            if self.verbose:
                print >> sys.stderr , "\nGetting %s file from storage\n"%(fileName)

            # Download an object and save it
            content = self._getConnection().get_object(container, fileName)[1]

            # Write compressed contents in temporary file
            tempFilePath = os.path.join(tempFolder,"TemporaryCompressed")

            with open(tempFilePath, 'w') as compressedFile:
                compressedFile.write(content)

            with open(savePath,'w') as file:
                with gzip.open(tempFilePath, 'rb') as uncompressedFile:
                    file.write(uncompressedFile.read())

            if self.verbose:
                print >> sys.stderr, "\nFile %s downloaded successfully, uncompressed and saved as %s\n" % (fileName,savePath)
        
        finally:
            shutil.rmtree(tempFolder)


    def _tryUntilSucced(self, function):
        while True:
            try:
                return function()
            except:
                if self.verbose:
                    print >> sys.stderr, "\nError in object storage operation\n"
                    print >> sys.stderr, "\nTrying again\n"
                    print >> sys.stderr, traceback.format_exc()
                time.sleep(10)
                continue

    def getFileNamesOfContainer(self,containerName):
        return self._tryUntilSucced(function = lambda: self._getFileNamesOfContainer(containerName)) 

    def _getFileNamesOfContainer(self,containerName):
        if self.verbose:
            print >> sys.stderr, "\nGetting file names from container %s\n"%(containerName)

        connection = self._getConnection()
        return  [file['name'] for file in connection.get_container(containerName)[1]]

if __name__=="__main__":
    try:
        global manager
        credentials = json.loads(os.environ['OBJECT_STORAGE_CREDENTIALS'].replace("'",'"'))

        manager = ObjectStorageManager(credentials,True)

        dbManager = DatabaseBackupManager(volumeDir=VOLUME_PATH,objectStoragecredentials=credentials, verbose=True)
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

        #getDB()
        #threading.Thread(target=backupCheck, args=()).start()

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