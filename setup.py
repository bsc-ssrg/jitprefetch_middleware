from setuptools import setup

setup(name='bsc',
    packages=['bsc', ],
    zip_safe=False,
    entry_points={
       'paste.filter_factory': ['middleware = bsc.jitprefetch:filter_factory'],
    },
)
