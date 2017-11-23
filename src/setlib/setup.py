from distutils.core import setup
from Cython.Build import cythonize

setup(ext_modules = cythonize(
           "pytset.pyx",                 # our Cython source
           ["tset.cpp"],  # additional source file(s)
           "c++",             # generate C++ code
      ))

