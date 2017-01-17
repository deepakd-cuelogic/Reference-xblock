from setuptools import setup

setup(
    name='xblock-reference-explorer',
    version='0.1',
    description='ReferenceInfoBlock XBlock Tutorial Sample',
    py_modules=['referenceblock'],
    install_requires=['XBlock', 'requests'],
    entry_points={
        'xblock.v1': [
            'referenceblock = referenceblock:ReferenceInfoBlock',
        ]
    }
)
