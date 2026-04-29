#!/bin/bash

# disable C-states
sudo cpupower idle-set -D 2

# disable hyperthreading
sudo su -c "echo off > /sys/devices/system/cpu/smt/control"
