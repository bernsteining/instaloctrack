import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="instaloctrack",  # Replace with your own username
    version="1.0.0",
    author="bernstein",
    author_email="author@example.com",
    description=
    "A Python3 tool to scrap all the locations of an Instagram account",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bernsteining/InstaLocTrack",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    entry_points = {
                'console_scripts': ['instaloctrack=instaloctrack.instaloctrack:main'],
                    }
)
