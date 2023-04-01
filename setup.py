from setuptools import setup


setup(
    name='findliner',
    version='1.0',
    py_modules=['findliner'],
    install_requires=[
        'click',
        'pypdf',
        'reportlab'
    ],
    entry_points='''
        [console_scripts]
        findliner=findliner:cli
    '''
)