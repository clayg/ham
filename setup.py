from setuptools import setup, find_packages
import sys, os

version = '0.0'

setup(name='ham',
      version=version,
      description="launch monkies into the cloud",
      long_description="""\
http://en.wikipedia.org/wiki/Ham_the_Chimp""",
      classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      keywords='',
      author='clayg',
      author_email='clay.gerrard@gmail.com',
      url='clayg.info',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          # -*- Extra requirements: -*-
          "python-novaclient",
          "fabric",
      ],
      entry_points={
          'console_scripts': [
              'ham = ham.main:main'
          ]
      },
      )
