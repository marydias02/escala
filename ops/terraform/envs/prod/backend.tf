terraform {
  backend "s3" {
    bucket = "ltp-gitlab-terraform-state"
    key    = "grupo-sousa/escala/escala/prod/terraform.tfstate"
    region = "eu-west-1"
  }
}