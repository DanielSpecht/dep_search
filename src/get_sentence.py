#!/usr/bin/env python
import traceback
import sys
import os

THISDIR=os.path.dirname(os.path.abspath(__file__))
os.chdir(THISDIR)

import subprocess
import cPickle as pickle
import sqlite3
import codecs
from datetime import datetime
from tree import Tree
import re
import zlib
import importlib
import argparse
import db_util
import glob
import tempfile
import redone_expr
import json
#output in json
JSON = False

#Show additional info not present in the original sentence
CLEAN = True

field_re=re.compile(ur"^(!?)(gov|dep|token|lemma|tag)_(a|s)_(.*)$",re.U)
query_folder = './queries/'

def query(query_fields,cli_args):
    """
    cli_args: command line args
    query_fields: A list of strings describing the data to fetch
          Each string names a set to retrieve

          (gov|dep)_(a|s)_deptype
          - gov -> retrieve a from-governor-to-dependent mapping/set
          - dep -> retrieve a from-dependent-to-governor mapping/set
          - a -> retrieve a mapping (i.e. used as the third argument of the pairing() function
          - s -> retrieve a set (i.e. the set of governors or dependents of given type)
          - deptype -> deptype or u"anytype"
          prefixed with "!" means that only non-empty sets are of interest

          tag_s_TAG  -> retrieve the token set for a given tag
          prefixed with "!" means that only non-empty sets are of interest

          token_s_WORD -> retrieve the token set for a given token
          lemma_s_WORD -> retrieve the token set for a given lemma
          prefixed with "!" means that only non-empty sets are of interest
    """

    joins=[(u"FROM graph",[])]
    wheres=[]
    args=[]
    selects=[u"graph.graph_id",u"graph.token_count"]
    for i,f in enumerate(query_fields):
        match=field_re.match(f)
        assert match
        req,ftype,stype,res=match.groups() #required? field-type?  set-type?  restriction
        if req==u"!":
            j_type=u""
        elif not req:
            j_type=u"LEFT "
        else:
            assert False #should never happen
        if ftype in (u"gov",u"dep"):
            joins.append((u"%sJOIN rel AS t_%d ON graph.graph_id=t_%d.graph_id and t_%d.dtype=?"%(j_type,i,i,i),[res]))
            if stype==u"s":
                selects.append(u"t_%d.token_%s_set"%(i,ftype))
            elif stype==u"a":
                selects.append(u"t_%d.token_%s_map"%(i,ftype))
        elif ftype in (u"token",u"lemma",u"tag"):
            if not cli_args.insensitive and ftype!=u"tag":
                case_ins_clause=u" and t_%d.norm=0"%i #force lookup purely in non-normalized fields
            else:
                case_ins_clause=u""
            joins.append((u"%sJOIN %s_index AS t_%d ON graph.graph_id=t_%d.graph_id and t_%d.%s=?%s"%(j_type,ftype,i,i,i,ftype,case_ins_clause),[res]))
            selects.append(u"t_%d.token_set"%i)
    
    joins.sort() #This is a horrible hack, but it will sort FROM JOIN ... LEFT JOIN the right way and help the QueryPlan generator
    q=u"SELECT %s"%(u", ".join(selects))
    q+=u"\n"+(u"\n".join(j[0] for j in joins))
    q+=u"\n"
    args=[]
    for j in joins:
        args.extend(j[1])
    return q,args

def get_data_from_db(db_conn,graph_id):
    results=db_conn.execute('SELECT conllu_data_compressed,conllu_comment_compressed FROM graph WHERE graph_id=?',(str(graph_id),))
    for sent,comment in results.fetchall():
        return zlib.decompress(sent).strip(),zlib.decompress(comment).strip()
    return None,None

def load(pyxFile):
    """Loads a search pyx file, returns the module"""
    ###I need to hack around this, because this thing is messing stdout
    print >> sys.stderr, "Loading", pyxFile
    error=subprocess.call(["python","compile_ext.py",pyxFile], stdout=sys.stderr, stderr=sys.stderr)
    if error!=0:
        print >> sys.stderr, "Cannot compile search code, error:",error
        sys.exit(1)
    mod=importlib.import_module(pyxFile)
    return mod

