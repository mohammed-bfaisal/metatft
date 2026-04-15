from setuptools import setup, find_packages
setup(
    name="metatft",
    version="1.0.0",
    packages=find_packages(),
    install_requires=["rich>=13.0", "questionary>=2.0"],
    entry_points={"console_scripts": ["metatft=metatft.cli:main"]},
)
