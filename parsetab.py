
# parsetab.py
# This file is automatically generated. Do not edit.
_tabversion = '3.2'

_lr_method = 'LALR'

_lr_signature = '\x04\xb6\xcb\xbe\ni\x02?\xb9\xf7\xd6\xfa\x18?\x0f\xfc'
    
_lr_action_items = {u'AND':([6,7,8,9,15,17,20,22,27,29,31,35,36,38,39,40,41,],[-14,-13,24,-15,-12,30,-10,-24,30,-23,24,-8,-17,24,-9,-16,30,]),u'LPAR':([0,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,28,29,30,31,32,33,34,35,36,37,38,39,40,41,],[3,12,3,3,3,-14,-13,-11,-15,-6,-3,12,-5,3,-12,12,3,3,3,-10,12,-24,-2,3,3,3,-19,-23,12,-7,12,-20,-21,-8,-17,-4,-18,-9,-16,-22,]),u'OR':([6,7,8,9,15,17,20,22,27,29,31,35,36,38,39,40,41,],[-14,-13,26,-15,-12,32,-10,-24,32,-23,26,-8,-17,-18,-9,-16,-22,]),u'WORD':([0,3,4,5,14,15,17,18,19,20,24,25,26,29,39,40,41,],[7,7,7,7,7,-12,7,7,7,-10,7,7,7,-23,-9,-16,-22,]),u'ECOM':([2,6,7,8,9,10,11,13,21,22,23,28,31,33,34,35,36,37,38,],[13,-14,-13,-11,-15,-6,-3,-5,13,-24,-2,13,-7,13,13,-8,-17,-4,-18,]),u'TEXT':([0,3,4,5,14,15,17,18,19,20,24,25,26,29,39,40,41,],[6,6,6,6,6,-12,6,6,6,-10,6,6,6,-23,-9,-16,-22,]),u'BGN':([0,3,5,14,18,19,25,],[5,5,5,5,5,5,5,]),u'RPAR':([6,7,8,9,10,11,13,15,20,21,22,23,27,28,29,31,33,34,35,36,37,38,39,40,41,],[-14,-13,-11,-15,-6,-3,-5,-12,-10,35,-24,-2,39,-19,-23,-7,-20,-21,-8,-17,-4,-18,-9,-16,-22,]),u'XDOT':([6,7,8,9,22,35,36,38,],[-14,-13,25,-15,-24,-8,-17,-18,]),u'PLUS':([2,6,7,8,9,10,11,13,21,22,23,28,31,33,34,35,36,37,38,],[14,-14,-13,-11,-15,-6,-3,-5,14,-24,-2,-19,-7,-20,-21,-8,-17,-4,-18,]),u'NEG':([0,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,28,29,30,31,32,33,34,35,36,37,38,39,40,41,],[4,16,4,4,4,-14,-13,-11,-15,-6,-3,16,-5,4,-12,16,4,4,4,-10,16,-24,-2,4,4,4,16,-23,16,-7,16,16,16,-8,-17,-4,-18,-9,-16,-22,]),u'END':([2,6,7,8,9,10,11,13,21,22,23,28,31,33,34,35,36,37,38,],[11,-14,-13,-11,-15,-6,-3,-5,11,-24,11,11,-7,11,11,-8,-17,11,-18,]),u'DEPOP':([2,6,7,8,9,10,11,12,13,16,21,22,23,28,30,31,32,33,34,35,36,37,38,],[20,-14,-13,-11,-15,-6,-3,20,-5,20,20,-24,-2,20,20,-7,20,20,20,-8,-17,-4,-18,]),u'EQ':([2,6,7,8,9,10,11,13,21,22,23,28,31,33,34,35,36,37,38,],[18,-14,-13,-11,-15,-6,-3,-5,18,-24,-2,18,-7,-20,-21,-8,-17,-4,-18,]),u'ANYTOKEN':([0,3,4,5,14,15,17,18,19,20,24,25,26,29,39,40,41,],[9,9,9,9,9,-12,9,9,9,-10,9,9,9,-23,-9,-16,-22,]),u'SE':([2,6,7,8,9,10,11,13,21,22,23,28,31,33,34,35,36,37,38,],[19,-14,-13,-11,-15,-6,-3,-5,19,-24,-2,19,-7,19,-21,-8,-17,-4,-18,]),'$end':([1,2,6,7,8,9,10,11,13,22,23,28,31,33,34,35,36,37,38,],[0,-1,-14,-13,-11,-15,-6,-3,-5,-24,-2,-19,-7,-20,-21,-8,-17,-4,-18,]),}

_lr_action = { }
for _k, _v in _lr_action_items.items():
   for _x,_y in zip(_v[0],_v[1]):
      if not _x in _lr_action:  _lr_action[_x] = { }
      _lr_action[_x][_k] = _y
