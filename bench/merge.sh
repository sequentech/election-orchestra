#!/bin/bash

files="vmn*"
regex="([a-z]+)-([a-z]*)?-([0-9]+)"
declare -A LINES

for f in $files
do
    [[ $f =~ $regex ]]
    name="${BASH_REMATCH[1]}"
    action="${BASH_REMATCH[2]}"
    votes="${BASH_REMATCH[3]}"
    # echo $f
    # echo "${name} $action $votes"

    cpu=`grep "Percent of CPU this job got" $f | cut -d' ' -f7`
    elapsed=`grep "Elapsed (wall clock) time (h:mm:ss or m:ss)" $f | cut -d' ' -f8`
    elapsed_sec=`echo $elapsed | awk -F[:.] '{ if(NF == 3) {print ($1 * 60) + ($2 * 1) + ($3 / 100) } else {print ($1 * 3600) + ($2 * 60) + ($3 * 1) + ($4 / 100)} }'`
    memory=`grep "Maximum resident set size (kbytes)" $f | cut -d' ' -f6`
    tally_total=`grep "Total tally time" $f | cut -d' ' -f4`

    extra="$action $cpu $elapsed_sec $memory"
    [ -z $tally_total ] || extra="$extra $tally_total"
    line="${LINES[$votes]}$extra "
    LINES[$votes]="$line"
done

for i in "${!LINES[@]}"; do
    echo "$i ${LINES[$i]}"
done