#!/bin/bash
COMMIT=$(git rev-parse HEAD)
echo "{\"commit\": \"$COMMIT\"}"