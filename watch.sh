#!/bin/bash

# Surveiller les modifications dans les fichiers Python et HTML et exécuter docker-compose build
find . \( -name '*.py' -o -name '*.html' \) | entr -r docker-compose build
