import setuptools
import codecs
import os.path

with open("README.md", "r") as fh:
    long_description = fh.read()


# https://packaging.python.org/guides/single-sourcing-package-version/
def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError("Unable to find version string.")


setuptools.setup(
    name="memd_api",
    version=get_version("memd_api/__init__.py"),
    author="Craig Welton",
    description="Python Client for MEMD API",
    install_requires=[
        'requests==2.26.0',
        'jsonschema==4.3.1',
        'click>=8.0.1',
        'names==0.3.0'
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cswelton/flask_app",
    entry_points={
        "console_scripts": [
            "memd-api=memd_api.command_line:cli"
        ]
    },
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    license='MIT',
    include_package_data=True,
    test_suite='nose.collector',
    tests_require=['nose'],
    zip_safe=False)
