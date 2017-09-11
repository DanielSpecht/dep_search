# -*- coding: utf-8 -*-
import argparse
import sys
import cPickle as pickle
import sqlite3
import codecs
from datetime import datetime
from tree import Tree, SymbolStats
import json
import re
import struct
import os
import setlib.pytset as pytset
import zlib
import itertools
import os.path
import traceback
import glob
import db_util

ID,FORM,LEMMA,PLEMMA,POS,PPOS,FEAT,PFEAT,HEAD,PHEAD,DEPREL,PDEPREL=range(12)

DEBUG_MODE = True


def read_conll(inp,maxsent=0):
    """ Read conll format file and yield one sentence at a time as a list of lists of columns. If inp is a string it will be interpreted as fi
lename, otherwise as open file for reading in unicode"""
    if isinstance(inp,basestring):
        f=codecs.open(inp,u"rt",u"utf-8")

    else:
        f=codecs.getreader("utf-8")(inp) # read inp directly

    count=0
    sent=[]
    comments=[]
    for line in f:
        line=line.strip()
        if not line:
            if sent:
                count+=1
                yield sent, comments
                if maxsent!=0 and count>=maxsent:
                    break
                sent=[]
                comments=[]
        elif line.startswith(u"#"):
            if sent:
                raise ValueError("Missing newline after sentence")
            comments.append(line)
            continue
        else:
            cols=line.split(u"\t")
            if cols[0].isdigit() or u"." in cols[0]:
                sent.append(cols)
    else:
        if sent:
            yield sent, comments

    if isinstance(inp,basestring):
        f.close() #Close it if you opened it
 

def serialize_as_tset_array(tree_len,sets):
    """
    tree_len -> length of the tree to be serialized
    sets: array of tree_len sets, each set holding the indices of the elements
    """
    indices=[]
    for set_idx,s in enumerate(sets):
        for item in s:
            indices.append(struct.pack("@HH",set_idx,item))
    #print "IDXs", len(indices)
    res=struct.pack("@H",tree_len)+("".join(indices))
    return res

def save_stats(stats):
    try:
        if os.path.exists(os.path.join(args.dir,"symbols.json")):
            stats.update_with_json(os.path.join(args.dir,"symbols.json"))
    except:
        traceback.print_exc()
    stats.save_json(os.path.join(args.dir,"symbols.json"))

def skip(items,skip):
    counter=0
    for i in items:
        counter+=1
        if counter<=skip:
            if counter%1000000==0:
                print >> sys.stderr, "Skipped ", counter
            continue
        yield i

def update_sentence(db,file,sent_id):
    res_db=sqlite3.connect(unicode(db))
    c = res_db.cursor()
    src_data=read_conll(file,1)
    sent_id = int(sent_id)

    if DEBUG_MODE:
        print >> sys.stderr, "----------------\n\n"
        print >> sys.stderr, open(file,"r").read()
        print >> sys.stderr, sent_id

    for sent_idx,(sent,comments) in enumerate(src_data):
        stats=SymbolStats()
        t=Tree.from_conll(comments,sent,stats)

        
        # Update sentence registred
        c.execute('UPDATE graph SET token_count=?, conllu_data_compressed=?, conllu_comment_compressed=? WHERE graph_id = ?', [len(sent),buffer(zlib.compress(t.conllu.encode("utf-8"))),buffer(zlib.compress(t.comments.encode("utf-8"))),sent_id ] )

        # Delete registries associated to the sentence
        c.execute('delete from lemma_index where graph_id =?', [sent_id])
        c.execute('delete from rel where graph_id =?', [sent_id])
        c.execute('delete from tag_index where graph_id =?', [sent_id])
        c.execute('delete from token_index where graph_id =?', [sent_id])

        #Remake registries associated to the sentence
        for token, token_set in t.tokens.iteritems():
            c.execute('INSERT INTO token_index VALUES(?,?,?,?)', [0,token,sent_id,buffer(token_set.tobytes())])

        for lemma, token_set in t.lemmas.iteritems():
            c.execute('INSERT INTO lemma_index VALUES(?,?,?,?)', [0,lemma,sent_id,buffer(token_set.tobytes())])

        for token, token_set in t.normtokens.iteritems():
            c.execute('INSERT INTO token_index VALUES(?,?,?,?)', [1,token,sent_id,buffer(token_set.tobytes())])

        for lemma, token_set in t.normlemmas.iteritems():
            c.execute('INSERT INTO lemma_index VALUES(?,?,?,?)', [1,lemma,sent_id,buffer(token_set.tobytes())])

        for tag, token_set in t.tags.iteritems():
            c.execute('INSERT INTO tag_index VALUES(?,?,?)', [sent_id,tag,buffer(token_set.tobytes())])

        for dtype, (govs,deps) in t.rels.iteritems():
            ne_g=[x for x in govs if x]
            ne_d=[x for x in deps if x]
            assert ne_g and ne_d
            gov_set=pytset.PyTSet(len(sent),(idx for idx,s in enumerate(govs) if s))
            dep_set=pytset.PyTSet(len(sent),(idx for idx,s in enumerate(deps) if s))
            try:
                c.execute('INSERT INTO rel VALUES(?,?,?,?)', [sent_id,dtype,buffer(serialize_as_tset_array(len(sent),govs)),buffer(serialize_as_tset_array(len(sent),deps))])
            except struct.error:
                for l in sent:
                    print >> sys.stderr, l
                print >> sys.stderr


    res_db.commit()
    res_db.close()
    
