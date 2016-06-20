#!/bin/bash

# This file is part of election-orchestra.
# Copyright (C) 2013  Agora Voting SL <agora@agoravoting.com>

# election-orchestra is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License.

# election-orchestra  is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with election-orchestra.  If not, see <http://www.gnu.org/licenses/>.

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
    elapsed_sec=`echo $elapsed | awk -F[:.] '{ count = split($0, a, ":"); if(count == 2) {print ($1 * 60) + ($2 * 1) + ($3 / 100) } else {print ($1 * 3600) + ($2 * 60) + ($3 * 1) + ($4 / 100)} }'`
    # elapsed_sec=`echo $elapsed | awk -F[:.] '{ if(NF == 3) {print ($1 * 60) + ($2 * 1) + ($3 / 100) } else {print ($1 * 3600) + ($2 * 60) + ($3 * 1) + ($4 / 100)} }'`
    memory=`grep "Maximum resident set size (kbytes)" $f | cut -d' ' -f6`
    tally_total=`grep "Total tally time" $f | cut -d' ' -f4`
    size=`grep "Size on disk" $f | cut -d' ' -f4`

    data="$action $cpu $elapsed_sec $memory"
    [ -z $tally_total ] || data="$data $tally_total"
    [ -z $size ] || data="$data $size"
    # echo data is $data
    line="${LINES[$votes]}$data "
    LINES[$votes]="$line"
done

for i in "${!LINES[@]}"; do
    echo "$i ${LINES[$i]}"
done