def get_url(comments):
    for c in comments:
        if c.startswith(u"# URL:"):
            return c.split(u":",1)[1].strip()
    return None

def print_sent(r,idx,res_db,args):
    if not CLEAN:
        print "# graph id:",idx
        
    hit,hit_comment=get_data_from_db(res_db,idx)
    hit_lines=hit.splitlines()
    
    if not CLEAN:
        for x in sorted(r):
            print "# visual-style\t%s\tbgColor:lightgreen"%(hit_lines[x].split("\t",1)[0])
            print "# hittoken:\t"+hit_lines[x]
    if True:
        comments = []
        if hit_comment:
            comments = get_comments_dict(hit_comment)
        tokens = get_tokens_dict(hit)

        sentence_dict = {"TOKENS":tokens,"COMMENTS":comments}

        print json.dumps(sentence_dict)
    else:
        print >> sys.stderr, json.dumps(get_tokens_dict(hit))
        print >> sys.stderr, hit

        if hit_comment:
            print hit_comment
        print hit
        print

def get_comments_dict(comments_text):
    comments = []
    for line in comments_text.split("\n"):
        if line.startswith("#"):
            comments.append(line[1:])

    return comments

def get_tokens_dict(conllu_tokens_text):
    tokens = []
    print >> sys.stderr, conllu_tokens_text.split("\n")

    for line in conllu_tokens_text.split("\n"):
        columns = line.split("\t")
        tokens.append({"ID":columns[0],
                       "FORM":columns[1],
                       "LEMMA":columns[2],
                       "UPOSTAG":columns[3],
                       "XPOSTAG":columns[4],
                       "FEATS":columns[5],
                       "HEAD":columns[6],
                       "DEPREL":columns[7],
                       "DEPS":columns[8],
                       "MISC":columns[9]})
    return tokens





def get_tokens_and_comments_json(src):
    lines = remove_added_comments(src)
    sentences = []
    
    sentence_dict = {}
    sentence_dict["COMMENTS"] = []
    sentence_dict["TOKENS"] = []

    for line in lines:
        if line==u"":
            
            sentences.append({"TOKENS":json.dumps(sentence_dict["TOKENS"]),
                              "COMMENTS":json.dumps(sentence_dict["COMMENTS"])})

            sentence_dict = {}
            sentence_dict["COMMENTS"] = []
            sentence_dict["TOKENS"] = []

        elif line.startswith(u"#"):
            sentence_dict["COMMENTS"].append(line[1:])

        else:
            columns = line.split("\t")
            sentence_dict["TOKENS"].append({"ID":columns[0],
                                            "FORM":columns[1],
                                            "LEMMA":columns[2],
                                            "UPOSTAG":columns[3],
                                            "XPOSTAG":columns[4],
                                            "FEATS":columns[5],
                                            "HEAD":columns[6],
                                            "DEPREL":columns[7],
                                            "DEPS":columns[8],
                                            "MISC":columns[9]})
    return sentences


def query_from_db(db_name,sql_query,sql_args,args,hit_counter):
    old_hit_counter=hit_counter
    db=db_util.DB()
    db.open_db(unicode(db_name))
    res_db=sqlite3.connect(unicode(db_name))
    db.exec_query(sql_query,sql_args)
    print >> sys.stderr, sql_query, sql_args
    sql_counter=0
    current_idx=None
    current_set=set()
    while True:
        idx,r,rows=query_obj.next_result(db)
        sql_counter+=rows
        if r==None:
            if current_set:
                print_sent(current_set,current_idx,res_db,args)
                hit_counter+=1
            break

        if not CLEAN:
            print "# db-name:",db_name
            print "# graph id:",idx
        
        if idx!=current_idx and current_set: #We have a new sentence, finish the old one!
            print_sent(current_set,current_idx,res_db,args)
            current_set=set()
            hit_counter+=1
        current_idx=idx
        for x in r:
            current_set.add(x)

    print >> sys.stderr, sql_counter,"rows from database",db_name
    print >> sys.stderr, hit_counter-old_hit_counter, "hits in", db_name
    db.close_db()
    res_db.close()
    return hit_counter
    
