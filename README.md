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
nthreads = 200
```
Where `probthreshold` is the minimum probability for an object to be prefetched, `totalseconds` is the maximum time difference between objects in order to be considered consecutive, `chainsave` is the location to save the chain and `nthreads` is the number of threads in the prefetch downloader pool.

* Also it is necessary to add this filter to the pipeline variable in the same proxy-server.conf file. This filter must be added after `keystoneauth` filter and before `slo`, `proxy-logging` and `proxy-server` filters.
