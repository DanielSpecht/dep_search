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

DB_CONLLU_FILE="bosque.conllu"
ABSOLUTE_RETMAX=100000
MAXCONTEXT=10

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

        # 1 validate paremeters

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
    while True:
            time.sleep(5)
            print >> sys.stderr,"Checking changes in database."
            global LAST_BACKUP
            global LAST_UPDATE
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
    myurl = "".join(["http://localhost:",str(DEFAULT_PORT),"/?search=_","&db=Bosque","&c","retmax=",str(ABSOLUTE_RETMAX)])
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
        DB_CONLLU_FILE,
        contents= DBfile.read())

# Get The DB

def getConlluDBFile():
    while True:
        try:
            if VERBOSE:
                print >> sys.stderr , "Getting the conllu file for the DB."

            conn = getConnection()
            # Download an object and save it
            obj = conn.get_object("bosque-UD", DB_CONLLU_FILE)
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

def buildDB():
    while True:
        try:
            if VERBOSE:
                print >> sys.stderr, "Building database from file."
                
            command = ["cat",DB_CONLLU_FILE,"|","python","../build_index.py","--wipe","-d","../bosque_db"]
            os.system(" ".join(command))
            break
        except:
            print >> sys.stderr,"Error building the DB file:"
            print >> sys.stderr,traceback.format_exc()
            print >> sys.stderr, "Trying building the DB again..."            
            time.sleep(5)
            continue

def getDB():
    getConlluDBFile()
    buildDB()

if __name__=="__main__":
    try:
        #DEFAULT_PORT set at the top of this file, defaults to 45678
        host='0.0.0.0'

        global LAST_BACKUP
        global LAST_UPDATE

        date = datetime.datetime.now()
        LAST_BACKUP = date
        LAST_UPDATE = date

        getDB()
        threading.Thread(target=backupCheck, args=()).start()

        app.run(host=host, port=DEFAULT_PORT, debug=False, use_reloader=False)
    except:
        print >> sys.stderr,"Error starting the system:"
        print >> sys.stderr,traceback.format_exc()


#http://0.0.0.0:45678/update
# ?db=Bosque
# &sent_id=3
# &comments=[%22sentence-text:%20Bush%20nominated%20Jennifer%20M.%20Anderson%20for%20a%2015-year%20term%20as%20associate%20judge%20of%20the%20Superior%20Court%20of%20the%20District%20of%20Columbia,%20replacing%20Steffen%20W.%20Graae.%22,%22bbb%22]&tokens=[{%22UPOSTAG%22:%20%22PROPN%22,%20%22LEMMA%22:%20%22PT%22,%20%22HEAD%22:%20%220%22,%20%22DEPREL%22:%20%22root%22,%20%22FORM%22:%20%22PT%22,%20%22XPOSTAG%22:%20%22PROP|M|S|@NPHR%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%221%22,%20%22FEATS%22:%20%22Gender=Masc|Number=Sing%22},%20{%22UPOSTAG%22:%20%22ADP%22,%20%22LEMMA%22:%20%22em%22,%20%22HEAD%22:%20%224%22,%20%22DEPREL%22:%20%22case%22,%20%22FORM%22:%20%22em%22,%20%22XPOSTAG%22:%20%22%3Csam-%3E|PRP|@N%3C%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%222%22,%20%22FEATS%22:%20%22_%22},%20{%22UPOSTAG%22:%20%22DET%22,%20%22LEMMA%22:%20%22o%22,%20%22HEAD%22:%20%224%22,%20%22DEPREL%22:%20%22det%22,%20%22FORM%22:%20%22o%22,%20%22XPOSTAG%22:%20%22%3C-sam%3E|%3Cartd%3E|ART|M|S|@%3EN%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%223%22,%20%22FEATS%22:%20%22Definite=Def|Gender=Masc|Number=Sing|PronType=Art%22},%20{%22UPOSTAG%22:%20%22NOUN%22,%20%22LEMMA%22:%20%22governo%22,%20%22HEAD%22:%20%221%22,%20%22DEPREL%22:%20%22nmod%22,%20%22FORM%22:%20%22governo%22,%20%22XPOSTAG%22:%20%22%3Cnp-def%3E|N|M|S|@P%3C%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%224%22,%20%22FEATS%22:%20%22Gender=Masc|Number=Sing%22}]
