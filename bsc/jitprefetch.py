import StringIO

from swift.common import wsgi
from swift.common.swob import wsgify
from swift.common.utils import split_path


class JITPrefetchMiddleware(object):
    def __init__(self, app, *args, **kwargs):
        self.app = app
      
    @wsgify
    def __call__(self, request):
        try:
            (version, account, container, objname) = split_path(request.path_info, 4, 4, True)
        except ValueError:
            return self.app

        preview_path = '/%s/%s/%s/%s' % (version, account, container, objname)

        if request.method == 'GET':
            print "hola mundo"
       


        if request.method == 'DELETE':
            sub = wsgi.make_subrequest(request.environ, path=preview_path)
            sub.get_response(self.app)

        return self.app

def filter_factory(global_config, **local_config):
    def factory(app):
        return JITPrefetchMiddleware(app)
    return factory
