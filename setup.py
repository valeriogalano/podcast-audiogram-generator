from setuptools import setup, find_packages

setup(
    name="podcast-audiogram-generator",
    version="0.1.0",
    description="Generatore di audiogrammi per podcast",
    author="Valerio Galano",
    packages=find_packages(),
    install_requires=[
        "pydub>=0.25.1",
        "moviepy>=1.0.3",
        "pillow>=10.0.0",
        "numpy>=1.24.0",
    ],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "audiogram-generator=audiogram_generator.cli:main",
        ],
    },
)
