import os
import re

from setuptools import find_packages, setup

HERE = os.path.abspath(os.path.dirname(__file__))


def read_version():
    """Read __version__ out of the package without importing it.

    Importing would pull in Django, which is not installed yet when pip is
    resolving this file.
    """
    with open(os.path.join(HERE, "django_startr", "__init__.py")) as handle:
        match = re.search(r'^__version__ = "([^"]+)"', handle.read(), re.M)
    if not match:
        raise RuntimeError("django_startr/__init__.py has no __version__")
    return match.group(1)


with open(os.path.join(HERE, "README.md")) as readme:
    README = readme.read()

setup(
    name="django-startr",
    version=read_version(),
    # find_packages, not a hand-listed ['django_startr']. The hand-listed form
    # silently dropped management/, management/commands/ and templatetags/, so
    # an installed copy had no `startr` command at all.
    packages=find_packages(include=["django_startr", "django_startr.*"]),
    include_package_data=True,
    license="BSD License",
    description=(
        "Management command that generates views, forms, urls, admin, and "
        "templates for models"
    ),
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/Startr/STARTR-django-code",
    author="Alexander Somma",
    author_email="asomma@startr.ca",
    python_requires=">=3.9",
    install_requires=["Django>=4.2", "Jinja2>=3.1"],
    classifiers=[
        "Environment :: Web Environment",
        "Framework :: Django",
        "Framework :: Django :: 4.2",
        "Framework :: Django :: 5.0",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    keywords="generator generates django scaffold crud",
)
