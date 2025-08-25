# Robotic Vision & Control [RVC]

The RVC documentation is built from source using Sphinx.

## Install dependencies:

```console
$ sudo apt update
$ sudo apt install python3-pip
$ sudo apt-get install graphviz libenchant-2-dev
$ pip3 install -r requirements.txt
$ echo "export PATH=$(python -m site --user-base)/bin:\$PATH" >> ~/.bashrc
$ source ~/.bashrc
```

## Make HTML for Release

```console
$ make html
```
