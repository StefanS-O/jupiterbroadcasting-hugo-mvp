#!/usr/bin/env bash

if [ -f scraped-data ]; then
    echo "Copying scraped data into project root directory..."
    cp -a scraped-data/* .
    echo "Done."
fi
