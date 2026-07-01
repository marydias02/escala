module "litellm" {
  source = "git@git.ltplabs.net:infrastructure/terraform-modules/litellm/managing-keys.git"

  client           = "grupo-sousa"
  project          = "escala"
  project_tag      = "GSO037"
  application_name = "escala"
  environment      = "prod"
  litellm_api_key  = var.litellm_api_key
}

variable "litellm_api_key" {
  description = "The LiteLLM API Key that will be used to acess the LiteLLM API"
  type        = string
  sensitive   = true
}
