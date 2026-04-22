#!/bin/bash

echo "Destroying lab, this may take a few seconds or minutes"

sudo containerlab destroy -t containerlab/topologies/pdsno-distributed-lab.yml
sleep 30
sudo rm sim_distributed/pdsno.db
echo "Database has been deleted successfully"

