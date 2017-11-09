from setuptools import setup

setup(name='bsc',
    packages=['bsc', ],
    zip_safe=False,
    entry_points={
       'paste.filter_factory': ['jitprefetch = bsc.jitprefetch:filter_factory'],
    },
)
