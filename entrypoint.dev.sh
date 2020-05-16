#!/bin/bash
pip3 uninstall sapporo
python3 ./setup.py develop

tail -f /dev/null
