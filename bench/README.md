<!--
SPDX-FileCopyrightText: 2013-2021 Sequent Tech Inc <legal@sequentech.io>

SPDX-License-Identifier: AGPL-3.0-only
-->
Election Orchestra Benchmarking
===============================

These scripts provide a way to run benchmarks on election orchestra to get basic
timing and memory statistics. The data is obtained through calls to gnu time
inserted into mixnet scripts. These scripts use eotest, so that should be
working.

Installation
============

You need gnuplot and the expect-dev package:

    apt-get install expect-dev
    apt-get install gnuplot

You also need bash version 4 or greater.

Configuration
=============

At the top of bench.sh specify the location of gnu time and the authorities that
will participate:

    PEERS=wadobo-auth2
    GNU_TIME=/usr/bin/time

Note that statistics will only be provided for the local authority (as
well as a global tally time)

Use
===

Run bench.sh passing the number of ciphertexts to use:

./bench.sh 10000

Once the run has completed several files will be placed in the directory, containing
statistics produced by the gnu time command. Currently, these files are (for a 100
ciphertext test):

    vmnv-verify-100.stat
    vmnc-plain-100.stat
    vmn-mix-100.stat

When you have carried out several runs you will have accumulated many of these files.
To merge the data ready for analysis use the following:

./merge.sh > data

which will generate a file with one line per ciphertext size, and several columns with
data.

Three gnuplot files are provided to obtain graphs and linear regressions. Note these files
assume a file name of 'data' for the result of merge. To run, use:

    gnuplot time.gpi
    gnuplot mem.gpi
    gnuplot cpu.gpi

The graphs are output as png image files. The time plot shows timings for mixing, proof
verification and global tally. Mem shows maximum resident set size. Cpu shows %cpu (can be
over 100 for multicore). Refer to gnu time for for info on these values.

Cleaning up
===========

Bench.sh reverts changes made to mixnet scripts after it is run. You can make sure this has worked
by manually copying the bak files that hold the original scripts.

The clear_disk.sh script can be used to delete files generated during tests. To avoid accidental use,
you must edit it manually to review and uncomment its lines before running it.