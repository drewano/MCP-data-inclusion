#!/bin/bash

awslocal s3api \
    create-bucket --bucket datainclusion-elements \
    --create-bucket-configuration LocationConstraint=eu-central-1 \
    --region eu-central-1
echo '{"CORSRules":[{"AllowedHeaders":["*"],"AllowedMethods":["GET","POST","PUT"],"AllowedOrigins":["*"],"ExposeHeaders":["ETag"]}]}' > cors.json
awslocal s3api put-bucket-cors --bucket datainclusion-elements --cors-configuration file://cors.json