Description
===========

Launch (mostly trained) monkeys into the cloud

Long Description
================

Sometimes all you really want is to launch a bunch of trained monkeys
into the cloud.

Ham was the name of the first chimp NASA sent into space:
http://en.wikipedia.org/wiki/Ham_the_Chimp

"ham" is a command line tool for launching a one or more cloud servers on
an OpenStack cloud, running a bit of bash, and capturing the result.

INSTALLATION AND DEPENDENCIES
=============================

ham depends on novaclient and fabric

 1. python setup.py develop  # cruse pbr
 1. python setup.py develop  # will install dependencies

AUTHENTICATION
==============

Houston, do you read?

Authentication is handled by ENVIRONMENT VARS in a novaclient compatible way.

see rackspace.rc-sample

Make sure to test novaclient (e.g. nova flavor-list).


GETTING STARTED
===============

Install ham and source your OpenStack runcom.

For your first test flight you might run something like:

    ham -d 100:SSD -n 2 example.script


