# BSC JITPrefetch Middleware
Code for an OpenStack Swift Just In Time Prefetch middleware.


## Instalation

* Clone this repository (`git clone https://github.com/marsqui/jitprefetch_middleware.git`)

* Run `sudo python setup.py install` 

* Alter your proxy-server.conf to have the jitprefetch middleware `[filter:jitprefetch]` section.
```ini
[filter:jitprefetch]
use = egg:jitprefetch#jitprefetch
probthreshold = 0.75
totalseconds = 65
chainsave = /tmp/chain.p
nthreads = 5
```

* Also it is necessary to add this filter to the pipeline variable in the same proxy-server.conf file. This filter must be added after `keystoneauth` filter and before `slo`, `proxy-logging` and `proxy-server` filters.
