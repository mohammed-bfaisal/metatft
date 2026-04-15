from setuptools import setup, find_packages

setup(
    name="metatft",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "rich>=13.7.1",
        "questionary>=2.0.1",
        "prompt_toolkit>=3.0.36",
        "wcwidth>=0.2.13",
    ],
    entry_points={"console_scripts": ["metatft=metatft.cli:main"]},
)
