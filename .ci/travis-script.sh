#!/bin/bash

if [ "${BUILD}" == "tests" ]; then
    pytest -v --cov=honeybadgerbft
elif [ "${BUILD}" == "docs" ]; then
    sphinx-build -W -c docs -b html -d docs/_build/doctrees docs docs/_build/html
fi
