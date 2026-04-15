from setuptools import find_packages, setup

setup(
    name='metatft',
    version='3.1.0',
    packages=find_packages(),
    install_requires=[
        'rich>=13.7.1',
        'questionary>=2.0.1',
        'prompt_toolkit>=3.0.36',
        'wcwidth>=0.2.13',
    ],
    entry_points={'console_scripts': ['metatft=metatft.__main__:run']},
)
