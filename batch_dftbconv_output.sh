#!/bin/bash

cdir=$(pwd)
find $1 -name "*dftb+" | while read -r file
do
    seed=$(cut -d '/' -f2 <<< "$file")
    echo "Processing $seed"
    cd $file
    dftbconv.py --mode output $seed
    cd $cdir
done
