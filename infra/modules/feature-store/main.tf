resource "aws_sagemaker_feature_group" "this" {
  feature_group_name             = var.feature_group_name
  record_identifier_feature_name = "objectid"
  event_time_feature_name        = "event_time"
  role_arn                       = var.feature_store_role_arn

  feature_definition {
    feature_name = "objectid"
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
    feature_name = "metadata"
    feature_type = "String"
  }

  # 13 Sentinel-2 bands
  feature_definition {
    feature_name = "coastal_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "blue_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "green_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "red_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "rededge1_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "rededge2_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "rededge3_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "nir_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "nir08_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "nir09_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "swir16_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "swir22_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "aot_series"
    feature_type = "String"
  }

  # 14 spectral indexes + veg_index
  feature_definition {
    feature_name = "veg_index_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "ndvi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "evi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "gndvi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "savi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "msavi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "ndwi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "gcvi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "vari_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "ndre_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "cire_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "ndmi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "mndwi_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "psri_series"
    feature_type = "String"
  }

  feature_definition {
    feature_name = "rendvi_series"
    feature_type = "String"
  }

  offline_store_config {
    s3_storage_config {
      s3_uri = "s3://${var.bucket_name}/feature-store"
    }

    disable_glue_table_creation = false
  }

}