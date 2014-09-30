from setuptools import setup, find_packages

version = '0.1'

setup(name='ham',
      version=version,
      description="launch monkies into the cloud",
      long_description="""\
http://en.wikipedia.org/wiki/Ham_the_Chimp""",
      classifiers=[],
      keywords='',
      author='clayg',
      author_email='clay.gerrard@gmail.com',
      url='clayg.info',
      license='',
      packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          "python-novaclient",
          "fabric",
      ],
      entry_points={
          'console_scripts': [
              'ham = ham.main:main'
          ]
      },
      )
