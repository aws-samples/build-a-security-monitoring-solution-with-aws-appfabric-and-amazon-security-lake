#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
import os

import aws_cdk as cdk

from appfabric_security_lake.appfabric_security_lake_stack import AppfabricSecurityLakeStack


app = cdk.App()
AppfabricSecurityLakeStack(app,"AppfabricSecurityLakeStack",
    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
)

app.synth()
