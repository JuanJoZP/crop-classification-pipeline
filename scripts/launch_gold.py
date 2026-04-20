import argparse
import subprocess
import time

import boto3

FEATURE_GROUP_NAME = "crop-polygon-features"
BUCKET_NAME = "crop-classification-data"
REGION = "us-west-2"


def get_ecr_image() -> str:
    ecr = boto3.client("ecr", region_name=REGION)
    repos = ecr.describe_repositories(
        repositoryNames=["crop-classification-processing"]
    )
    return f"{repos['repositories'][0]['repositoryUri']}:latest"


def get_role_arn() -> str:
    iam = boto3.client("iam", region_name=REGION)
    role = iam.get_role(RoleName="crop-classification-sagemaker-processing-gold")
    return role["Role"]["Arn"]


def get_git_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() or "unknown"


def main():
    parser = argparse.ArgumentParser(description="Launch gold SageMaker Processing job")
    parser.add_argument("--instance-type", default="ml.t3.medium")
    parser.add_argument("--instance-count", type=int, default=1)
    parser.add_argument("--volume-size", type=int, default=4)
    parser.add_argument("--s3-prefix", default="processed")
    args = parser.parse_args()

    image_uri = get_ecr_image()
    role_arn = get_role_arn()
    git_sha = get_git_sha()
    job_name = f"gold-processing-{int(time.time())}"

    sm = boto3.client("sagemaker", region_name=REGION)

    response = sm.create_processing_job(
        ProcessingJobName=job_name,
        ProcessingResources={
            "ClusterConfig": {
                "InstanceType": args.instance_type,
                "InstanceCount": args.instance_count,
                "VolumeSizeInGB": args.volume_size,
            }
        },
        AppSpecification={
            "ImageUri": image_uri,
            "ContainerEntrypoint": [
                "sh",
                "-c",
                "uv run --package processing python -m processing.gold.main",
            ],
        },
        RoleArn=role_arn,
        Environment={
            "PROCESSING_STEP": "gold",
            "S3_BUCKET": BUCKET_NAME,
            "FEATURE_GROUP_NAME": FEATURE_GROUP_NAME,
            "GIT_SHA": git_sha,
            "RAM_THRESHOLD_PERCENT": "80",
            "AWS_DEFAULT_REGION": REGION,
        },
        ProcessingInputs=[
            {
                "InputName": "silver-data",
                "S3Input": {
                    "S3Uri": f"s3://{BUCKET_NAME}/{args.s3_prefix}/",
                    "LocalPath": "/opt/ml/processing/input",
                    "S3DataType": "S3Prefix",
                    "S3InputMode": "File",
                    "S3DataDistributionType": "FullyReplicated",
                },
            }
        ],
    )

    print(f"Processing job created: {job_name}")
    print(f"  Image: {image_uri}")
    print(f"  Role: {role_arn}")
    print(f"  Input: s3://{BUCKET_NAME}/{args.s3_prefix}/")
    print(f"  Instance: {args.instance_type} x{args.instance_count}")
    print(f"  ARN: {response['ProcessingJobArn']}")


if __name__ == "__main__":
    main()
