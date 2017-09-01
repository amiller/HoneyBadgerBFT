#!/bin/bash

if [ "${BUILD}" == "tests" ]; then
    pytest -v --cov=honeybadgerbft test/
elif [ "${BUILD}" == "docs" ]; then
    sphinx-build -W -c docs -b html -d docs/_build/doctrees docs docs/_build/html
fi