del _lr_action_items

_lr_goto_items = {u'depres':([2,21,23,28,33,34,37,],[10,10,10,10,10,10,10,]),u'search':([0,],[1,]),u'setnode':([0,3,5,14,18,19,25,],[2,21,23,28,33,34,37,]),u'depnode':([2,12,21,23,28,30,32,33,34,37,],[17,27,17,17,17,40,41,17,17,17,]),u'tokendef':([0,3,4,5,14,17,18,19,24,25,26,],[8,8,22,8,8,31,8,8,36,8,38,]),u'depdef':([2,12,16,21,23,28,30,32,33,34,37,],[15,15,29,15,15,15,15,15,15,15,15,]),}

_lr_goto = { }
for _k, _v in _lr_goto_items.items():
   for _x,_y in zip(_v[0],_v[1]):
       if not _x in _lr_goto: _lr_goto[_x] = { }
       _lr_goto[_x][_k] = _y
del _lr_goto_items
_lr_productions = [
  ("S' -> search","S'",1,None,None,None),
  (u'search -> setnode',u'search',1,'p_top','/home/daniel/Repositorios/dep_search/redone_expr.py',327),
  (u'setnode -> BGN setnode',u'setnode',2,'p_bgn','/home/daniel/Repositorios/dep_search/redone_expr.py',336),
  (u'setnode -> setnode END',u'setnode',2,'p_end','/home/daniel/Repositorios/dep_search/redone_expr.py',341),
  (u'setnode -> tokendef XDOT setnode',u'setnode',3,'p_dot','/home/daniel/Repositorios/dep_search/redone_expr.py',345),
  (u'setnode -> setnode ECOM',u'setnode',2,'p_ecomxpr','/home/daniel/Repositorios/dep_search/redone_expr.py',349),
  (u'setnode -> setnode depres',u'setnode',2,'p_expr2','/home/daniel/Repositorios/dep_search/redone_expr.py',354),
  (u'depres -> depnode tokendef',u'depres',2,'p_sn_depres_a','/home/daniel/Repositorios/dep_search/redone_expr.py',362),
  (u'tokendef -> LPAR setnode RPAR',u'tokendef',3,'p_exprp','/home/daniel/Repositorios/dep_search/redone_expr.py',366),
  (u'depdef -> LPAR depnode RPAR',u'depdef',3,'p_exprp_d','/home/daniel/Repositorios/dep_search/redone_expr.py',375),
  (u'depdef -> DEPOP',u'depdef',1,'p_exprp_d','/home/daniel/Repositorios/dep_search/redone_expr.py',376),
  (u'setnode -> tokendef',u'setnode',1,'p_exprp2','/home/daniel/Repositorios/dep_search/redone_expr.py',383),
  (u'depnode -> depdef',u'depnode',1,'p_exprp5','/home/daniel/Repositorios/dep_search/redone_expr.py',390),
  (u'tokendef -> WORD',u'tokendef',1,'p_exprp3','/home/daniel/Repositorios/dep_search/redone_expr.py',394),
  (u'tokendef -> TEXT',u'tokendef',1,'p_exprp3','/home/daniel/Repositorios/dep_search/redone_expr.py',395),
  (u'tokendef -> ANYTOKEN',u'tokendef',1,'p_exprp3','/home/daniel/Repositorios/dep_search/redone_expr.py',396),
  (u'depnode -> depnode AND depnode',u'depnode',3,'p_dn_and','/home/daniel/Repositorios/dep_search/redone_expr.py',408),
  (u'tokendef -> tokendef AND tokendef',u'tokendef',3,'p_sn_and','/home/daniel/Repositorios/dep_search/redone_expr.py',415),
  (u'tokendef -> tokendef OR tokendef',u'tokendef',3,'p_sn_or','/home/daniel/Repositorios/dep_search/redone_expr.py',419),
  (u'setnode -> setnode PLUS setnode',u'setnode',3,'p_sn_plus','/home/daniel/Repositorios/dep_search/redone_expr.py',423),
  (u'setnode -> setnode EQ setnode',u'setnode',3,'p_sn_eq','/home/daniel/Repositorios/dep_search/redone_expr.py',427),
  (u'setnode -> setnode SE setnode',u'setnode',3,'p_sn_seq','/home/daniel/Repositorios/dep_search/redone_expr.py',431),
  (u'depnode -> depnode OR depnode',u'depnode',3,'p_dn_or','/home/daniel/Repositorios/dep_search/redone_expr.py',435),
  (u'depdef -> NEG depdef',u'depdef',2,'p_dn_not','/home/daniel/Repositorios/dep_search/redone_expr.py',442),
  (u'tokendef -> NEG tokendef',u'tokendef',2,'p_sn_not','/home/daniel/Repositorios/dep_search/redone_expr.py',446),
]
