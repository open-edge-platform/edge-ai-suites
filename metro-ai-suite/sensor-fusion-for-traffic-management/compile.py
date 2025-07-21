from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
ext_modules = [
    Extension("esb_install",  ["tfcc_esc_install.py"]),
]
setup(
    name = "tfcc_esc_install",
    cmdclass = {'build_ext': build_ext},
    ext_modules = ext_modules
)