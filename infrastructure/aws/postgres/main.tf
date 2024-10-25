locals {
  name = "${var.team_name}-${terraform.workspace}-${var.project_name}"
}
module "postgres" {
  # checkov:skip=CKV_TF_1: We're using semantic versions instead of commit hash
  # source              = "../../../i-ai-core-infrastructure//modules/postgres"
  source = "git::https://github.com/i-dot-ai/i-dot-ai-core-terraform-modules.git//modules/infrastructure/postgres?ref=v1.0.0-postgres"
  kms_secrets_arn     = data.terraform_remote_state.platform.outputs.kms_key_arn
  name                = local.name
  db_name             = "postgres"
  db_instance_address = data.terraform_remote_state.redbox.outputs.db_instance_address
  db_master_username  = data.terraform_remote_state.redbox.outputs.db_master_username
  db_master_password  = data.terraform_remote_state.redbox.outputs.db_master_password

  secret_tags = {
    "platform:secret-purpose" = "general"
  }
}

