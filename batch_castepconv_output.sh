#!/bin/bash
cwdir=$(pwd)

find $1 -path "*castep*.conv" | sed 's/\.conv//g' | xargs -L1 -I{} bash -c 'cd $(dirname {}) && castepconv.py -t o $(basename {})'
find $1 -name "*.gp" | while read -r file
do
    cd $(dirname $file)
    file=$(basename $file)
    echo $file
    sed -i 's/^pause.*$//' $file
    out_name=$(echo $file | sed 's/.gp$/.png/')
    gnuplot -e "set output '$out_name'; set term png; load '$file'"
    cd $cwdir
done
