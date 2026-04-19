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
    feature_name = "cultivo"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "departamen"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "municipio"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "year"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "semester"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "label"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "n_timesteps"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "n_pixels"
    feature_type = "Integral"
  }

  feature_definition {
    feature_name = "ndvi_mean"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "ndvi_std"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "evi_mean"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "evi_std"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "gndvi_mean"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "gndvi_std"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "ndmi_mean"
    feature_type = "Fractional"
  }

  feature_definition {
    feature_name = "ndmi_std"
    feature_type = "Fractional"
  }

  offline_store_config {
    s3_storage_config {
      s3_uri = "s3://${var.bucket_name}/feature-store"
    }

    disable_glue_table_creation = true
  }

}