if __name__=="__main__":
    parser = argparse.ArgumentParser(description='Execute a sentence update against the db')
    parser.add_argument('sentence', nargs=1, help='The sentence file to be saved')
    parser.add_argument('-d', '--database', nargs=1, help='Single database or a wildcard of databases to query.')
    parser.add_argument('--dblist', nargs='+', help='A list of databases to query. Note that this argument must be passed as the last to avoid the query term being interpreted as a database name.')
    parser.add_argument('--sent_id', nargs=1, help='The id in the db of the sentence')

    args = parser.parse_args()
 
    dbs=[]

    if args.database:
        dbs.append(args.database[0])
        dbs.sort()

    elif args.dblist:
        dbs=args.dblist
    else:
        print >> sys.stderr, "No database given"
        sys.exit() #no db to search

    #print >> sys.stderr, args.sentence[0]
    
    if DEBUG_MODE:
        print >> sys.stderr, "----------------\n\n"
        print >> sys.stderr, "dbs: "+str(dbs)
        print >> sys.stderr, "sent_id: "+str(args.sent_id[0])
        if args.database:
            print >> sys.stderr, "database: "+str(args.database[0])

    # TODO - what if the sentence has different ids in  multiple databases? Isn't it better to send tuples [id,db]?
    for d in dbs:
        print >> sys.stderr, d
        update_sentence(d,args.sentence[0],args.sent_id[0])

#Test:
#http://0.0.0.0:45678/?db=Bosque&sent_id=3&update=%20[{%22UPOSTAG%22:%20%22PROPN%22,%20%22LEMMA%22:%20%22PT%22,%20%22HEAD%22:%20%220%22,%20%22DEPREL%22:%20%22root%22,%20%22FORM%22:%20%22PT%22,%20%22XPOSTAG%22:%20%22PROP|M|S|@NPHR%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%221%22,%20%22FEATS%22:%20%22Gender=Masc|Number=Sing%22},%20{%22UPOSTAG%22:%20%22ADP%22,%20%22LEMMA%22:%20%22em%22,%20%22HEAD%22:%20%224%22,%20%22DEPREL%22:%20%22case%22,%20%22FORM%22:%20%22em%22,%20%22XPOSTAG%22:%20%22%3Csam-%3E|PRP|@N%3C%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%222%22,%20%22FEATS%22:%20%22_%22},%20{%22UPOSTAG%22:%20%22DET%22,%20%22LEMMA%22:%20%22o%22,%20%22HEAD%22:%20%224%22,%20%22DEPREL%22:%20%22det%22,%20%22FORM%22:%20%22o%22,%20%22XPOSTAG%22:%20%22%3C-sam%3E|%3Cartd%3E|ART|M|S|@%3EN%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%223%22,%20%22FEATS%22:%20%22Definite=Def|Gender=Masc|Number=Sing|PronType=Art%22},%20{%22UPOSTAG%22:%20%22NOUN%22,%20%22LEMMA%22:%20%22governo%22,%20%22HEAD%22:%20%221%22,%20%22DEPREL%22:%20%22nmod%22,%20%22FORM%22:%20%22governo%22,%20%22XPOSTAG%22:%20%22%3Cnp-def%3E|N|M|S|@P%3C%22,%20%22DEPS%22:%20%22_%22,%20%22MISC%22:%20%22_%22,%20%22ID%22:%20%224%22,%20%22FEATS%22:%20%22Gender=Masc|Number=Sing%22}]&comments=[1,2,3]

