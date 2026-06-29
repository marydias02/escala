terraform {
  backend "s3" {
    bucket = "ltp-gitlab-terraform-state"
    key    = "grupo-sousa/escala/escala/shared/terraform.tfstate"
    region = "eu-west-1"
  }
}