resource "aws_sagemaker_feature_group" "this" {
  feature_group_name             = var.feature_group_name
  record_identifier_feature_name = "polygon_id"
  event_time_feature_name        = "event_time"
  role_arn                       = var.feature_store_role_arn

  feature_definition {
    feature_name = "polygon_id"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "event_time"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "crop_type"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "ndvi_mean"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "ndvi_std"
    feature_type = "Fractional"
  }

  offline_store_config {
    s3_storage_config {
      s3_uri = "s3://${var.bucket_name}/feature-store"
    }

    disable_glue_table_creation = true
  }

}