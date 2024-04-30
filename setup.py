from setuptools import setup


setup(
    name='findliner',
    version='1.0.1',
    py_modules=['findliner'],
    install_requires=[
        'click==8.1.7',
        'pypdf==3.10.0',
        'reportlab==4.2.0'
    ],
    entry_points='''
        [console_scripts]
        findliner=findliner:cli
    '''
)
