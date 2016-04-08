# Setup file for creation of PyFormatTransformer 
# distribution
from setuptools import setup, Extension

setup(name="PyFormatTransformer",
      version = "0.5",
      description = "Scientific Data Format Transformation Framework",
      author = "James Hester",
      author_email = "jamesrhester at gmail.com",
      license = 'GPL',
      install_requires = ['PyCifRW>=4.2.1','numpy'],
      include_package_data = True,
      classifiers = [
	'Development Status :: 1',
	'Environment :: Console',
	'Intended Audience :: Developers',
	'Intended Audience :: Science/Research',
        'Operating System :: OS Independent',
	'Programming Language :: Python :: 2',
	'Topic :: Scientific/Engineering :: Bio-Informatics',
      ],
      packages = ['FormatTransformer','FormatTransformer.FormatAdapters'] 
      )
