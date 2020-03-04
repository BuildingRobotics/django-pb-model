#! /usr/bin/env bash


# Example: ./runtests.sh ComfyConvertingTest.test_comfy_model

protoc --python_out=. pb_model/tests/models.proto
python runtests.py $1
