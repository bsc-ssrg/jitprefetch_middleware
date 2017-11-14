from setuptools import setup, find_packages

setup(name='bsc',
	version = '0.1.0',
    packages=find_packages(),
    description='Jit Prefetching filter middleware for OpenStack Swift',
    author='BSC: Marc Siquier, Ramon Nou',
    zip_safe=False,
    entry_points={
       'paste.filter_factory': ['jitprefetch = bsc.jitprefetch:filter_factory'],
    },
)
