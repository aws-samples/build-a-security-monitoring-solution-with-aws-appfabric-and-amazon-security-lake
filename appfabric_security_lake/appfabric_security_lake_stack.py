# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_glue as glue,
    aws_kinesisfirehose as firehose,
    aws_iam as iam,
    aws_logs as logs,
    aws_lakeformation as lakeformation,
    RemovalPolicy
)
from constructs import Construct
import constructs

# Configure the constants below:
# The Amazon Resource Name (ARN) of the Security Lake output bucket in your region of choice.
SECURITY_LAKE_S3_BUCKET_ARN = "arn:aws:s3:::DOC-EXAMPLE-DESTINATION-BUCKET"
# The name of your AppFabric custom source in Security Lake
SECURITY_LAKE_CUSTOM_SOURCE_NAME = "AppFabric"
# Name a new Glue database for the AppFabric schema.
GLUE_DATABASE_NAME = "appfabric_schema_db"
# Name a new Glue database table for the AppFabric schema.
GLUE_TABLE_NAME = "appfabric_schema"
# Name a new CloudWatch log group for your Kinesis Data Firehose.
CLOUDWATCH_LOG_GROUP_NAME="/firehose-appfabric-security-lake"
# A unique name for your firehose delivery stream. Optional.
FIREHOSE_DELIVERY_STREAM_NAME=None

class AppfabricSecurityLakeStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Before deployment, build and configure the following resources:
        #   - Security Lake 
        #       a. https://docs.aws.amazon.com/appfabric/latest/adminguide/security-lake.html

        # After deployment, build and create the following resources:
        #   - AppFabric
        #       a. https://docs.aws.amazon.com/appfabric/latest/adminguide/security-lake.html
        #       b. https://docs.aws.amazon.com/appfabric/latest/adminguide/prerequisites.html#create-output-location 

        region = Stack.of(self).region
        account_id = Stack.of(self).account

        ###
        # Glue definition
        # Resources: AWS Glue, Amazon S3
        ###

        # Load the predefined table schema
        appfabric_schema = [
                {"Name": "activity_id", "Type": "string"},
                {"Name": "activity_name", "Type": "string"}, 
                {"Name": "actor", "Type": "struct<session:struct<created_time:bigint,uid:string,issuer:string>,user:struct<uid:string,email_addr:string,credential_uid:string,name:string,type:string>>"},
                {"Name": "user", "Type": "struct<uid:string,email_addr:string,credential_uid:string,name:string,type:string>"},
                {"Name": "group", "Type": "struct<uid:string,desc:string,name:string,type:string,privileges:array<string>>"},
                {"Name": "privileges", "Type": "array<string>"},
                {"Name": "web_resources", "Type": "array<struct<type:string,uid:string,name:string,data:struct<current_value:string,previous_value:string>>>"},
                {"Name": "http_request", "Type": "struct<http_method:string,user_agent:string,url:string>"},
                {"Name": "auth_protocol", "Type": "string"}, 
                {"Name": "auth_protocol_id", "Type": "int"},
                {"Name": "category_name", "Type": "string"},
                {"Name": "category_uid", "Type": "string"},
                {"Name": "class_name", "Type": "string"},
                {"Name": "class_uid", "Type": "string"},
                {"Name": "is_mfa", "Type": "boolean"},
                {"Name": "raw_data", "Type": "string"},
                {"Name": "severity", "Type": "string"},
                {"Name": "severity_id", "Type": "int"},
                {"Name": "status", "Type": "string"},
                {"Name": "status_detail", "Type": "string"},
                {"Name": "status_id", "Type": "int"}, 
                {"Name": "time", "Type": "bigint"},
                {"Name": "type_name", "Type": "string"},
                {"Name": "type_uid", "Type": "string"},
                {"Name": "description", "Type": "string"},
                {"Name": "metadata", "Type": "struct<product:struct<uid:string,vendor_name:string,name:string>,processed_time:string,version:string,uid:string,event_code:string>"},
                {"Name": "device", "Type": "struct<uid:string,hostname:string,ip:string,name:string,region:string,type:string,os:struct<name:string,type:string,version:string>,location:struct<coordinates:array<float>,city:string,state:string,country:string,postal_code:string,continent:string,desc:string>>"}, 
                {"Name": "unmapped", "Type": "map<string,string>"}
        ]

        # Create Glue resources
        glue_s3_bucket = s3.Bucket(self, 
            "AWSGlueAmazonS3Bucket", 
            removal_policy=RemovalPolicy.DESTROY,
            versioned=True
        )

        glue_database = glue.CfnDatabase(self, GLUE_DATABASE_NAME, 
            catalog_id=account_id,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                description="AppFabric glue database", 
                name=GLUE_DATABASE_NAME
            )
        )

        glue_table = glue.CfnTable(self, "MyGlueTable",
            catalog_id=account_id,
            database_name=GLUE_DATABASE_NAME,
            table_input=glue.CfnTable.TableInputProperty(
                name=GLUE_TABLE_NAME,
                retention=0,
                table_type="EXTERNAL_TABLE",
                parameters={"EXTERNAL": "TRUE"},
                storage_descriptor=glue.CfnTable.StorageDescriptorProperty(
                    location=glue_s3_bucket.bucket_name,
                    columns=[
                        glue.CfnTable.ColumnProperty(name=row["Name"], type=row["Type"]) for row in appfabric_schema
                    ]
                )
            )
        )

        ###
        # Kinesis Data Firehose definition
        ###

        # Create Kinesis Data Firehose permissions
        log_group = logs.LogGroup(self, "FirehoseLogs",
            log_group_name=CLOUDWATCH_LOG_GROUP_NAME,
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        log_stream = logs.LogStream(self, "FirehoseLogStream",
            log_group=log_group
        )
        kdf_policy_document = iam.ManagedPolicy(self, "FirehosePermissions",
            document=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        sid="",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "lakeformation:GetDataAccess",
                            "lakeformation:GetResourceLFTags",
                            "lakeformation:ListLFTags",
                            "lakeformation:GetLFTag",
                            "lakeformation:SearchTablesByLFTags",
                            "lakeformation:SearchDatabasesByLFTags",
                        ],
                        resources=["*"]
                    ),
                    iam.PolicyStatement(
                        sid="", 
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "glue:GetTable",
                            "glue:GetTables",
                            "glue:GetTableVersions",
                            "glue:SearchTables",
                            "glue:GetDatabase",
                            "glue:GetDatabases",
                            "glue:GetPartitions"
                        ],
                        resources=[
                            f"arn:aws:glue:{region}:{account_id}:database/{GLUE_DATABASE_NAME}",
                            f"arn:aws:glue:{region}:{account_id}:table/{GLUE_DATABASE_NAME}/{GLUE_TABLE_NAME}",  
                            f"arn:aws:glue:{region}:{account_id}:catalog"
                        ]
                    ),
                    iam.PolicyStatement(
                        sid="",
                        effect=iam.Effect.ALLOW, 
                        actions=[
                            "s3:AbortMultipartUpload",
                            "s3:PutObject",
                            "s3:GetObject",
                            "s3:PutObjectAcl"
                        ],
                        resources=[str(SECURITY_LAKE_S3_BUCKET_ARN + f"/ext/{SECURITY_LAKE_CUSTOM_SOURCE_NAME}/*")]
                    ),
                    iam.PolicyStatement(
                        sid="",
                        effect=iam.Effect.ALLOW,
                        actions=[
                            "s3:GetBucketLocation",
                            "s3:ListBucket",
                            "s3:ListBucketMultipartUploads"
                        ],
                        resources=[
                            f"{SECURITY_LAKE_S3_BUCKET_ARN}",
                            f"{SECURITY_LAKE_S3_BUCKET_ARN}/*"
                        ]
                    ),
                    iam.PolicyStatement(
                        sid="",
                        effect=iam.Effect.ALLOW,
                        actions=["logs:PutLogEvents"],
                        resources=[f"arn:aws:logs:{region}:{account_id}:log-group:{log_group.log_group_name}:log-stream:{log_stream.log_stream_name}:*"]
                    )
                ]
            )
        )

        firehose_role = iam.Role(self, "FirehoseRole",
            assumed_by=iam.ServicePrincipal("firehose.amazonaws.com"),
            managed_policies=[kdf_policy_document]
        )


        # Create LakeFormation permissions for the Kinesis Firehose
        lakeformation_db_permissions = lakeformation.CfnPermissions(
            self, "LakeformationDBPermissions",
            data_lake_principal=lakeformation.CfnPermissions.DataLakePrincipalProperty(
                data_lake_principal_identifier=firehose_role.role_arn
            ),
            resource=lakeformation.CfnPermissions.ResourceProperty(
                database_resource=lakeformation.CfnPermissions.DatabaseResourceProperty(
                    catalog_id=account_id,
                    name=glue_database.ref      
                )
            ),
            permissions=["DESCRIBE"],
            permissions_with_grant_option=["DESCRIBE"]
        )

        lakeformation_table_permissions= lakeformation.CfnPermissions(
            self, "LakeformationTablePermissions",
            data_lake_principal=lakeformation.CfnPermissions.DataLakePrincipalProperty(
                data_lake_principal_identifier=firehose_role.role_arn
            ),
            resource=lakeformation.CfnPermissions.ResourceProperty(
                table_resource=lakeformation.CfnPermissions.TableResourceProperty(
                    catalog_id=account_id,
                    database_name=glue_database.ref,
                    name=glue_table.ref
                )
            ),
            permissions=["SELECT", "DESCRIBE"],
            permissions_with_grant_option=["SELECT", "DESCRIBE"]
        )

        # Create Kinesis Data Firehose resources
        firehose_delivery_stream = firehose.CfnDeliveryStream(self, "firehose-delivery-stream",
            delivery_stream_name=FIREHOSE_DELIVERY_STREAM_NAME,
            delivery_stream_type="DirectPut",
            extended_s3_destination_configuration=firehose.CfnDeliveryStream.ExtendedS3DestinationConfigurationProperty(
                error_output_prefix=f"ext/{SECURITY_LAKE_CUSTOM_SOURCE_NAME}/error/",
                prefix=f"ext/{SECURITY_LAKE_CUSTOM_SOURCE_NAME}/region={region}/accountId={account_id}/eventDay=!{{partitionKeyFromQuery:eventDayValue}}/",
                role_arn=firehose_role.role_arn,
                bucket_arn=SECURITY_LAKE_S3_BUCKET_ARN,
                buffering_hints=firehose.CfnDeliveryStream.BufferingHintsProperty(
                    interval_in_seconds=60,
                    size_in_m_bs=128
                ),
                cloud_watch_logging_options=firehose.CfnDeliveryStream.CloudWatchLoggingOptionsProperty(
                    enabled=True,
                    log_group_name=log_group.log_group_name,
                    log_stream_name=log_stream.log_stream_name
                ),
                s3_backup_mode="Disabled",
                dynamic_partitioning_configuration=firehose.CfnDeliveryStream.DynamicPartitioningConfigurationProperty(
                    enabled=True,
                    retry_options=firehose.CfnDeliveryStream.RetryOptionsProperty(
                        duration_in_seconds=300
                    )
                ),
                compression_format="UNCOMPRESSED",
                processing_configuration=firehose.CfnDeliveryStream.ProcessingConfigurationProperty(
                    enabled=True,
                    processors=
                        [firehose.CfnDeliveryStream.ProcessorProperty(
                            type="MetadataExtraction",
                            parameters=[firehose.CfnDeliveryStream.ProcessorParameterProperty(
                                parameter_name="MetadataExtractionQuery",
                                parameter_value='{eventDayValue:(.time/1000)|strftime("%Y%m%d")}'
                            ),
                            firehose.CfnDeliveryStream.ProcessorParameterProperty(
                                parameter_name="JsonParsingEngine",
                                parameter_value="JQ-1.6"
                            )]
                        )]
                ),
                data_format_conversion_configuration=firehose.CfnDeliveryStream.DataFormatConversionConfigurationProperty(
                    enabled=True,
                    input_format_configuration=firehose.CfnDeliveryStream.InputFormatConfigurationProperty(
                        deserializer=firehose.CfnDeliveryStream.DeserializerProperty(
                            open_x_json_ser_de=firehose.CfnDeliveryStream.OpenXJsonSerDeProperty(case_insensitive=True)
                        )
                    ),
                    output_format_configuration=firehose.CfnDeliveryStream.OutputFormatConfigurationProperty(
                        serializer=firehose.CfnDeliveryStream.SerializerProperty(
                            parquet_ser_de=firehose.CfnDeliveryStream.ParquetSerDeProperty(
                                block_size_bytes=268435456,
                                compression="GZIP",
                                enable_dictionary_compression=False,
                                max_padding_bytes=0,
                                page_size_bytes=1048576,
                                writer_version="V1"
                            )
                        )
                    ),
                    schema_configuration=firehose.CfnDeliveryStream.SchemaConfigurationProperty(
                        role_arn=firehose_role.role_arn,
                        region=region,
                        database_name=GLUE_DATABASE_NAME,
                        table_name=GLUE_TABLE_NAME,
                        version_id="LATEST"
                    )
                )
            )
        )
        permissions_dependency_group = constructs.DependencyGroup()
        permissions_dependency_group.add(lakeformation_db_permissions)
        permissions_dependency_group.add(lakeformation_table_permissions)
        firehose_delivery_stream.node.add_dependency(permissions_dependency_group)
