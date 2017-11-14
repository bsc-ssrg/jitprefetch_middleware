# BSC JITPrefetch Middleware
Code for an OpenStack Swift Just In Time Prefetch middleware.

* Please note, use only the following code in your Swift proxy server configuration for this middleware:
```ini
[filter:jitprefetch]
use = egg:bsc#jitprefetch
probthreshold = 0.75
totalseconds = 65
chainsave = /tmp/chain.p
nthreads = 5
```

* Also it is necessary to add this filter to the pipeline variable in the same files. This filter must be added after `keystoneauth` filter and before `slo`, `proxy-logging` and `proxy-server` filters.

* You also need to install the middleware first:
```sh
python setup.py install 
```