def main(argv):
    global query_obj

    parser = argparse.ArgumentParser(description='Get a sentence by id from db')
    parser.add_argument('sentence', nargs=1, help='The sentence id')
    parser.add_argument('-d', '--database', nargs=1, help='Single database or a wildcard of databases to query.')
    parser.add_argument('--dblist', nargs='+', help='A list of databases to query. Note that this argument must be passed as the last to avoid the query term being interpreted as a database name.')
    parser.add_argument('sentence', nargs=1, help='The sentence id')

    args = parser.parse_args(argv)
    print >> sys.stderr, args.sentence[0]
    print >> sys.stderr, type(args.sentence[0])
    sql_args = [unicode(args.sentence[0])]
    total_hits = 0
    dbs = []
    query_term = "NOUN"
    sql_query = u'''
    SELECT graph.graph_id, graph.token_count, t_0.token_set
    FROM graph
    JOIN tag_index AS t_0 ON graph.graph_id=t_0.graph_id
    WHERE graph.graph_id = ?
    GROUP BY graph.graph_id
    '''

    if args.database:
        dbs=glob.glob(args.database[0])
        dbs.sort()
    elif args.dblist:
        dbs=args.dblist
    else:
        print >> sys.stderr, "No database given"
        raise

    if os.path.exists(query_term+".pyx"):
        print >> sys.stderr, "Loading "+query_term+".pyx"
        mod=load(query_term)
    else:
        path = '/'.join(dbs[0].split('/')[:-1])
        json_filename = path + '/symbols.json' 
        #This is a query, compile first
        import pseudocode_ob_3 as pseudocode_ob

        import hashlib
        m = hashlib.md5()
        m.update(query_term)
        m.update(json_filename) #the json filename is part of the hash
        m.update(str(False)) #the case-sensitivity is also a part of the hash

        #1. Check if the queries folder has the search
        #2. If not, generate it here and move to the new folder
        try:
            os.mkdir(query_folder)
        except:
            pass

        temp_file_name = 'qry_' + m.hexdigest() + '.pyx'
        if not os.path.isfile(query_folder + temp_file_name):
            f = open('qry_' + m.hexdigest() + '.pyx', 'wt')
            try:
                pseudocode_ob.generate_and_write_search_code_from_expression(query_term, f, json_filename=json_filename)
            except redone_expr.ExpressionError as e:
                print "# Error in query"
                for line in unicode(e).splitlines():
                    print (u"# "+line).encode("utf-8")
                os.remove(temp_file_name)
                return -1
            except:
                os.remove(temp_file_name)
                raise

            mod=load(temp_file_name[:-4])
            os.rename(temp_file_name, query_folder + temp_file_name)
            os.rename(temp_file_name[:-4] + '.cpp', query_folder + temp_file_name[:-4] + '.cpp')
            os.rename(temp_file_name[:-4] + '.so', query_folder + temp_file_name[:-4] + '.so')

        else:
            os.rename(query_folder + temp_file_name, temp_file_name)
            os.rename(query_folder + temp_file_name[:-4] + '.cpp', temp_file_name[:-4] + '.cpp')
            os.rename(query_folder + temp_file_name[:-4] + '.so', temp_file_name[:-4] + '.so')

            mod=load(temp_file_name[:-4])            

            os.rename(temp_file_name, query_folder + temp_file_name)
            os.rename(temp_file_name[:-4] + '.cpp', query_folder + temp_file_name[:-4] + '.cpp')
            os.rename(temp_file_name[:-4] + '.so', query_folder + temp_file_name[:-4] + '.so')

    query_obj=mod.GeneratedSearch()


    for d in dbs:
        total_hits=query_from_db(d,sql_query,sql_args,args,total_hits)
        
if __name__=="__main__":
    sys.exit(main(sys.argv))
