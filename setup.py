from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in erpnext_agencik/__init__.py
from erpnext_agencik import __version__ as version

setup(
    name="erpnext_agencik",
    version=version,
    description="Agencik for ERPNext",
    author="Jan",
    author_email="your@email.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
