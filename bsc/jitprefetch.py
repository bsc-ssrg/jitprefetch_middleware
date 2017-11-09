import os
import sys
import time
import hashlib
import urllib2
import StringIO
import itertools
import threading
import multiprocessing
import cPickle as pickle
import multiprocessing.pool
from utils import Singleton
from itertools import chain
from swift.common import wsgi
from datetime import datetime as dt
from swift.common.swob import wsgify
from swift.common.swob import Response
from sys import argv, getsizeof, stderr
from swift.common.utils import split_path
from collections import deque, OrderedDict
from swift.common.internal_client import InternalClient
from swiftclient.service import SwiftService, SwiftError


################### CONFIGURATION ###################
TOTALSECONDS = 60 #allowed time diff in seconds between previous and next object
PROB_THRESHOLD = 0.5 #minimum probability to be prefetched
N_THREADS = 5 #number of threads in the download threadpool
AUTOSAVE = 30 #autosave chain each X seconds
MAX_PREFETCHED_SIZE =  1073741824 #1Gb of prefetched objects
PREFETCH = True #Enables prefetching objects. If False it just updates the chain
DELETE_WHEN_SERVED = True #True if objects are deleted from memory after being served
CHAINSAVE = '/tmp/chain.p' #where to save the chain
WAIT_TIME_MULTIPLIER = 0.5 #wait time for download multiplier
PROXY_PATH = '/etc/swift/proxy-server.conf' #proxy configuration file
MAX_TIME_IN_MEMORY = 30 #max seconds for an object to be in memory without being downloaded


#Global Variables
acc_status= [200]
multiplier = 0.5
prefetched_objects = OrderedDict()



class JITPrefetchMiddleware(object):

    __metaclass__ = Singleton

    def __init__(self, app, *args, **kwargs):
        self.app = app
        self.th = float(kwargs.get('probthreshold', '0.5'))
      
    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, objname) = split_path(request.path_info, 4, 4, True)
        except ValueError:
            return self.app

        if request.method == 'GET':
            print "hola mundo " + str(self.th)
       


        if request.method == 'DELETE':
            sub = wsgi.make_subrequest(request.environ, path=preview_path)
            sub.get_response(self.app)

        return self.app

def filter_factory(global_config, **local_config):
    probthreshold = local_config.get('probthreshold')
    def factory(app):
        return JITPrefetchMiddleware(app, probthreshold=probthreshold)
    return factory
