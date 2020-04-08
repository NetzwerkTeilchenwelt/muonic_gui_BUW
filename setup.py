"""A setuptools based setup module.

See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
# To use a consistent encoding
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='muonic_gui',

    version='1.0.0',

    description='A muonic consumer for Qt5',
    long_description=long_description,

    url='https://github.com/phyz777/muonic_gui_BUW',

    author='Jonathan Debus, Nicolas Lang',
    author_email='jdphysik@gmail.com',

    license='MIT',

    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        'Development Status :: 3 - Alpha',

        'Intended Audience :: Physicists',
        'Topic :: Science :: Astro-particle-phyics',

        'License :: OSI Approved :: MIT License',

        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    keywords='PyQt5 Qt GUI muonic muon skyview',

    packages=['muonic_gui', 'muonic_gui.analysis', 'muonic_gui.gui'],

    package_data={
      'muonic_gui': ['daq_commands_help.txt', 'gui/muonic.xpm']
    }
)
