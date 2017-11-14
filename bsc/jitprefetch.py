import os
import sys
import time
import hashlib
import urllib2
import StringIO
import itertools
import threading
import eventlet
from itertools import chain
from swift.common.swob import Response, Request
from sys import argv, getsizeof, stderr
from swift.common.utils import split_path
from collections import deque, OrderedDict
from datetime import datetime as dt
from swift.common.internal_client import InternalClient
from swift.common.utils import GreenAsyncPile
from swiftclient.service import SwiftService, SwiftError


################### CONFIGURATION ###################
AUTOSAVE = 30 #autosave chain each X seconds
MAX_PREFETCHED_SIZE =  1073741824 #1Gb of prefetched objects
PREFETCH = True #Enables prefetching objects. If False it just updates the chain
DELETE_WHEN_SERVED = True #True if objects are deleted from memory after being served
WAIT_TIME_MULTIPLIER = 0.5 #wait time for download multiplier
PROXY_PATH = '/etc/swift/proxy-server.conf' #proxy configuration file
MAX_TIME_IN_MEMORY = 30 #max seconds for an object to be in memory without being downloaded


#Global Variables
acc_status= [200]
multiplier = 0.5
prefetched_objects = OrderedDict()



class Singleton(type):
    _instances = {}
    def __call__(cls, *args, **kwargs):  # @NoSelf
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class JITPrefetchMiddleware(object):

    __metaclass__ = Singleton

    def __init__(self, app, conf, jit_conf):
        self.app = app
        self.conf = jit_conf
        
        self.chain = Chain(self.conf['chainsave'], self.conf['totalseconds'], self.conf['probthreshold'])
        self.pool = GreenAsyncPile(self.conf['nthreads'])


    def __call__(self, env, start_response):
        request = Request(env)
        resp = request.get_response(self.app)
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
                    if data:
                        request.response_headers = rheaders
                        request.response_headers['X-object-prefetched'] = 'True'
                        resp.body = data
                        
        return resp(env, start_response)

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
                self.pool.spawn(Downloader(oid, acc, obj.container, obj.name, user_agent, token, obj.time_stamp.total_seconds()*multiplier).run)


def filter_factory(global_config, **local_config):

    conf = global_config.copy()
    conf.update(local_config)

    jit_conf = dict()

    jit_conf['totalseconds'] = int(conf.get('totalseconds', 60)) #allowed time diff in seconds between previous and next object
    jit_conf['chainsave'] = conf.get('chainsave', '/tmp/chain.p') #where to save the chain
    jit_conf['probthreshold'] = float(conf.get('probthreshold', '0.5')) #minimum probability to be prefetched
    jit_conf['nthreads'] = int(conf.get('nthreads', 5)) #number of threads in the download threadpool

    def factory(app):
        return JITPrefetchMiddleware(app, conf, jit_conf)
    return factory


class Downloader(object):

    def __init__(self, oid, acc, container, objname, user_agent, token, delay=0, request_tries=5):
        self.oid = oid
        self.acc = acc
        self.container = container
        self.objname = objname
        self.user_agent = user_agent
        self.token = token
        self.delay = delay
        self.request_tries = request_tries

    def run(self):
        print 'Prefetching object with InternalClient: ' + self.oid + ' after ' + str(self.delay) + ' seconds of delay.'
        eventlet.sleep(self.delay)
        start_time = dt.now()
        swift = InternalClient(PROXY_PATH, self.user_agent, request_tries=self.request_tries)
        headers = {}
        headers['X-Auth-Token'] = self.token
        headers['X-No-Prefetch'] = 'True'
        status, head, it = swift.get_object(self.acc, self.container, self.objname, headers, acc_status)
        data = [el for el in it]
        end_time = dt.now()
        diff = end_time - start_time
        self.log_results(self.oid, data, head, end_time, diff)


    def log_results(self, oid, data, headers, ts, diff):
        if data:
            while total_size(prefetched_objects) > MAX_PREFETCHED_SIZE:
                print "MAX PREFETCHED SIZE: Deleting objects..."
                prefetched_objects.popitem(last=True)
            prefetched_objects[oid] = (data, headers, ts)
            print "Object " + oid + " downloaded in " + str(diff.total_seconds()) + " seconds."


class ChainObject():

    def __init__(self, id, name, container, ts):
        self.object_id = id
        self.object_name = name
        self.object_container = container
        self.hits = 1
        self.time_stamp = ''
        self.set_ts(ts)

    def object_to_string(self):
        return "ID:" + self.object_id + " HITS:" + str(self.hits) + " TS:" + str(self.time_stamp.total_seconds())

    def get_object_name(self):
        return self.object_container + " " + self.object_name

    def hit(self):
        self.hits += 1  

    def set_ts(self, ts):
        if not self.time_stamp:
            self.time_stamp = ts
        elif ts.total_seconds() < self.time_stamp.total_seconds():
                self.time_stamp = ts

    def id(self):
        return self.object_id

class ProbObject():
    def __init__(self, container, name, prob, ts=0):
        self.container = container
        self.name = name
        self.probability = prob
        self.time_stamp = ts

    def object_to_string(self):
        return "CONTAINER: " + self.container + " NAME: " + self.name + " P: " + str(self.probability)


