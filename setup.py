from setuptools import setup, find_packages
from jitprefetch import name, version

setup(name=name,
	version = version,
    packages=find_packages(),
    description='Jit Prefetching filter middleware for OpenStack Swift',
    keywords="openstack swift middleware prefetch",
    url="https://github.com/marsqui/jitprefetch_middleware",
    author='BSC: Marc Siquier, Ramon Nou',
    entry_points={
       'paste.filter_factory': ['jitprefetch = jitprefetch.middleware:filter_factory'],
    },
)
