# distutils: language = c++
# distutils: include_dirs = setlib
# distutils: extra_objects = setlib/pytset.so
# distutils: sources = query_functions.cpp
include "search_common.pxi"
cdef class  GeneratedSearch(Search):
    cdef TSetArray *extra_array
    cdef TSet *node_0_all_tokens_1
    cdef TSet *empty_set
    cdef public object query_fields
    def __cinit__(self):
        self.sets=<void**>malloc(1*sizeof(void*))
        self.set_types=<int*>malloc(1*sizeof(int))
        self.empty_set = new TSet(2048)
        self.node_0_all_tokens_1 = new TSet(2048)
        self.set_types[0] = 2
        self.extra_array = new TSetArray(2048)
        self.sets[0] = self.extra_array
        self.query_fields = [u'!dep_a_anyrel']
    cdef void initialize(self):
        self.empty_set.set_length(self.extra_array.tree_length)
        self.node_0_all_tokens_1.set_length(self.extra_array.tree_length)
        self.node_0_all_tokens_1.fill_ones()
    cdef TSet* exec_search(self):
        #0
        #SetNode(Token:_)[]
        #Reporting node_0_all_tokens_1 as output set
        return self.node_0_all_tokens_1
