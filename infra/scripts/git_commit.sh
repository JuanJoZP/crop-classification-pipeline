#!/bin/bash
COMMIT=$(git rev-parse --short HEAD)
echo "{\"commit\": \"$COMMIT\"}"