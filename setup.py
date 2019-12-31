#!/usr/bin/env python
from setuptools import setup

setup(
    name='rpi_streamer',
    version='1.0.0',
    author='Kimmo Huoman',
    author_email='kipenroskaposti@gmail.com',
    url='https://github.com/kipe/rpi-streamer',
    packages=['rpi_streamer', 'rpi_streamer.templates'],
    package_data={
        'rpi_streamer.templates': [
            'rpi_streamer/templates/*',
        ],
    },
    install_requires=[
        'picamera==1.13',
        'Jinja2==2.10.3',
        'wheel>=0.34.2'
    ])
