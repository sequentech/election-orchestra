#!/bin/bash

# you need the unbuffer program from the expect package:
# apt-get install expect-dev

# PEERS=wadobo-auth2
PEERS=openkratio-authority
GNU_TIME=/usr/bin/time

VMN=`which vmn`
VMNV=`which vmnv`
VMNC=`which vmnc`
VOTES=$1

re='^[0-9]+$'
if ! [[ $VOTES =~ $re ]] ; then
   echo "error: No votes argument given or not a number"; exit 1
fi

[ -z $VMN ] && { echo "No vmn"; exit 1; }

[ -z $VMNV ] && { echo "No vmnv"; exit 1; }

[ -z $VMNC ] && { echo "No vmnc"; exit 1; }

if grep "/usr/bin/time" $VMN
then
  cp $VMN.bak $VMN
fi

if grep "/usr/bin/time" $VMNV
then
  cp $VMNV.bak $VMNV
fi

if grep "/usr/bin/time" $VMNC
then
  cp $VMNC.bak $VMNC
fi

sed -i.bak "s|^java|$GNU_TIME -v -o /tmp/vmn\${1}-$VOTES.stat java|g" $VMN
# add verify to make it easier to parse file names in merge
sed -i.bak "s|^java|$GNU_TIME -v -o /tmp/vmnv-verify-$VOTES.stat java|g" $VMNV
sed -i.bak "s|^java|$GNU_TIME -v -o /tmp/vmnc\${1}-$VOTES.stat java|g" $VMNC

datastore=`du -sk /home/eorchestra/election-orchestra/datastore/private/ | cut -f1`
public=`du -sk /srv/election-orchestra/server1/public/ | cut -f1`
before=$((public + datastore))

unbuffer eotest full --peers $PEERS --vmnd --vcount $VOTES 2>&1 | tee /tmp/eotest-$VOTES.out

datastore=`du -sk /home/eorchestra/election-orchestra/datastore/private/ | cut -f1`
public=`du -sk /srv/election-orchestra/server1/public/ | cut -f1`
after=$((public + datastore))

SIZE=$((after - before))

cp $VMN.bak $VMN
cp $VMNV.bak $VMNV
cp $VMNC.bak $VMNC
cp /tmp/vmn-mix-$VOTES.stat .
cp /tmp/vmnv-verify-$VOTES.stat .
cp /tmp/vmnc-plain-$VOTES.stat .

CREATED_T=`grep "> Election created " /tmp/eotest-$VOTES.out | cut -d' ' -f4`
TALLY_T=`grep "> Received tally data" /tmp/eotest-$VOTES.out | cut -d' ' -f5`
echo -e "\tTotal tally time: $TALLY_T" >> ./vmn-mix-$VOTES.stat
echo -e "\tSize on disk: $SIZE" >> ./vmn-mix-$VOTES.stat