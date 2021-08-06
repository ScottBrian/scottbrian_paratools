#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jul 12 2021

@author: Scott Tuttle
"""
import setuptools
if __name__ == "__main__":
    setuptools.setup()

# from pathlib import Path
# from setuptools import setup, find_packages
#
# with open('README.rst', 'r') as readme:
#     long_description = readme.read()
#
#
# def get_version(rel_path):
#     target_path = Path(__file__).resolve().parent.joinpath(rel_path)
#     with open(target_path, 'r') as file:
#         for line in file:
#             if line.startswith('__version__'):
#                 delimiter = '"' if '"' in line else "'"
#                 return line.split(delimiter)[1]
#         else:
#             raise RuntimeError("Unable to find version string.")
#
#
# setup(
#       name='scottbrian_paratools',
#       version=get_version('src/scottbrian_paratools/__init__.py'),
#       author='Scott Tuttle',
#       description='Parallel processing tools',
#       long_description=long_description,
#       long_description_content_type='text/x-rst',
#       url='https://github.com/ScottBrian/scottbrian_paratools.git',
#       license='MIT',
#       classifiers=[
#           'License :: OSI Approved :: MIT License',
#           'Development Status :: 5 - Production/Stable',
#           'Intended Audience :: Developers',
#           'Topic :: Software Development :: Libraries :: Python Modules',
#           'Topic :: System :: Recovery Tools',
#           'Topic :: Utilities',
#           'Programming Language :: Python :: 3',
#           'Programming Language :: Python :: 3.9',
#           'Operating System :: POSIX :: Linux'
#                   ],
#       project_urls={
#           'Documentation': 'https://scottbrian-paratools.readthedocs.io/en'
#                            '/latest/',
#           'Source': 'https://github.com/ScottBrian/scottbrian_paratools.git'},
#       python_requires='>=3.9',
#       packages=find_packages('src'),
#       package_dir={'': 'src'},
#       install_requires=['typing-extensions', 'scottbrian-utils'],
#       package_data={"scottbrian_paratools": ["__init__.pyi", "py.typed"]},
#       zip_safe=False
#      )
