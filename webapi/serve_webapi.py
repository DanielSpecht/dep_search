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

DEFAULT_PORT=45678

THISDIR=os.path.abspath(os.path.dirname(__file__))

help_response="""\
<html>
<body>
<h1>/</h1>
<ul>
   <li>search: the query to run</li>
   <li>db: corpus,corpus,corpus</li>
   <li>retmax: max number of results (will be capped at 100K by us)</li>
   <li>dl: set headers to offer file for download</li>
   <li>shuffle: randomly shuffle the tree index databases (note: trees still returned in their document order, though!)</li>
   <li>i or case=False or case=false: case insensitive search</li>
   <li>context: number of sentences of context to include in the result. Currently capped at 10.</li>
</ul>
<h1>/metadata</h1>
Returns a json with the list of available corpora, etc...
</body>
</html>
"""

app = flask.Flask(__name__)

ABSOLUTE_RETMAX=100000
MAXCONTEXT=10

@app.route("/metadata",methods=["GET"],strict_slashes=False)
def get_metadata():
    corpora=available_corpora.get_corpora(os.path.join(THISDIR,"corpora.yaml"))
    corpus_groups=available_corpora.get_corpus_groups(os.path.join(THISDIR,"corpus_groups.yaml"),corpora)
    res={"corpus_groups":corpus_groups}
    return json.dumps(res)

@app.route("/",methods=["GET"])
def run_query():
    corpora=available_corpora.get_corpora(os.path.join(THISDIR,"corpora.yaml"))
    if "search" not in flask.request.args and "update" not in flask.request.args:
        return flask.Response(help_response)

    sent_id = None

    if "sent_id" in flask.request.args:
        sent_id = flask.request.args["sent_id"]

    comments = None

    if "comments" in flask.request.args:
        comments = flask.request.args["comments"]


    retmax=int(flask.request.args.get("retmax",1000)) #default is 1000
    retmax=min(retmax,ABSOLUTE_RETMAX)

    extra_args=[]
    if "i" in flask.request.args or flask.request.args.get("case","true").lower()=="false":
        extra_args.append("-i")
        
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
        print dbs

        if "update" in flask.request.args and "sent_id" in flask.request.args:
            temporary_file = tempfile.NamedTemporaryFile(mode="w+b", suffix=".conllu", prefix="tmp",delete=False)

            print >> sys.stderr,"=======================\n\n"                       
            print >> sys.stderr, flask.request.args["update"]           

            token_json_text = urllib.unquote(flask.request.args["update"])
            comment_json_text = urllib.unquote(flask.request.args["comments"])

            token_list = json.loads(token_json_text.encode("utf-8"))
            comment_list = json.loads(comment_json_text.encode("utf-8"))
            #TODO - checar se a estrutura do json está válida, 
            # adicionar ao readme como deve ser a estrutura do josn dos conllus
            # criar o /search
            # averiguar se o id está presente no banco e é inteiro

            for comment in comment_list:                
                if comment and comment[0]==" ":
                    temporary_file.write("#"+comment.encode("utf-8")+"\n")
                else:
                    temporary_file.write("# "+comment.encode("utf-8")+"\n")

            for token in token_list:
                temporary_file.write(token["ID"]+"\t")
                temporary_file.write(token["FORM"]+"\t")
                temporary_file.write(token["LEMMA"]+"\t")
                temporary_file.write(token["UPOSTAG"]+"\t")
                temporary_file.write(token["XPOSTAG"]+"\t")
                temporary_file.write(token["FEATS"]+"\t")
                temporary_file.write(token["HEAD"]+"\t")
                temporary_file.write(token["DEPREL"]+"\t")
                temporary_file.write(token["DEPS"]+"\t")
                temporary_file.write(token["MISC"]+"\n")

            temporary_file.write("\n")

            print >> sys.stderr, "Temporary file created: " + temporary_file.name
            
            args=["python","update_sentence.py",temporary_file.name,"--sent_id",sent_id,"--dblist"]+dbs

            print >> sys.stderr, "Running", args
            proc=sproc.Popen(args=args,cwd="..",stdout=sproc.PIPE)

        if "search" in flask.request.args:
            args=["python","query.py"]+extra_args+["-m",str(retmax),flask.request.args["search"].encode("utf-8"),"--dblist"]+dbs
            print >> sys.stderr, "Running", args            
            proc=sproc.Popen(args=args,cwd="..",stdout=sproc.PIPE)
            for line in proc.stdout:
                yield line
        
    resp=flask.Response(flask.stream_with_context(generate()),content_type="text/plain; charset=utf-8")
    if "dl" in flask.request.args:
        resp.headers["Content-Disposition"]="attachment; filename=query_result.conllu"
    return resp

if __name__=="__main__":
    #DEFAULT_PORT set at the top of this file, defaults to 45678
    host='0.0.0.0'
    app.run(host=host, port=DEFAULT_PORT, debug=True, use_reloader=True)


    #http://0.0.0.0:45678/?db=Bosque&sent_id=3&update={%22COMMENTS%22:[%22sentence-text:%20Bush%20nominated%20Jennifer%20M.%20Anderson%20for%20a%2015-year%20term%20as%20associate%20judge%20of%20the%20Superior%20Court%20of%20the%20District%20of%20Columbia,%20replacing%20Steffen%20W.%20Graae.%22,%22bbb%22],%20%22TOKENS%22:%20[{%22UPOSTAG%22:%20%22PROPN%22,%20%22LEMMA%22:%20%22PT%22,%20%22HEAD%22:%20%220%22,%20%22DEPREL%22:%20%22root%22,%20%22FORM%22:%20%22PT%22,%20%22XPOSTAG%22:%20%22PROP|M|S|@NPHR%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%221%22,%20%22FEATS%22:%20%22Gender=Masc|Number=Sing%22},%20{%22UPOSTAG%22:%20%22ADP%22,%20%22LEMMA%22:%20%22em%22,%20%22HEAD%22:%20%224%22,%20%22DEPREL%22:%20%22case%22,%20%22FORM%22:%20%22em%22,%20%22XPOSTAG%22:%20%22%3Csam-%3E|PRP|@N%3C%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%222%22,%20%22FEATS%22:%20%22_%22},%20{%22UPOSTAG%22:%20%22DET%22,%20%22LEMMA%22:%20%22o%22,%20%22HEAD%22:%20%224%22,%20%22DEPREL%22:%20%22det%22,%20%22FORM%22:%20%22o%22,%20%22XPOSTAG%22:%20%22%3C-sam%3E|%3Cartd%3E|ART|M|S|@%3EN%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%223%22,%20%22FEATS%22:%20%22Definite=Def|Gender=Masc|Number=Sing|PronType=Art%22},%20{%22UPOSTAG%22:%20%22NOUN%22,%20%22LEMMA%22:%20%22governo%22,%20%22HEAD%22:%20%221%22,%20%22DEPREL%22:%20%22nmod%22,%20%22FORM%22:%20%22governo%22,%20%22XPOSTAG%22:%20%22%3Cnp-def%3E|N|M|S|@P%3C%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%224%22,%20%22FEATS%22:%20%22Gender=Masc|Number=Sing%22}]}