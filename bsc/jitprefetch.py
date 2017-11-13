import os
import sys
import time
import hashlib
import urllib2
import StringIO
import itertools
import threading
from itertools import chain
from swift.common import wsgi
from swift.common.swob import wsgify
from swift.common.swob import Response
from sys import argv, getsizeof, stderr
from swift.common.utils import split_path
from collections import deque, OrderedDict
from utils import Singleton, Chain, Downloader
from swift.common.utils import GreenAsyncPile
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
        self.th = float(kwargs.get('probthreshold', '0.5')) #minimum probability to be prefetched
        self.totalseconds = float(kwargs.get('totalseconds', '60')) #allowed time diff in seconds between previous and next object
        self.chainsave = kwargs.get('chainsave', '/tmp/chain.p') #where to save the chain
        self.nthreads = int(kwargs.get('nthreads', '5')) #number of threads in the download threadpool
        
        self.chain = Chain(self.chainsave, self.totalseconds, self.th)
        self.pool = GreenAsyncPile(self.nthreads)

    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, objname) = split_path(request.path_info, 4, 4, True)
        except ValueError:
            return self.app
        if 'HTTP_X_NO_PREFETCH' not in request.environ:
            if request.method == 'GET':
                oid = (hashlib.md5(request.path_info).hexdigest())
                self.add_object_to_chain(oid, container, objname)
                if PREFETCH:
                    data, rheaders = self.get_prefetched(oid, objname)
                    self.prefetch_objects(oid, request)



        return self.app

    def add_object_to_chain(self, oid, container, object_name):
        self.chain.add(oid, object_name, container)


      def get_prefetched(self, oid, name):
        global multiplier
        if oid in prefetched_objects:
            data, resp_headers, ts = prefetched_objects[oid]
            multiplier = multiplier + 0.05
            if multiplier > 1:
                multiplier = 1
            if DELETE_WHEN_SERVED:
                del prefetched_objects[oid]
                print 'Object '+name+' served and deleted'
            return (data, resp_headers)
        return (False, False)


        def prefetch_objects(self, oid, req_resp):
            objs = self.chain.get_probabilities(oid)
            for oid, o in objs:
                print o.object_to_string()
            token = req_resp.environ['HTTP_X_AUTH_TOKEN']
            acc = 'AUTH_' + req_resp.environ['HTTP_X_TENANT_ID']
            user_agent =  req_resp.environ['HTTP_USER_AGENT']
            path = req_resp.environ['PATH_INFO']
            server_add = req_resp.environ['REMOTE_ADDR']
            server_port = req_resp.environ['SERVER_PORT']
            
            for oid, obj in objs:
                if oid not in prefetched_objects:
                    self.pool.spawn(Downloader(5))
                    #self.pool.apply_async(download, args=(oid, acc, obj.container, obj.name, user_agent, token, obj.time_stamp.total_seconds()*multiplier, ), callback=log_result)


def filter_factory(global_config, **local_config):
    totalseconds = local_config.get('totalseconds') #allowed time diff in seconds between previous and next object
    chainsave = local_config.get('chainsave') #where to save the chain
    probthreshold = local_config.get('probthreshold') #minimum probability to be prefetched
    nthreads = local_config.get('nthreads') #number of threads in the download threadpool
    def factory(app):
        return JITPrefetchMiddleware(app, probthreshold=probthreshold, totalseconds=totalseconds,
            chainsave=chainsave, nthreads=nthreads)
    return factory
