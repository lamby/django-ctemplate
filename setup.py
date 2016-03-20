from setuptools import setup

setup(
    name='django-ctemplate',
    version='2.0.2',
    packages=(
        'ctemplate',
    ),
    url='https://chris-lamb.co.uk/projects/django-ctemplate',
    author="Chris Lamb",
    author_email="chris@chris-lamb.co.uk",
    description="Compile Django templates to C",

    install_requires=(
        'Django>=1.8',
    ),
)
