from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in shree_polymer_custom_app/__init__.py
from shree_polymer_custom_app import __version__ as version

setup(
	name="shree_polymer_custom_app",
	version=version,
	description="Shree Polymer Custom App",
	author="Tridotstech",
	author_email="info@tridotstech.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