class Chain():

    def __init__(self, chainsave='/tmp/chain.p', maxseconds=60, prth=0.5): 
        self._chain = {}
        self._chainsave = chainsave
        self._maxseconds = maxseconds
        self._prth = prth
        self._last_oid = None
        self._last_ts = None
        self.load_chain()

    def __del__(self):
        with open(self._chainsave, 'wb') as fp:
            pickle.dump(self._chain, fp)

    def load_chain(self):
        try:
            with open(self._chainsave, 'rb') as fp:
                self._chain = pickle.load(fp)
        except: 
            pass

    def save_chain(self):
        with open(self._chainsave, 'wb') as fp:
            pickle.dump(self._chain, fp)

    def auto_save(self, timer=30):
        self.save_chain()
        threading.Timer(timer, self.auto_save, [timer]).start()
        

    def _get_object_chain(self, oid):
        if oid in self._chain:
            return sorted(self._chain[oid], key=lambda x: x.hits, reverse=True)
        return []

    def _set_object_chain(self, oid, objs_list):
        self._chain[oid] = objs_list

    def add(self, oid, name, container):
        if oid not in self._chain:
            self._chain[oid] = []
    
        diff = self._check_time_diff()
        if diff:
            objs = self._get_object_chain(self._last_oid)
            found = False
            for o in filter(lambda x: x.id()==oid, objs):
                o.hit()
                o.set_ts(diff)
                found = True
            if not found:
                objs.append(ChainObject(oid, name, container, diff))
            self._set_object_chain(self._last_oid, objs)
        self._last_oid = oid
        self._last_ts = dt.now()

    def _check_time_diff(self):
        if self._last_ts:
            diff = dt.now() - self._last_ts
            if diff.total_seconds() < self._maxseconds:
                return diff

    def chain_stats(self):
        self.chain_length()
        for o in self._chain:
            print "\tOBJECT: " + o
            for och in self._chain[o]:
                print "\t\tnext: " + och.object_to_string()

    def chain_length(self):
        print "Chain length: " + str(len(self._chain))

    def get_probabilities(self, oid):
        probs1 = self._probabilities(self._get_object_chain(oid))
        probs2 = dict()
        for oi in probs1:
            pr = self._probabilities(self._get_object_chain(oi))
            pr = {k: ProbObject(v.container, v.name, v.probability*probs1[oi].probability, v.time_stamp) for k, v in pr.items()}
            probs2.update(pr)
        for oi in probs2:
            if oi in probs1:
                probs1[oi].probability += probs2[oi].probability
            else:
                probs1[oi] = probs2[oi]
        objs =  filter(lambda (a,b): b.probability>self._prth, probs1.iteritems())
        return sorted(objs, key=lambda (a,b): b.probability, reverse=True)

    def _probabilities(self, chain):
        total_hits = sum(o.hits for o in chain)
        return {o.id(): ProbObject(o.object_container, o.object_name, o.hits/float(total_hits), o.time_stamp) for o in chain}
 

def total_size(o, handlers={}):
    """ Returns the approximate memory footprint an object and all of its contents.
    """
    dict_handler = lambda d: chain.from_iterable(d.items())
    all_handlers = {tuple: iter,
                    list: iter,
                    deque: iter,
                    dict: dict_handler,
                    set: iter,
                    frozenset: iter,
                   }
    all_handlers.update(handlers)     # user handlers take precedence
    seen = set()                      # track which object id's have already been seen
    default_size = getsizeof(0)       # estimate sizeof object without __sizeof__

    def sizeof(o):
        if id(o) in seen:       # do not double count the same object
            return 0
        seen.add(id(o))
        s = getsizeof(o, default_size)
       
        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)


class FilterIter(object):
    def __init__(self, obj_data, timeout):
        self.closed = False
        self.obj_data = obj_data
        self.timeout = timeout
        self.buf = b''



    def __iter__(self):
        return self

    def read_with_timeout(self, size):
        try:
            with Timeout(self.timeout):
                if hasattr(self.obj_data, 'read'):
                    chunk = self.obj_data.read(size)
                else:
                    chunk = self.obj_data.next()

        except Timeout:
            self.close()
            raise
        except Exception:
            self.close()
            raise

        return chunk

    def next(self, size=64 * 1024):
        if len(self.buf) < size:
            self.buf += self.read_with_timeout(size - len(self.buf))
            if self.buf == b'':
                self.close()
                raise StopIteration('Stopped iterator ex')

        if len(self.buf) > size:
            data = self.buf[:size]
            self.buf = self.buf[size:]
        else:
            data = self.buf
            self.buf = b''
        return data

    def _close_check(self):
        if self.closed:
            raise ValueError('I/O operation on closed file')

    def read(self, size=64 * 1024):
        self._close_check()
        return self.next(size)

    def readline(self, size=-1):
        self._close_check()

        # read data into self.buf if there is not enough data
        while b'\n' not in self.buf and \
              (size < 0 or len(self.buf) < size):
            if size < 0:
                chunk = self.read()
            else:
                chunk = self.read(size - len(self.buf))
            if not chunk:
                break
            self.buf += chunk

        # Retrieve one line from buf
        data, sep, rest = self.buf.partition(b'\n')
        data += sep
        self.buf = rest

        # cut out size from retrieved line
        if size >= 0 and len(data) > size:
            self.buf = data[size:] + self.buf
            data = data[:size]

        return data

    def readlines(self, sizehint=-1):
        self._close_check()
        lines = []
        try:
            while True:
                line = self.readline(sizehint)
                if not line:
                    break
                lines.append(line)
                if sizehint >= 0:
                    sizehint -= len(line)
                    if sizehint <= 0:
                        break
        except StopIteration:
            pass
        return lines

    def close(self):
        if self.closed:
            return
        try:
            self.obj_data.close()
        except AttributeError:
            pass
        self.closed = True

    def __del__(self):
        self.close()
