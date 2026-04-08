from setuptools import setup

setup(
    name="subnet-calculator",
version="0.1.3",
    description="CLI and library for IPv4/IPv6 subnet calculations, VLSM, supernet, overlap, and EUI-64 generation.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Muhamad Fahmi",
    author_email="muhamadfahmi3240@gmail.com",
    url="https://www.linkedin.com/in/muhamad-fahmi-5a0b47271",
    license="MIT",
    python_requires=">=3.8",
    py_modules=["subnet_calc", "subnet_utils"],
    install_requires=[],
    extras_require={
        "dev": ["tabulate", "rich", "pyyaml", "pytest>=7.0", "pytest-cov", "black", "flake8", "mypy"],
    },
    entry_points={
        "console_scripts": [
            "subnet-calc = subnet_calc:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
