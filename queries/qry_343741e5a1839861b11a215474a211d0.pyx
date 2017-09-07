# distutils: language = c++
# distutils: include_dirs = setlib
# distutils: extra_objects = setlib/pytset.so
# distutils: sources = query_functions.cpp
include "search_common.pxi"
cdef class  GeneratedSearch(Search):
    cdef TSet *node_0_set_1
    cdef TSet *node_0_out
    cdef TSet *empty_set
    cdef public object query_fields
    def __cinit__(self):
        self.sets=<void**>malloc(1*sizeof(void*))
        self.set_types=<int*>malloc(1*sizeof(int))
        self.empty_set = new TSet(2048)
        self.node_0_out = new TSet(2048)
        self.set_types[0] = 1
        self.node_0_set_1= new TSet(2048)
        self.sets[0] = self.node_0_set_1
        self.query_fields = [u'!tag_s_NOUN']
    cdef void initialize(self):
        self.empty_set.set_length(self.node_0_set_1.tree_length)
        self.node_0_out.set_length(self.node_0_set_1.tree_length)
        self.node_0_out.copy(self.empty_set)
    cdef TSet* exec_search(self):
        #0
        #SetNode(Token:@CGTAGNOUN)[]
        self.node_0_out.copy(self.node_0_set_1)
        #Reporting node_0_out as output set
        return self.node_0_out
