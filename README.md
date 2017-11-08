# BSC JITPrefetch Middleware
Code for an OpenStack Swift Just In Time Prefetch middleware.

Please note, use only the following code in your Swift proxy server configuration for this middleware:
```
[filter:jitprefetch]
use = bsc:#jitprefetch
```
You also need to install the middleware first:
```
python setup.py install 
```
