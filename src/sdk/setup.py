"""
Setup script for py-microvm SDK package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent.parent.parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements = [
    "httpx>=0.25.0",
    "pydantic>=2.4.0",
    "asyncio>=3.4.3",
    "typing-extensions>=4.0.0",
]

dev_requirements = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "flake8>=6.0.0",
    "mypy>=1.5.0",
    "pre-commit>=3.0.0",
]

setup(
    name="py-microvm",
    version="1.0.0",
    description="Enterprise Python SDK for MicroVM Sandbox with AI agent support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="MicroVM Sandbox Team",
    author_email="support@microvm-sandbox.dev",
    url="https://github.com/microvm-sandbox/py-microvm",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: System :: Virtualization",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: AsyncIO",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": dev_requirements,
        "all": dev_requirements,
    },
    entry_points={
        "console_scripts": [
            "microvm-sdk=microvm_sdk.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords=[
        "microvm",
        "virtualization", 
        "sandbox",
        "ai-agents",
        "cloud-hypervisor",
        "automation",
        "containers",
        "isolation",
        "security"
    ],
    project_urls={
        "Bug Reports": "https://github.com/microvm-sandbox/py-microvm/issues",
        "Source": "https://github.com/microvm-sandbox/py-microvm",
        "Documentation": "https://microvm-sandbox.dev/docs/sdk",
    },
)